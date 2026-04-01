"""
BTC 全策略回测优化器 (2021-2026)
===================================
预算: 每2周 $1000 (USD等值) / 对比基准: 每周 $500 简单DCA
数据: Kraken BTC/USD 周线

测试9种策略:
  S1  Simple DCA             — $500/周，永远全买
  S2  MA-Linear              — 分配比 = MA200w/price
  S3  MA-Conservative        — 分配比 = (MA200w/price)²  (高位极度保守)
  S4  MA-Aggressive          — 分配比 = √(MA200w/price)  (高位仍买不少)
  S5  RSI-Weighted           — 低RSI买更多，高RSI存钱
  S6  MA × RSI Combined      — MA信号 × RSI信号 联合决策
  S7  ATH-Discount           — 距高点越远买越多
  S8  Value Averaging        — 以恒定速率增长组合价值为目标
  S9  Threshold Bimodal      — 低于MA全力买+动用存款；高于1.5xMA全存

所有带存款池的策略: 每2周预算 $1000，未用资金进存款，价格低时从存款额外提取
"""

import time
import requests
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.gridspec as gridspec
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Callable


# ══════════════════════════════════════════════
# 1. 数据获取
# ══════════════════════════════════════════════

def fetch_kraken_weekly() -> pd.DataFrame:
    """BTC/USD 周线 OHLCV (Kraken 公开 API)"""
    url    = "https://api.kraken.com/0/public/OHLC"
    params = {"pair": "XBTUSD", "interval": 10080}

    print("Downloading BTC/USD weekly OHLCV from Kraken ...")
    for attempt in range(5):
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if data.get("error"):
                raise RuntimeError(f"Kraken: {data['error']}")
            result = data["result"]
            key    = [k for k in result if k != "last"][0]
            rows   = result[key]
            break
        except Exception as e:
            print(f"  Retry {attempt+1}: {e}")
            time.sleep(5)
    else:
        raise RuntimeError("Failed to fetch data.")

    df = pd.DataFrame(rows, columns=[
        "time","open","high","low","close","vwap","volume","count"])
    df["date"]  = pd.to_datetime(df["time"].astype(int), unit="s", utc=True)
    for col in ["open","high","low","close","vwap","volume"]:
        df[col] = df[col].astype(float)
    df = df.drop_duplicates("date").set_index("date").sort_index()
    print(f"  {len(df)} weekly candles  "
          f"({df.index[0].date()} → {df.index[-1].date()})")
    return df


