"""Offline regression checks for publishing failure visibility and credential paths."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class RecoveryTests(unittest.TestCase):
    def test_gsc_uses_runner_token_path(self):
        with patch.dict(os.environ, {'GSC_TOKEN_FILE': '/tmp/site-test-token.json'}):
            module = load('sitemap_test', 'submit-gsc-sitemap.py')
        self.assertEqual(module.TOKEN, Path('/tmp/site-test-token.json'))

    def test_gsc_partial_failure_is_not_success(self):
        module = load('sitemap_failure_test', 'submit-gsc-sitemap.py')
        with patch.object(module, 'token', return_value='test'), patch.object(module.urllib.request, 'urlopen', side_effect=OSError('offline')):
            self.assertEqual(module.main(), 1)

    def test_empty_backlog_reports_failure_without_sending_dry_run_message(self):
        module = load('refill_test', 'refill_queue.py')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'cosmetics/src/content/blog/en').mkdir(parents=True)
            with patch.object(module, 'ROOT', root), patch.object(module, 'SITES', ['cosmetics']), patch.object(module, 'BACKLOG_DIR', root/'backlog'), patch.object(module, 'tg_notify') as notify, patch('sys.argv', ['refill_queue.py', '--dry-run']):
                self.assertEqual(module.main(), 1)
                notify.assert_not_called()

    def test_generator_failure_is_reported(self):
        module = load('refill_generator_test', 'refill_queue.py')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'cosmetics/src/content/blog/en').mkdir(parents=True)
            backlog=root/'backlog';backlog.mkdir()
            (backlog/'cosmetics.json').write_text(json.dumps([{'slug':'new-article'}]))
            with patch.object(module, 'ROOT', root), patch.object(module, 'SITES', ['cosmetics']), patch.object(module, 'BACKLOG_DIR', backlog), patch.object(module, 'tg_notify'), patch.object(module.subprocess, 'run', side_effect=RuntimeError('generator failed')), patch('sys.argv', ['refill_queue.py']):
                self.assertEqual(module.main(), 1)

    def test_product_photo_cannot_be_generated_from_text(self):
        module=load('queue_test','queue_health.py')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);article=root/'review.mdx'
            article.write_text('---\ntitle: Test\ntype: review\nimage: /images/product.jpg\n---\nA product review.')
            with patch.dict(module.SITES, {'cosmetics': {'images':root}}), patch.object(module, 'generate_hero_image') as generate:
                self.assertIsNone(module.ensure_hero(article,'cosmetics','test-key',False))
                generate.assert_not_called()

if __name__ == '__main__':
    unittest.main()
