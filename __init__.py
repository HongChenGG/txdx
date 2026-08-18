# -*- coding: utf-8 -*-
"""Tencent click-select solver; pure protocol by default."""

from . import protocol_solver
from .hongchen import HongchenProvider
from .provider import CaptchaProvider

__all__ = ["solve", "get_ticket", "CaptchaProvider", "HongchenProvider"]
CLICK_AID = "192037696"


def get_ticket(appid, **kwargs):
    """Lazy compatibility wrapper for the legacy browser implementation."""
    from .get_ticket import get_ticket as browser_get_ticket

    return browser_get_ticket(appid, **kwargs)


def solve(
    aid=CLICK_AID,
    proxy=None,
    headless=True,
    rounds=1,
    timeout=50,
    port=None,
    captcha_kind="auto",
    *,
    mode="protocol",
    entry_url=None,
    captcha_provider=None,
    gap_seconds=60.0,
    verbose=True,
):
    """Return a Tencent ticket using pure protocol or explicit browser fallback.

    ``mode="protocol"`` never imports Playwright. ``mode="browser"`` keeps the
    legacy implementation for diagnostics and compatibility.
    """
    del captcha_kind
    if mode == "protocol":
        return protocol_solver.solve_protocol(
            aid=aid,
            entry_url=entry_url,
            proxy=proxy,
            captcha_provider=captcha_provider,
            gap_seconds=gap_seconds,
            max_rounds=rounds,
            verbose=verbose,
        )
    if mode != "browser":
        raise ValueError("mode must be 'protocol' or 'browser'")

    result = dict(
        get_ticket(
            aid,
            max_try=rounds,
            headless=headless,
            timeout=timeout,
            proxy=proxy,
            port=port or 8081,
        )
        or {}
    )
    result["success"] = result.get("ret") == 0 and bool(result.get("ticket"))
    result["mode"] = "browser"
    return result
