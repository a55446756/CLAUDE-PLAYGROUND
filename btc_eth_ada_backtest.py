"""
多资产组合回测: BTC 40% + ETH 30% + ADA 30%
=============================================
预算: 每2周 $1000 (USD)  /  每周对比基准 $500
数据: Kraken 周线 (BTC/USD, ETH/USD, ADA/USD)

测试策略 (每种都对三个资产独立应用信号, 各资产有独立存款池):
  P1  Portfolio DCA             — 40/30/30 简单DCA
  P2  Portfolio MA-Conservative — (ma/price)²  各资产独立
  P3  Portfolio Threshold Bimodal — <MA全买; >1.5×MA全存
  P4  Portfolio MA-Linear        — ma/price 各资产独立

对比基准 (BTC 100%):
  B1  BTC-only DCA
  B2  BTC-only MA-Conservative
  B3  BTC-only Threshold Bimodal
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


# ══════════════════════════════════════════════
# 1. 数据获取
# ══════════════════════════════════════════════

KRAKEN_PAIRS = {
    "BTC": "XBTUSD",
    "ETH": "XETHZUSD",
    "ADA": "ADAUSD",
}

def fetch_weekly(pair_key: str) -> pd.DataFrame:
    symbol = KRAKEN_PAIRS[pair_key]
    url    = "https://api.kraken.com/0/public/OHLC"
    params = {"pair": symbol, "interval": 10080}
    print(f"  Fetching {pair_key} ({symbol}) ...")
    for attempt in range(5):
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if data.get("error"):
                raise RuntimeError(data["error"])
            result = data["result"]
            key    = [k for k in result if k != "last"][0]
            rows   = result[key]
            break
        except Exception as e:
            print(f"    Retry {attempt+1}: {e}")
            time.sleep(5)
    else:
        raise RuntimeError(f"Failed to fetch {pair_key}")

    df = pd.DataFrame(rows, columns=[
        "time","open","high","low","close","vwap","volume","count"])
    df["date"]  = pd.to_datetime(df["time"].astype(int), unit="s", utc=True)
    df["close"] = df["close"].astype(float)
    df = df.drop_duplicates("date").set_index("date").sort_index()
    return df[["close"]]


def build_indicators(df: pd.DataFrame, asset: str) -> pd.DataFrame:
    df = df.copy()
    df["ma200w"]   = df["close"].rolling(200, min_periods=1).mean()
    df["rsi14"]    = _calc_rsi(df["close"])
    df["ath"]      = df["close"].cummax()
    df["ath_disc"] = (df["ath"] - df["close"]) / df["ath"]
    # Flag how many weeks of history we had (for MA quality note)
    df["ma_weeks"] = df["close"].expanding().count()
    print(f"    {asset}: {len(df)} weekly candles  "
          f"({df.index[0].date()} → {df.index[-1].date()})")
    return df


def _calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0).ewm(com=period - 1, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(com=period - 1, adjust=False).mean()
    rs    = gain / loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))


# ══════════════════════════════════════════════
# 2. 单资产分配函数 (与 optimizer 一致)
# ══════════════════════════════════════════════

def alloc_dca(price, ma, rsi, disc, savings):
    return 1.0, 0.0

def alloc_ma_conservative(price, ma, rsi, disc, savings):
    pct   = min(1.0, (ma / price) ** 2)
    extra = 0.0
    if price <= ma:
        deviation = min(0.50, ((ma - price) / ma) ** 0.5)
        extra = savings * deviation
    return pct, extra

def alloc_ma_linear(price, ma, rsi, disc, savings):
    pct   = min(1.0, ma / price)
    extra = 0.0
    if price <= ma:
        deviation = min(0.30, (ma - price) / ma)
        extra = savings * deviation
    return pct, extra

def alloc_bimodal(price, ma, rsi, disc, savings):
    if price < ma:
        depth = min(0.50, (ma - price) / ma * 1.5)
        return 1.0, savings * depth
    ratio = price / ma
    if ratio >= 1.5:
        return 0.0, 0.0
    pct = 1.0 - (ratio - 1.0) / 0.5
    return pct, 0.0


# ══════════════════════════════════════════════
# 3. 单资产回测引擎
# ══════════════════════════════════════════════

def run_single_asset(df: pd.DataFrame,
                     alloc_fn,
                     biweekly_budget: float,
                     weekly_flat: float = 0.0) -> pd.DataFrame:
    """
    Returns weekly DataFrame per asset:
      holdings, savings, invested, portfolio_value (in USD)
    """
    holdings = 0.0
    savings  = 0.0
    avail    = 0.0
    total_in = 0.0
    rows     = []

    for i, (date, row) in enumerate(df.iterrows()):
        price = float(row["close"])
        ma    = float(row["ma200w"])
        rsi   = float(row["rsi14"]) if not np.isnan(row["rsi14"]) else 50.0
        disc  = float(row["ath_disc"])

        if weekly_flat > 0:
            avail += weekly_flat
        elif i % 2 == 0:
            avail += biweekly_budget

        pct, extra = alloc_fn(price, ma, rsi, disc, savings)
        extra   = min(extra, savings)
        invest  = avail * pct + extra
        savings += avail * (1.0 - pct) - extra
        savings  = max(0.0, savings)
        avail    = 0.0

        holdings += invest / price if invest > 0 else 0.0
        total_in += invest

        rows.append({
            "date":      date,
            "price":     price,
            "ma200w":    ma,
            "holdings":  holdings,
            "savings":   savings,
            "invested":  invest,
            "usd_value": holdings * price,
            "total_in":  total_in + savings,
        })

    return pd.DataFrame(rows).set_index("date")


# ══════════════════════════════════════════════
# 4. 多资产组合引擎
# ══════════════════════════════════════════════

WEIGHTS = {"BTC": 0.40, "ETH": 0.30, "ADA": 0.30}
TOTAL_BIWEEKLY = 1000.0   # USD per 2 weeks
TOTAL_WEEKLY   = 500.0    # for DCA baseline

PORTFOLIO_STRATEGIES = {
    "P1-DCA":  {"fn": alloc_dca,            "label": "Portfolio DCA 40/30/30",            "color": "#6b7280", "weekly": True},
    "P2-MAcon":{"fn": alloc_ma_conservative,"label": "Portfolio MA-Conservative (x²)",   "color": "#1d4ed8", "weekly": False},
    "P3-BMOD": {"fn": alloc_bimodal,         "label": "Portfolio Threshold Bimodal",       "color": "#8b5cf6", "weekly": False},
    "P4-MAlin":{"fn": alloc_ma_linear,       "label": "Portfolio MA-Linear",               "color": "#3b82f6", "weekly": False},
    # BTC-only baselines
    "B1-DCA":  {"fn": alloc_dca,            "label": "BTC-only DCA $500/wk",             "color": "#9ca3af", "weekly": True,  "btc_only": True},
    "B2-MAcon":{"fn": alloc_ma_conservative,"label": "BTC-only MA-Conservative",         "color": "#f97316", "weekly": False, "btc_only": True},
    "B3-BMOD": {"fn": alloc_bimodal,         "label": "BTC-only Threshold Bimodal",        "color": "#ef4444", "weekly": False, "btc_only": True},
}

def run_portfolio(asset_dfs: dict,
                  strategy_key: str,
                  strategy_cfg: dict,
                  start_date: str = "2021-01-01") -> pd.DataFrame:
    """
    Runs a multi-asset or BTC-only strategy.
    Returns combined weekly portfolio DataFrame.
    """
    btc_only = strategy_cfg.get("btc_only", False)
    alloc_fn = strategy_cfg["fn"]
    weekly   = strategy_cfg["weekly"]

    assets = ["BTC"] if btc_only else ["BTC", "ETH", "ADA"]

    # Budgets per asset (split by weight, or full for BTC-only)
    if btc_only:
        budget = {
            "BTC": TOTAL_WEEKLY if weekly else TOTAL_BIWEEKLY
        }
    else:
        if weekly:
            budget = {a: TOTAL_WEEKLY * WEIGHTS[a] for a in assets}
        else:
            budget = {a: TOTAL_BIWEEKLY * WEIGHTS[a] for a in assets}

    # Run per-asset backtests
    asset_results = {}
    for asset in assets:
        df_asset = asset_dfs[asset][asset_dfs[asset].index >= start_date].copy()
        asset_results[asset] = run_single_asset(
            df_asset, alloc_fn,
            biweekly_budget=budget[asset],
            weekly_flat=budget[asset] if weekly else 0.0,
        )

    # Align to common weekly index (BTC as reference)
    ref_index = asset_results["BTC"].index
    combined  = pd.DataFrame(index=ref_index)

    total_usd_value = pd.Series(0.0, index=ref_index)
    total_savings   = pd.Series(0.0, index=ref_index)
    total_cash_in   = pd.Series(0.0, index=ref_index)

    for asset in assets:
        r = asset_results[asset].reindex(ref_index, method="ffill")
        combined[f"{asset}_holdings"]   = r["holdings"]
        combined[f"{asset}_price"]      = r["price"]
        combined[f"{asset}_usd_value"]  = r["usd_value"]
        combined[f"{asset}_savings"]    = r["savings"]
        combined[f"{asset}_invested"]   = r["invested"]
        total_usd_value += r["usd_value"]
        total_savings   += r["savings"]
        total_cash_in   += r["total_in"]

    combined["portfolio_value"] = total_usd_value + total_savings
    combined["total_savings"]   = total_savings
    combined["total_cash_in"]   = total_cash_in
    combined["roi_pct"] = (
        (combined["portfolio_value"] - combined["total_cash_in"])
        / combined["total_cash_in"] * 100
    ).fillna(0)

    return combined


# ══════════════════════════════════════════════
# 5. 分析 & 排名
# ══════════════════════════════════════════════

def analyse_portfolios(results: dict) -> pd.DataFrame:
    rows = []
    for key, cfg in PORTFOLIO_STRATEGIES.items():
        r    = results[key]
        last = r.iloc[-1]
        port  = last["portfolio_value"]
        tin   = last["total_cash_in"]
        roi   = (port - tin) / tin * 100

        roll_max = r["portfolio_value"].cummax()
        dd       = (r["portfolio_value"] - roll_max) / roll_max * 100
        max_dd   = dd.min()
        calmar   = roi / abs(max_dd) if max_dd != 0 else 0.0

        btc_only = cfg.get("btc_only", False)
        assets   = ["BTC"] if btc_only else ["BTC", "ETH", "ADA"]
        btc_held = last.get("BTC_holdings", 0)
        eth_held = last.get("ETH_holdings", 0) if not btc_only else 0
        ada_held = last.get("ADA_holdings", 0) if not btc_only else 0

        rows.append({
            "Key":           key,
            "Strategy":      cfg["label"],
            "Type":          "BTC-only" if btc_only else "Portfolio",
            "ROI %":         roi,
            "Portfolio $":   port,
            "Net Profit $":  port - tin,
            "Total Cash In": tin,
            "Max DD %":      max_dd,
            "Calmar":        calmar,
            "Savings $":     last["total_savings"],
            "BTC Held":      btc_held,
            "ETH Held":      eth_held,
            "ADA Held":      ada_held,
        })

    df = pd.DataFrame(rows)
    df["Rank"] = df["ROI %"].rank(ascending=False).astype(int)
    return df.sort_values("ROI %", ascending=False)


def print_results(df: pd.DataFrame):
    print("\n" + "═" * 110)
    print("  PORTFOLIO vs BTC-ONLY — FINAL RANKING  (2021-01 → 2026-03)")
    print("═" * 110)
    hdr = (f"  {'#':>2}  {'Key':<10}  {'Type':<12}  {'ROI':>8}  "
           f"{'Portfolio':>12}  {'Net Profit':>12}  {'Max DD':>8}  "
           f"{'Calmar':>7}  {'BTC Held':>9}  {'ETH Held':>9}  {'ADA Held':>10}")
    print(hdr)
    print("  " + "-" * 106)
    fmt = ("  {rank:>2}  {key:<10}  {type_:<12}  {roi:>7.1f}%  "
           "${port:>11,.0f}  ${profit:>11,.0f}  {dd:>7.1f}%  "
           "{cal:>7.3f}  {btc:>9.4f}  {eth:>9.3f}  {ada:>10.0f}")
    for _, row in df.iterrows():
        print(fmt.format(
            rank=row["Rank"], key=row["Key"], type_=row["Type"],
            roi=row["ROI %"], port=row["Portfolio $"],
            profit=row["Net Profit $"], dd=row["Max DD %"],
            cal=row["Calmar"], btc=row["BTC Held"],
            eth=row["ETH Held"], ada=row["ADA Held"]))
    print("═" * 110)

    # Portfolio vs BTC-only same strategy
    print("\n  Same-strategy comparison: Portfolio 40/30/30  vs  BTC-only 100%")
    print("  " + "-" * 80)
    pairs = [("P1-DCA","B1-DCA"), ("P2-MAcon","B2-MAcon"), ("P3-BMOD","B3-BMOD")]
    for pk, bk in pairs:
        pr = df[df["Key"] == pk].iloc[0]
        br = df[df["Key"] == bk].iloc[0]
        diff = pr["ROI %"] - br["ROI %"]
        sign = "+" if diff >= 0 else ""
        winner = "Portfolio" if diff >= 0 else "BTC-only "
        print(f"  {pr['Strategy']:<40}  {pr['ROI %']:>7.1f}%")
        print(f"  {br['Strategy']:<40}  {br['ROI %']:>7.1f}%")
        print(f"  → {winner} wins by  {sign}{diff:.1f}%   "
              f"(${abs(pr['Portfolio $'] - br['Portfolio $']):,.0f} difference)\n")


# ══════════════════════════════════════════════
# 6. 可视化
# ══════════════════════════════════════════════

ASSET_COLORS = {"BTC": "#f7931a", "ETH": "#627eea", "ADA": "#0033ad"}

def plot_all(asset_dfs: dict, results: dict, ranking: pd.DataFrame, out_path: str):
    fig = plt.figure(figsize=(18, 24))
    gs  = gridspec.GridSpec(5, 2, figure=fig, hspace=0.38, wspace=0.28,
                            height_ratios=[1.0, 1.1, 1.0, 1.0, 1.0])

    # ── Panel 0: Asset prices normalised to 100 at start ──
    ax0 = fig.add_subplot(gs[0, :])
    for asset, color in ASSET_COLORS.items():
        s = asset_dfs[asset]["close"]
        s = s[s.index >= "2021-01-01"]
        ax0.plot(s.index, s / s.iloc[0] * 100, color=color,
                 lw=1.8, label=f"{asset} (normalised)")
    ax0.axhline(100, color="black", lw=0.8, ls="--", alpha=0.4)
    ax0.set_ylabel("Normalised Price (start = 100)")
    ax0.legend(fontsize=10)
    ax0.set_title("BTC / ETH / ADA — Normalised Performance (Jan 2021 = 100)", fontsize=11, fontweight="bold")
    ax0.grid(True, alpha=0.25)

    # ── Panel 1 (full row): Portfolio value all strategies ──
    ax1 = fig.add_subplot(gs[1, :])
    for key, cfg in PORTFOLIO_STRATEGIES.items():
        r    = results[key]
        rank = ranking.loc[ranking["Key"] == key, "Rank"].values[0]
        lw   = 2.4 if rank <= 3 else 1.2
        ls   = "-"  if "Portfolio" in cfg["label"] else "--"
        ax1.plot(r.index, r["portfolio_value"], color=cfg["color"],
                 lw=lw, ls=ls, label=f"#{rank} {key}: {cfg['label']}", alpha=0.9)
    ax1.plot(results["B1-DCA"].index, results["B1-DCA"]["total_cash_in"],
             color="black", lw=1.0, ls=":", alpha=0.5, label="Total Cash Deployed")
    ax1.set_ylabel("Portfolio Value (USD)")
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax1.legend(fontsize=8, ncol=2)
    ax1.set_title("Portfolio Value: All Strategies vs BTC-only", fontsize=11, fontweight="bold")
    ax1.grid(True, alpha=0.25)

    # ── Panel 2,0: Asset breakdown for best portfolio strategy ──
    best_portfolio = ranking[ranking["Type"] == "Portfolio"].iloc[0]["Key"]
    ax2a = fig.add_subplot(gs[2, 0])
    r_best = results[best_portfolio]
    btc_v = r_best["BTC_holdings"] * r_best["BTC_price"]
    eth_v = r_best["ETH_holdings"] * r_best["ETH_price"]
    ada_v = r_best["ADA_holdings"] * r_best["ADA_price"]
    ax2a.stackplot(r_best.index,
                   [btc_v, eth_v, ada_v],
                   labels=["BTC value", "ETH value", "ADA value"],
                   colors=[ASSET_COLORS["BTC"], ASSET_COLORS["ETH"], ASSET_COLORS["ADA"]],
                   alpha=0.75)
    ax2a.plot(r_best.index, r_best["portfolio_value"], color="black",
              lw=1.2, ls="--", label="Total (incl. savings)")
    ax2a.set_ylabel("USD")
    ax2a.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax2a.legend(fontsize=8, ncol=2)
    ax2a.set_title(f"Asset Breakdown — {best_portfolio} ({PORTFOLIO_STRATEGIES[best_portfolio]['label']})",
                   fontsize=9, fontweight="bold")
    ax2a.grid(True, alpha=0.25)

    # ── Panel 2,1: MA indicators per asset ──
    ax2b = fig.add_subplot(gs[2, 1])
    for asset, color in ASSET_COLORS.items():
        d = asset_dfs[asset]
        d = d[d.index >= "2021-01-01"]
        ratio = d["close"] / d["ma200w"]
        ax2b.plot(d.index, ratio, color=color, lw=1.5, label=f"{asset} price/MA200w")
    ax2b.axhline(1.0, color="black", lw=1.2, ls="--", alpha=0.6, label="MA = price")
    ax2b.axhline(1.5, color="gray",  lw=0.8, ls=":", alpha=0.5, label="1.5× MA (save threshold)")
    ax2b.fill_between(d.index, 0, 1,
                      alpha=0.08, color="green")
    ax2b.set_ylabel("Price / 200-Week MA ratio")
    ax2b.legend(fontsize=8)
    ax2b.set_title("Price vs 200-Week MA (ratio): All 3 Assets", fontsize=9, fontweight="bold")
    ax2b.grid(True, alpha=0.25)

    # ── Panel 3,0: ROI % comparison ──
    ax3a = fig.add_subplot(gs[3, 0])
    for key, cfg in PORTFOLIO_STRATEGIES.items():
        r    = results[key]
        rank = ranking.loc[ranking["Key"] == key, "Rank"].values[0]
        lw   = 2.0 if rank <= 3 else 1.0
        ls   = "-" if "Portfolio" in cfg["label"] else "--"
        ax3a.plot(r.index, r["roi_pct"], color=cfg["color"], lw=lw, ls=ls,
                  label=f"#{rank} {key}", alpha=0.9)
    ax3a.axhline(0, color="black", lw=0.8, ls="-", alpha=0.4)
    ax3a.set_ylabel("ROI %")
    ax3a.legend(fontsize=8, ncol=2)
    ax3a.set_title("Rolling ROI % Over Time", fontsize=9, fontweight="bold")
    ax3a.grid(True, alpha=0.25)

    # ── Panel 3,1: Savings pool ──
    ax3b = fig.add_subplot(gs[3, 1])
    for key, cfg in PORTFOLIO_STRATEGIES.items():
        r    = results[key]
        rank = ranking.loc[ranking["Key"] == key, "Rank"].values[0]
        lw   = 1.8 if rank <= 3 else 0.9
        ls   = "-" if "Portfolio" in cfg["label"] else "--"
        ax3b.plot(r.index, r["total_savings"], color=cfg["color"], lw=lw, ls=ls,
                  label=f"#{rank} {key}", alpha=0.9)
    ax3b.set_ylabel("Total Savings Pool (USD)")
    ax3b.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax3b.legend(fontsize=8, ncol=2)
    ax3b.set_title("Savings Pool Over Time", fontsize=9, fontweight="bold")
    ax3b.grid(True, alpha=0.25)

    # ── Panel 4 (full row): Final ROI bar chart ──
    ax4 = fig.add_subplot(gs[4, :])
    rank_df = ranking.sort_values("ROI %", ascending=True)
    bar_colors = [PORTFOLIO_STRATEGIES[k]["color"] for k in rank_df["Key"]]
    hatches    = ["" if t == "Portfolio" else "//" for t in rank_df["Type"]]
    bars = ax4.barh(
        [f"#{r} {k}" for r, k in zip(rank_df["Rank"], rank_df["Key"])],
        rank_df["ROI %"], color=bar_colors, edgecolor="white", height=0.6)
    for bar, h in zip(bars, hatches):
        bar.set_hatch(h)
    for bar, (_, row) in zip(bars, rank_df.iterrows()):
        ax4.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                 f"{row['ROI %']:.1f}%  (${row['Portfolio $']:,.0f})",
                 va="center", fontsize=8.5)
    ax4.set_xlabel("Final ROI %")
    ax4.set_xlim(0, ranking["ROI %"].max() * 1.25)
    ax4.set_title(
        "Final ROI: Portfolio 40/30/30 (solid) vs BTC-only (hatched) — same strategies",
        fontsize=10, fontweight="bold")
    ax4.grid(True, alpha=0.25, axis="x")

    from matplotlib.patches import Patch
    legend_els = [
        Patch(facecolor="#aaaaaa", label="Portfolio 40/30/30"),
        Patch(facecolor="#aaaaaa", hatch="//", label="BTC-only 100%"),
    ]
    ax4.legend(handles=legend_els, fontsize=9, loc="lower right")

    fig.suptitle(
        "Multi-Asset Portfolio Backtest: BTC 40% + ETH 30% + ADA 30%\n"
        "vs BTC-only  |  2021-01 → 2026-03  |  Budget $1000/2wks (USD)",
        fontsize=13, fontweight="bold", y=0.998)

    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"\nChart saved: {out_path}")


# ══════════════════════════════════════════════
# 7. 主程序
# ══════════════════════════════════════════════

def main():
    print("Downloading market data ...")
    raw = {}
    for asset in ["BTC", "ETH", "ADA"]:
        raw[asset] = fetch_weekly(asset)

    print("\nBuilding indicators ...")
    asset_dfs = {}
    for asset in ["BTC", "ETH", "ADA"]:
        asset_dfs[asset] = build_indicators(raw[asset], asset)

    print("\nRunning portfolio backtests ...")
    results = {}
    for key, cfg in PORTFOLIO_STRATEGIES.items():
        print(f"  {key}: {cfg['label']} ...")
        results[key] = run_portfolio(asset_dfs, key, cfg, start_date="2021-01-01")

    ranking = analyse_portfolios(results)
    print_results(ranking)

    out = "/home/user/CLAUDE-PLAYGROUND/btc_eth_ada_backtest.png"
    plot_all(asset_dfs, results, ranking, out_path=out)

    csv_out = "/home/user/CLAUDE-PLAYGROUND/btc_eth_ada_ranking.csv"
    ranking.to_csv(csv_out, index=False, float_format="%.4f")
    print(f"Ranking CSV saved: {csv_out}")


if __name__ == "__main__":
    main()
