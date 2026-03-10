# Crypto Analyzer — 开发文档 v1.0

## 一、项目现状

### 1.1 当前架构

```
crypto-analyzer/
└── analyze.py          # 单文件，597行，纯 Python 标准库，零依赖
```

**核心能力**：从 OKX 公开 API 拉取 K 线数据，计算 13+ 技术指标，输出中文分析报告。

| 模块 | 功能 | 行数 |
|------|------|------|
| 数据获取 | OKX REST API → Candle 数据 | 30-64 |
| 技术指标 | EMA(20/50/200)、RSI(14)、ATR(14)、线性回归 | 71-127 |
| 形态检测 | 摆动点、支撑阻力、趋势通道、真假突破、流动性池、FVG、K线形态、RSI背离 | 133-327 |
| 报告输出 | 终端彩色报告 + 综合多空评分 | 334-501 |
| 告警系统 | macOS osascript 通知 | 508-531 |
| CLI 入口 | 参数解析、watch 循环 | 538-597 |

### 1.2 当前限制

- **单文件，不可扩展** — 所有逻辑耦合在一起
- **无数据持久化** — 每次运行即丢失，无法回溯
- **仅 macOS 通知** — 不支持微信/Telegram 等
- **无交易记录** — 不记录开单、平仓、盈亏
- **无 Web 界面** — 纯命令行
- **无自动化部署** — 手动运行

---

## 二、目标架构设计

### 2.1 升级后的项目结构

```
crypto-analyzer/
├── README.md
├── requirements.txt
├── config.yaml                    # 统一配置文件
├── .env                           # 敏感信息 (API Key, 微信 Token)
├── .github/
│   └── workflows/
│       ├── analyze.yml            # GitHub Actions 定时分析
│       └── deploy-pages.yml       # GitHub Pages 部署
│
├── src/
│   ├── __init__.py
│   ├── main.py                    # 入口：CLI + 调度
│   ├── config.py                  # 配置管理 (yaml + env)
│   ├── fetcher.py                 # OKX 数据获取
│   ├── indicators.py              # 技术指标 (EMA/RSI/ATR)
│   ├── patterns.py                # 形态检测 (突破/FVG/吞没/通道)
│   ├── analyzer.py                # 综合分析引擎
│   ├── reporter.py                # 报告生成 (终端 + JSON + HTML)
│   ├── notifier.py                # 通知系统 (macOS/微信/Server酱)
│   ├── trade_journal.py           # 交易日志记录
│   └── ai_reflection.py           # AI 反思模块 (调用 Claude)
│
├── data/
│   ├── trades.json                # 交易记录数据库
│   ├── analysis_history/          # 历史分析快照
│   │   └── 2026-03-10_BTC-USDT_4H.json
│   └── reflections/               # AI 反思记录
│       └── weekly_2026-W10.md
│
├── web/                           # GitHub Pages 前端
│   ├── index.html                 # 仪表盘主页
│   ├── trades.html                # 交易记录页
│   ├── style.css
│   └── js/
│       ├── app.js                 # 主逻辑
│       ├── chart.js               # 图表渲染
│       └── trades.js              # 交易记录展示
│
├── docs/                          # GitHub Pages 发布目录
│   ├── index.html
│   ├── data/                      # 自动生成的 JSON 数据
│   │   ├── latest.json            # 最新分析结果
│   │   ├── history.json           # 历史数据索引
│   │   └── trades.json            # 交易记录 (脱敏)
│   └── assets/
│
└── tests/
    ├── test_indicators.py
    ├── test_patterns.py
    └── test_analyzer.py
```

### 2.2 模块职责详解

#### `src/config.py` — 配置中心

```python
# config.yaml 示例
okx:
  base_url: "https://www.okx.com/api/v5/market"
  default_pairs: ["BTC-USDT", "ETH-USDT", "SOL-USDT"]
  default_timeframe: "4H"

watch:
  interval: 300          # 秒
  pairs: ["BTC-USDT"]

notify:
  wechat:
    enabled: true
    method: "serverchan"  # serverchan | pushplus | wxpusher
    token: "${WECHAT_TOKEN}"
  macos: true

journal:
  enabled: true
  file: "data/trades.json"

ai_reflection:
  enabled: true
  model: "claude-sonnet-4-6"
  schedule: "weekly"       # daily | weekly
```

#### `src/notifier.py` — 通知系统

支持多渠道推送：

