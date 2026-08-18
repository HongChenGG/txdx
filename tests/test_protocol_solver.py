# -*- coding: utf-8 -*-
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from txdx.collect_gen import gen_collect_eks as real_gen_collect_eks
from txdx.protocol_solver import _build_answer_clicks, solve_protocol


ENTRY = "https://example.test/captcha"
PROXY = "http://127.0.0.1:7897"
PROXIES = {"http": PROXY, "https": PROXY}


class ProtocolSolverTest(unittest.TestCase):
    def test_answer_and_behavior_share_one_click_geometry(self):
        answers, clicks = _build_answer_clicks(
            [[40, 20, 60, 40]],
            bg_size=(100, 50),
            confirm=True,
            jitter=0,
        )

        self.assertEqual(answers[0]["data"], "62,43")
        self.assertEqual(len(clicks), 2)
        self.assertEqual(clicks[-1], {"x": 640.0, "y": 569.4})

    def test_single_round_routes_proxy_and_verifies_once(self):
        round_data = {
            "sess": "fresh-session",
            "tkid": "page-token",
            "sid": "sid",
            "instruction": "请依次点击：甲 乙 丙",
            "tdc_path": "/tdc.js",
            "pow": {"prefix": "p", "md5": "m"},
            "bg_cfg": {"size_2d": [672, 480]},
            "subcapclass": "2404",
        }

        class Provider:
            def solve_click(self, instruction, bg_path, proxy=None):
                self.proxy = proxy
                return [[10, 20, 40, 50], [50, 60, 80, 90], [90, 100, 120, 130]]

        provider = Provider()
        prehandle = Mock(return_value=(round_data, None))
        get_bg = Mock(return_value="bg.png")

        def save_tdc(tdc_path, workdir, proxies, entry_url=""):
            Path(workdir, "tdc.js").write_text("tdc", encoding="utf-8")

        download_tdc = Mock(side_effect=save_tdc)
        collect = Mock(return_value=("collect", "eks", "tdc-token"))
        solve_pow = Mock(return_value=("pow-answer", 350))
        verify = Mock(return_value={"errorCode": "0", "ticket": "ticket", "randstr": "@r"})

        with (
            patch("txdx.protocol_solver.prehandle", prehandle),
            patch("txdx.protocol_solver.get_bg", get_bg),
            patch("txdx.protocol_solver.download_tdc", download_tdc),
            patch("txdx.protocol_solver.gen_collect_eks", collect),
            patch("txdx.protocol_solver.solve_pow", solve_pow),
            patch("txdx.protocol_solver.verify", verify),
        ):
            result = solve_protocol(
                aid="192037696",
                entry_url=ENTRY,
                proxy=PROXY,
                captcha_provider=provider,
                gap_seconds=0,
                max_rounds=1,
                verbose=False,
            )

        self.assertTrue(result["success"])
        prehandle.assert_called_once_with("192037696", ENTRY, PROXIES)
        self.assertEqual(provider.proxy, PROXY)
        self.assertEqual(download_tdc.call_args.args[2], PROXIES)
        self.assertEqual(verify.call_args.args[6], PROXIES)
        self.assertEqual(verify.call_args.kwargs["tkid"], "tdc-token")
        self.assertEqual(verify.call_count, 1)

    def test_provider_exception_does_not_trigger_verify(self):
        round_data = {
            "sess": "fresh-session",
            "tkid": "page-token",
            "sid": "sid",
            "instruction": "请依次点击：甲",
            "tdc_path": "/tdc.js",
            "pow": {"prefix": "p", "md5": "m"},
            "bg_cfg": {"size_2d": [672, 480]},
            "subcapclass": "2404",
        }
        provider = Mock()
        provider.solve_click.side_effect = RuntimeError("recognizer unavailable")
        with (
            patch("txdx.protocol_solver.prehandle", return_value=(round_data, None)),
            patch("txdx.protocol_solver.get_bg", return_value="bg.png"),
            patch("txdx.protocol_solver.download_tdc"),
            patch("txdx.protocol_solver.gen_collect_eks"),
            patch("txdx.protocol_solver.verify") as verify,
        ):
            result = solve_protocol(
                aid="192037696",
                entry_url=ENTRY,
                captcha_provider=provider,
                gap_seconds=0,
                max_rounds=1,
                verbose=False,
            )

        self.assertFalse(result["success"])
        self.assertIn("recognizer unavailable", result["error"])
        verify.assert_not_called()

    def test_rejects_empty_aid_before_opening_a_session(self):
        with patch("txdx.protocol_solver.prehandle") as prehandle:
            with self.assertRaisesRegex(ValueError, "aid"):
                solve_protocol(aid="", captcha_provider=Mock(), max_rounds=1)
        prehandle.assert_not_called()

    def test_rejects_non_click_challenge_without_verify(self):
        round_data = {
            "sess": "fresh-session",
            "tkid": "page-token",
            "sid": "sid",
            "instruction": "拖动下方滑块完成拼图",
            "tdc_path": "/tdc.js",
            "pow": {"prefix": "p", "md5": "m"},
            "bg_cfg": {"size_2d": [672, 480]},
            "subcapclass": "2401",
        }
        provider = Mock()
        with (
            patch("txdx.protocol_solver.prehandle", return_value=(round_data, None)),
            patch("txdx.protocol_solver.get_bg") as get_bg,
            patch("txdx.protocol_solver.verify") as verify,
        ):
            result = solve_protocol(
                aid="192037696",
                entry_url=ENTRY,
                captcha_provider=provider,
                gap_seconds=0,
                max_rounds=1,
                verbose=False,
            )

        self.assertFalse(result["success"])
        self.assertEqual(result["errorCode"], "unsupported subcapclass 2401")
        get_bg.assert_not_called()
        verify.assert_not_called()

    def test_collect_generation_overlaps_recognition(self):
        """识别耗时期间 collect 生成必须已在进行（串行时 gen_start > recog_end）。"""
        fixture_value = os.environ.get("TXDX_TDC_FIXTURE_DIR")
        fixture_dir = Path(fixture_value) if fixture_value else None
        if fixture_dir is None or not fixture_dir.is_dir():
            self.skipTest("set TXDX_TDC_FIXTURE_DIR to run captured-vector regressions")
        tdc_fixture = fixture_dir / "tdc_same_round.js"
        if not tdc_fixture.is_file():
            self.skipTest("fixture tdc_same_round.js missing")

        round_data = {
            "sess": "fresh-session",
            "tkid": "page-token",
            "sid": "sid",
            "instruction": "请依次点击：甲 乙 丙",
            "tdc_path": "/tdc.js",
            "pow": {"prefix": "p", "md5": "m"},
            "bg_cfg": {"size_2d": [672, 480]},
            "subcapclass": "2404",
        }
        marks = {}

        class SlowProvider:
            def solve_click(self, instruction, bg_path, proxy=None):
                marks["recog_start"] = time.monotonic()
                time.sleep(1.2)
                marks["recog_end"] = time.monotonic()
                return [[10, 20, 40, 50], [50, 60, 80, 90], [90, 100, 120, 130]]

        def fake_download(tdc_path, workdir, proxies, entry_url=""):
            Path(workdir, "tdc.js").write_bytes(tdc_fixture.read_bytes())

        def wrapped_gen(*args, **kwargs):
            marks["gen_start"] = time.monotonic()
            out = real_gen_collect_eks(*args, **kwargs)
            marks["gen_end"] = time.monotonic()
            return out

        with (
            patch("txdx.protocol_solver.prehandle", return_value=(round_data, None)),
            patch("txdx.protocol_solver.get_bg", return_value="bg.png"),
            patch("txdx.protocol_solver.download_tdc", side_effect=fake_download),
            patch("txdx.protocol_solver.gen_collect_eks", side_effect=wrapped_gen),
            patch("txdx.protocol_solver.solve_pow", return_value=("pow", 350)),
            patch(
                "txdx.protocol_solver.verify",
                return_value={"errorCode": "0", "ticket": "ticket", "randstr": "@r"},
            ),
        ):
            result = solve_protocol(
                aid="192037696",
                entry_url=ENTRY,
                captcha_provider=SlowProvider(),
                gap_seconds=0,
                max_rounds=1,
                verbose=False,
            )

        self.assertTrue(result["success"])
        self.assertIn("gen_start", marks)
        self.assertLess(marks["gen_start"], marks["recog_end"])

    def test_failure_preserves_observed_error_code(self):
        round_data = {
            "sess": "fresh-session",
            "tkid": "page-token",
            "sid": "sid",
            "instruction": "请依次点击：甲",
            "tdc_path": "/tdc.js",
            "pow": {"prefix": "p", "md5": "m"},
            "bg_cfg": {"size_2d": [672, 480]},
            "subcapclass": "2404",
        }
        provider = Mock()
        provider.solve_click.return_value = [[10, 20, 40, 50]]
        with tempfile.TemporaryDirectory() as _:
            with (
                patch("txdx.protocol_solver.prehandle", return_value=(round_data, None)),
                patch("txdx.protocol_solver.get_bg", return_value="bg.png"),
                patch("txdx.protocol_solver.download_tdc"),
                patch("txdx.protocol_solver.gen_collect_eks", return_value=("collect", "eks", "token")),
                patch("txdx.protocol_solver.solve_pow", return_value=("pow", 350)),
                patch("txdx.protocol_solver.verify", return_value={"errorCode": "50", "ticket": ""}),
            ):
                result = solve_protocol(
                    aid="192037696",
                    entry_url=ENTRY,
                    captcha_provider=provider,
                    gap_seconds=0,
                    max_rounds=1,
                    verbose=False,
                )

        self.assertEqual(result["errorCode"], "50")
        self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()
