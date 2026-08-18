# -*- coding: utf-8 -*-
"""Command-line entry for the pure-protocol solver."""
import argparse
import json

from . import solve


def main():
    parser = argparse.ArgumentParser(description="腾讯文字点选验证码纯协议出票")
    parser.add_argument("--aid", default="192037696")
    parser.add_argument("--entry", default=None, help="业务入口 URL")
    parser.add_argument("--proxy", default=None, help="http://user:pass@ip:port 或 socks5://ip:port")
    parser.add_argument("--rounds", type=int, default=1, help="每轮使用全新 sess 且只 verify 一次")
    parser.add_argument("--gap", type=float, default=60.0, help="新会话之间的冷却秒数")
    args = parser.parse_args()
    result = solve(
        aid=args.aid,
        entry_url=args.entry,
        proxy=args.proxy,
        rounds=args.rounds,
        gap_seconds=args.gap,
        mode="protocol",
        verbose=True,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
