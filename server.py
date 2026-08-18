# -*- coding: utf-8 -*-
"""txdx HTTP service; pure protocol by default.

Run: ``python -m txdx.server --host 0.0.0.0 --port 9000``
Request: ``POST /solve {"aid":"192037696","ip":null,"rounds":1}``
"""
import argparse
import asyncio
import time
from functools import partial
from typing import Optional

try:
    from fastapi import FastAPI
    from pydantic import BaseModel, Field
    import uvicorn
except ImportError:
    raise SystemExit("缺少依赖：pip install fastapi uvicorn")

from txdx import solve

app = FastAPI(title="txdx pure-protocol click solver", version="2.0.0")


class SolveReq(BaseModel):
    aid: str = Field("192037696", description="腾讯验证码 AppID")
    ip: Optional[str] = Field(None, description="出口代理 IP，如 http://user:pass@ip:port 或 socks5://ip:port")
    entry_url: Optional[str] = Field(None, description="业务入口 URL")
    rounds: int = Field(1, ge=1, le=10, description="最多新建会话数；每个会话只 verify 一次")
    gap_seconds: float = Field(60.0, ge=0, description="新会话之间的冷却秒数")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/solve")
async def solve_endpoint(req: SolveReq):
    t0 = time.time()
    call = partial(
        solve,
        aid=req.aid,
        proxy=req.ip or None,
        rounds=req.rounds,
        mode="protocol",
        entry_url=req.entry_url,
        gap_seconds=req.gap_seconds,
        verbose=True,
    )
    result = await asyncio.get_running_loop().run_in_executor(None, call)
    result = dict(result or {})
    result["cost_s"] = round(time.time() - t0, 1)
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="txdx HTTP 出票服务")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("--workers", type=int, default=1)
    args = ap.parse_args()
    print(f"txdx server on http://{args.host}:{args.port}  workers={args.workers}")
    uvicorn.run(app, host=args.host, port=args.port, workers=args.workers)
