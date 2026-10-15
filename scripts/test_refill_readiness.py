"""Prevent raw inventory from masking an editorially blocked publisher."""
import contextlib
import io
import unittest
from unittest.mock import patch
import refill_queue as refill

class RefillReadinessTests(unittest.TestCase):
    def run_inventory(self, raw, passing, cadence=1):
        output = io.StringIO()
        with patch.object(refill, 'SITES', ['cosmetics']), \
             patch.dict(refill.CADENCE_DAYS, {'cosmetics': cadence}), \
             patch.object(refill, 'inventory', return_value={'cosmetics': {
                 'rawDrafts': raw, 'automatedChecksPassing': passing}}), \
             patch.object(refill, 'load_backlog', return_value=[]), \
             patch.object(refill.subprocess, 'run') as generate, \
             patch.object(refill, 'tg_notify') as notify, \
             patch('sys.argv', ['refill_queue.py', '--dry-run']), \
             contextlib.redirect_stdout(output):
            code = refill.main()
            generate.assert_not_called()
            notify.assert_not_called()
        return code, output.getvalue()

    def test_full_raw_queue_does_not_hide_blockers(self):
        code, text = self.run_inventory(7, 0)
        self.assertEqual(code, 1)
        self.assertIn('BLOCKED', text)
        self.assertIn('0 pass automated checks', text)
        self.assertNotIn('— OK', text)

    def test_automated_capacity_does_not_certify_editorial_approval(self):
        code, text = self.run_inventory(7, 7)
        self.assertEqual(code, 0)
        self.assertIn('not editorial approval', text)

    def test_cadence_uses_passing_drafts_not_raw_total(self):
        code, text = self.run_inventory(3, 1, cadence=3)
        self.assertEqual(code, 1)
        self.assertIn('~3 days', text)

    def test_empty_backlog_stays_visible(self):
        code, text = self.run_inventory(2, 0)
        self.assertEqual(code, 1)
        self.assertIn('no eligible unused topics', text)

if __name__ == '__main__':
    unittest.main()
