# -*- coding: utf-8 -*-
"""Generate collect/eks from a downloaded same-round TDC in local jsdom."""
import json
import os
import subprocess

TDC_JS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tdc_js")
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
)


def gen_collect_eks(
    round_data,
    entry_url,
    workdir,
    clicks,
    *,
    ua=None,
    confirm_last=True,
):
    """Return ``(collect, eks, tdc_tokenid)`` without any Node network request."""
    del confirm_last
    tdc_local = os.path.join(workdir, "tdc.js")
    if not os.path.isfile(tdc_local):
        raise RuntimeError("missing local tdc.js; call download_tdc() first")

    payload = json.dumps({
        "tdc_url": round_data.get("tdc_path", ""),
        "tdc_local": tdc_local,
        "ua": ua or DEFAULT_UA,
        "sid": round_data.get("sid", ""),
        "entry_url": entry_url,
        "clicks": clicks,
    })
    driver = os.path.join(TDC_JS_DIR, "click_driver.js")
    result = subprocess.run(
        ["node", driver],
        input=payload,
        capture_output=True,
        text=True,
        cwd=TDC_JS_DIR,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "click_driver.js exited %d: %s"
            % (result.returncode, result.stderr[-2000:])
        )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "click_driver.js invalid JSON: %s; tail: %s"
            % (error, result.stdout[-300:])
        ) from error

    collect = data.get("collect", "")
    if not collect:
        raise RuntimeError("click_driver.js returned empty collect")
    return collect, data.get("eks", ""), str(data.get("tokenid", "") or "")
