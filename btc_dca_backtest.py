"""
BTC DCA 回测: 200周均线策略 vs 简单DCA
从2021年开始，每两周1000澳币预算

策略1 (MA策略):
  - 每2周 +1000 USD 可用资金
  - 分配比例 = min(1.0, MA200w / price)  → 越接近均线买越多
  - 未使用资金进入存款池
  - 当价格低于200周MA时，从存款中额外提取 (比例 = 偏离程度)

策略2 (简单DCA):
  - 每周固定投入500 USD

数据源: CoinGecko (BTC/USD 日线, 重采样为周线)
"""

import json
import time
import requests
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from datetime import datetime, timezone

# ─────────────────────────────────────────────
# 1. 获取历史数据
# ─────────────────────────────────────────────

def fetch_btc_weekly_kraken() -> pd.Series:
    """
    从 Kraken 公共 API 获取 BTC/USD 周线收盘价 (无需 API key)
    interval=10080 (分钟) = 1周; Kraken 返回最近 ~650 条历史数据
    注意: 数据为 USD, 但两种策略用相同货币, 相对结论不变
    """
    url = "https://api.kraken.com/0/public/OHLC"
    params = {"pair": "XBTUSD", "interval": 10080}

    print("正在从 Kraken 下载 BTC/USD 周线数据 ...")
    for attempt in range(5):
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if data.get("error"):
                raise RuntimeError(f"Kraken error: {data['error']}")
            result = data["result"]
            key    = [k for k in result if k != "last"][0]
            candles = result[key]
            break
        except Exception as e:
            print(f"  Request error: {e}, retrying in 5s ...")
            time.sleep(5)
    else:
        raise RuntimeError("无法获取数据")

    # Kraken OHLC: [time, open, high, low, close, vwap, volume, count]
    df = pd.DataFrame(candles, columns=["time","open","high","low","close",
                                         "vwap","volume","count"])
    df["date"]  = pd.to_datetime(df["time"].astype(int), unit="s", utc=True)
    df["close"] = df["close"].astype(float)
    df = df.drop_duplicates("date").set_index("date")["close"].sort_index()
    print(f"  获取到 {len(df)} 条周线数据  ({df.index[0].date()} → {df.index[-1].date()})")
    return df


def build_weekly_df(weekly_close: pd.Series) -> pd.DataFrame:
    """计算 200周MA"""
    df = weekly_close.to_frame("close")
    df["ma200w"] = df["close"].rolling(200, min_periods=1).mean()
    return df


# ─────────────────────────────────────────────
# 2. 回测引擎
# ─────────────────────────────────────────────

def backtest_ma_strategy(weekly: pd.DataFrame,
                          biweekly_budget: float = 1000.0,
                          savings_draw_cap: float = 0.30) -> pd.DataFrame:
    """
    MA 策略
    -------
    每2周: available_funds += 1000
    本周分配比例:
      - price >= ma: invest_pct = ma / price  (越高于均线买越少)
      - price <  ma: invest_pct = 1.0 + 从存款额外提取
          extra = savings * min(savings_draw_cap, (ma - price)/ma)

    剩余资金 → 存款池 (计息 = 0, 简化处理)
    """
    btc      = 0.0
    savings  = 0.0
    avail    = 0.0
    total_in = 0.0

    rows = []
    for i, (date, row) in enumerate(weekly.iterrows()):
        price = float(row["close"])
        ma    = float(row["ma200w"])

        # 每两周补充预算
        if i % 2 == 0:
            avail += biweekly_budget

        ratio = ma / price  # >1 means below MA, <1 means above MA

        if ratio >= 1.0:
            # 价格 ≤ MA → 全投 + 从存款额外提取
            deviation = min(savings_draw_cap, (ma - price) / ma)
            extra     = savings * deviation
            invest    = avail + extra
            savings  -= extra
            avail     = 0.0
        else:
            # 价格 > MA → 按比例投入
            invest_pct = ratio          # ma/price ∈ (0, 1)
            invest     = avail * invest_pct
            savings   += avail - invest
            avail      = 0.0

        btc_bought = invest / price
        btc       += btc_bought
        total_in  += invest

        rows.append({
            "date":           date,
            "price":          price,
            "ma200w":         ma,
            "invested":       invest,
            "btc_held":       btc,
            "savings":        savings,
            "portfolio_value": btc * price + savings,
            "total_cash_in":  total_in + savings,
        })

    return pd.DataFrame(rows).set_index("date")


