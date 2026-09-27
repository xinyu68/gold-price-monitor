import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import gold_monitor
import check_env


class BarkPushTests(unittest.TestCase):
    def setUp(self):
        self.config = {'bark_key': 'test-secret', 'proxy_mode': 'inherit', 'proxy_address': ''}

    def test_post_json_without_optional_fields(self):
        with patch.object(gold_monitor, 'urlopen', return_value=io.BytesIO(b'{"code":200}')) as request:
            self.assertTrue(gold_monitor.send_bark(self.config, '金价', '926.16 元/克'))

        sent = request.call_args.args[0]
        self.assertEqual(sent.get_method(), 'POST')
        self.assertEqual(json.loads(sent.data), {'title': '金价', 'body': '926.16 元/克'})
        self.assertEqual(sent.full_url, 'https://api.day.app/test-secret')

    def test_service_error_is_not_success(self):
        output = io.StringIO()
        with patch.object(gold_monitor, 'urlopen', return_value=io.BytesIO(b'{"code":400}')):
            with redirect_stdout(output):
                self.assertFalse(gold_monitor.send_bark(self.config, 'test', 'body'))
        self.assertIn('code=400', output.getvalue())

    def test_missing_service_code_is_not_success(self):
        output = io.StringIO()
        with patch.object(gold_monitor, 'urlopen', return_value=io.BytesIO(b'{}')):
            with redirect_stdout(output):
                self.assertFalse(gold_monitor.send_bark(self.config, 'test', 'body'))

    def test_exception_does_not_log_key(self):
        output = io.StringIO()
        with patch.object(gold_monitor, 'urlopen', side_effect=OSError('test-secret')):
            with redirect_stdout(output):
                self.assertFalse(gold_monitor.send_bark(self.config, 'test', 'body'))
        self.assertNotIn('test-secret', output.getvalue())

    def test_configured_proxy_is_used(self):
        config = dict(self.config, proxy_mode='proxy', proxy_address='http://127.0.0.1:7897')
        opener = Mock()
        opener.open.return_value = io.BytesIO(b'{"code":200}')
        with patch.object(gold_monitor, 'build_opener', return_value=opener) as build:
            self.assertTrue(gold_monitor.send_bark(config, 'test', 'body'))
        build.assert_called_once()
        self.assertEqual(build.call_args.args[0].proxies, {})
        self.assertEqual(opener.open.call_args.args[0].host, '127.0.0.1:7897')
        opener.open.assert_called_once()

    def test_direct_mode_ignores_environment_proxy(self):
        config = dict(self.config, proxy_mode='direct')
        opener = Mock()
        opener.open.return_value = io.BytesIO(b'{"code":200}')
        with patch.object(gold_monitor, 'build_opener', return_value=opener) as build:
            with patch.object(gold_monitor, 'urlopen') as inherited:
                self.assertTrue(gold_monitor.send_bark(config, 'test', 'body'))
        self.assertEqual(build.call_args.args[0].proxies, {})
        inherited.assert_not_called()

    def test_proxy_mode_requires_address(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertFalse(gold_monitor.send_bark(dict(self.config, proxy_mode='proxy'), 'test', 'body'))
        self.assertIn('缺少代理地址', output.getvalue())

    def test_proxy_mode_rejects_unsupported_or_malformed_url(self):
        for address in ('https://127.0.0.1:7897', 'http://127.0.0.1:bad'):
            with self.subTest(address=address):
                with redirect_stdout(io.StringIO()):
                    self.assertFalse(gold_monitor.send_bark(
                        dict(self.config, proxy_mode='proxy', proxy_address=address), 'test', 'body'))

    def test_legacy_proxy_flag_is_supported(self):
        data = 'bark:\n  key: test-secret\nproxy:\n  enabled: true\n  address: http://127.0.0.1:7897\n'
        with patch.object(gold_monitor.os.path, 'isfile', return_value=True):
            with patch('builtins.open', mock_open(read_data=data)):
                config = gold_monitor.load_config()
        self.assertEqual(config['proxy_mode'], 'proxy')
        self.assertEqual(config['proxy_address'], 'http://127.0.0.1:7897')

    def test_environment_check_uses_same_sender_without_claiming_direct(self):
        output = io.StringIO()
        with patch.object(gold_monitor, 'load_config', return_value=self.config):
            with patch.object(gold_monitor, 'send_bark', return_value=True) as send:
                with redirect_stdout(output):
                    self.assertTrue(check_env.check_bark())
        send.assert_called_once_with(
            self.config, '测试推送', '环境检查通过'
        )
        self.assertNotIn('直连', output.getvalue())


if __name__ == '__main__':
    unittest.main()
