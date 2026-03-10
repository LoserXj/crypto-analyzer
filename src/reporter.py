"""报告生成 — 终端 + JSON"""


def print_terminal_report(r: dict):
    """打印终端报告"""
    price = r["price"]

    print()
    print("=" * 64)
    print(f"  {r['inst_id']}  {r['bar']}  技术分析报告")
    print(f"  数据时间: {r['timestamp'][:16].replace('T', ' ')} UTC")
    print(f"  当前价格: ${price:,.1f}")
    print("=" * 64)

    # 最新蜡烛
    icon = "\U0001f7e2" if r["change_pct"] >= 0 else "\U0001f534"
    c = r["candle"]
    print(f"\n{icon} 最新 {r['bar']} 蜡烛:")
    print(f"   O: ${c['open']:,.1f}  H: ${c['high']:,.1f}  L: ${c['low']:,.1f}  C: ${c['close']:,.1f}  ({r['change_pct']:+.2f}%)")

    # 趋势通道
    labels = {
        "descending": "\u26a0\ufe0f  【下降通道】高点和低点持续走低",
        "ascending": "\u2705  【上升通道】高点和低点持续走高",
        "converging": "\U0001f4d0  【收敛三角/楔形】高点走低 + 低点走高",
        "expanding": "\U0001f4ca  【扩散形态】波动扩大",
        "ranging": "\U0001f4ca  【横盘震荡】无明显趋势",
    }
    print(f"\n\U0001f4d0 趋势通道 (近20根{r['bar']}):")
    print(f"   高点斜率: {r['slope_high']:+.1f} $/根  |  低点斜率: {r['slope_low']:+.1f} $/根")
    print(f"   {labels.get(r['channel'], r['channel'])}")

    # 摆动点
    print(f"\n\U0001f511 关键摆动点:")
    print("   高点:", "  ".join(f"${v:,.0f}({t[5:10]})" for v, t in r["swing_highs"]))
    print("   低点:", "  ".join(f"${v:,.0f}({t[5:10]})" for v, t in r["swing_lows"]))

    # 支撑阻力
    print(f"\n\U0001f9f1 支撑/阻力:")
    if r["resistances"]:
        print("   阻力:", "  ".join(f"${s['price']:,.0f}(x{s['count']})" for s in r["resistances"]))
    if r["supports"]:
        print("   支撑:", "  ".join(f"${s['price']:,.0f}(x{s['count']})" for s in r["supports"]))

    # 均线
    print(f"\n\U0001f4c9 均线:")
    print(f"   EMA20: ${r['ema20']:,.1f} ({'上方' if price > r['ema20'] else '下方'})")
    print(f"   EMA50: ${r['ema50']:,.1f} ({'上方' if price > r['ema50'] else '下方'})")
    if r["ema200"]:
        print(f"   EMA200: ${r['ema200']:,.1f} ({'上方' if price > r['ema200'] else '下方'})")
    cross_labels = {
        "golden": "   \U0001f525 EMA20 金叉 EMA50！",
        "death": "   \u2620\ufe0f  EMA20 死叉 EMA50！",
        "bull_align": "   \U0001f4c8 多头排列",
        "bear_align": "   \U0001f4c9 空头排列",
    }
    print(cross_labels.get(r["ema_cross"], ""))

    # RSI
    rsi_icon = "\u26a0\ufe0f" if r["rsi_label"] in ("超买", "超卖") else ""
    print(f"\n\U0001f4ca RSI(14): {r['rsi']:.1f} — {r['rsi_label']} {rsi_icon}")
    if r["rsi_divergence"] == "bullish":
        print("   \U0001f525 底背离！价格新低但 RSI 未新低 — 潜在反转")
    elif r["rsi_divergence"] == "bearish":
        print("   \u26a0\ufe0f  顶背离！价格新高但 RSI 未新高 — 潜在见顶")

    # ATR
    print(f"\n\U0001f4cf ATR(14): ${r['atr']:,.0f} ({r['atr_pct']:.2f}%)")

    # K线形态
    if r["patterns"]:
        plabels = {
            "pin_bar_bull": "\U0001f53a 看涨Pin Bar",
            "pin_bar_bear": "\U0001f53b 看跌Pin Bar",
            "bullish_engulf": "\U0001f53a 看涨吞没",
            "bearish_engulf": "\U0001f53b 看跌吞没",
        }
        print(f"\n\U0001f56f\ufe0f  K线形态 (近5根):")
        for p in r["patterns"]:
            print(f"   {plabels.get(p['type'], p['type'])}  {p['time'][5:16].replace('T', ' ')}  收于 ${p['close']:,.0f}")

    # FVG
    if r["fvgs"]:
        print(f"\n\U0001f4e6 FVG (公允价值缺口):")
        for f in r["fvgs"]:
            label = "看涨" if f["type"] == "bull_fvg" else "看跌"
            print(f"   {label} FVG: ${f['low']:,.0f}-${f['high']:,.0f}  ({f['time'][5:16].replace('T', ' ')})")

    # 突破
    if r["breakouts"]:
        blabels = {
            "fake_high": "\U0001f53b 假突破(扫高点)",
            "fake_low": "\U0001f53a 假突破(扫低点)",
            "break_high": "\u2705 真突破(上破)",
            "break_low": "\u274c 真突破(下破)",
        }
        print(f"\n\U0001f4a5 突破检测:")
        for b in r["breakouts"]:
            print(f"   {blabels.get(b['type'], b['type'])}  ${b['level']:,.0f} → 收于 ${b['close']:,.0f}  ({b['time'][5:16].replace('T', ' ')})")

    # 流动性
    if r["liquidity_highs"] or r["liquidity_lows"]:
        print(f"\n\U0001f4a7 流动性池:")
        if r["liquidity_highs"]:
            print("   上方(止损聚集):", "  ".join(f"${h:,.0f}" for h in r["liquidity_highs"]))
        if r["liquidity_lows"]:
            print("   下方(止损聚集):", "  ".join(f"${l:,.0f}" for l in r["liquidity_lows"]))

    # 成交量
    vol_label = "\U0001f525 放量" if r["vol_ratio"] > 150 else "\u26a1 缩量" if r["vol_ratio"] < 50 else "正常"
    print(f"\n\U0001f4ca 成交量: ({r['vol_ratio']:.0f}% of 均值) — {vol_label}")

    # 综合
    print(f"\n{'=' * 64}")
    print(f"\U0001f4cb 综合: 多头 {r['bull_signals']} | 空头 {r['bear_signals']}")
    if r["verdict"] == "偏多":
        print("   偏多，关注回踩支撑做多")
    elif r["verdict"] == "偏空":
        print("   偏空，关注反弹阻力做空")
    else:
        print("   多空交织，建议观望或轻仓")
    print(f"{'=' * 64}")
    print("\u26a0\ufe0f  技术面参考，不构成投资建议。请结合消息面和仓位管理。\n")


