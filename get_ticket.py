# -*- coding: utf-8 -*-
"""
腾讯验证码自动出票工具（滑块 / 文字点选）
用法：python get_ticket.py --aid 192294958
功能：
  1. 浏览器加载 captcha（*.guaishouyiyou.cn 白名单域名经 host-resolver 映射到本地）
  2. 截获 prehandle 协议 → 解析题目（sess/sid/图片 URL/拼图配置）
  3. 下载题目图 → 调红尘识别（滑块缺口 / 点选坐标）
  4. 模拟拖动/点击（类人轨迹）→ 真实 JS 生成 collect/eks/pow 并提交
  5. 从回调拿到 ticket + randstr 返回

依赖：pip install playwright requests；浏览器用系统 Chrome。
"""
import argparse, base64, json, os, random, re, threading, time
import urllib.parse
import requests
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from playwright.sync_api import sync_playwright

# ---------- 配置 ----------
PORT = 8080
WHITE_DOMAIN = "kegdemo.guaishouyiyou.cn"


def _find_chrome():
    """自动探测 Chrome/Chromium（Windows + Linux）。可用 CHROME_PATH 覆盖。"""
    p = os.environ.get("CHROME_PATH")
    if p and os.path.exists(p):
        return p
    cands = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium", "/usr/bin/chromium-browser",
        "/snap/bin/chromium", "/usr/bin/microsoft-edge",
    ]
    for c in cands:
        if os.path.exists(c):
            return c
    raise SystemExit("未找到 Chrome：设置 CHROME_PATH 环境变量，或安装 chromium")


CHROME = _find_chrome()


def _cjk_font():
    """中文字体探测（点选指令字渲染用）：Windows 雅黑/黑体 → Linux Noto/WQY。"""
    cands = [
        r"C:/Windows/Fonts/msyhbd.ttc", r"C:/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
    ]
    for p in cands:
        if os.path.exists(p):
            return p
    raise SystemExit("缺少中文字体：Linux 执行 apt install fonts-noto-cjk")

HONGCHEN_BASE = "http://223.109.142.75:7448"
HONGCHEN_TOKEN = os.environ.get("HONGCHEN_TOKEN", "")

