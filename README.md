# txdx — 腾讯文字点选验证码纯协议求解

AppId `192037696`、`subcapclass=2404` 的浏览器外协议实现。默认链路不导入
Playwright，也不启动 Chrome/Chromium：

```text
prehandle → 背景图 → 同轮 tdc.js → Node/jsdom collect+eks → PoW → verify
```

已用全新 `sess`、单次 verify 在线验证返回 `errorCode=0`。浏览器实现仍保留，
但只有显式指定 `mode="browser"` 时才延迟导入。完整脱敏验证记录在主项目
`capture/protocol_success_latest.json`。

## 安装

需要 Python、Node.js，以及红尘识别 Token：

```bash
pip install -r requirements.txt
cd tdc_js && npm ci
export HONGCHEN_TOKEN='你的 token'
```

`tdc_js` 固定使用 `jsdom@25.0.1`。生产链只需要该依赖，不需要浏览器或
`node-canvas`。

## 命令行

```bash
python -m txdx.cli --aid 192037696 --rounds 1
python -m txdx.cli --aid 192037696 --proxy http://user:pass@ip:port
```

## 性能（并行编排）

`solve_protocol` 在 prehandle 后立即并行启动两路：

- Node/jsdom 提前 eval 同轮 `tdc.js` 并开始页面年龄计时；
- 红尘识别 + PoW 同时进行，坐标就绪后写入 `clicks_file`，驱动再派发事件。

事件序列（32 个事件、20 个 `mousemove`）与串行版逐字节一致，只消除了识别阶段
的串行等待。离线固定向量端到端约 4.7–5.2s（其中页面年龄 1.2–2.0s、事件轨迹约
2s 为保持真实感的必要开销；继续压缩会改变服务器可见的时间轴，属于风险决策）。

## Python

```python
from txdx import solve

result = solve(
    aid="192037696",
    entry_url="https://sssjz.guaishouyiyou.cn/#/pages/index",
    proxy=None,       # None 表示直连
    rounds=1,
)
print(result["ticket"], result["randstr"])
```

默认 `mode="protocol"`。显式浏览器回退：

```python
result = solve(aid="192037696", mode="browser", headless=True)
```

浏览器回退需要另行安装 `playwright` 和 Chromium；纯协议路径不需要。

## HTTP 服务

```bash
python -m txdx.server --host 0.0.0.0 --port 9000 --workers 1
```

```http
POST /solve
Content-Type: application/json

{
  "aid": "192037696",
  "entry_url": "https://sssjz.guaishouyiyou.cn/#/pages/index",
  "ip": null,
  "rounds": 1,
  "gap_seconds": 60
}
```

## 协议约束

- `tkid` 在 prehandle 前生成，并在 prehandle、图片 URL、verify 三处复用。
- `window.TDC.getInfo().tokenid` 不是页面 `tkid`，仅作兼容回退。
- verify `ans` 与 TDC 行为事件必须来自同一个显示点击点。
- ClickEl mark 原生尺寸为 32；330px 背景中的显示尺寸为 29.333px。
- 当前轨迹为 32 个事件、20 个 `mousemove`，并使用 Chrome 风格整数 offset。
- 每个新 `sess` 只允许一次 verify。失败后不可复用同一会话扫坐标。
- supplied proxy 会原样用于腾讯、图片、TDC、verify 和红尘识别；`None` 为直连。
- 服务端错误码不是公开契约，不能把 `12`、`50`、`9` 固定解释成单一原因。

## 许可证与来源

本仓库包含基于 `hailan09/crackTCaptcha` 修改的 jsdom/TDC 执行代码，按
GPL-3.0-or-later 分发。具体来源和上游版本见 `NOTICE`，完整条款见 `LICENSE`。

## 目录

```text
txdx/
├── __init__.py          默认入口及显式 browser dispatch
├── protocol_solver.py   纯协议编排及 ClickEl 坐标公式
├── protocol.py          prehandle / image / TDC / PoW / verify
├── collect_gen.py       本地同轮 TDC 驱动
├── hongchen.py          默认识别 Provider
├── provider.py          可替换识别器接口
├── tdc_js/              jsdom 环境与点选事件驱动
├── get_ticket.py        旧浏览器回退
└── server.py            FastAPI 服务
```
