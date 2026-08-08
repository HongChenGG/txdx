# -*- coding: utf-8 -*-
"""txdx HTTP 服务：POST /solve 传 {ip}，用该 IP 完成一次点选出票。

用法：
  export HONGCHEN_TOKEN=xxx
  export CHROME_PATH=/usr/bin/chromium
  python server.py --host 0.0.0.0 --port 9000

请求：
  POST /solve
  {"aid": "192037696", "ip": "http://user:pass@ip:port", "headless": true, "rounds": 2}

返回：
  {"success": true, "ticket": "tr03...", "randstr": "@xx", "ret": 0, "cost_s": 8.1}
"""
import argparse, asyncio, json, os, socket, sys, threading, time, uuid

os.environ.setdefault("HONGCHEN_TOKEN", "")
os.environ.setdefault("CHROME_PATH", "/usr/bin/chromium")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # /root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from fastapi import FastAPI, Request
    from pydantic import BaseModel, Field
    import uvicorn
except ImportError:
    raise SystemExit("缺少依赖：pip install fastapi uvicorn")

from txdx import solve

app = FastAPI(title="txdx point-click solver", version="1.0.0")

# ---------- 端口分配（线程安全 + 冲突检测，修复 __init__.py 自动分配 bug） ----------
_PORT_LOCK = threading.Lock()
_PORT_BASE = 8080

def _pick_port():
    """从 8081 起找一个可用端口（避免并发撞端口）。"""
    global _PORT_BASE
    with _PORT_LOCK:
        while True:
            _PORT_BASE += 1
            cand = _PORT_BASE
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", cand)) != 0:   # 端口未被占用
                    return cand


class SolveReq(BaseModel):
    aid: str = Field("192037696", description="腾讯验证码 AppID")
    ip: str = Field(None, description="出口代理 IP，如 http://user:pass@ip:port 或 socks5://ip:port")
    headless: bool = Field(True, description="无头模式")
    rounds: int = Field(2, ge=1, le=10, description="最多尝试轮数")
    timeout: int = Field(50, description="每轮超时秒")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/solve")
async def solve_endpoint(req: SolveReq):
    port = _pick_port()
    proxy = req.ip or None
    t0 = time.time()
    # 独立线程跑（playwright 会阻塞事件循环）
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None, solve, req.aid, proxy, req.headless, req.rounds, req.timeout, port, "auto")
    result = dict(result or {})
    result["port"] = port
    result["cost_s"] = round(time.time() - t0, 1)
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="txdx HTTP 出票服务")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    print(f"txdx server on http://{args.host}:{args.port}  workers={args.workers}")
    uvicorn.run(app, host=args.host, port=args.port, workers=args.workers)
