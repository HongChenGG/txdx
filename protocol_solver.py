# -*- coding: utf-8 -*-
"""Browser-free Tencent 2404 solver."""
import json
import math
import os
import random
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

from .collect_gen import gen_collect_eks
from .hongchen import HongchenProvider
from .protocol import _proxies, download_tdc, get_bg, prehandle, solve_pow, verify

DOM_BG_LEFT = 475.0
DOM_BG_TOP = 295.1484375
DOM_BG_WIDTH = 330.0
DOM_BG_HEIGHT = 235.714
WIDGET_STANDARD_WIDTH = 360.0
MARK_SIZE = 32.0
CONFIRM = (640.0, 569.4)
DEFAULT_ENTRY_URL = "https://sssjz.guaishouyiyou.cn/#/pages/index"


def _answer_from_display_click(x, y, bg_size):
    bg_width, bg_height = (float(v) for v in bg_size)
    rendered_mark_size = MARK_SIZE * min(DOM_BG_WIDTH / WIDGET_STANDARD_WIDTH, 1.0)
    offset_x = x - DOM_BG_LEFT
    offset_y = y - DOM_BG_TOP
    answer_x = bg_width * ((offset_x - rendered_mark_size / 2.0) / DOM_BG_WIDTH) + MARK_SIZE / 2.0
    answer_y = bg_height * ((offset_y - rendered_mark_size / 2.0) / DOM_BG_HEIGHT) + MARK_SIZE / 2.0
    return int(math.floor(answer_x + 0.5)), int(math.floor(answer_y + 0.5))


def _build_answer_clicks(boxes, bg_size=(672, 480), confirm=True, jitter=1.0):
    """Build verify answers and TDC events from the same display click."""
    bg_width, bg_height = (float(v) for v in bg_size)
    scale_x = DOM_BG_WIDTH / bg_width
    scale_y = DOM_BG_HEIGHT / bg_height
    answers, clicks = [], []
    for index, box in enumerate(boxes):
        x0, y0, x1, y1 = (float(v) for v in box)
        native_x = (x0 + x1) / 2.0 + random.uniform(-jitter, jitter)
        native_y = (y0 + y1) / 2.0 + random.uniform(-jitter, jitter)
        display_x = DOM_BG_LEFT + native_x * scale_x
        display_y = DOM_BG_TOP + native_y * scale_y
        answer_x, answer_y = _answer_from_display_click(
            round(display_x - DOM_BG_LEFT) + DOM_BG_LEFT,
            round(display_y - DOM_BG_TOP) + DOM_BG_TOP,
            bg_size,
        )
        answers.append({
            "elem_id": index + 1,
            "type": "DynAnswerType_POS",
            "data": "%d,%d" % (answer_x, answer_y),
        })
        clicks.append({"x": display_x, "y": display_y})
    if confirm:
        clicks.append({"x": CONFIRM[0], "y": CONFIRM[1]})
    return answers, clicks


def solve_protocol(
    aid,
    entry_url=None,
    proxy=None,
    captcha_provider=None,
    gap_seconds=60.0,
    max_rounds=1,
    verbose=True,
):
    """Solve one or more fresh sessions without importing or starting a browser."""
    if not aid:
        raise ValueError("aid is required")
    entry_url = entry_url or DEFAULT_ENTRY_URL
    provider = captcha_provider or HongchenProvider(proxy=proxy)
    proxies = _proxies(proxy)
    last_error = ""

    for round_index in range(max(1, max_rounds)):
        try:
            with tempfile.TemporaryDirectory(prefix="txdx_protocol_") as workdir:
                round_data, error = prehandle(aid, entry_url, proxies)
                if error:
                    last_error = error
                elif round_data.get("subcapclass") != "2404":
                    last_error = "unsupported subcapclass %s" % round_data.get("subcapclass", "")
                else:
                    bg_path = get_bg(round_data, workdir, proxies, entry_url=entry_url)
                    download_tdc(round_data["tdc_path"], workdir, proxies, entry_url=entry_url)
                    # 并行：collect 生成（Node 提前 eval TDC、跑页面年龄/ambient）
                    # 与 识别+PoW 同时进行，坐标就绪后写入 clicks_file。
                    clicks_file = os.path.join(workdir, "clicks.json")
                    boxes = []
                    answers = []
                    with ThreadPoolExecutor(max_workers=2) as pool:
                        collect_fut = pool.submit(
                            gen_collect_eks,
                            round_data,
                            entry_url,
                            workdir,
                            [],
                            clicks_file=clicks_file,
                            confirm_last=True,
                        )
                        try:
                            boxes = provider.solve_click(round_data["instruction"], bg_path, proxy=proxy)
                            pow_answer, pow_calc = solve_pow(round_data["pow"])
                            if boxes:
                                answers, clicks = _build_answer_clicks(
                                    boxes,
                                    bg_size=tuple(round_data.get("bg_cfg", {}).get("size_2d") or (672, 480)),
                                    confirm=True,
                                )
                                with open(clicks_file, "w", encoding="utf-8") as fh:
                                    json.dump(clicks, fh)
                        finally:
                            # 识别失败也写入空列表，释放驱动轮询，避免会话卡住
                            if not os.path.exists(clicks_file):
                                with open(clicks_file, "w", encoding="utf-8") as fh:
                                    json.dump([], fh)
                        collect, eks, tdc_tokenid = collect_fut.result(timeout=60)
                    if boxes:
                        if verbose:
                            print(
                                "[protocol] instruction=%s ans=%s collect=%d eks=%d tkid=%s"
                                % (
                                    round_data["instruction"],
                                    json.dumps(answers, ensure_ascii=False),
                                    len(collect),
                                    len(eks),
                                    round_data.get("tkid", ""),
                                )
                            )
                        response = verify(
                            round_data,
                            collect,
                            eks,
                            answers,
                            pow_answer,
                            pow_calc,
                            proxies,
                            entry_url=entry_url,
                            tkid=tdc_tokenid,
                        )
                        error_code = str(response.get("errorCode", ""))
                        if error_code == "0" and response.get("ticket"):
                            return {
                                "success": True,
                                "ticket": response.get("ticket"),
                                "randstr": response.get("randstr", ""),
                                "sess": round_data["sess"],
                                "errorCode": "0",
                                "mode": "protocol",
                            }
                        last_error = error_code or "verify failed"
                    else:
                        last_error = "recognition failed"
        except Exception as error:
            last_error = "%s: %s" % (type(error).__name__, error)

        if round_index + 1 < max(1, max_rounds) and gap_seconds > 0:
            time.sleep(gap_seconds)

    return {
        "success": False,
        "errorCode": last_error,
        "error": last_error or "rounds exhausted",
        "mode": "protocol",
    }
