# -*- coding: utf-8 -*-
import os
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import txdx


ROOT = Path(__file__).resolve().parents[1]


class ModeDispatchTest(unittest.TestCase):
    def test_import_does_not_load_browser_stack(self):
        code = (
            "import sys, txdx; "
            "assert 'txdx.get_ticket' not in sys.modules; "
            "assert 'playwright' not in sys.modules; "
            "print('pure import ok')"
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT.parent)
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT.parent,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("pure import ok", result.stdout)

    def test_default_mode_dispatches_to_pure_protocol(self):
        expected = {"success": True, "errorCode": "0"}
        with patch("txdx.protocol_solver.solve_protocol", return_value=expected) as pure:
            result = txdx.solve(
                aid="192037696",
                proxy=None,
                rounds=1,
                entry_url="https://example.test/captcha",
            )

        self.assertEqual(result, expected)
        pure.assert_called_once_with(
            aid="192037696",
            entry_url="https://example.test/captcha",
            proxy=None,
            captcha_provider=None,
            gap_seconds=60.0,
            max_rounds=1,
            verbose=True,
        )

    def test_browser_mode_is_explicit_and_lazy(self):
        expected = {"success": True, "ret": 0}
        fake = types.ModuleType("txdx.get_ticket")
        fake.get_ticket = lambda *args, **kwargs: {"ret": 0, "ticket": "tr03-test"}
        with patch.dict(sys.modules, {"txdx.get_ticket": fake}):
            result = txdx.solve(
                aid="192037696",
                mode="browser",
                rounds=2,
                timeout=7,
                headless=True,
                port=8088,
            )

        self.assertEqual(result["success"], expected["success"])
        self.assertEqual(result["ret"], expected["ret"])
        self.assertEqual(result["ticket"], "tr03-test")

    def test_legacy_get_ticket_is_also_lazy(self):
        fake = types.ModuleType("txdx.get_ticket")
        fake.get_ticket = lambda appid, **kwargs: {"ret": 0, "appid": appid}
        with patch.dict(sys.modules, {"txdx.get_ticket": fake}):
            result = txdx.get_ticket("192037696", headless=True)

        self.assertEqual(result, {"ret": 0, "appid": "192037696"})

    def test_unknown_mode_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "mode"):
            txdx.solve(aid="192037696", mode="something-else")


if __name__ == "__main__":
    unittest.main()
