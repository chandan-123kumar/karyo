"""Offline credential and onboarding integration tests; no real tokens used."""
import os
import re
import ssl
import stat
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

import harness_auth as auth


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.environment = patch.dict(os.environ, {"XDG_CONFIG_HOME": self.directory.name, "HF_TOKEN": ""})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_private_storage_and_environment_precedence(self):
        self.assertIsNone(auth.read_token())
        auth.save_token("hf_test_only")
        self.assertEqual(auth.read_token(), "hf_test_only")
        self.assertEqual(stat.S_IMODE(auth.token_path().stat().st_mode), 0o600)
        with patch.dict(os.environ, {"HF_TOKEN": "hf_env_test"}):
            self.assertEqual(auth.read_token(), "hf_env_test")
        auth.save_token("hf_replaced")
        self.assertEqual(auth.read_token(), "hf_replaced")

    def test_invalid_token_is_not_sent(self):
        with patch("harness_auth.urlopen") as network:
            with self.assertRaises(ValueError):
                auth.validate_token("invalid")
            network.assert_not_called()

    def test_validation_uses_verified_certificate_bundle(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"name":"test"}'
        with patch("harness_auth.urlopen", return_value=response) as network:
            auth.validate_token("hf_test_only")
        context = network.call_args.kwargs["context"]
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertGreater(context.cert_store_stats()["x509_ca"], 0)

    def test_validation_errors_do_not_expose_credentials(self):
        for error, expected in (
            (HTTPError("https://huggingface.co", 401, "hf_private", {}, None), "rejected"),
            (HTTPError("https://huggingface.co", 503, "hf_private", {}, None), "unavailable"),
            (URLError("hf_private"), "connect securely"),
        ):
            with self.subTest(expected=expected), patch("harness_auth.urlopen", side_effect=error):
                with self.assertRaises(auth.LoginError) as raised:
                    auth.validate_token("hf_private")
                self.assertIn(expected, str(raised.exception))
                self.assertNotIn("hf_private", str(raised.exception))

    def test_legacy_token_survives_rename_and_logout_clears_both(self):
        legacy = auth.token_path("ai-harness")
        legacy.parent.mkdir(parents=True)
        legacy.write_text("hf_legacy_test")
        self.assertEqual(auth.read_token(), "hf_legacy_test")
        auth.save_token("hf_karyo_test")
        self.assertEqual(auth.read_token(), "hf_karyo_test")
        auth.logout()
        self.assertIsNone(auth.read_token())
        self.assertFalse(legacy.exists())

    def test_terminal_validates_before_saving(self):
        with patch("sys.stdin.isatty", return_value=True), patch("getpass.getpass", return_value="hf_invalid"), patch("harness_auth.validate_token", side_effect=ValueError("invalid")):
            with self.assertRaises(ValueError):
                auth.login(terminal=True)
        self.assertFalse(auth.token_path().exists())

    def test_browser_login_and_cross_origin_rejection(self):
        for origin_mode in ("same-origin", "null", "missing"):
            with self.subTest(origin=origin_mode):
                self.browser_login(origin_mode)
                auth.token_path().unlink()

    def browser_login(self, origin_mode):
        failures = []
        worker = []

        def browser(url):
            def submit():
                try:
                    with urlopen(url, timeout=5) as response:
                        page = response.read()
                        self.assertIn(b'type="password"', page)
                        csrf = re.search(rb'name="csrf" value="([^"]+)"', page).group(1).decode()
                        self.assertEqual(response.headers["Cache-Control"], "no-store")
                    body = urlencode({"token": "hf_test_only", "csrf": csrf}).encode()
                    with self.assertRaises(HTTPError) as rejected:
                        urlopen(Request(url, body, headers={"Origin": "https://example.com"}), timeout=5)
                    self.assertEqual(rejected.exception.code, 403)
                    self.assertFalse(auth.token_path().exists())
                    origin = "http://" + urlsplit(url).netloc
                    headers = {} if origin_mode == "missing" else {"Origin": "null" if origin_mode == "null" else origin}
                    for nonce in (None, "wrong"):
                        fields = {"token": "hf_test_only"}
                        if nonce is not None:
                            fields["csrf"] = nonce
                        with self.assertRaises(HTTPError) as rejected:
                            urlopen(Request(url, urlencode(fields).encode(), headers=headers), timeout=5)
                        self.assertEqual(rejected.exception.code, 403)
                        self.assertFalse(auth.token_path().exists())
                    with urlopen(Request(url, body, headers=headers), timeout=5) as response:
                        self.assertIn(b"connected", response.read())
                except Exception as exc:
                    failures.append(exc)
            thread = threading.Thread(target=submit, daemon=True)
            worker.append(thread)
            thread.start()
            return True

        with patch("webbrowser.open", side_effect=browser), patch("harness_auth.validate_token") as validate:
            self.assertEqual(auth.login(), "hf_test_only")
            worker[0].join(timeout=10)
            validate.assert_called_once_with("hf_test_only")
        if failures:
            raise failures[0]
        self.assertEqual(auth.read_token(), "hf_test_only")


if __name__ == "__main__":
    unittest.main()
