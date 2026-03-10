"""AI 反思模块 — 调用 Claude API 分析交易记录"""
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen, Request

REFLECTIONS_DIR = Path(__file__).parent.parent / "data" / "reflections"


def generate_reflection(trades: list[dict], api_key: str, period: str = "7d") -> str:
    """调用 Claude API 生成交易反思报告"""
    if not trades:
        return "暂无交易记录可供分析。"

    closed = [t for t in trades if t["exit_time"] is not None]
    open_trades = [t for t in trades if t["exit_time"] is None]

    prompt = f"""你是一位专业的加密货币交易教练。请分析以下交易记录，给出详细的反思和改进建议。

## 已平仓交易 ({len(closed)} 笔)
{json.dumps(closed, ensure_ascii=False, indent=2)}

## 当前持仓 ({len(open_trades)} 笔)
{json.dumps(open_trades, ensure_ascii=False, indent=2)}

请从以下维度分析：

### 1. 绩效统计
- 胜率、盈亏比、总盈亏
- 最大单笔盈利/亏损

### 2. 策略有效性
- 哪些入场信号组合的胜率最高？
- 哪些信号经常导致亏损？
- 止盈/止损设置是否合理？

### 3. 行为模式
- 是否存在过度交易？
- 是否有追涨杀跌倾向？
- 持仓时间是否合理？

### 4. 改进建议
- 具体的、可执行的改进措施
- 下一阶段应重点关注什么

### 5. 本期关键教训
- 用一句话总结最重要的经验

请用中文回答，务必基于数据分析，避免泛泛而谈。"""

    # 调用 Claude API
    url = "https://api.anthropic.com/v1/messages"
    payload = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    req = Request(url, data=payload, headers={
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    })

    try:
        with urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            content = result["content"][0]["text"]
    except Exception as e:
        return f"AI 反思生成失败: {e}"

    # 保存反思
    REFLECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    week = now.strftime("%Y-W%V")
    filepath = REFLECTIONS_DIR / f"weekly_{week}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# 交易反思周报 {week}\n\n")
        f.write(f"生成时间: {now.isoformat()}\n\n")
        f.write(content)

    return content


def print_reflection(content: str):
    """打印反思报告"""
    print("\n" + "=" * 64)
    print("  AI 交易反思报告")
    print("=" * 64)
    print(content)
    print("=" * 64)
