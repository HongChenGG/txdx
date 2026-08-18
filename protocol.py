# -*- coding: utf-8 -*-
"""Prehandle, image/TDC downloads, PoW and verify with exact proxy routing."""
import hashlib
import json
import os
import random
import re
import time
from urllib.parse import urlparse, urlencode
from curl_cffi import requests as cffi_requests

BASE = "https://turing.captcha.qcloud.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")
_MAX_POW_NONCE = 1_000_000


def _proxies(proxy):
    """curl_cffi 代理格式（与 requests 兼容）。"""
    if not proxy:
        return None
    p = proxy if "://" in proxy else "http://" + proxy
    return {"http": p, "https": p}


def _session(proxies=None):
    """创建 curl_cffi Session，模拟 Chrome TLS 指纹。proxies 为 _proxies() 返回的 dict。"""
    kwargs = {"impersonate": "chrome", "verify": False}
    if proxies:
        kwargs["proxies"] = proxies
    return cffi_requests.Session(**kwargs)


def _parse_jsonp(raw):
    """Strip JSONP callback wrapper and return the inner dict."""
    m = re.match(r"^\s*\w+\s*\(\s*(.*)\s*\)\s*;?\s*$", raw, re.S)
    body = m.group(1) if m else raw
    return json.loads(body)


def _new_tkid():
    """TJCaptcha page token reused by prehandle, image URLs and verify."""
    return str(random.randint(0, 999_999_999) + random.randint(0, 999_999_999))


def _with_tkid(url, tkid):
    separator = "&" if "?" in url else "?"
    return url if re.search(r"(?:^|[?&])tkid=", url) else "%s%stkid=%s" % (url, separator, tkid)


def _origin_of(url):
    """Return scheme://host[:port] for a URL."""
    if not url:
        return ""
    pu = urlparse(url)
    if not pu.scheme or not pu.netloc:
        return ""
    return "%s://%s" % (pu.scheme, pu.netloc)


