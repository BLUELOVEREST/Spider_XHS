import os
import tempfile
import unittest
from unittest.mock import patch

from server import load_cookie


class ServerConfigTest(unittest.TestCase):
    def test_load_cookie_prefers_xhs_cookie(self):
        with patch.dict(
            os.environ,
            {"XHS_COOKIE": " a1=from-xhs ", "COOKIES": "a1=from-cookies"},
            clear=True,
        ):
            self.assertEqual(load_cookie(), "a1=from-xhs")

    def test_load_cookie_reads_cookie_file(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8") as cookie_file:
            cookie_file.write(" a1=from-file \n")
            cookie_file.flush()
            with patch.dict(os.environ, {"XHS_COOKIE_FILE": cookie_file.name}, clear=True):
                self.assertEqual(load_cookie(), "a1=from-file")

    def test_load_cookie_falls_back_to_existing_cookies_env_name(self):
        with patch.dict(os.environ, {"COOKIES": " a1=legacy "}, clear=True):
            self.assertEqual(load_cookie(), "a1=legacy")

    def test_load_cookie_requires_configuration(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "XHS_COOKIE"):
                load_cookie()


if __name__ == "__main__":
    unittest.main()