class H(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

def serve(port=PORT):
    httpd = ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd

def hc_headers():
    if not HONGCHEN_TOKEN:
        raise RuntimeError("未配置红尘 Token：export HONGCHEN_TOKEN=xxx")
    return {"Authorization": f"Bearer {HONGCHEN_TOKEN}"}


def _proxies_d(proxy):
    if not proxy:
        return None
    p = proxy if "://" in proxy else "http://" + proxy
    return {"http": p, "https": p}


def hc_slider_match(bg_b64, piece_b64, proxy=None):
    r = requests.post(f"{HONGCHEN_BASE}/api/slider/match",
                      json={"target_base64": piece_b64, "background_base64": bg_b64},
                      headers=hc_headers(), proxies=_proxies_d(proxy), timeout=40)
    r.raise_for_status()
    return r.json()["result"]


def crop_piece(sprite_bytes, sprite_pos, size_2d):
    """从 sprite（img_index=0）按 fg_elem_list 的 sprite_pos 裁剪拼图块"""
    from PIL import Image
    import io as _io
    im = Image.open(_io.BytesIO(sprite_bytes)).convert("RGBA")
    x, y = sprite_pos
    w, h = size_2d
    buf = _io.BytesIO()
    im.crop((x, y, x + w, y + h)).save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def hc_detection_text(img_b64, proxy=None):
    r = requests.post(f"{HONGCHEN_BASE}/api/detection/text",
                      json={"img_base64": img_b64}, headers=hc_headers(),
                      proxies=_proxies_d(proxy), timeout=40)
    r.raise_for_status()
    return r.json()["result"]


def hc_text_order(render_b64, bg_b64, proxy=None):
    r = requests.post(f"{HONGCHEN_BASE}/api/detection/text/order",
                      json={"order_img_base64": render_b64, "target_img_base64": bg_b64},
                      headers=hc_headers(), proxies=_proxies_d(proxy), timeout=90)
    r.raise_for_status()
    return r.json()["result"]


def img_b64(png_bytes):
    return base64.b64encode(png_bytes).decode()

# ---------- 轨迹生成 ----------
def human_track(distance):
    """类人拖动轨迹：加速→匀速→减速→微调回退"""
    import math
    points = []
    x = 0.0
    v = 0.0
    t = 0
    accel = 5 + random.random() * 4
    while x < distance:
        t += 1
        if t < 12:
            v += accel
        elif t < 28:
            v = max(v, random.uniform(16, 26))
        else:
            v = max(v - (4 + random.random() * 5), 7)
        x += v
        if x > distance:
            x = distance
        points.append((x, random.uniform(-1.8, 1.8)))
    # 回退微调
    back = random.uniform(2, 9)
    points.append((distance - back, random.uniform(-1, 1)))
    points.append((distance - 1, random.uniform(-0.5, 0.5)))
    points.append((distance, 0))
    return points

# ---------- 主流程 ----------
def get_ticket(appid, max_try=3, headless=False, timeout=45, proxy=None, port=8080):
    serve(port)
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            executable_path=CHROME,
            # 腾讯请求走代理；本地 loader/白名单域名直连（host-resolver 映射到 127.0.0.1）
            proxy={"server": proxy, "bypass": "127.0.0.1,localhost,*.guaishouyiyou.cn"} if proxy else None,
            args=[f"--host-resolver-rules=MAP *.{WHITE_DOMAIN.split('.',1)[1]} 127.0.0.1",
                  "--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(ignore_https_errors=True, viewport={"width": 1280, "height": 900})
        page = ctx.new_page()

        state = {"prehandle": None, "bg_png": None, "piece_png": None,
                 "display_scale": 1.0, "piece_init_x": 50, "click_text": ""}

        def on_response(resp):
            if "cap_union_prehandle" in resp.url:
                try:
                    body = resp.text()
                    m = re.search(r"\((.*)\)\s*$", body, re.S)
                    if m:
                        state["prehandle"] = json.loads(m.group(1))
                except Exception:
                    pass
            if "cap_union_new_getcapbysig" in resp.url and state["prehandle"]:
                try:
                    body = resp.body()
                except Exception:
                    return
                if resp.headers.get("content-type", "").startswith("image"):
                    if "img_index=0" in resp.url:
                        state["piece_png"] = body
                    elif "img_index=1" in resp.url:
                        state["bg_png"] = body

        page.on("response", on_response)

        def grab_round():
            """轮询等待 prehandle + 图片就绪，返回当前题目配置"""
            for _ in range(40):
                pre = state["prehandle"]
                if pre:
                    dsi = pre.get("data", {}).get("dyn_show_info", {})
                    bg_ok = state["bg_png"] is not None
                    need_piece = str(pre.get("subcapclass")) == "2401"
                    if bg_ok and (not need_piece or state["piece_png"] is not None):
                        return pre
                page.wait_for_timeout(500)
            return None

        url = f"http://{WHITE_DOMAIN}:{port}/ticket_loader.html?aid={appid}"
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        if page.evaluate("window.__ticket_error !== undefined"):
            err = page.evaluate("window.__ticket_error")
            browser.close()
            return {"ret": -1, "error": f"captcha init error: {err}"}

        for attempt in range(max_try):
            pre = grab_round()
            if not pre:
                browser.close()
                return {"ret": -1, "error": "prehandle/题目图片超时未就绪"}

            sub = str(pre.get("subcapclass"))
            dsi = pre["data"]["dyn_show_info"]
            instruction = dsi.get("instruction", "")
            print(f"[round {attempt+1}] subcapclass={sub} instruction={instruction}")

            # 测量显示尺寸换算比例（多 selector 取最宽，兼容不同 widget 版本）
            page.wait_for_timeout(500)
            scale_info = page.evaluate("""() => {
                const sels = ['.tencent-captcha-dy__bg-placeholder', '.tencent-captcha-dy__verify-bg-img',
                              "[class*=bg-img] img", "img[src*='getcapbysig']"];
                let best = 0, bestNw = 672;
                for (const s of sels) {
                    const el = document.querySelector(s);
                    if (!el) continue;
                    const r = el.getBoundingClientRect();
                    if (r.width > best) { best = r.width; bestNw = el.naturalWidth || 672; }
                }
                return {w: best, nw: bestNw};
            }""")
            print("[scale] bg img:", scale_info)
            state["display_scale"] = (scale_info["w"] / 672) if scale_info and scale_info["w"] else 0.49

            if sub == "2401":
                # ---------- 滑块 ----------
                fg = dsi.get("fg_elem_list", [])
                piece_cfg = next((f for f in fg if f.get("id") == 1), None) or next((f for f in fg if f.get("move_cfg")), None)
                piece_init_x = (piece_cfg or {}).get("init_pos", [50, 0])[0]
                if not state["piece_png"]:
                    browser.close()
                    return {"ret": -1, "error": "滑块小图未抓到"}
                # 从 sprite 裁剪拼图块（img_index=0 是整张 sprite）
                sprite_pos = (piece_cfg or {}).get("sprite_pos")
                size_2d = (piece_cfg or {}).get("size_2d")
                piece_b64 = crop_piece(state["piece_png"], sprite_pos, size_2d) if sprite_pos and size_2d \
                    else img_b64(state["piece_png"])
                res = hc_slider_match(img_b64(state["bg_png"]), piece_b64, proxy=proxy)
                target = res.get("target")
                if not target:
                    browser.close()
                    return {"ret": -1, "error": f"滑块识别失败: {res}"}
                x1 = target[0]
                native_dist = x1 - piece_init_x
                disp_dist = native_dist * state["display_scale"]
                print(f"[solve] gap x1={x1} piece_init={piece_init_x} native={native_dist} display={disp_dist:.1f}")

                el = page.evaluate("""() => {
                    const el = document.querySelector('.tencent-captcha-dy__slider-block, .tcaptcha-drag-icon');
                    if (!el) return null;
                    const r = el.getBoundingClientRect();
                    return {x: r.x, y: r.y, w: r.width, h: r.height};
                }""")
                if not el:
                    browser.close()
                    return {"ret": -1, "error": "未找到滑块元素"}
                sx = el["x"] + el["w"] / 2
                sy = el["y"] + el["h"] / 2
                page.mouse.move(sx, sy)
                page.mouse.down()
                track = human_track(max(disp_dist, 10))
                for px, py in track:
                    page.mouse.move(sx + px, sy + py, steps=1)
                    page.wait_for_timeout(random.randint(8, 22))
                page.mouse.up()
                print(f"[drag] {len(track)} 步, 目标 {disp_dist:.1f}px")

            elif sub == "2404":
                # ---------- 文字点选 ----------
                if not state["bg_png"]:
                    browser.close()
                    return {"ret": -1, "error": "点选底图未抓到"}
                # 优先用 order 接口按指令排序；失败回退 detection/text + 顺序点击
                instr = dsi.get("instruction", "")
                chars = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", instr.split("：")[-1].split(":")[-1])
                pts = None
                if chars:
                    try:
                        from PIL import Image, ImageDraw, ImageFont
                        import io as _io
                        im = Image.new("RGB", (400, 120), (255, 255, 255))
                        d = ImageDraw.Draw(im)
                        try:
                            f = ImageFont.truetype(_cjk_font(), 48)
                        except Exception:
                            f = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", 48)
                        x = 10
                        for ch in chars:
                            d.text((x, 20), ch, font=f, fill=(0, 0, 0))
                            x += 130
                        b = _io.BytesIO(); im.save(b, "PNG")
                        boxes = hc_text_order(base64.b64encode(b.getvalue()).decode(), img_b64(state["bg_png"]), proxy=proxy)
                        if boxes and len(boxes) >= len(chars):
                            pts = [{"box": boxes[i], "ch": ch} for i, ch in enumerate(chars)]
                    except Exception as e:
                        print(f"[solve] order api fail: {e}")
                if not pts:
                    res = hc_detection_text(img_b64(state["bg_png"]), proxy=proxy)
                    pts = res if isinstance(res, list) else []
                print(f"[solve] pts: {json.dumps(pts, ensure_ascii=False)[:250]}")
                if not pts:
                    browser.close()
                    return {"ret": -1, "error": "点选识别失败"}
                # 换算到显示坐标：图片元素左上角 + native*scale
                img_rect = page.evaluate("""() => {
                    const sels = ['.tencent-captcha-dy__bg-placeholder', '.tencent-captcha-dy__verify-bg-img',
                                  "[class*=bg-img] img", "img[src*='getcapbysig']"];
                    for (const s of sels) {
                        const el = document.querySelector(s);
                        if (!el) continue;
                        const r = el.getBoundingClientRect();
                        if (r.width > 50) return {x: r.x, y: r.y, w: r.width, h: r.height};
                    }
                    return null;
                }""")
                if not img_rect:
                    browser.close()
                    return {"ret": -1, "error": "未找到点选底图元素"}
                scale = state["display_scale"]
                for i, pt in enumerate(pts[:6]):
                    box = pt.get("box") if isinstance(pt, dict) else None
                    if box:
                        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
                    else:
                        cx, cy = pt["x"], pt["y"]
                    x = img_rect["x"] + cx * scale + random.uniform(-2, 2)
                    y = img_rect["y"] + cy * scale + random.uniform(-2, 2)
                    page.mouse.move(x, y, steps=random.randint(3, 6))
                    page.wait_for_timeout(random.randint(120, 350))
                    page.mouse.down()
                    page.wait_for_timeout(random.randint(40, 90))
                    page.mouse.up()
                    page.wait_for_timeout(random.randint(200, 450))
                print(f"[click] 点了 {len(pts)} 个目标")
                # 点选必须点确认按钮才触发 verify（verify_trigger_cfg.verify_icon）
                btn = page.evaluate("""() => {
                    const el = document.querySelector('.tencent-captcha-dy__verify-confirm-btn');
                    if (!el) return null;
                    const r = el.getBoundingClientRect();
                    return {x: r.x, y: r.y, w: r.width, h: r.height};
                }""")
                if btn:
                    page.mouse.click(btn["x"] + btn["w"] / 2, btn["y"] + btn["h"] / 2)
                    print("[click] 点了确认按钮")
                else:
                    print("[click] 未找到确认按钮（可能不需要）")

            else:
                browser.close()
                return {"ret": -1, "error": f"未知 subcapclass={sub}（非滑块2401/点选2404）"}

            # 等回调
            deadline = time.time() + timeout
            result = None
            while time.time() < deadline:
                result = page.evaluate("window.__ticket_result")
                if result and (result.get("ret") == 0 or result.get("ticket")):
                    break
                page.wait_for_timeout(800)
                if result and result.get("ret") not in (0, 2):
                    break  # 用户关闭等
            if result and result.get("ret") == 0 and result.get("ticket"):
                out = {"ret": 0, "ticket": result.get("ticket"),
                       "randstr": result.get("randstr"),
                       "appid": appid, "sid": (state["prehandle"] or {}).get("sid")}
                browser.close()
                return out
            print(f"[round {attempt+1}] 未出票，等待换题重试...")
            page.wait_for_timeout(4000)

        browser.close()
        return {"ret": -1, "error": "多次尝试未出票"}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="腾讯验证码自动出票（滑块/点选）")
    ap.add_argument("--aid", required=True, help="AppId")
    ap.add_argument("--headless", action="store_true", help="无头模式（风控更严）")
    ap.add_argument("--try", dest="max_try", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=45)
    ap.add_argument("--proxy", default=None, help="出口代理，如 http://ip:port")
    ap.add_argument("--port", type=int, default=8080, help="本地 loader 端口（多实例并发时需不同端口）")
    args = ap.parse_args()
    res = get_ticket(args.aid, max_try=args.max_try, headless=args.headless,
                     timeout=args.timeout, proxy=args.proxy, port=args.port)
    print(json.dumps(res, ensure_ascii=False, indent=2))
