#!/usr/bin/env python3
"""
OKX 加密货币技术分析工具
用法:
  python3 analyze.py                     # 默认 BTC-USDT 4H
  python3 analyze.py ETH-USDT            # 指定交易对
  python3 analyze.py BTC-USDT 1H         # 指定时间周期
  python3 analyze.py BTC-USDT 4H --watch 300  # 每5分钟自动刷新
  python3 analyze.py BTC-USDT 4H --alert 70000 65000  # 价格突破报警
"""

import sys
import json
import time
import subprocess
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from dataclasses import dataclass

# ============================================================
# 配置
# ============================================================

OKX_BASE = "https://www.okx.com/api/v5/market"
DEFAULT_INST = "BTC-USDT"
DEFAULT_BAR = "4H"
VALID_BARS = ["1m", "5m", "15m", "30m", "1H", "2H", "4H", "6H", "12H", "1D", "1W"]


# ============================================================
# 数据获取
# ============================================================

@dataclass
class Candle:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    vol: float


def fetch_candles(inst_id: str, bar: str, limit: int = 100) -> list[Candle]:
    """从 OKX 拉取 K 线数据"""
    url = f"{OKX_BASE}/candles?instId={inst_id}&bar={bar}&limit={limit}"
    req = Request(url, headers={"User-Agent": "crypto-analyzer/1.0"})
    with urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())

    if data["code"] != "0":
        raise RuntimeError(f"OKX API error: {data['msg']}")

    candles = []
    for c in reversed(data["data"]):  # OKX 返回最新在前，反转为时间顺序
        candles.append(Candle(
            ts=datetime.fromtimestamp(int(c[0]) / 1000, tz=timezone.utc),
            open=float(c[1]),
            high=float(c[2]),
            low=float(c[3]),
            close=float(c[4]),
            vol=float(c[5]),
        ))
    return candles


# ============================================================
# 技术指标计算
# ============================================================

def calc_ema(closes: list[float], period: int) -> list[float]:
    k = 2 / (period + 1)
    result = [closes[0]]
    for i in range(1, len(closes)):
        result.append(closes[i] * k + result[-1] * (1 - k))
    return result


def calc_rsi(closes: list[float], period: int = 14) -> list[float]:
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0) for d in deltas]
    losses = [max(-d, 0) for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    rsi_values = []

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100 - 100 / (1 + rs))

    return rsi_values


def calc_atr(candles: list[Candle], period: int = 14) -> list[float]:
    """Average True Range"""
    trs = []
    for i in range(1, len(candles)):
        c = candles[i]
        prev_close = candles[i - 1].close
        tr = max(c.high - c.low, abs(c.high - prev_close), abs(c.low - prev_close))
        trs.append(tr)

    atr_values = [sum(trs[:period]) / period]
    for i in range(period, len(trs)):
        atr_values.append((atr_values[-1] * (period - 1) + trs[i]) / period)
    return atr_values


def linreg_slope(points: list[tuple[int, float]]) -> float:
    n = len(points)
    if n < 2:
        return 0.0
    sx = sum(p[0] for p in points)
    sy = sum(p[1] for p in points)
    sxy = sum(p[0] * p[1] for p in points)
    sxx = sum(p[0] ** 2 for p in points)
    denom = n * sxx - sx * sx
    if denom == 0:
        return 0.0
    return (n * sxy - sx * sy) / denom


# ============================================================
# 形态检测
# ============================================================

def find_swing_points(candles: list[Candle], lookback: int = 2):
    """找摆动高/低点"""
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    swing_highs = []
    swing_lows = []

    for i in range(lookback, len(candles) - lookback):
        is_high = all(highs[i] > highs[i - j] for j in range(1, lookback + 1)) and \
                  all(highs[i] > highs[i + j] for j in range(1, lookback + 1))
        is_low = all(lows[i] < lows[i - j] for j in range(1, lookback + 1)) and \
                 all(lows[i] < lows[i + j] for j in range(1, lookback + 1))
        if is_high:
            swing_highs.append((i, highs[i], candles[i].ts))
        if is_low:
            swing_lows.append((i, lows[i], candles[i].ts))

    return swing_highs, swing_lows