def backtest_dca_strategy(weekly: pd.DataFrame,
                           weekly_budget: float = 500.0) -> pd.DataFrame:
    """简单DCA: 每周固定投入 weekly_budget USD"""
    btc      = 0.0
    total_in = 0.0
    rows = []

    for date, row in weekly.iterrows():
        price      = float(row["close"])
        invest     = weekly_budget
        btc       += invest / price
        total_in  += invest

        rows.append({
            "date":           date,
            "price":          price,
            "invested":       invest,
            "btc_held":       btc,
            "portfolio_value": btc * price,
            "total_cash_in":  total_in,
        })

    return pd.DataFrame(rows).set_index("date")


# ─────────────────────────────────────────────
# 3. 输出结果
# ─────────────────────────────────────────────

def print_summary(name: str, df: pd.DataFrame):
    last       = df.iloc[-1]
    first_date = df.index[0].strftime("%Y-%m-%d")
    last_date  = df.index[-1].strftime("%Y-%m-%d")
    total_cash = last["total_cash_in"]
    port_val   = last["portfolio_value"]
    roi        = (port_val - total_cash) / total_cash * 100

    print(f"\n{'='*50}")
    print(f"  {name}")
    print(f"{'='*50}")
    print(f"  期间:          {first_date} → {last_date}")
    print(f"  累计投入:      $ {total_cash:,.0f}")
    print(f"  持有BTC:       {last['btc_held']:.6f} BTC")
    print(f"  组合总值:      $ {port_val:,.0f}")
    print(f"  净收益:        $ {port_val - total_cash:,.0f}")
    print(f"  ROI:           {roi:.1f}%")
    if "savings" in df.columns:
        print(f"  存款余额:      $ {last['savings']:,.0f}")


def plot_results(weekly: pd.DataFrame,
                 ma_res: pd.DataFrame,
                 dca_res: pd.DataFrame,
                 out_path: str = "btc_dca_backtest.png"):

    fig, axes = plt.subplots(3, 1, figsize=(14, 16), sharex=True)
    fig.suptitle("BTC DCA Backtest: 200-Week MA Strategy vs Simple DCA (2021-2026, USD)\n"
                 "Budget: MA Strategy $1000/2wk | Simple DCA $500/wk",
                 fontsize=13, fontweight="bold")

    # ── Panel 1: BTC price + 200-week MA ──
    ax1 = axes[0]
    ax1.semilogy(weekly.index, weekly["close"], color="#f7931a",
                 linewidth=1.2, label="BTC/USD Weekly Close")
    ax1.semilogy(weekly.index, weekly["ma200w"], color="#3b82f6",
                 linewidth=2, linestyle="--", label="200-Week MA")
    ax1.fill_between(weekly.index,
                     weekly["close"], weekly["ma200w"],
                     where=(weekly["close"] < weekly["ma200w"]),
                     alpha=0.25, color="green", label="Below MA (buy zone)")
    ax1.set_ylabel("BTC/USD (log scale)")
    ax1.legend(fontsize=9)
    ax1.set_title("BTC Price & 200-Week Moving Average", fontsize=11)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda x, _: f"${x:,.0f}"))
    ax1.grid(True, alpha=0.3)

    # ── Panel 2: Portfolio value comparison ──
    ax2 = axes[1]
    ax2.plot(ma_res.index,  ma_res["portfolio_value"],
             color="#10b981", linewidth=1.8, label="MA Strategy (BTC + savings)")
    ax2.plot(dca_res.index, dca_res["portfolio_value"],
             color="#8b5cf6", linewidth=1.8, label="Simple DCA $500/wk")
    ax2.plot(ma_res.index,  ma_res["total_cash_in"],
             color="#6b7280", linewidth=1.2, linestyle=":",
             label="MA Strategy total cash in")
    ax2.plot(dca_res.index, dca_res["total_cash_in"],
             color="#9ca3af", linewidth=1.0, linestyle=":",
             label="DCA total cash in")
    ax2.set_ylabel("USD")
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda x, _: f"${x:,.0f}"))
    ax2.legend(fontsize=9)
    ax2.set_title("Portfolio Value Comparison", fontsize=11)
    ax2.grid(True, alpha=0.3)

    # ── Panel 3: MA strategy — weekly spend & savings ──
    ax3 = axes[2]
    ax3.bar(ma_res.index, ma_res["invested"],
            width=5, color="#f59e0b", alpha=0.7, label="MA Strategy: weekly spend")
    ax3_r = ax3.twinx()
    ax3_r.plot(ma_res.index, ma_res["savings"],
               color="#ef4444", linewidth=1.5, label="MA Strategy: savings pool")
    ax3.set_ylabel("Weekly Spend ($)")
    ax3_r.set_ylabel("Savings Pool ($)", color="#ef4444")
    ax3_r.tick_params(axis="y", labelcolor="#ef4444")
    lines1, labels1 = ax3.get_legend_handles_labels()
    lines2, labels2 = ax3_r.get_legend_handles_labels()
    ax3.legend(lines1 + lines2, labels1 + labels2, fontsize=9)
    ax3.set_title("MA Strategy: Weekly Investment & Savings Pool", fontsize=11)
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"\n  图表已保存: {out_path}")


