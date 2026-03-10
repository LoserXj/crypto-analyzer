"""交易日志记录"""
import json
from datetime import datetime, timezone
from pathlib import Path

TRADES_FILE = Path(__file__).parent.parent / "data" / "trades.json"


def _load_trades() -> list[dict]:
    if TRADES_FILE.exists():
        with open(TRADES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_trades(trades: list[dict]):
    TRADES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TRADES_FILE, "w", encoding="utf-8") as f:
        json.dump(trades, f, ensure_ascii=False, indent=2)


def _next_id(trades: list[dict]) -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    today_trades = [t for t in trades if t["id"].startswith(f"T{today}")]
    seq = len(today_trades) + 1
    return f"T{today}-{seq:03d}"


def open_trade(pair: str, direction: str, price: float, size: float,
               reason: str, timeframe: str = "4H", tags: list[str] = None,
               analysis_snapshot: str = None) -> dict:
    """记录开单"""
    trades = _load_trades()
    trade = {
        "id": _next_id(trades),
        "pair": pair,
        "direction": direction,
        "entry_time": datetime.now(timezone.utc).isoformat(),
        "entry_price": price,
        "exit_time": None,
        "exit_price": None,
        "size": size,
        "pnl": None,
        "pnl_pct": None,
        "reason_entry": reason,
        "reason_exit": None,
        "timeframe": timeframe,
        "tags": tags or [],
        "analysis_snapshot": analysis_snapshot,
        "reflection": "",
        "grade": None,
    }
    trades.append(trade)
    _save_trades(trades)
    return trade


def close_trade(trade_id: str, price: float, reason: str) -> dict:
    """记录平仓"""
    trades = _load_trades()
    for t in trades:
        if t["id"] == trade_id:
            t["exit_time"] = datetime.now(timezone.utc).isoformat()
            t["exit_price"] = price
            t["reason_exit"] = reason
            # 计算盈亏
            if t["direction"] == "long":
                t["pnl"] = round((price - t["entry_price"]) * t["size"], 2)
                t["pnl_pct"] = round((price - t["entry_price"]) / t["entry_price"] * 100, 2)
            else:
                t["pnl"] = round((t["entry_price"] - price) * t["size"], 2)
                t["pnl_pct"] = round((t["entry_price"] - price) / t["entry_price"] * 100, 2)
            _save_trades(trades)
            return t
    raise ValueError(f"交易 {trade_id} 不存在")


def add_reflection(trade_id: str, reflection: str, grade: str = None) -> dict:
    """添加交易反思"""
    trades = _load_trades()
    for t in trades:
        if t["id"] == trade_id:
            t["reflection"] = reflection
            if grade:
                t["grade"] = grade
            _save_trades(trades)
            return t
    raise ValueError(f"交易 {trade_id} 不存在")


def list_trades(status: str = "all", last: int = 0) -> list[dict]:
    """查询交易"""
    trades = _load_trades()
    if status == "open":
        trades = [t for t in trades if t["exit_time"] is None]
    elif status == "closed":
        trades = [t for t in trades if t["exit_time"] is not None]
    if last > 0:
        trades = trades[-last:]
    return trades


def get_stats(days: int = 30) -> dict:
    """统计"""
    trades = _load_trades()
    closed = [t for t in trades if t["exit_time"] is not None]

    if not closed:
        return {"total": 0, "message": "暂无已平仓交易"}

    # 按时间过滤
    if days > 0:
        cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
        closed = [t for t in closed
                  if datetime.fromisoformat(t["entry_time"]).timestamp() > cutoff]

    if not closed:
        return {"total": 0, "message": f"近{days}天无已平仓交易"}

    wins = [t for t in closed if t["pnl"] and t["pnl"] > 0]
    losses = [t for t in closed if t["pnl"] and t["pnl"] <= 0]
    total_pnl = sum(t["pnl"] for t in closed if t["pnl"])
    avg_win = sum(t["pnl"] for t in wins) / len(wins) if wins else 0
    avg_loss = abs(sum(t["pnl"] for t in losses) / len(losses)) if losses else 0

    return {
        "total": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(closed) * 100, 1),
        "total_pnl": round(total_pnl, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": round(avg_win / avg_loss, 2) if avg_loss > 0 else float("inf"),
        "best_trade": max(closed, key=lambda t: t["pnl"] or 0),
        "worst_trade": min(closed, key=lambda t: t["pnl"] or 0),
    }


def print_stats(days: int = 30):
    """打印统计"""
    s = get_stats(days)
    if s["total"] == 0:
        print(f"\n{s.get('message', '暂无数据')}")
        return

    print(f"\n{'=' * 50}")
    print(f"  交易统计 (近{days}天)")
    print(f"{'=' * 50}")
    print(f"  总交易: {s['total']}  |  胜: {s['wins']}  |  负: {s['losses']}")
    print(f"  胜率: {s['win_rate']}%")
    print(f"  总盈亏: ${s['total_pnl']:,.2f}")
    print(f"  平均盈利: ${s['avg_win']:,.2f}  |  平均亏损: ${s['avg_loss']:,.2f}")
    print(f"  盈亏比: {s['profit_factor']:.2f}")
    print(f"  最佳: {s['best_trade']['id']} ${s['best_trade']['pnl']:,.2f}")
    print(f"  最差: {s['worst_trade']['id']} ${s['worst_trade']['pnl']:,.2f}")
    print(f"{'=' * 50}")


def print_trades(trades: list[dict]):
    """打印交易列表"""
    if not trades:
        print("\n暂无交易记录")
        return

    print(f"\n{'ID':<16} {'币对':<12} {'方向':<6} {'入场价':>10} {'出场价':>10} {'盈亏':>10} {'状态':<6}")
    print("-" * 72)
    for t in trades:
        status = "持仓中" if t["exit_time"] is None else "已平仓"
        exit_p = f"${t['exit_price']:,.1f}" if t["exit_price"] else "-"
        pnl = f"${t['pnl']:,.2f}" if t["pnl"] is not None else "-"
        direction = "做多" if t["direction"] == "long" else "做空"
        print(f"{t['id']:<16} {t['pair']:<12} {direction:<6} ${t['entry_price']:>9,.1f} {exit_p:>10} {pnl:>10} {status:<6}")