def detect_channel(candles: list[Candle], window: int = 20) -> str:
    """检测趋势通道"""
    recent = candles[-window:]
    slope_h = linreg_slope([(i, c.high) for i, c in enumerate(recent)])
    slope_l = linreg_slope([(i, c.low) for i, c in enumerate(recent)])

    threshold = 20
    if slope_h < -threshold and slope_l < -threshold:
        return "descending", slope_h, slope_l
    elif slope_h > threshold and slope_l > threshold:
        return "ascending", slope_h, slope_l
    elif slope_h < -threshold and slope_l > -threshold / 2:
        return "converging", slope_h, slope_l
    elif slope_h > threshold / 2 and slope_l < -threshold:
        return "expanding", slope_h, slope_l
    else:
        return "ranging", slope_h, slope_l


def find_support_resistance(candles: list[Candle], current_price: float, window: int = 50):
    """聚类找支撑阻力"""
    levels = []
    for c in candles[-window:]:
        levels.extend([c.high, c.low, c.open, c.close])
    levels.sort()

    # 动态容差：基于价格的 0.4%
    tolerance = current_price * 0.004

    clusters = []
    cluster_prices = [levels[0]]
    for p in levels[1:]:
        if p - cluster_prices[0] < tolerance:
            cluster_prices.append(p)
        else:
            if len(cluster_prices) >= 6:
                clusters.append((sum(cluster_prices) / len(cluster_prices), len(cluster_prices)))
            cluster_prices = [p]
    if len(cluster_prices) >= 6:
        clusters.append((sum(cluster_prices) / len(cluster_prices), len(cluster_prices)))

    resistances = sorted([c for c in clusters if c[0] > current_price * 1.002], key=lambda x: x[0])[:3]
    supports = sorted([c for c in clusters if c[0] < current_price * 0.998], key=lambda x: -x[0])[:3]

    return supports, resistances


def detect_breakouts(candles: list[Candle], swing_highs, swing_lows, window: int = 10):
    """检测真/假突破"""
    results = []
    for i in range(-window, 0):
        if abs(i) > len(candles):
            continue
        c = candles[i]
        for _, sh_val, _ in swing_highs[-8:]:
            if c.high > sh_val and c.close < sh_val:
                results.append(("fake_high", c.ts, sh_val, c.close))
                break
        for _, sl_val, _ in swing_lows[-8:]:
            if c.low < sl_val and c.close > sl_val:
                results.append(("fake_low", c.ts, sl_val, c.close))
                break

    for i in range(-5, 0):
        if abs(i) > len(candles):
            continue
        c = candles[i]
        for _, sh_val, _ in swing_highs[-5:]:
            if c.close > sh_val and c.open < sh_val:
                results.append(("break_high", c.ts, sh_val, c.close))
        for _, sl_val, _ in swing_lows[-5:]:
            if c.close < sl_val and c.open > sl_val:
                results.append(("break_low", c.ts, sl_val, c.close))

    return results


def find_liquidity_pools(swing_highs, swing_lows, tolerance: float = 80):
    """等高/等低点 = 流动性池"""
    eq_highs = []
    eq_lows = []

    for i in range(len(swing_highs)):
        for j in range(i + 1, len(swing_highs)):
            if abs(swing_highs[i][1] - swing_highs[j][1]) < tolerance:
                eq_highs.append((swing_highs[i][1] + swing_highs[j][1]) / 2)
    for i in range(len(swing_lows)):
        for j in range(i + 1, len(swing_lows)):
            if abs(swing_lows[i][1] - swing_lows[j][1]) < tolerance:
                eq_lows.append((swing_lows[i][1] + swing_lows[j][1]) / 2)

    return (
        sorted(set(round(h, -1) for h in eq_highs))[-3:] if eq_highs else [],
        sorted(set(round(l, -1) for l in eq_lows), reverse=True)[:3] if eq_lows else [],
    )


