# -*- coding: utf-8 -*-
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from txdx import protocol


ENTRY = "http://kegdemo.guaishouyiyou.cn:8080/ticket_loader.html?aid=192037696"


class ProtocolIdentityTest(unittest.TestCase):
    def test_prehandle_reuses_page_tkid_for_image(self):
        payload = {
            "sess": "session",
            "sid": "sid",
            "subcapclass": "2404",
            "data": {
                "comm_captcha_cfg": {
                    "pow_cfg": {"prefix": "p", "md5": "m"},
                    "tdc_path": "/tdc.js",
                },
                "dyn_show_info": {
                    "instruction": "请依次点击：甲",
                    "bg_elem_cfg": {
                        "size_2d": [672, 480],
                        "img_url": "/cap_union_new_getcapbysig?img_index=1&image=x&sess=session",
                    },
                },
            },
        }
        response = SimpleNamespace(
            text="cb(%s)" % json.dumps(payload),
            raise_for_status=lambda: None,
        )
        session = SimpleNamespace(get=lambda *args, **kwargs: response)

        with patch("txdx.protocol._session", return_value=session):
            round_data, error = protocol.prehandle("192037696", ENTRY, None)

        self.assertIsNone(error)
        self.assertTrue(round_data["tkid"].isdigit())
        image_query = parse_qs(urlparse(round_data["bg_cfg"]["img_url"]).query)
        self.assertEqual(image_query["tkid"], [round_data["tkid"]])

    def test_verify_prefers_page_tkid_over_tdc_tokenid(self):
        response = SimpleNamespace(json=lambda: {"errorCode": "0"})
        captured = {}

        class Session:
            def post(self, url, data, headers, timeout):
                captured.update(parse_qs(data.decode()))
                return response

        round_data = {"sess": "session", "tkid": "123456789"}
        with patch("txdx.protocol._session", return_value=Session()):
            protocol.verify(
                round_data,
                "collect",
                "eks",
                [],
                "pow",
                350,
                None,
                entry_url=ENTRY,
                tkid="987654321",
            )

        self.assertEqual(captured["tkid"], ["123456789"])


if __name__ == "__main__":
    unittest.main()
