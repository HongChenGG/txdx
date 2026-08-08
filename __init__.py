# -*- coding: utf-8 -*-
"""txdx — 腾讯文字点选验证码自动出票（浏览器方式，支持 Linux 无头 + 传 IP）。

用法：
    from txdx import solve
    r = solve(aid="192037696", proxy="http://ip:port", headless=True)
    # -> {"success": True, "ticket": "tr03...", "randstr": "@xx", ...}

浏览器方式（真实 Chrome/Chromium + 真实 tgJCap 执行），
滑块/点选均可，点选为主。红尘打码默认，可传自定义识别函数。
"""
import os
from .get_ticket import get_ticket

__all__ = ["solve", "get_ticket"]
SLIDER_AID = "192294958"
CLICK_AID = "192037696"


def solve(aid=None, proxy=None, headless=True, rounds=3, timeout=50,
          port=None, captcha_kind="auto"):
    """一次点选（或滑块）自动出票。

    :param aid: AppID（缺省：点选 192037696 / 滑块 192294958 由 captcha_kind 决定）
    :param proxy: 出口代理 http://user:pass@ip:port 或 socks5://ip:port（可空=直连）
    :param headless: Linux 服务器建议 True
    :param rounds: 最多尝试轮数
    :param timeout: 每轮超时秒
    :param port: 本地 loader 端口（并发多实例时需不同端口）
    :return: {"success": bool, "ticket": str, "randstr": str, "ret": int, ...}
    """
    if aid is None:
        aid = SLIDER_AID if captcha_kind == "slider" else CLICK_AID
    import threading
    lock = threading.Lock()
    counter = [8080]

    def _port():
        with lock:
            counter[0] += 1
            return counter[0]

    r = get_ticket(aid, max_try=rounds, headless=headless, timeout=timeout,
                   proxy=proxy, port=port or _port())
    r = dict(r or {})
    r["success"] = r.get("ret") == 0 and bool(r.get("ticket"))
    return r
