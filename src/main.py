#!/usr/bin/env python3
"""
Crypto Analyzer — OKX 加密货币技术分析工具

用法:
  python -m src.main                              # 默认 BTC-USDT 4H
  python -m src.main ETH-USDT 1H                  # 指定交易对和周期
  python -m src.main --pairs BTC,ETH,SOL           # 多币种分析
  python -m src.main --watch 300                   # 每5分钟自动刷新
  python -m src.main --alert 70000 65000           # 价格警报
  python -m src.main --output json                 # JSON 输出
  python -m src.main --notify                      # 发送微信通知

交易记录:
  python -m src.main trade open --pair BTC-USDT --dir long --price 85000 --size 0.1 --reason "金叉"
  python -m src.main trade close --id T20260310-001 --price 87500 --reason "触及阻力"
  python -m src.main trade list [--status open|closed] [--last 20]
  python -m src.main trade stats [--days 30]

AI 反思:
  python -m src.main reflect [--days 30]
"""

import sys
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from src.config import load_config
from src.fetcher import fetch_candles
from src.analyzer import analyze
from src.reporter import print_terminal_report, format_wechat_report
from src.notifier import send_notification


PROJECT_ROOT = Path(__file__).parent.parent


def save_analysis(result: dict):
    """保存分析快照"""
    hist_dir = PROJECT_ROOT / "data" / "analysis_history"
    hist_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
    filename = f"{ts}_{result['inst_id']}_{result['bar']}.json"
    with open(hist_dir / filename, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return str(hist_dir / filename)


def save_latest_for_pages(results: list[dict]):
    """保存最新结果到 docs/data/ 供 GitHub Pages 使用"""
    docs_dir = PROJECT_ROOT / "docs" / "data"
    docs_dir.mkdir(parents=True, exist_ok=True)
    with open(docs_dir / "latest.json", "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "analyses": results,
        }, f, ensure_ascii=False, indent=2)


def cmd_analyze(args: list[str], cfg: dict):
    """分析命令"""
    base_url = cfg["okx"]["base_url"]
    valid_bars = cfg["okx"]["valid_bars"]

    # 解析参数
    pairs = []
    bar = cfg["okx"]["default_timeframe"]
    watch_interval = 0
    alert_above = alert_below = None
    output_json = False
    do_notify = False

    i = 0
    positional = []
    while i < len(args):
        if args[i] == "--watch" and i + 1 < len(args):
            watch_interval = int(args[i + 1])
            i += 2
        elif args[i] == "--alert" and i + 2 < len(args):
            alert_above = float(args[i + 1])
            alert_below = float(args[i + 2])
            i += 3
        elif args[i] == "--pairs" and i + 1 < len(args):
            for p in args[i + 1].split(","):
                p = p.strip().upper()
                if "-" not in p:
                    p += "-USDT"
                pairs.append(p)
            i += 2
        elif args[i] == "--output" and i + 1 < len(args):
            if args[i + 1] == "json":
                output_json = True
            i += 2
        elif args[i] == "--notify":
            do_notify = True
            i += 1
        else:
            positional.append(args[i])
            i += 1

    if not pairs:
        if positional:
            inst_id = positional[0].upper()
            if "-" not in inst_id:
                inst_id += "-USDT"
            pairs = [inst_id]
        else:
            pairs = [cfg["okx"]["default_pairs"][0]]

    if len(positional) >= 2:
        bar = positional[1]

    if bar not in valid_bars:
        print(f"无效周期 '{bar}'，可选: {', '.join(valid_bars)}")
        return

    try:
        while True:
            all_results = []
            for pair in pairs:
                candles = fetch_candles(base_url, pair, bar)
                result = analyze(candles, pair, bar)
                all_results.append(result)

                if output_json:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                else:
                    print_terminal_report(result)

                # 保存快照
                save_analysis(result)

                # 价格警报
                if alert_above or alert_below:
                    price = result["price"]
                    if alert_above and price >= alert_above:
                        msg = f"🚨 {pair} 突破 ${alert_above:,.0f}！当前 ${price:,.1f}"
                        print(f"\n{'!' * 60}\n{msg}\n{'!' * 60}")
                        send_notification(msg, msg, cfg)
                    if alert_below and price <= alert_below:
                        msg = f"🚨 {pair} 跌破 ${alert_below:,.0f}！当前 ${price:,.1f}"
                        print(f"\n{'!' * 60}\n{msg}\n{'!' * 60}")
                        send_notification(msg, msg, cfg)

                # 微信推送
                if do_notify:
                    title, body = format_wechat_report(result)
                    send_notification(title, body, cfg)

            # 保存到 Pages
            save_latest_for_pages(all_results)

            if watch_interval <= 0:
                break

            print(f"\n⏰ {watch_interval} 秒后刷新... (Ctrl+C 退出)")
            time.sleep(watch_interval)

    except KeyboardInterrupt:
        print("\n👋 已退出")