def detect_rsi_divergence(closes: list[float], rsi_values: list[float], window: int = 20):
    """RSI 背离检测"""
    if len(rsi_values) < window:
        return None

    offset = len(rsi_values) - window
    rsi_lows = []
    price_lows = []

    for i in range(2, window - 2):
        idx = offset + i
        if 0 < idx < len(rsi_values) - 1:
            if rsi_values[idx] < rsi_values[idx - 1] and rsi_values[idx] < rsi_values[idx + 1]:
                ci = len(closes) - window + i
                if 0 <= ci < len(closes):
                    rsi_lows.append((i, rsi_values[idx]))
                    price_lows.append((i, closes[ci]))

    if len(price_lows) >= 2:
        p1, p2 = price_lows[-2], price_lows[-1]
        r1, r2 = rsi_lows[-2], rsi_lows[-1]
        if p2[1] < p1[1] and r2[1] > r1[1]:
            return "bullish"  # 底背离
        elif p2[1] > p1[1] and r2[1] < r1[1]:
            return "bearish"  # 顶背离

    return None


def detect_candlestick_patterns(candles: list[Candle], window: int = 5):
    """K 线形态检测"""
    patterns = []
    for i in range(-window, 0):
        if abs(i) >= len(candles):
            continue
        c = candles[i]
        body = abs(c.close - c.open)
        total_range = c.high - c.low
        if total_range == 0:
            continue

        upper_wick = c.high - max(c.open, c.close)
        lower_wick = min(c.open, c.close) - c.low

        # Pin bar (长影线)
        if lower_wick > body * 2.5 and lower_wick > upper_wick * 2:
            patterns.append(("pin_bar_bull", c.ts, c.close))
        elif upper_wick > body * 2.5 and upper_wick > lower_wick * 2:
            patterns.append(("pin_bar_bear", c.ts, c.close))

        # 吞没
        if abs(i) < len(candles) - 1:
            prev = candles[i - 1]
            prev_body = prev.close - prev.open
            cur_body = c.close - c.open
            if prev_body < 0 and cur_body > 0 and cur_body > abs(prev_body) * 1.2:
                patterns.append(("bullish_engulf", c.ts, c.close))
            elif prev_body > 0 and cur_body < 0 and abs(cur_body) > prev_body * 1.2:
                patterns.append(("bearish_engulf", c.ts, c.close))

    return patterns


def detect_fvg(candles: list[Candle], window: int = 10):
    """FVG (Fair Value Gap / 公允价值缺口)"""
    gaps = []
    for i in range(max(-window, -len(candles) + 2), 0):
        c1 = candles[i - 2]
        c3 = candles[i]

        # Bullish FVG: c3.low > c1.high
        if c3.low > c1.high:
            gaps.append(("bull_fvg", c3.ts, c1.high, c3.low))
        # Bearish FVG: c3.high < c1.low
        elif c3.high < c1.low:
            gaps.append(("bear_fvg", c3.ts, c3.high, c1.low))

    return gaps


# ============================================================
# 报告输出
# ============================================================

