# 腾讯文字点选验证码 自动出票模块（浏览器方式）

**实测**：点选 2404（AppId 192037696）headless + 代理连续出票 ✅；滑块 2401 同样支持 ✅。

## 特点

- **真实浏览器**（Chrome/Chromium + playwright）加载官方 captcha，tgJCap 真实执行 → collect/eks/pow 全自动
- **支持 Linux 无头**：`--headless`（实测出票）+ 中文字体自动探测
- **支持传 IP**：`--proxy http://user:pass@ip:port`（腾讯请求 + 红尘打码 API 全走代理）
- **打码默认红尘**：点选字符顺序 + 框定位（order API）；可自定义
- **类人轨迹**：真实样本统计的点击/拖动轨迹

## 安装

```bash
pip install playwright requests pillow
playwright install chromium            # 或 apt install chromium
apt install fonts-noto-cjk             # Linux 中文字体（点选指令渲染必需）
```

## 用法

### 命令行（复用 get_ticket.py）

```bash
# 点选（无头 + 代理）
python get_ticket.py --aid 192037696 --headless --proxy http://ip:port

# 滑块
python get_ticket.py --aid 192294958 --headless --proxy http://ip:port

# 本机有头调试
python get_ticket.py --aid 192037696

# 多实例并发（不同 --port）
python get_ticket.py --aid 192037696 --headless --port 8081
```

### Python 调用

```python
from txdx import solve

r = solve(aid="192037696", proxy="http://ip:port", headless=True)
print(r["ticket"], r["randstr"])
```

### 并发

- 每个验证一个浏览器实例，互不干扰
- **多实例必须不同 `--port`**（本地 loader 端口）
- 腾讯风控：同一 IP 高频会收窄容差 → **每 IP 限速 + IP 池轮换**

## 环境变量

| 变量 | 说明 |
|---|---|
| `HONGCHEN_TOKEN` | 红尘打码 token（必填） |
| `CHROME_PATH` | 自定义 Chrome/Chromium 路径（默认自动探测） |

## 架构

```
txdx/
├── __init__.py     solve(aid, proxy, headless, ...) 主入口
├── get_ticket.py   浏览器出票核心（loader/prehandle/识别/点击/回调）
└── tests/          测试用例
```

流程：
```
本地 loader（host-resolver 白名单→127.0.0.1）
→ 浏览器加载 tgJCap → 截获 prehandle 协议 → 解析题目
→ 下载图 → 红尘识别（点选 order / 滑块 match）
→ 类人点击/拖动 → tgJCap 生成 collect/eks/pow 提交 → 回调 ticket
```

## 并发注意（txdx 浏览器方式）

- playwright sync API **线程不安全** → 多并发用**多进程**（multiprocessing / 每 worker 一个端口）
- 每实例必须独立 `--port`（loader 端口），`__init__.py` 的 solve() 自动分配
- 示例（4 进程并发）：
  ```python
  from multiprocessing import Pool
  def f(p): return solve(aid="192037696", proxy=p, headless=True)
  with Pool(4) as pool:
      print(pool.map(f, ["http://ip1:port", "http://ip2:port", ...]))
  ```
- 腾讯风控：同 IP 高频会收窄容差 → **每 IP 限速 + IP 池轮换**