def format_wechat_report(r: dict) -> tuple[str, str]:
    """格式化为微信推送的 title + markdown body"""
    verdict_icon = {"偏多": "\U0001f7e2", "偏空": "\U0001f534", "多空交织": "\U0001f7e1"}
    title = f"{r['inst_id']} {verdict_icon.get(r['verdict'], '')} {r['verdict']} | ${r['price']:,.0f} ({r['change_pct']:+.1f}%)"

    lines = [
        f"## {r['inst_id']} {r['bar']} 分析报告\n",
        f"**价格**: ${r['price']:,.1f} ({r['change_pct']:+.2f}%)",
        f"**趋势**: {r['channel']}",
        f"**RSI**: {r['rsi']:.1f} ({r['rsi_label']})",
        f"**EMA**: {r['ema_cross']}\n",
    ]

    if r["resistances"]:
        lines.append("**阻力**: " + " / ".join(f"${s['price']:,.0f}" for s in r["resistances"]))
    if r["supports"]:
        lines.append("**支撑**: " + " / ".join(f"${s['price']:,.0f}" for s in r["supports"]))

    if r["patterns"]:
        plabels = {"pin_bar_bull": "看涨Pin Bar", "pin_bar_bear": "看跌Pin Bar",
                   "bullish_engulf": "看涨吞没", "bearish_engulf": "看跌吞没"}
        lines.append("\n**K线形态**:")
        for p in r["patterns"]:
            lines.append(f"- {plabels.get(p['type'], p['type'])}")

    if r["rsi_divergence"]:
        div_label = "底背离 \U0001f525" if r["rsi_divergence"] == "bullish" else "顶背离 \u26a0\ufe0f"
        lines.append(f"\n**RSI背离**: {div_label}")

    lines.append(f"\n**综合**: 多头 {r['bull_signals']} | 空头 {r['bear_signals']} → **{r['verdict']}**")
    lines.append(f"\n---\n\u23f0 {r['timestamp'][:16].replace('T', ' ')} UTC")

    return title, "\n".join(lines)
