# -*- coding: utf-8 -*-
import json
import os
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / "tdc_js" / "click_driver.js"


class TdcDriverTest(unittest.TestCase):
    def _run(self, **extra):
        fixture_value = os.environ.get("TXDX_TDC_FIXTURE_DIR")
        fixture_dir = Path(fixture_value) if fixture_value else None
        if fixture_dir is None or not fixture_dir.is_dir():
            self.skipTest("set TXDX_TDC_FIXTURE_DIR to run captured-vector regressions")
        chrome = json.loads((fixture_dir / "collectors_chrome.json").read_text(encoding="utf-8"))
        tdc = fixture_dir / "tdc_same_round.js"
        payload = {
            "tdc_url": chrome["tdcUrl"],
            "tdc_local": str(tdc),
            "ua": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/151.0.0.0 Safari/537.36"
            ),
            "entry_url": (
                "http://kegdemo.guaishouyiyou.cn:8080/"
                "ticket_loader.html?aid=192037696"
            ),
            "clicks": [],
            "debug_collectors": True,
            "skip_events": True,
        }
        payload.update(extra)
        result = subprocess.run(
            ["node", str(DRIVER)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            cwd=DRIVER.parent,
            timeout=120,
            check=True,
        )
        return json.loads(result.stdout)

    def test_static_collectors_match_chrome(self):
        data = self._run()
        values = {str(item["id"]): item["value"] for item in data["collectors"]}
        self.assertEqual(values["3"], [2])
        self.assertEqual(values["18"], [0])
        self.assertEqual(values["33"], [0])
        self.assertEqual(values["35"], [900])
        self.assertEqual(values["36"], [735])
        self.assertEqual(len(data["collect"]), 1016)
        self.assertEqual(len(data["eks"]), 236)

    def test_packaged_driver_needs_only_jsdom(self):
        package = DRIVER.parent / "package.json"
        env_patch = (DRIVER.parent / "env_patch.js").read_text(encoding="utf-8")
        self.assertNotIn('require("canvas")', env_patch)
        self.assertEqual(
            json.loads(package.read_text(encoding="utf-8"))["dependencies"],
            {"jsdom": "25.0.1"},
        )
        result = subprocess.run(
            [
                "node",
                "-e",
                (
                    "for(const n of ['canvas','playwright']){"
                    "try{require.resolve(n);process.exit(2)}catch(e){}}"
                ),
            ],
            cwd=DRIVER.parent,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_click_trace_matches_successful_shape(self):
        data = self._run(
            clicks=[
                {"x": 597.6, "y": 372.6},
                {"x": 744.4, "y": 370.6},
                {"x": 498.9, "y": 370.6},
                {"x": 640.0, "y": 569.4},
            ],
            debug_collectors=False,
            skip_events=False,
        )
        self.assertEqual(len(data["events"]), 32)
        self.assertEqual(sum(e["type"] == "mousemove" for e in data["events"]), 20)
        self.assertTrue(all(e["offsetX"] == round(e["offsetX"]) for e in data["events"]))
        self.assertTrue(all(e["offsetY"] == round(e["offsetY"]) for e in data["events"]))
        self.assertIn(len(data["collect"]), {1272, 1304, 1336, 1368})
        self.assertIn(len(data["eks"]), {236, 248})

    def test_clicks_file_mode_preserves_event_shape(self):
        """clicks 由 Python 稍后写入文件时，事件形状与直接传入一致。"""
        fixture_value = os.environ.get("TXDX_TDC_FIXTURE_DIR")
        fixture_dir = Path(fixture_value) if fixture_value else None
        if fixture_dir is None or not fixture_dir.is_dir():
            self.skipTest("set TXDX_TDC_FIXTURE_DIR to run captured-vector regressions")
        tdc = fixture_dir / "tdc_same_round.js"
        clicks = [
            {"x": 597.6, "y": 372.6},
            {"x": 744.4, "y": 370.6},
            {"x": 498.9, "y": 370.6},
            {"x": 640.0, "y": 569.4},
        ]
        with tempfile.TemporaryDirectory() as td:
            clicks_file = os.path.join(td, "clicks.json")

            def write_late():
                time.sleep(0.3)
                with open(clicks_file, "w", encoding="utf-8") as fh:
                    json.dump(clicks, fh)

            threading.Thread(target=write_late, daemon=True).start()
            payload = {
                "tdc_url": "/tdc.js",
                "tdc_local": str(tdc),
                "ua": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/151.0.0.0 Safari/537.36"
                ),
                "entry_url": (
                    "http://kegdemo.guaishouyiyou.cn:8080/"
                    "ticket_loader.html?aid=192037696"
                ),
                "clicks": [],
                "clicks_file": clicks_file,
                "skip_events": False,
                "debug_collectors": False,
            }
            result = subprocess.run(
                ["node", str(DRIVER)],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                cwd=DRIVER.parent,
                timeout=120,
                check=True,
            )
            data = json.loads(result.stdout)
        self.assertEqual(len(data["events"]), 32)
        self.assertEqual(sum(e["type"] == "mousemove" for e in data["events"]), 20)
        self.assertTrue(all(e["offsetX"] == round(e["offsetX"]) for e in data["events"]))
        self.assertIn(len(data["collect"]), {1272, 1304, 1336, 1368})


if __name__ == "__main__":
    unittest.main()
