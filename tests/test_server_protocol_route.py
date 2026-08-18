# -*- coding: utf-8 -*-
import asyncio
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class ServerProtocolRouteTest(unittest.TestCase):
    def test_importing_server_does_not_import_browser_stack(self):
        code = (
            "import sys, txdx.server; "
            "assert 'txdx.get_ticket' not in sys.modules; "
            "assert 'playwright' not in sys.modules; "
            "print('protocol server import ok')"
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
        self.assertIn("protocol server import ok", result.stdout)

    def test_solve_route_forces_protocol_mode(self):
        from txdx import server

        request = server.SolveReq(aid="192037696", rounds=1)
        with patch("txdx.server.solve", return_value={"success": True}) as solve:
            result = asyncio.run(server.solve_endpoint(request))

        self.assertTrue(result["success"])
        solve.assert_called_once_with(
            aid="192037696",
            proxy=None,
            rounds=1,
            mode="protocol",
            entry_url=None,
            gap_seconds=60.0,
            verbose=True,
        )


if __name__ == "__main__":
    unittest.main()
