"""综合分析引擎"""
from src.fetcher import Candle
from src.indicators import calc_ema, calc_rsi, calc_atr
from src.patterns import (
    find_swing_points, detect_channel, find_support_resistance,
    detect_breakouts, find_liquidity_pools, detect_rsi_divergence,
    detect_candlestick_patterns, detect_fvg,
)


def _generate_strategy(direction: str, r: dict) -> dict:
    """根据方向生成具体操作建议"""
    price = r["price"]
    atr = r["atr"]
    supports = r["supports"]
    resistances = r["resistances"]

    if direction == "long":
        # 做多策略
        # 入场：回踩最近支撑位附近
        if supports:
            entry = supports[0]["price"]
        else:
            entry = round(price - atr * 0.5, 1)

        stop_loss = round(entry - atr * 1.5, 1)

        if resistances:
            take_profit_1 = resistances[0]["price"]
            take_profit_2 = resistances[1]["price"] if len(resistances) > 1 else round(entry + atr * 3, 1)
        else:
            take_profit_1 = round(entry + atr * 2, 1)
            take_profit_2 = round(entry + atr * 3, 1)

        risk = entry - stop_loss
        reward = take_profit_1 - entry
        rr_ratio = round(reward / risk, 2) if risk > 0 else 0

        # 理由汇总
        reasons_for = []
        reasons_against = []

        if r["channel"] == "ascending":
            reasons_for.append("上升通道，趋势向上")
        elif r["channel"] == "descending":
            reasons_against.append("下降通道，趋势向下")

        if r["ema_cross"] in ("golden", "bull_align"):
            reasons_for.append("均线多头排列")
        else:
            reasons_against.append("均线空头排列")

        if r["rsi"] < 30:
            reasons_for.append("RSI 超卖，可能反弹")
        elif r["rsi"] > 70:
            reasons_against.append("RSI 超买，上方动力不足")
        elif r["rsi"] < 50:
            reasons_against.append(f"RSI {r['rsi']:.0f} 偏弱")

        if r["rsi_divergence"] == "bullish":
            reasons_for.append("RSI 底背离")
        elif r["rsi_divergence"] == "bearish":
            reasons_against.append("RSI 顶背离")

        for p in r["patterns"]:
            if p["type"] in ("pin_bar_bull", "bullish_engulf"):
                reasons_for.append("看涨K线形态")
            elif p["type"] in ("pin_bar_bear", "bearish_engulf"):
                reasons_against.append("看跌K线形态")

        if r["vol_ratio"] > 120 and r["change_pct"] > 0:
            reasons_for.append("放量上涨")
        elif r["vol_ratio"] > 120 and r["change_pct"] < 0:
            reasons_against.append("放量下跌")

        return {
            "direction": "long",
            "label": "做多",
            "entry_zone": [round(entry, 1), round(entry + atr * 0.3, 1)],
            "stop_loss": stop_loss,
            "take_profit": [take_profit_1, take_profit_2],
            "risk_reward": rr_ratio,
            "reasons_for": reasons_for,
            "reasons_against": reasons_against,
            "confidence": len(reasons_for) - len(reasons_against),
        }

    else:
        # 做空策略
        if resistances:
            entry = resistances[0]["price"]
        else:
            entry = round(price + atr * 0.5, 1)

        stop_loss = round(entry + atr * 1.5, 1)

        if supports:
            take_profit_1 = supports[0]["price"]
            take_profit_2 = supports[1]["price"] if len(supports) > 1 else round(entry - atr * 3, 1)
        else:
            take_profit_1 = round(entry - atr * 2, 1)
            take_profit_2 = round(entry - atr * 3, 1)

        risk = stop_loss - entry
        reward = entry - take_profit_1
        rr_ratio = round(reward / risk, 2) if risk > 0 else 0

        reasons_for = []
        reasons_against = []

        if r["channel"] == "descending":
            reasons_for.append("下降通道，趋势向下")
        elif r["channel"] == "ascending":
            reasons_against.append("上升通道，趋势向上")

        if r["ema_cross"] in ("death", "bear_align"):
            reasons_for.append("均线空头排列")
        else:
            reasons_against.append("均线多头排列")

        if r["rsi"] > 70:
            reasons_for.append("RSI 超买，可能回落")
        elif r["rsi"] < 30:
            reasons_against.append("RSI 超卖，下方动力不足")
        elif r["rsi"] > 50:
            reasons_against.append(f"RSI {r['rsi']:.0f} 偏强")

        if r["rsi_divergence"] == "bearish":
            reasons_for.append("RSI 顶背离")
        elif r["rsi_divergence"] == "bullish":
            reasons_against.append("RSI 底背离")

        for p in r["patterns"]:
            if p["type"] in ("pin_bar_bear", "bearish_engulf"):
                reasons_for.append("看跌K线形态")
            elif p["type"] in ("pin_bar_bull", "bullish_engulf"):
                reasons_against.append("看涨K线形态")

        if r["vol_ratio"] > 120 and r["change_pct"] < 0:
            reasons_for.append("放量下跌")
        elif r["vol_ratio"] > 120 and r["change_pct"] > 0:
            reasons_against.append("放量上涨")

        return {
            "direction": "short",
            "label": "做空",
            "entry_zone": [round(entry - atr * 0.3, 1), round(entry, 1)],
            "stop_loss": stop_loss,
            "take_profit": [take_profit_1, take_profit_2],
            "risk_reward": rr_ratio,
            "reasons_for": reasons_for,
            "reasons_against": reasons_against,
            "confidence": len(reasons_for) - len(reasons_against),
        }


def analyze(candles: list[Candle], inst_id: str, bar: str, bias: str = None) -> dict:
    """执行完整技术分析，返回结构化结果

    bias: "bull" | "bear" | None
        设定主观偏好方向，会生成对应方向的操作建议。
        无论 bias 如何，始终同时输出多空双向策略供参考。
    """
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

    result = {
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
        "bias": bias,
    }

    # 始终生成双向策略
    result["strategy_long"] = _generate_strategy("long", result)
    result["strategy_short"] = _generate_strategy("short", result)

    # 根据 bias 标记主策略
    if bias == "bear":
        result["primary_strategy"] = "short"
    elif bias == "bull":
        result["primary_strategy"] = "long"
    else:
        result["primary_strategy"] = "long" if bull >= bear else "short"

    return result