def print_report(inst_id: str, bar: str, candles: list[Candle]):
    cur = candles[-1]
    price = cur.close
    closes = [c.close for c in candles]

    print()
    print("=" * 64)
    print(f"  {inst_id}  {bar}  技术分析报告")
    print(f"  数据时间: {cur.ts.strftime('%Y-%m-%d %H:%M')} UTC")
    print(f"  当前价格: ${price:,.1f}")
    print("=" * 64)

    # -- 最新蜡烛 --
    change = (cur.close - cur.open) / cur.open * 100
    icon = "🟢" if change >= 0 else "🔴"
    print(f"\n{icon} 最新 {bar} 蜡烛:")
    print(f"   O: ${cur.open:,.1f}  H: ${cur.high:,.1f}  L: ${cur.low:,.1f}  C: ${cur.close:,.1f}  ({change:+.2f}%)")

    # -- 趋势通道 --
    channel_type, slope_h, slope_l = detect_channel(candles)
    labels = {
        "descending": "⚠️  【下降通道】高点和低点持续走低",
        "ascending": "✅  【上升通道】高点和低点持续走高",
        "converging": "📐  【收敛三角/楔形】高点走低 + 低点走高",
        "expanding": "📊  【扩散形态】波动扩大",
        "ranging": "📊  【横盘震荡】无明显趋势",
    }
    print(f"\n📐 趋势通道 (近20根{bar}):")
    print(f"   高点斜率: {slope_h:+.1f} $/根  |  低点斜率: {slope_l:+.1f} $/根")
    print(f"   {labels[channel_type]}")

    # -- 关键价位 --
    swing_highs, swing_lows = find_swing_points(candles)
    print(f"\n🔑 关键摆动点:")
    print("   高点:", "  ".join(f"${v:,.0f}({t.strftime('%m-%d')})" for _, v, t in swing_highs[-4:]))
    print("   低点:", "  ".join(f"${v:,.0f}({t.strftime('%m-%d')})" for _, v, t in swing_lows[-4:]))

    # -- 支撑阻力 --
    supports, resistances = find_support_resistance(candles, price)
    print(f"\n🧱 支撑/阻力:")
    if resistances:
        print("   阻力:", "  ".join(f"${p:,.0f}(x{n})" for p, n in resistances))
    if supports:
        print("   支撑:", "  ".join(f"${p:,.0f}(x{n})" for p, n in supports))

    # -- 均线 --
    ema20 = calc_ema(closes, 20)
    ema50 = calc_ema(closes, 50)
    ema200 = calc_ema(closes, 200) if len(closes) >= 200 else None

    print(f"\n📉 均线:")
    print(f"   EMA20: ${ema20[-1]:,.1f} ({'上方' if price > ema20[-1] else '下方'})")
    print(f"   EMA50: ${ema50[-1]:,.1f} ({'上方' if price > ema50[-1] else '下方'})")
    if ema200:
        print(f"   EMA200: ${ema200[-1]:,.1f} ({'上方' if price > ema200[-1] else '下方'})")
    if ema20[-1] > ema50[-1] and ema20[-2] <= ema50[-2]:
        print("   🔥 EMA20 金叉 EMA50！")
    elif ema20[-1] < ema50[-1] and ema20[-2] >= ema50[-2]:
        print("   ☠️  EMA20 死叉 EMA50！")
    else:
        print(f"   {'📈 多头排列' if ema20[-1] > ema50[-1] else '📉 空头排列'}")

    # -- RSI --
    rsi_values = calc_rsi(closes)
    rsi = rsi_values[-1] if rsi_values else 50
    rsi_label = "超买 ⚠️" if rsi > 70 else "超卖 ⚠️" if rsi < 30 else "偏强" if rsi > 60 else "偏弱" if rsi < 40 else "中性"
    print(f"\n📊 RSI(14): {rsi:.1f} — {rsi_label}")

    div = detect_rsi_divergence(closes, rsi_values)
    if div == "bullish":
        print("   🔥 底背离！价格新低但 RSI 未新低 — 潜在反转")
    elif div == "bearish":
        print("   ⚠️  顶背离！价格新高但 RSI 未新高 — 潜在见顶")

    # -- ATR 波动率 --
    atr_values = calc_atr(candles)
    if atr_values:
        atr = atr_values[-1]
        atr_pct = atr / price * 100
        print(f"\n📏 ATR(14): ${atr:,.0f} ({atr_pct:.2f}%)")

    # -- K线形态 --
    patterns = detect_candlestick_patterns(candles)
    if patterns:
        labels = {
            "pin_bar_bull": "🔺 看涨Pin Bar",
            "pin_bar_bear": "🔻 看跌Pin Bar",
            "bullish_engulf": "🔺 看涨吞没",
            "bearish_engulf": "🔻 看跌吞没",
        }
        print(f"\n🕯️  K线形态 (近5根):")
        for ptype, ts, close in patterns:
            print(f"   {labels[ptype]}  {ts.strftime('%m-%d %H:%M')}  收于 ${close:,.0f}")

    # -- FVG --
    fvgs = detect_fvg(candles)
    if fvgs:
        print(f"\n📦 FVG (公允价值缺口):")
        for ftype, ts, low, high in fvgs[-3:]:
            label = "看涨" if ftype == "bull_fvg" else "看跌"
            print(f"   {label} FVG: ${low:,.0f}-${high:,.0f}  ({ts.strftime('%m-%d %H:%M')})")

    # -- 突破检测 --
    breakouts = detect_breakouts(candles, swing_highs, swing_lows)
    if breakouts:
        labels = {
            "fake_high": "🔻 假突破(扫高点)",
            "fake_low": "🔺 假突破(扫低点)",
            "break_high": "✅ 真突破(上破)",
            "break_low": "❌ 真突破(下破)",
        }
        print(f"\n💥 突破检测:")
        for btype, ts, level, close in breakouts:
            print(f"   {labels[btype]}  ${level:,.0f} → 收于 ${close:,.0f}  ({ts.strftime('%m-%d %H:%M')})")

    # -- 流动性 --
    liq_tolerance = price * 0.001  # 0.1% 容差
    pool_highs, pool_lows = find_liquidity_pools(swing_highs, swing_lows, liq_tolerance)
    if pool_highs or pool_lows:
        print(f"\n💧 流动性池:")
        if pool_highs:
            print("   上方(止损聚集):", "  ".join(f"${h:,.0f}" for h in pool_highs))
        if pool_lows:
            print("   下方(止损聚集):", "  ".join(f"${l:,.0f}" for l in pool_lows))

    # -- 成交量 --
    vols = [c.vol for c in candles[-20:]]
    avg_vol = sum(vols) / len(vols)
    last_vol = candles[-1].vol
    vol_ratio = last_vol / avg_vol * 100 if avg_vol > 0 else 0
    vol_label = "🔥 放量" if vol_ratio > 150 else "⚡ 缩量" if vol_ratio < 50 else "正常"
    print(f"\n📊 成交量: {last_vol:.1f} ({vol_ratio:.0f}% of 均值) — {vol_label}")

    # -- 综合判断 --
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

    print(f"\n{'=' * 64}")
    print(f"📋 综合: 多头 {bull} | 空头 {bear}")
    if bull > bear + 1:
        print("   偏多，关注回踩支撑做多")
    elif bear > bull + 1:
        print("   偏空，关注反弹阻力做空")
    else:
        print("   多空交织，建议观望或轻仓")
    print(f"{'=' * 64}")
    print("⚠️  技术面参考，不构成投资建议。请结合消息面和仓位管理。\n")

    return {
        "price": price,
        "rsi": rsi,
        "ema20": ema20[-1],
        "ema50": ema50[-1],
        "channel": channel_type,
        "bull_signals": bull,
        "bear_signals": bear,
    }