| 渠道 | 方案 | 说明 |
|------|------|------|
| macOS | osascript | 现有功能，仅本地 |
| 微信 (Server酱) | sct.ftqq.com | 免费，单向推送，简单 |
| 微信 (PushPlus) | pushplus.plus | 免费，支持模板消息 |
| 微信 (WxPusher) | wxpusher.zjiecode.com | 免费，支持多用户 |
| Telegram | Bot API | 备用方案 |

#### `src/trade_journal.py` — 交易日志

```python
# 交易记录数据结构
{
  "id": "T20260310-001",
  "pair": "BTC-USDT",
  "direction": "long",           # long | short
  "entry_time": "2026-03-10T14:00:00Z",
  "entry_price": 85000.0,
  "exit_time": "2026-03-11T02:00:00Z",  # null 表示持仓中
  "exit_price": 87500.0,
  "size": 0.1,                   # BTC 数量
  "pnl": 250.0,                  # 盈亏 (USDT)
  "pnl_pct": 2.94,               # 盈亏百分比
  "reason_entry": "EMA20金叉EMA50 + RSI底背离 + 看涨吞没",
  "reason_exit": "触及阻力位88000",
  "timeframe": "4H",
  "tags": ["趋势跟踪", "金叉"],
  "analysis_snapshot": "data/analysis_history/2026-03-10_BTC-USDT_4H.json",
  "reflection": "",              # 事后反思
  "grade": null                  # 自评 A/B/C/D/F
}
```

#### `src/ai_reflection.py` — AI 反思系统

调用 Claude API，输入交易记录 + 分析快照，输出反思报告：

```python
# 反思维度
1. 胜率统计：近 N 笔交易的胜率、盈亏比
2. 模式识别：哪些信号组合胜率高？哪些经常失败？
3. 行为分析：是否存在过早止盈、死扛亏损、追涨杀跌？
4. 改进建议：基于数据的具体策略调整建议
5. 情绪偏差：从交易频率和时间分布推断情绪状态
```

---

## 三、持续运行策略

### 3.1 方案对比

| 方案 | 适用场景 | 成本 | 稳定性 |
|------|----------|------|--------|
| **GitHub Actions (推荐)** | 定时分析 + 推送 | 免费 (2000分钟/月) | 高 |
| 本地 cron/launchd | 本地运行，实时性高 | 0 | 取决于电脑开机 |
| 云服务器 | 24/7 高频监控 | ¥30-100/月 | 最高 |
| Vercel/Railway | Serverless | 免费额度内 | 中 |

### 3.2 GitHub Actions 定时运行 (推荐)

```yaml
# .github/workflows/analyze.yml
name: Crypto Analysis

on:
  schedule:
    # 每4小时运行一次 (UTC)
    - cron: '0 */4 * * *'
  workflow_dispatch:        # 支持手动触发

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run analysis
        env:
          WECHAT_TOKEN: ${{ secrets.WECHAT_TOKEN }}
        run: python -m src.main --pairs BTC-USDT,ETH-USDT --output json

      - name: Push results to docs/
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add docs/data/
          git diff --staged --quiet || git commit -m "chore: update analysis data"
          git push
```

**关键策略**：
- `schedule` cron 控制运行频率（免费额度：2000 分钟/月 ≈ 每 4 小时跑一次完全够用）
- 分析结果写入 `docs/data/*.json`，自动 commit & push
- GitHub Pages 读取 `docs/` 目录展示最新数据
- 通过 `secrets` 安全存储微信 Token

### 3.3 本地持续运行 (macOS launchd)

```xml
<!-- ~/Library/LaunchAgents/com.crypto.analyzer.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.crypto.analyzer</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/sustech_xujian/Desktop/crypto-analyzer/src/main.py</string>
        <string>--watch</string>
    </array>
    <key>StartInterval</key>
    <integer>900</integer>  <!-- 每15分钟 -->
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/crypto-analyzer.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/crypto-analyzer-err.log</string>
</dict>
</plist>
```

安装：`launchctl load ~/Library/LaunchAgents/com.crypto.analyzer.plist`

---

## 四、GitHub Pages 部署

### 4.1 架构

```
用户浏览器
    ↓
GitHub Pages (静态站点)
    ↓ 读取
docs/data/latest.json     ← GitHub Actions 定时生成
docs/data/trades.json     ← 交易记录 (手动或自动更新)
docs/data/history.json    ← 历史分析索引
```

**核心思路**：GitHub Pages 只能托管静态文件，所以后端逻辑全部通过 GitHub Actions 完成，结果以 JSON 文件形式存入 `docs/data/`，前端纯 JS 读取渲染。

### 4.2 前端功能规划

