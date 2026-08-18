# -*- coding: utf-8 -*-
"""Offline contract tests for the default pure-protocol entry."""
import unittest
from unittest.mock import patch

import txdx


class ClickEntryTest(unittest.TestCase):
    def test_default_is_protocol_mode(self):
        expected = {"success": True, "ticket": "ticket", "errorCode": "0"}
        with patch("txdx.protocol_solver.solve_protocol", return_value=expected) as solve_protocol:
            result = txdx.solve(aid="192037696", rounds=1)

        self.assertEqual(result, expected)
        solve_protocol.assert_called_once()


if __name__ == "__main__":
    unittest.main()
