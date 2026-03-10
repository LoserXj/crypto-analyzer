"""综合分析引擎"""
from src.fetcher import Candle
from src.indicators import calc_ema, calc_rsi, calc_atr
from src.patterns import (
    find_swing_points, detect_channel, find_support_resistance,
    detect_breakouts, find_liquidity_pools, detect_rsi_divergence,
    detect_candlestick_patterns, detect_fvg,
)


def analyze(candles: list[Candle], inst_id: str, bar: str) -> dict:
    """执行完整技术分析，返回结构化结果"""
    cur = candles[-1]
    price = cur.close
    closes = [c.close for c in candles]

    # 指标
    ema20 = calc_ema(closes, 20)
    ema50 = calc_ema(closes, 50)
    ema200 = calc_ema(closes, 200) if len(closes) >= 200 else None
    rsi_values = calc_rsi(closes)
    rsi = rsi_values[-1] if rsi_values else 50.0
    atr_values = calc_atr(candles)
    atr = atr_values[-1] if atr_values else 0.0

    # 形态
    channel_type, slope_h, slope_l = detect_channel(candles)
    swing_highs, swing_lows = find_swing_points(candles)
    supports, resistances = find_support_resistance(candles, price)
    breakouts = detect_breakouts(candles, swing_highs, swing_lows)
    liq_tolerance = price * 0.001
    pool_highs, pool_lows = find_liquidity_pools(swing_highs, swing_lows, liq_tolerance)
    divergence = detect_rsi_divergence(closes, rsi_values)
    patterns = detect_candlestick_patterns(candles)
    fvgs = detect_fvg(candles)

    # 成交量
    vols = [c.vol for c in candles[-20:]]
    avg_vol = sum(vols) / len(vols) if vols else 1
    last_vol = candles[-1].vol
    vol_ratio = last_vol / avg_vol * 100 if avg_vol > 0 else 0

    # 综合评分
    change = (cur.close - cur.open) / cur.open * 100
    bull = bear = 0
    if price > ema20[-1]: bull += 1
    else: bear += 1
    if price > ema50[-1]: bull += 1
    else: bear += 1
    if ema20[-1] > ema50[-1]: bull += 1
    else: bear += 1
    if rsi > 50: bull += 1
    else: bear += 1
    if channel_type == "ascending": bull += 1
    elif channel_type == "descending": bear += 1
    if vol_ratio > 120 and change > 0: bull += 1
    elif vol_ratio > 120 and change < 0: bear += 1

    if bull > bear + 1:
        verdict = "偏多"
    elif bear > bull + 1:
        verdict = "偏空"
    else:
        verdict = "多空交织"

    return {
        "inst_id": inst_id,
        "bar": bar,
        "timestamp": cur.ts.isoformat(),
        "price": price,
        "change_pct": round(change, 2),
        "candle": cur.to_dict(),
        "ema20": round(ema20[-1], 1),
        "ema50": round(ema50[-1], 1),
        "ema200": round(ema200[-1], 1) if ema200 else None,
        "ema_cross": "golden" if (ema20[-1] > ema50[-1] and ema20[-2] <= ema50[-2]) else
                     "death" if (ema20[-1] < ema50[-1] and ema20[-2] >= ema50[-2]) else
                     "bull_align" if ema20[-1] > ema50[-1] else "bear_align",
        "rsi": round(rsi, 1),
        "rsi_label": "超买" if rsi > 70 else "超卖" if rsi < 30 else "偏强" if rsi > 60 else "偏弱" if rsi < 40 else "中性",
        "rsi_divergence": divergence,
        "atr": round(atr, 1),
        "atr_pct": round(atr / price * 100, 2) if price > 0 else 0,
        "channel": channel_type,
        "slope_high": round(slope_h, 1),
        "slope_low": round(slope_l, 1),
        "swing_highs": [(v, t.isoformat()) for _, v, t in swing_highs[-4:]],
        "swing_lows": [(v, t.isoformat()) for _, v, t in swing_lows[-4:]],
        "supports": [{"price": round(p, 1), "count": n} for p, n in supports],
        "resistances": [{"price": round(p, 1), "count": n} for p, n in resistances],
        "breakouts": [{"type": b, "time": t.isoformat(), "level": lv, "close": cl} for b, t, lv, cl in breakouts],
        "liquidity_highs": pool_highs,
        "liquidity_lows": pool_lows,
        "patterns": [{"type": p, "time": t.isoformat(), "close": cl} for p, t, cl in patterns],
        "fvgs": [{"type": f, "time": t.isoformat(), "low": lo, "high": hi} for f, t, lo, hi in fvgs[-3:]],
        "vol_ratio": round(vol_ratio, 0),
        "bull_signals": bull,
        "bear_signals": bear,
        "verdict": verdict,
    }