# ============================================================
# 价格报警
# ============================================================

def check_alerts(price: float, alert_above: float | None, alert_below: float | None):
    triggered = False
    if alert_above and price >= alert_above:
        msg = f"🚨 BTC 突破上方警戒线 ${alert_above:,.0f}！当前 ${price:,.1f}"
        print(f"\n{'!' * 60}\n{msg}\n{'!' * 60}")
        notify(msg)
        triggered = True
    if alert_below and price <= alert_below:
        msg = f"🚨 BTC 跌破下方警戒线 ${alert_below:,.0f}！当前 ${price:,.1f}"
        print(f"\n{'!' * 60}\n{msg}\n{'!' * 60}")
        notify(msg)
        triggered = True
    return triggered


def notify(msg: str):
    """macOS 系统通知"""
    try:
        subprocess.run([
            "osascript", "-e",
            f'display notification "{msg}" with title "Crypto Alert"'
        ], timeout=5, capture_output=True)
    except Exception:
        pass


# ============================================================
# 入口
# ============================================================

def main():
    args = sys.argv[1:]

    inst_id = DEFAULT_INST
    bar = DEFAULT_BAR
    watch_interval = 0
    alert_above = None
    alert_below = None

    # 解析参数
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
        elif args[i] == "--help" or args[i] == "-h":
            print(__doc__)
            return
        else:
            positional.append(args[i])
            i += 1

    if len(positional) >= 1:
        inst_id = positional[0].upper()
        if "-" not in inst_id:
            inst_id += "-USDT"
    if len(positional) >= 2:
        bar = positional[1]
        if bar not in VALID_BARS:
            print(f"无效周期 '{bar}'，可选: {', '.join(VALID_BARS)}")
            return

    try:
        while True:
            candles = fetch_candles(inst_id, bar)
            result = print_report(inst_id, bar, candles)

            if alert_above or alert_below:
                check_alerts(result["price"], alert_above, alert_below)

            if watch_interval <= 0:
                break

            print(f"⏰ {watch_interval} 秒后刷新... (Ctrl+C 退出)")
            time.sleep(watch_interval)

    except KeyboardInterrupt:
        print("\n👋 已退出")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
