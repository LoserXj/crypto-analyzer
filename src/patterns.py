"""形态检测"""
from src.fetcher import Candle
from src.indicators import linreg_slope


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


def detect_channel(candles: list[Candle], window: int = 20):
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
            return "bullish"
        elif p2[1] > p1[1] and r2[1] < r1[1]:
            return "bearish"

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

        if lower_wick > body * 2.5 and lower_wick > upper_wick * 2:
            patterns.append(("pin_bar_bull", c.ts, c.close))
        elif upper_wick > body * 2.5 and upper_wick > lower_wick * 2:
            patterns.append(("pin_bar_bear", c.ts, c.close))

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
    """FVG (公允价值缺口)"""
    gaps = []
    for i in range(max(-window, -len(candles) + 2), 0):
        c1 = candles[i - 2]
        c3 = candles[i]

        if c3.low > c1.high:
            gaps.append(("bull_fvg", c3.ts, c1.high, c3.low))
        elif c3.high < c1.low:
            gaps.append(("bear_fvg", c3.ts, c3.high, c1.low))

    return gaps