| 页面 | 功能 |
|------|------|
| 仪表盘 `index.html` | 最新分析结果、多空信号、关键价位、RSI/EMA 图表 |
| 交易记录 `trades.html` | 开单/平仓记录列表、盈亏统计、筛选 |
| 反思报告 `reflection.html` | AI 生成的周报/月报、策略改进建议 |
| 历史回顾 `history.html` | 过去 N 天分析结果趋势、信号准确率回测 |

### 4.3 技术选型

- **无框架纯静态**：HTML + CSS + Vanilla JS（零构建，GitHub Pages 直接部署）
- **图表库**：[Chart.js](https://www.chartjs.org/) 或 [Lightweight Charts](https://tradingview.github.io/lightweight-charts/)（轻量级 K 线图）
- **样式**：简洁暗色主题（交易界面风格）

### 4.4 部署配置

```yaml
# .github/workflows/deploy-pages.yml
name: Deploy Pages

on:
  push:
    paths: ['docs/**']

permissions:
  pages: write
  id-token: write

jobs:
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/configure-pages@v4
      - uses: actions/upload-pages-artifact@v3
        with:
          path: 'docs'
      - uses: actions/deploy-pages@v4
        id: deployment
```

仓库设置：Settings → Pages → Source: GitHub Actions

---

## 五、微信推送方案

### 5.1 Server酱 (推荐，最简单)

1. 访问 https://sct.ftqq.com/ ，微信扫码登录
2. 获取 `SendKey`
3. 发送消息：

```python
# src/notifier.py
import urllib.request
import urllib.parse

def send_wechat(title: str, content: str, token: str):
    """通过 Server酱 推送到微信"""
    url = f"https://sctapi.ftqq.com/{token}.send"
    data = urllib.parse.urlencode({
        "title": title,
        "desp": content,  # 支持 Markdown
    }).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read())
        return result.get("code") == 0
```

### 5.2 推送内容模板

```markdown
## BTC-USDT 4H 分析报告

**价格**: $85,234.5 (+1.32%)
**趋势**: 上升通道 📈
**RSI**: 62.3 (偏强)
**EMA**: 多头排列 (20>50>200)

### 信号
- 🔺 看涨吞没 @ $84,800
- 🔥 底背离！

### 关键价位
- 阻力: $86,500 $88,000 $90,000
- 支撑: $83,000 $81,500 $80,000

### 综合: 多头 5 | 空头 1 → **偏多**

---
⏰ 2026-03-10 14:00 UTC
```

### 5.3 触发推送的时机

| 事件 | 推送 |
|------|------|
| 定时分析完成 | 每次推送摘要（可配置频率） |
| 价格突破关键位 | 立即推送告警 |
| 信号变化 | 多空翻转时推送 |
| 交易记录更新 | 开单/平仓确认 |
| AI 反思完成 | 周报推送 |

---

## 六、交易记录与反思系统

### 6.1 交易记录流程

```
                        ┌─────────────────┐
  CLI / Web 录入 ──────→│  trade_journal   │
                        │  (trades.json)   │
                        └────────┬────────┘
                                 │
                     ┌───────────┼───────────┐
                     ↓           ↓           ↓
              统计汇总      与分析快照      AI 反思
            (胜率/盈亏比)     关联         (Claude API)
                     │           │           │
                     ↓           ↓           ↓
                  trades.html   回测验证   reflection.md
```

### 6.2 CLI 交易管理命令

```bash
# 记录开单
python -m src.main trade open --pair BTC-USDT --dir long \
  --price 85000 --size 0.1 --reason "金叉+底背离"

# 记录平仓
python -m src.main trade close --id T20260310-001 \
  --price 87500 --reason "触及阻力"

# 查看持仓
python -m src.main trade list --status open

# 查看历史
python -m src.main trade list --last 20

# 统计
python -m src.main trade stats --period 30d

# AI 反思
python -m src.main reflect --period 7d
```

### 6.3 AI 反思系统设计

```python
# src/ai_reflection.py

def generate_reflection(trades: list, analyses: list, period: str) -> str:
    """
    输入: 交易记录 + 对应时间的分析快照
    输出: 结构化反思报告
    """
    prompt = f"""
    你是一位专业的加密货币交易教练。分析以下交易记录和技术分析数据，
    给出详细的反思和改进建议。

    ## 交易记录 ({period})
    {json.dumps(trades, ensure_ascii=False, indent=2)}

    ## 分析快照
    {json.dumps(analyses, ensure_ascii=False, indent=2)}

    请从以下维度分析：

    ### 1. 绩效统计
    - 总交易次数、胜率、盈亏比
    - 最大盈利/最大亏损
    - 平均持仓时间

    ### 2. 策略有效性
    - 哪些入场信号组合的胜率最高？
    - 哪些信号经常导致亏损？
    - 止盈/止损设置是否合理？

    ### 3. 行为模式
    - 是否存在过度交易？
    - 是否有追涨杀跌倾向？
    - 是否对亏损单持有过久（死扛）？
    - 是否对盈利单过早平仓？

    ### 4. 改进建议
    - 具体的、可执行的改进措施
    - 下一阶段应重点关注什么

    ### 5. 本周关键教训
    - 用一句话总结最重要的经验
    """
    # 调用 Claude API
    return call_claude(prompt)
```

### 6.4 反思数据的持久化

```
data/reflections/
├── weekly_2026-W10.md        # 周报
├── weekly_2026-W11.md
├── monthly_2026-03.md        # 月报
└── trade_reviews/
    ├── T20260310-001.md      # 单笔交易复盘
    └── T20260312-003.md
```

---

## 七、开发路线图

### Phase 1: 基础重构 (1-2天)

- [ ] 拆分 `analyze.py` 为模块化结构 (`src/` 目录)
- [ ] 添加 `config.yaml` 配置系统
- [ ] 添加 `requirements.txt`
- [ ] 报告支持 JSON 输出格式
- [ ] 基础单元测试

### Phase 2: 交易日志 (1-2天)

- [ ] 实现 `trade_journal.py`（开单/平仓/查询/统计）
- [ ] 分析结果快照保存到 `data/analysis_history/`
- [ ] 交易记录与分析快照关联
- [ ] CLI 交易管理命令

### Phase 3: 微信推送 (半天)

- [ ] 实现 `notifier.py` (Server酱 / PushPlus)
- [ ] 分析报告 Markdown 模板
- [ ] 告警推送逻辑
- [ ] 在 GitHub Actions secrets 中配置 Token

### Phase 4: GitHub Actions + Pages (1天)

- [ ] 配置定时 Actions workflow
- [ ] 分析结果自动写入 `docs/data/`
- [ ] 搭建 GitHub Pages 前端（仪表盘 + 交易记录）
- [ ] 自动部署 workflow

### Phase 5: AI 反思 (1天)

- [ ] 实现 `ai_reflection.py`
- [ ] 交易数据聚合与 prompt 构建
- [ ] 定时（每周）生成反思报告
- [ ] 反思结果推送微信 + 展示在 Pages

### Phase 6: 增强 (持续迭代)

- [ ] 多交易对同时监控
- [ ] 信号准确率回测统计
- [ ] K 线图表在 Web 展示 (Lightweight Charts)
- [ ] 移动端适配
- [ ] 历史数据导出 CSV

---

## 八、关键技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 后端运行环境 | GitHub Actions | 免费、稳定、无需服务器 |
| 前端框架 | 无框架 (Vanilla JS) | 简单、零构建、GitHub Pages 友好 |
| 图表库 | Lightweight Charts | 专业 K 线图、轻量、TradingView 出品 |
| 微信推送 | Server酱 | 免费、最简集成、稳定 |
| 数据存储 | JSON 文件 | 零依赖、Git 版本控制、够用 |
| AI 反思 | Claude API | 最强推理能力、中文优秀 |
| 配置管理 | YAML + .env | 结构化 + 安全分离 |

---

## 九、环境变量与密钥

```bash
# .env (本地开发)
WECHAT_TOKEN=SCT1234567890abcdef    # Server酱 SendKey
ANTHROPIC_API_KEY=sk-ant-...        # Claude API Key (反思用)

# GitHub Secrets (线上)
# Settings → Secrets and variables → Actions
# - WECHAT_TOKEN
# - ANTHROPIC_API_KEY
```

---

## 十、快速开始（重构后）

```bash
# 安装
git clone https://github.com/YOUR_USER/crypto-analyzer.git
cd crypto-analyzer
pip install -r requirements.txt
cp .env.example .env  # 填写 Token

# 分析
python -m src.main                           # 默认 BTC-USDT 4H
python -m src.main --pairs BTC,ETH,SOL       # 多币种
python -m src.main --watch 300               # 持续监控
python -m src.main --output json             # JSON 输出

# 交易记录
python -m src.main trade open --pair BTC-USDT --dir long --price 85000
python -m src.main trade close --id T001 --price 87500
python -m src.main trade stats

# AI 反思
python -m src.main reflect --period 7d
```