def cmd_trade(args: list[str]):
    """交易记录命令"""
    from src.trade_journal import (
        open_trade, close_trade, add_reflection,
        list_trades, print_trades, print_stats,
    )

    if not args:
        print("用法: python -m src.main trade [open|close|list|stats|reflect]")
        return

    subcmd = args[0]
    rest = args[1:]

    if subcmd == "open":
        # 解析参数
        params = _parse_kv_args(rest)
        trade = open_trade(
            pair=params.get("--pair", "BTC-USDT"),
            direction=params.get("--dir", "long"),
            price=float(params.get("--price", 0)),
            size=float(params.get("--size", 0)),
            reason=params.get("--reason", ""),
            timeframe=params.get("--tf", "4H"),
            tags=params.get("--tags", "").split(",") if params.get("--tags") else [],
        )
        print(f"\n✅ 开单成功: {trade['id']}")
        print(f"   {trade['pair']} {trade['direction']} @ ${trade['entry_price']:,.1f} x{trade['size']}")
        print(f"   理由: {trade['reason_entry']}")

    elif subcmd == "close":
        params = _parse_kv_args(rest)
        trade = close_trade(
            trade_id=params.get("--id", ""),
            price=float(params.get("--price", 0)),
            reason=params.get("--reason", ""),
        )
        pnl_icon = "🟢" if trade["pnl"] >= 0 else "🔴"
        print(f"\n{pnl_icon} 平仓成功: {trade['id']}")
        print(f"   {trade['pair']} {trade['direction']} @ ${trade['exit_price']:,.1f}")
        print(f"   盈亏: ${trade['pnl']:,.2f} ({trade['pnl_pct']:+.2f}%)")

    elif subcmd == "list":
        params = _parse_kv_args(rest)
        status = params.get("--status", "all")
        last = int(params.get("--last", 0))
        trades = list_trades(status=status, last=last)
        print_trades(trades)

    elif subcmd == "stats":
        params = _parse_kv_args(rest)
        days = int(params.get("--days", 30))
        print_stats(days)

    elif subcmd == "reflect":
        params = _parse_kv_args(rest)
        trade_id = params.get("--id", "")
        if trade_id:
            reflection = params.get("--text", "")
            grade = params.get("--grade")
            t = add_reflection(trade_id, reflection, grade)
            print(f"\n✅ 反思已记录: {t['id']}")
        else:
            print("用法: python -m src.main trade reflect --id T001 --text '反思内容' [--grade A]")

    else:
        print(f"未知子命令: {subcmd}")


def cmd_reflect(args: list[str], cfg: dict):
    """AI 反思命令"""
    from src.trade_journal import list_trades
    from src.ai_reflection import generate_reflection, print_reflection

    api_key = cfg.get("ai_reflection", {}).get("api_key", "")
    if not api_key:
        print("\n❌ 需要配置 ANTHROPIC_API_KEY 环境变量")
        return

    params = _parse_kv_args(args)
    days = int(params.get("--days", 30))

    trades = list_trades(status="all")
    if not trades:
        print("\n暂无交易记录")
        return

    print(f"\n🤖 正在调用 AI 分析 {len(trades)} 笔交易记录...")
    content = generate_reflection(trades, api_key, f"{days}d")
    print_reflection(content)

    # 推送
    notify_cfg = cfg.get("notify", {})
    if notify_cfg.get("wechat", {}).get("enabled"):
        from src.notifier import send_notification
        send_notification("交易反思周报", content, cfg)


def _parse_kv_args(args: list[str]) -> dict:
    """解析 --key value 参数"""
    result = {}
    i = 0
    while i < len(args):
        if args[i].startswith("--") and i + 1 < len(args) and not args[i + 1].startswith("--"):
            result[args[i]] = args[i + 1]
            i += 2
        else:
            i += 1
    return result


def main():
    args = sys.argv[1:]

    if not args or args[0] in ("--help", "-h"):
        print(__doc__)
        return

    cfg = load_config()

    if args[0] == "trade":
        cmd_trade(args[1:])
    elif args[0] == "reflect":
        cmd_reflect(args[1:], cfg)
    else:
        cmd_analyze(args, cfg)


if __name__ == "__main__":
    main()
