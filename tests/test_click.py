# -*- coding: utf-8 -*-
"""点选出票测试（AppId 192037696，浏览器方式）。
用法：python tests/test_click.py [--proxy http://ip:port] [--headless]
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from txdx import solve

CLICK_AID = "192037696"


def test_solve_click():
    r = solve(aid=CLICK_AID, headless=True, rounds=2, timeout=50)
    assert r["success"] is True, "点选出票失败: %s" % r
    assert r["ticket"].startswith("tr03"), "ticket 格式异常"
    print("[OK] ticket=%s... randstr=%s" % (r["ticket"][:36], r["randstr"]))
    return r


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--proxy", default=None)
    ap.add_argument("--headless", action="store_true", default=True)
    args = ap.parse_args()
    test_solve_click()
