# -*- coding: utf-8 -*-
"""红尘打码 Provider（默认打码源）：文字点选坐标识别。

接口：POST {base}/api/detection/text/order
  {order_img_base64: 渲染的指令字行, target_img_base64: 背景图}
返回：{"result": [[x0,y0,x1,y1], ...]}（按指令顺序的背景图原生坐标框）

Token 读取：显式 ``token=`` 或环境变量 ``HONGCHEN_TOKEN``。
"""
import base64
import io
import os
import re

import requests
from PIL import Image, ImageDraw, ImageFont
from .provider import CaptchaProvider

DEFAULT_HC = "http://223.109.142.75:7448"


def _b64buf(buf):
    return base64.b64encode(buf).decode()


def _proxies(proxy):
    if not proxy:
        return None
    value = proxy if "://" in proxy else "http://" + proxy
    return {"http": value, "https": value}


def _parse_instruction(instruction):
    """'请依次点击：倍 拌 脖 ' -> ['倍','拌','脖']"""
    after = instruction.split("：")[-1].split(":")[-1]
    return re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", after)


def _render_order_line(chars):
    """把指令字渲染成一行大字距图（/api/detection/text/order 对这种输入定位最准）。"""
    # 跨平台字体探测：Windows → Linux 中文字体
    import glob
    font_candidates = [
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
    ]
    f = None
    for cand in font_candidates:
        try:
            f = ImageFont.truetype(cand, 48)
            break
        except Exception:
            continue
    if f is None:
        # 兜底：任意 CJK 字体
        for path in glob.glob("/usr/share/fonts/**/*.tt[cf]", recursive=True):
            try:
                f = ImageFont.truetype(path, 48)
                break
            except Exception:
                continue
    if f is None:
        raise RuntimeError("缺少中文字体：apt install fonts-noto-cjk")
    im = Image.new("RGB", (400, 120), (255, 255, 255))
    d = ImageDraw.Draw(im)
    x = 10
    for ch in chars:
        d.text((x, 20), ch, font=f, fill=(0, 0, 0))
        x += 130
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


class HongchenProvider(CaptchaProvider):
    name = "hongchen"

    def __init__(self, base=DEFAULT_HC, token=None, timeout=90, proxy=None):
        self.base = base
        self.token = token if token is not None else os.environ.get("HONGCHEN_TOKEN")
        self.timeout = timeout
        self.proxy = proxy
        if not self.token:
            raise ValueError("未配置红尘 Token：export HONGCHEN_TOKEN=xxx 或传 token= 参数")

    def solve_click(self, instruction, bg_path, proxy=None):
        chars = _parse_instruction(instruction)
        if not chars:
            return []
        bg = Image.open(bg_path).convert("RGB")
        b2 = io.BytesIO()
        bg.save(b2, "PNG")
        r = requests.post(
            self.base + "/api/detection/text/order",
            json={"order_img_base64": _b64buf(_render_order_line(chars)),
                  "target_img_base64": _b64buf(b2.getvalue())},
            headers={"Authorization": "Bearer " + self.token},
            proxies=_proxies(proxy or self.proxy),
            timeout=self.timeout)
        r.raise_for_status()
        boxes = r.json().get("result") or []
        if len(boxes) >= len(chars):
            return boxes[:len(chars)]
        return boxes