# ─────────────────────────────────────────────
# 4. 主程序
# ─────────────────────────────────────────────

def main():
    # --- 数据 ---
    weekly_close = fetch_btc_weekly_kraken()
    weekly       = build_weekly_df(weekly_close)

    # 回测只从2021-01-01起 (但MA用全量数据计算)
    weekly_bt = weekly[weekly.index >= "2021-01-01"].copy()

    print(f"\n回测区间: {weekly_bt.index[0].date()} → {weekly_bt.index[-1].date()}")
    print(f"共 {len(weekly_bt)} 个交易周")

    # --- 运行策略 ---
    ma_res  = backtest_ma_strategy(weekly_bt,
                                    biweekly_budget=1000.0,
                                    savings_draw_cap=0.30)
    dca_res = backtest_dca_strategy(weekly_bt, weekly_budget=500.0)

    # --- 摘要 ---
    print_summary("策略1: MA-200w 动态DCA (每2周$1000)", ma_res)
    print_summary("策略2: 简单DCA (每周$500)", dca_res)

    # 对比
    ma_roi  = (ma_res.iloc[-1]["portfolio_value"]  - ma_res.iloc[-1]["total_cash_in"])  / ma_res.iloc[-1]["total_cash_in"]  * 100
    dca_roi = (dca_res.iloc[-1]["portfolio_value"] - dca_res.iloc[-1]["total_cash_in"]) / dca_res.iloc[-1]["total_cash_in"] * 100

    print("\n" + "="*50)
    print("  策略对比总结")
    print("="*50)
    print(f"  MA策略  ROI: {ma_roi:.1f}%  |  组合值: ${ma_res.iloc[-1]['portfolio_value']:,.0f}")
    print(f"  DCA策略 ROI: {dca_roi:.1f}%  |  组合值: ${dca_res.iloc[-1]['portfolio_value']:,.0f}")

    diff = ma_res.iloc[-1]["portfolio_value"] - dca_res.iloc[-1]["portfolio_value"]
    winner = "MA策略" if diff > 0 else "简单DCA"
    print(f"\n  胜者: {winner}  (差额: ${abs(diff):,.0f})")

    # --- 图表 ---
    out = "/home/user/CLAUDE-PLAYGROUND/btc_dca_backtest.png"
    plot_results(weekly_bt, ma_res, dca_res, out_path=out)


if __name__ == "__main__":
    main()