def build_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算所有策略需要的技术指标:
      ma200w   — 200周简单均线
      rsi14    — 14周RSI
      ath      — 历史最高价 (滚动)
      ath_disc — ATH折扣率 = (ATH - close) / ATH  ∈ [0, 1)
    """
    df = df.copy()
    df["ma200w"]   = df["close"].rolling(200, min_periods=1).mean()
    df["rsi14"]    = _calc_rsi(df["close"], period=14)
    df["ath"]      = df["close"].cummax()
    df["ath_disc"] = (df["ath"] - df["close"]) / df["ath"]
    return df


def _calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0).ewm(com=period - 1, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(com=period - 1, adjust=False).mean()
    rs    = gain / loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))


# ══════════════════════════════════════════════
# 2. 策略定义
# ══════════════════════════════════════════════

@dataclass
class Strategy:
    name:        str
    short:       str
    color:       str
    biweekly:    float = 1000.0   # budget added every 2 weeks (USD)
    weekly_flat: float = 0.0      # flat weekly spend (for S1 simple DCA)
    # Allocation fn: (price, ma, rsi, ath_disc, savings) -> (invest_pct, extra_from_savings)
    # invest_pct applies to available_funds
    # extra_from_savings is absolute $ to pull from savings (capped internally)
    alloc_fn:    Callable = field(default=None)
    notes:       str = ""


def _alloc_s1(price, ma, rsi, disc, savings):
    """S1: Simple DCA — always 100% of flat $500"""
    return 1.0, 0.0

def _alloc_s2(price, ma, rsi, disc, savings):
    """S2: MA-Linear — invest_pct = ma/price (capped 1)"""
    pct   = min(1.0, ma / price)
    extra = 0.0
    if price <= ma:
        deviation = min(0.30, (ma - price) / ma)
        extra = savings * deviation
    return pct, extra

def _alloc_s3(price, ma, rsi, disc, savings):
    """S3: MA-Conservative — invest_pct = (ma/price)²"""
    pct   = min(1.0, (ma / price) ** 2)
    extra = 0.0
    if price <= ma:
        deviation = min(0.50, ((ma - price) / ma) ** 0.5)
        extra = savings * deviation
    return pct, extra

def _alloc_s4(price, ma, rsi, disc, savings):
    """S4: MA-Aggressive — invest_pct = √(ma/price)"""
    pct   = min(1.0, (ma / price) ** 0.5)
    extra = 0.0
    if price <= ma:
        deviation = min(0.20, (ma - price) / ma)
        extra = savings * deviation
    return pct, extra

def _alloc_s5(price, ma, rsi, disc, savings):
    """S5: RSI-Weighted — high RSI = save; low RSI = deploy savings"""
    # rsi: 0–100; invest_pct = 1 - rsi/100, clamped [0.1, 1.0]
    pct   = max(0.10, min(1.0, 1.0 - rsi / 100.0))
    extra = 0.0
    if rsi < 30:
        # Oversold: pull extra from savings proportional to how oversold
        depth = (30 - rsi) / 30          # 0→1 as RSI falls 30→0
        extra = savings * min(0.40, depth * 0.5)
    return pct, extra

def _alloc_s6(price, ma, rsi, disc, savings):
    """S6: MA × RSI Combined — geometric mean of MA signal & RSI signal"""
    ma_sig  = min(1.0, ma / price)
    rsi_sig = max(0.10, 1.0 - rsi / 100.0)
    # Geometric mean keeps the signal in (0,1)
    pct   = (ma_sig * rsi_sig) ** 0.5
    extra = 0.0
    if price <= ma and rsi < 35:
        depth = min(0.45, (1 - rsi / 35) * (ma - price) / ma)
        extra = savings * depth
    return pct, extra

def _alloc_s7(price, ma, rsi, disc, savings):
    """S7: ATH-Discount — invest proportional to distance from ATH"""
    # disc = 0 at ATH, 0.8 means 80% below ATH
    # sigmoid-like: even at ATH still invest a little
    pct   = max(0.05, min(1.0, disc ** 0.4))
    extra = 0.0
    if disc > 0.50:   # >50% off ATH: pull extra savings
        depth = min(0.35, (disc - 0.50) * 0.7)
        extra = savings * depth
    return pct, extra

def _alloc_s8(price, ma, rsi, disc, savings):
    """S8: Value Averaging — target portfolio grows $500/week linearly"""
    # Handled specially in the backtest loop (needs portfolio_value context)
    return 1.0, 0.0   # placeholder; logic is in the loop

def _alloc_s9(price, ma, rsi, disc, savings):
    """S9: Threshold Bimodal
    price < MA          → invest 100% + pull heavy savings
    MA ≤ price < 1.5×MA → linear taper 100%→10%
    price ≥ 1.5×MA      → invest nothing (accumulate everything)
    """
    if price < ma:
        depth = min(0.50, (ma - price) / ma * 1.5)
        return 1.0, savings * depth
    ratio = price / ma   # ≥1
    if ratio >= 1.5:
        return 0.0, 0.0
    pct = 1.0 - (ratio - 1.0) / 0.5   # linear 1→0 for ratio 1→1.5
    return pct, 0.0


STRATEGIES = [
    Strategy("Simple DCA $500/wk",      "S1-DCA",   "#6b7280", biweekly=0,      weekly_flat=500,  alloc_fn=_alloc_s1,  notes="Baseline: $500 every week, no savings"),
    Strategy("MA-Linear",               "S2-MAlin",  "#3b82f6", biweekly=1000,   alloc_fn=_alloc_s2,  notes="invest_pct = ma/price; saves above MA"),
    Strategy("MA-Conservative (x²)",    "S3-MAcon",  "#1d4ed8", biweekly=1000,   alloc_fn=_alloc_s3,  notes="invest_pct = (ma/price)²; very conservative at tops"),
    Strategy("MA-Aggressive (√x)",      "S4-MAagg",  "#93c5fd", biweekly=1000,   alloc_fn=_alloc_s4,  notes="invest_pct = √(ma/price); buys more even above MA"),
    Strategy("RSI-Weighted",            "S5-RSI",    "#10b981", biweekly=1000,   alloc_fn=_alloc_s5,  notes="invest_pct = 1 - RSI/100; deploys savings when RSI<30"),
    Strategy("MA × RSI Combined",       "S6-MARSI",  "#059669", biweekly=1000,   alloc_fn=_alloc_s6,  notes="Geometric mean of MA signal & RSI signal"),
    Strategy("ATH-Discount",            "S7-ATH",    "#f59e0b", biweekly=1000,   alloc_fn=_alloc_s7,  notes="invest_pct = disc^0.4; more discount = more buy"),
    Strategy("Value Averaging",         "S8-VAVG",   "#ef4444", biweekly=1000,   alloc_fn=_alloc_s8,  notes="Target $500/wk linear growth; surplus goes to savings"),
    Strategy("Threshold Bimodal",       "S9-BMOD",   "#8b5cf6", biweekly=1000,   alloc_fn=_alloc_s9,  notes="Below MA=all-in+savings; >1.5×MA=save everything"),
]


# ══════════════════════════════════════════════
# 3. 回测引擎
# ══════════════════════════════════════════════

def run_backtest(df: pd.DataFrame, strat: Strategy) -> pd.DataFrame:
    """
    Universal backtest engine.
    Returns weekly DataFrame with columns:
      price, ma200w, rsi14, ath_disc,
      invested, btc_held, savings, portfolio_value, total_cash_in, roi_pct
    """
    btc      = 0.0
    savings  = 0.0
    avail    = 0.0
    total_in = 0.0
    week_num = 0
    rows     = []

    # Value Averaging target: initial $500/wk linear
    VA_TARGET_RATE = 500.0

    for i, (date, row) in enumerate(df.iterrows()):
        price   = float(row["close"])
        ma      = float(row["ma200w"])
        rsi     = float(row["rsi14"]) if not np.isnan(row["rsi14"]) else 50.0
        disc    = float(row["ath_disc"])
        week_num += 1

        # Budget injection every 2 weeks
        if strat.weekly_flat > 0:
            avail += strat.weekly_flat          # S1: flat weekly
        elif i % 2 == 0:
            avail += strat.biweekly             # all others: biweekly

        # ── Value Averaging special logic ──
        if strat.short == "S8-VAVG":
            target_value = VA_TARGET_RATE * week_num
            current_value = btc * price + savings
            needed = target_value - current_value
            if needed <= 0:
                # Portfolio ahead of target: invest nothing, save budget
                invest = 0.0
                savings += avail
                avail = 0.0
            else:
                # Pull from savings if needed to hit target
                available_total = avail + savings
                invest = min(needed, available_total)
                if invest > avail:
                    savings -= (invest - avail)
                    savings  = max(0.0, savings)
                avail = 0.0
            total_in  += invest
            btc       += invest / price if invest > 0 else 0
        else:
            # ── Standard allocation ──
            pct, extra = strat.alloc_fn(price, ma, rsi, disc, savings)

            # Cap extra to actual savings
            extra = min(extra, savings)

            invest   = avail * pct + extra
            savings += avail * (1.0 - pct) - extra
            savings  = max(0.0, savings)
            avail    = 0.0

            total_in  += invest
            btc       += invest / price if invest > 0 else 0

        port_val = btc * price + savings
        roi_pct  = (port_val - total_in) / total_in * 100 if total_in > 0 else 0.0

        rows.append({
            "date":            date,
            "price":           price,
            "ma200w":          ma,
            "rsi14":           rsi,
            "ath_disc":        disc,
            "invested":        invest if strat.short != "S8-VAVG" else invest,
            "btc_held":        btc,
            "savings":         savings,
            "portfolio_value": port_val,
            "total_cash_in":   total_in + savings,  # total committed to system
            "btc_value":       btc * price,
            "roi_pct":         roi_pct,
        })

    return pd.DataFrame(rows).set_index("date")


# ══════════════════════════════════════════════
# 4. 分析 & 排名
# ══════════════════════════════════════════════

def analyse(results: dict[str, pd.DataFrame],
            strategies: list[Strategy]) -> pd.DataFrame:
    rows = []
    for s in strategies:
        r    = results[s.short]
        last = r.iloc[-1]
        port_val  = last["portfolio_value"]
        total_in  = last["total_cash_in"]
        roi       = (port_val - total_in) / total_in * 100
        btc       = last["btc_held"]
        # Max drawdown on portfolio value
        roll_max  = r["portfolio_value"].cummax()
        drawdowns = (r["portfolio_value"] - roll_max) / roll_max * 100
        max_dd    = drawdowns.min()
        # Calmar-like: ROI / abs(max_drawdown)
        calmar    = roi / abs(max_dd) if max_dd != 0 else 0.0
        # Savings efficiency (savings left / total_in)
        savings_ratio = last["savings"] / total_in * 100 if total_in > 0 else 0
        rows.append({
            "Strategy":       s.name,
            "Short":          s.short,
            "Total Cash In":  total_in,
            "BTC Held":       btc,
            "Portfolio $":    port_val,
            "Net Profit $":   port_val - total_in,
            "ROI %":          roi,
            "Max Drawdown %": max_dd,
            "Calmar Ratio":   calmar,
            "Savings $":      last["savings"],
            "Notes":          s.notes,
        })
    df = pd.DataFrame(rows)
    df["Rank ROI"]    = df["ROI %"].rank(ascending=False).astype(int)
    df["Rank Calmar"] = df["Calmar Ratio"].rank(ascending=False).astype(int)
    df["Rank BTC"]    = df["BTC Held"].rank(ascending=False).astype(int)
    df["Score"] = df["Rank ROI"] + df["Rank Calmar"] + df["Rank BTC"]
    df["Overall Rank"] = df["Score"].rank().astype(int)
    return df.sort_values("Score")


# ══════════════════════════════════════════════
# 5. 可视化
# ══════════════════════════════════════════════

def plot_all(weekly: pd.DataFrame,
             results: dict[str, pd.DataFrame],
             strategies: list[Strategy],
             ranking: pd.DataFrame,
             out_path: str):

    fig = plt.figure(figsize=(18, 22))
    gs  = gridspec.GridSpec(4, 2, figure=fig,
                            hspace=0.38, wspace=0.30,
                            height_ratios=[1.2, 1.1, 1.1, 1.0])

    # ── Panel 0,0 (spans full row): BTC Price + MA ──
    ax0 = fig.add_subplot(gs[0, :])
    ax0.semilogy(weekly.index, weekly["close"], color="#f7931a",
                 lw=1.2, label="BTC/USD Weekly Close", zorder=3)
    ax0.semilogy(weekly.index, weekly["ma200w"], color="#1d4ed8",
                 lw=2.0, ls="--", label="200-Week MA", zorder=4)
    ax0.fill_between(weekly.index, weekly["close"], weekly["ma200w"],
                     where=(weekly["close"] < weekly["ma200w"]),
                     alpha=0.22, color="green", label="Below MA (buy zone)")
    ax0.fill_between(weekly.index, weekly["close"], weekly["ma200w"],
                     where=(weekly["close"] >= weekly["ma200w"]),
                     alpha=0.08, color="red", label="Above MA (save zone)")
    # shade ATH discount
    ax0r = ax0.twinx()
    ax0r.fill_between(weekly.index, weekly["ath_disc"] * 100,
                      alpha=0.12, color="purple", label="ATH Discount %")
    ax0r.set_ylabel("ATH Discount %", color="purple", fontsize=8)
    ax0r.tick_params(axis="y", labelcolor="purple", labelsize=7)
    ax0.set_ylabel("BTC/USD (log)", fontsize=9)
    ax0.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    handles0, labels0 = ax0.get_legend_handles_labels()
    handlesr, labelsr = ax0r.get_legend_handles_labels()
    ax0.legend(handles0 + handlesr, labels0 + labelsr, fontsize=8, ncol=5)
    ax0.set_title("BTC/USD  |  200-Week MA  |  ATH Discount  (2021–2026)", fontsize=11, fontweight="bold")
    ax0.grid(True, alpha=0.25)

    # ── Panel 1,0: Portfolio Value all strategies ──
    ax1 = fig.add_subplot(gs[1, :])
    for s in strategies:
        r    = results[s.short]
        rank = ranking.loc[ranking["Short"] == s.short, "Overall Rank"].values[0]
        lw   = 2.4 if rank <= 3 else 1.1
        ls   = "-"  if rank <= 3 else "--"
        label = f"#{rank} {s.short}: {s.name}"
        ax1.plot(r.index, r["portfolio_value"], color=s.color,
                 lw=lw, ls=ls, label=label, alpha=0.9)
    ax1.plot(results["S1-DCA"].index, results["S1-DCA"]["total_cash_in"],
             color="black", lw=1.0, ls=":", label="Total Cash Deployed", alpha=0.6)
    ax1.set_ylabel("Portfolio Value (USD)")
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax1.legend(fontsize=7.5, ncol=3)
    ax1.set_title("Portfolio Value: All 9 Strategies (BTC + Savings)", fontsize=11, fontweight="bold")
    ax1.grid(True, alpha=0.25)

    # ── Panel 2,0: BTC Held ──
    ax2a = fig.add_subplot(gs[2, 0])
    for s in strategies:
        r    = results[s.short]
        rank = ranking.loc[ranking["Short"] == s.short, "Overall Rank"].values[0]
        lw   = 2.2 if rank <= 3 else 1.0
        ax2a.plot(r.index, r["btc_held"], color=s.color, lw=lw,
                  label=f"#{rank} {s.short}")
    ax2a.set_ylabel("BTC Accumulated")
    ax2a.legend(fontsize=7.5, ncol=2)
    ax2a.set_title("BTC Holdings Over Time", fontsize=10, fontweight="bold")
    ax2a.grid(True, alpha=0.25)

    # ── Panel 2,1: Savings Pool (strategies with savings) ──
    ax2b = fig.add_subplot(gs[2, 1])
    for s in [s for s in strategies if s.short != "S1-DCA"]:
        r    = results[s.short]
        rank = ranking.loc[ranking["Short"] == s.short, "Overall Rank"].values[0]
        lw   = 2.0 if rank <= 3 else 0.9
        ax2b.plot(r.index, r["savings"], color=s.color, lw=lw,
                  label=f"#{rank} {s.short}")
    ax2b.set_ylabel("Savings Pool (USD)")
    ax2b.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax2b.legend(fontsize=7.5, ncol=2)
    ax2b.set_title("Savings Pool Over Time", fontsize=10, fontweight="bold")
    ax2b.grid(True, alpha=0.25)

    # ── Panel 3,0: ROI % over time ──
    ax3a = fig.add_subplot(gs[3, 0])
    for s in strategies:
        r    = results[s.short]
        rank = ranking.loc[ranking["Short"] == s.short, "Overall Rank"].values[0]
        lw   = 2.2 if rank <= 3 else 1.0
        ax3a.plot(r.index, r["roi_pct"], color=s.color, lw=lw,
                  label=f"#{rank} {s.short}")
    ax3a.axhline(0, color="black", lw=0.8, ls="--", alpha=0.5)
    ax3a.set_ylabel("ROI %")
    ax3a.legend(fontsize=7.5, ncol=2)
    ax3a.set_title("Rolling ROI % (portfolio vs cash deployed)", fontsize=10, fontweight="bold")
    ax3a.grid(True, alpha=0.25)

    # ── Panel 3,1: Final ranking bar chart ──
    ax3b = fig.add_subplot(gs[3, 1])
    rank_df   = ranking.sort_values("ROI %", ascending=True)
    colors_b  = [s.color for name in rank_df["Short"]
                 for s in strategies if s.short == name]
    bars = ax3b.barh(rank_df["Short"], rank_df["ROI %"],
                     color=colors_b, edgecolor="white", height=0.65)
    for bar, val in zip(bars, rank_df["ROI %"]):
        ax3b.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                  f"{val:.1f}%", va="center", fontsize=8)
    ax3b.set_xlabel("Final ROI %")
    ax3b.set_title("Final ROI Comparison", fontsize=10, fontweight="bold")
    ax3b.grid(True, alpha=0.25, axis="x")

    fig.suptitle(
        "BTC Investment Strategy Optimizer  |  2021-01 → 2026-03  |  Budget: $1000/2wks  (USD)",
        fontsize=13, fontweight="bold", y=0.995)

    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"\nChart saved: {out_path}")


# ══════════════════════════════════════════════
# 6. 主程序
# ══════════════════════════════════════════════

def print_ranking(ranking: pd.DataFrame):
    print("\n" + "═" * 90)
    print("  FINAL RANKING (sorted by composite score: ROI + Calmar + BTC Accumulated)")
    print("═" * 90)
    cols = ["Overall Rank","Short","ROI %","Portfolio $","BTC Held",
            "Max Drawdown %","Calmar Ratio","Savings $"]
    fmt  = "{:>3}  {:<12}  {:>8.1f}%  {:>12,.0f}  {:>10.4f}  {:>9.1f}%  {:>8.3f}  {:>10,.0f}"
    header = f"{'#':>3}  {'Short':<12}  {'ROI':>9}  {'Portfolio':>12}  " \
             f"{'BTC Held':>10}  {'MaxDD':>9}  {'Calmar':>8}  {'Savings':>10}"
    print(header)
    print("-" * 90)
    for _, row in ranking.iterrows():
        print(fmt.format(
            row["Overall Rank"], row["Short"],
            row["ROI %"], row["Portfolio $"], row["BTC Held"],
            row["Max Drawdown %"], row["Calmar Ratio"], row["Savings $"]))
    print("═" * 90)

    # Winner
    winner = ranking.iloc[0]
    print(f"\n  WINNER: {winner['Strategy']}  ({winner['Short']})")
    print(f"  ROI: {winner['ROI %']:.1f}%   |   Portfolio: ${winner['Portfolio $']:,.0f}"
          f"   |   BTC: {winner['BTC Held']:.5f}   |   Calmar: {winner['Calmar Ratio']:.3f}")
    print(f"\n  Notes: {ranking.iloc[0]['Notes']}")
    print()

    # Head-to-head vs baseline DCA
    dca = ranking[ranking["Short"] == "S1-DCA"].iloc[0]
    print("  Head-to-head vs Simple DCA baseline:")
    print(f"  {'Strategy':<30}  {'ROI':>8}  {'vs DCA':>10}  {'BTC vs DCA':>12}  {'Rank':>6}")
    print(f"  {'-'*80}")
    for _, row in ranking.iterrows():
        diff_roi = row["ROI %"] - dca["ROI %"]
        diff_btc = row["BTC Held"] - dca["BTC Held"]
        sign     = "+" if diff_roi >= 0 else ""
        bsign    = "+" if diff_btc >= 0 else ""
        print(f"  {row['Strategy']:<30}  {row['ROI %']:>7.1f}%  "
              f"{sign}{diff_roi:>7.1f}%  {bsign}{diff_btc:>9.4f} BTC  #{row['Overall Rank']:>3}")


def main():
    # ── Data ──
    raw    = fetch_kraken_weekly()
    df     = build_indicators(raw)
    # Backtest from 2021 (full data used for MA calculation)
    df_bt  = df[df.index >= "2021-01-01"].copy()

    print(f"\nBacktest range: {df_bt.index[0].date()} → {df_bt.index[-1].date()}"
          f"  ({len(df_bt)} weeks)\n")

    # ── Run all strategies ──
    results = {}
    for s in STRATEGIES:
        print(f"  Running {s.short}: {s.name} ...")
        results[s.short] = run_backtest(df_bt, s)

    # ── Rank ──
    ranking = analyse(results, STRATEGIES)
    print_ranking(ranking)

    # ── Chart ──
    out = "/home/user/CLAUDE-PLAYGROUND/btc_strategy_optimizer.png"
    plot_all(df_bt, results, STRATEGIES, ranking, out_path=out)

    # ── Save ranking CSV ──
    csv_out = "/home/user/CLAUDE-PLAYGROUND/btc_strategy_ranking.csv"
    ranking.to_csv(csv_out, index=False, float_format="%.4f")
    print(f"Ranking CSV saved: {csv_out}")


if __name__ == "__main__":
    main()
