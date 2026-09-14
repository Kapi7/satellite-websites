"""A manual recovery run must not contact Telegram, even with credentials set."""
import importlib.util
import os
from pathlib import Path
from unittest.mock import patch

root = Path(__file__).resolve().parent
with patch.dict(os.environ, {'DISABLE_OUTBOUND_NOTIFICATIONS': '1',
                             'TELEGRAM_BOT_TOKEN': 'test-only',
                             'TELEGRAM_CHAT_ID': 'test-only'}):
    for path in [root / 'notify.py', root / 'social/tg.py']:
        spec = importlib.util.spec_from_file_location('notification_test', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch('urllib.request.urlopen', side_effect=AssertionError('Unexpected outbound message')):
            if hasattr(module, 'send'):
                assert module.send('test-only', 'test-only', 'test message')[0]
            else:
                assert module.notify('test message')
print('Notification suppression passed: no outbound request with credentials present.')