def _page_headers(entry_url):
    """浏览器子资源请求头（widget 流实测 capture/_real_headers.json）：
    prehandle(JSONP)/tdc.js(script)/getcapbysig(img) 的 Referer 全是业务页 origin+"/"，
    且带全套 sec-ch-ua 头。此前 prehandle=完整URL / tdc=qcloud / bg=gtimg 全错 →
    服务器按 sess 对账请求来源 → ec=12。"""
    org = _origin_of(entry_url) if entry_url else ""
    referer = (org + "/") if org else BASE + "/"
    return {
        "User-Agent": UA,
        "Referer": referer,
        "sec-ch-ua": '"Not=A?Brand";v="99", "Google Chrome";v="151", "Chromium";v="151"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }


def prehandle(aid, entry_url, proxies):
    """Create one fresh click-select round and bind its page-level ``tkid``."""
    ua_b64 = __import__("base64").b64encode(UA.encode()).decode()
    callback = "_aq_%d" % random.randint(100000, 999999)
    tkid = _new_tkid()
    params = {
        "aid": aid, "protocol": "https", "accver": "1", "showtype": "popup",
        "ua": ua_b64, "noheader": "1", "fb": "1", "aged": "0", "enableAged": "0",
        "enableDarkMode": "0", "grayscale": "1", "clientype": "2",
        "cap_cd": "", "uid": "", "lang": "zh-cn",
        "entry_url": entry_url,
        "elder_captcha": "0", "js": "/tgJCap.627c7f42.js",
        "login_appid": "", "wb": "1", "tkid": tkid, "subsid": "1",
        "callback": callback, "sess": "",
    }
    # Referer/头对齐真实 widget JSONP 请求（origin+"/" + sec-ch-ua，_real_headers.json 实测）
    h = _page_headers(entry_url)
    h["Accept"] = "*/*"
    s = _session(proxies)
    data = None
    for attempt in range(3):
        r = s.get(BASE + "/cap_union_prehandle", params=params, headers=h, timeout=20)
        r.raise_for_status()
        data = _parse_jsonp(r.text)
        if ("data" not in data) and attempt < 2:
            time.sleep(1.0 + attempt)
            continue
        break
    if "data" not in data:
        return None, "prehandle failed: " + (data.get("errMessage") or data.get("message") or "")[:300]
    sess, sid = data["sess"], data["sid"]
    cfg = data["data"]["comm_captcha_cfg"]
    show = data["data"]["dyn_show_info"]
    bg_cfg = dict(show["bg_elem_cfg"])
    bg_cfg["img_url"] = _with_tkid(bg_cfg["img_url"], tkid)
    roundj = {"sess": sess, "sid": sid, "pow": cfg["pow_cfg"], "tdc_path": cfg["tdc_path"],
              "bg_cfg": bg_cfg, "instruction": show.get("instruction", ""),
              "verify_icon": (show.get("verify_trigger_cfg") or {}).get("verify_icon", True),
              "subcapclass": str(data.get("subcapclass", "")), "tkid": tkid}
    return roundj, None


def get_bg(roundj, workdir, proxies, entry_url=""):
    # Referer=业务页 origin+"/"（widget <img> 实测），非 gtimg
    h = _page_headers(entry_url)
    s = _session(proxies)
    bg = s.get(BASE + roundj["bg_cfg"]["img_url"], headers=h, timeout=20)
    bg.raise_for_status()
    p = os.path.join(workdir, "bg.png")
    open(p, "wb").write(bg.content)
    return p


def download_tdc(tdc_path, workdir, proxies, entry_url=""):
    url = BASE + (tdc_path if tdc_path.startswith("/") else "/" + tdc_path)
    s = _session(proxies)
    # Referer=业务页 origin+"/"（widget <script> 实测），非 qcloud
    h = _page_headers(entry_url)
    h["Accept-Encoding"] = "identity"
    r = s.get(url, headers=h, timeout=20)
    r.raise_for_status()
    data = r.content
    if data[:2] == b"\x1f\x8b":
        import gzip
        data = gzip.decompress(data)
    open(os.path.join(workdir, "tdc.js"), "w", encoding="utf-8").write(data.decode("utf-8"))
    return data.decode("utf-8")


def solve_pow(pw, min_ms=300, max_ms=500):
    """Solve the MD5 prefix challenge and report a browser-like duration."""
    prefix = pw["prefix"]
    target = pw["md5"]
    t0 = time.perf_counter()
    for nonce in range(_MAX_POW_NONCE):
        candidate = prefix + str(nonce)
        if hashlib.md5(candidate.encode()).hexdigest() == target:
            calc_ms = int((time.perf_counter() - t0) * 1000)
            if min_ms > 0:
                target_ms = random.randint(min_ms, max_ms) if max_ms > min_ms else min_ms
                if calc_ms < target_ms:
                    time.sleep((target_ms - calc_ms) / 1000.0)
                    calc_ms = target_ms
            return candidate, calc_ms
    raise RuntimeError("PoW not solved within %d iterations" % _MAX_POW_NONCE)


def verify(roundj, collect, eks, ans, pow_answer, pow_calc, proxies, entry_url="", tkid=None):
    """提交与 TJCaptcha 2.0 浏览器请求一致的 verify 表单。

    ``tkid`` 使用 prehandle 前生成并写入图片 URL的页面 token；TDC
    ``getInfo().tokenid`` 仅作为旧调用方兼容回退。业务页完整 URL 作为
    Referer，其 origin 作为 Origin；``tlg`` 是 decodeURIComponent 后 collect
    字符串长度。
    """
    tkid = roundj.get("tkid") or tkid or _new_tkid()
    body = {
        "ans": json.dumps(ans) if not isinstance(ans, str) else ans,
        "sess": roundj["sess"],
        "pow_answer": pow_answer,
        "pow_calc_time": str(pow_calc),
        "collect": collect,
        "tlg": str(len(collect)),
        "eks": eks,
        "tkid": str(tkid),
    }
    # 真实浏览器 verify = 业务页 XHR → Referer=业务页 URL，Origin=业务域（evspec 抓包证实）。
    # 服务器交叉校验 entry_url / collect 内嵌 location / Referer 三方一致，错值 → ec=12。
    referer = entry_url or (BASE + "/")
    origin = _origin_of(referer) or BASE
    h = {"User-Agent": UA, "Accept": "application/json, text/javascript, */*; q=0.01",
         "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
         "Referer": referer,
         "Origin": origin}
    s = _session(proxies)
    r = s.post(BASE + "/cap_union_new_verify",
               data=urlencode(body).encode(),
               headers=h, timeout=30)
    try:
        return r.json()
    except Exception:
        return {"errorCode": str(r.status_code), "ticket": "", "raw": r.text[:200]}
