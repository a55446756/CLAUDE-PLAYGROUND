"""
BTC DCA Backtest: MA-based vs Simple DCA
==========================================
Strategy 1 (MA-based):
  - $1000 AUD arrives every 2 weeks
  - Each week, invest based on proximity to 200-week MA:
      invest = $500 / ratio  (ratio = price / MA200)
  - Above MA (ratio > 1): invest less than $500
  - Below MA (ratio < 1): invest more than $500, drawing from savings
  - End of 2-week cycle: unspent cash moves to savings

Strategy 2 (Simple DCA):
  - $500 AUD every week, no conditions

Comparison start: 2024-01-15
"""

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

# ──────────────────────────────────────────────
# 1. Download data
# ──────────────────────────────────────────────
print("Downloading BTC/AUD weekly data (from 2019 to calculate 200-week MA)...")
raw = yf.download("BTC-AUD", start="2019-01-01", interval="1wk", progress=False, auto_adjust=True)

if isinstance(raw.columns, pd.MultiIndex):
    close = raw["Close"]["BTC-AUD"]
else:
    close = raw["Close"]

close = close.dropna().sort_index()

# ──────────────────────────────────────────────
# 2. Compute 200-week MA
# ──────────────────────────────────────────────
ma200 = close.rolling(window=200).mean()

# ──────────────────────────────────────────────
# 3. Slice to backtest window
# ──────────────────────────────────────────────
START = pd.Timestamp("2024-01-15")
prices_all = close[close.index >= START]
ma200_all  = ma200[close.index >= START]

# Keep only weeks where MA200 is available
valid       = ma200_all.notna()
prices_bt   = prices_all[valid]
ma200_bt    = ma200_all[valid]

print(f"Backtest window : {prices_bt.index[0].date()} → {prices_bt.index[-1].date()}")
print(f"Total weeks     : {len(prices_bt)}\n")

# ──────────────────────────────────────────────
# 4. Strategy 1 – MA-based DCA
# ──────────────────────────────────────────────
cash         = 0.0   # funds available for purchase in current 2-week cycle
savings      = 0.0   # accumulated unspent capital
btc_s1       = 0.0
total_inv_s1 = 0.0
records_s1   = []

for week_num, (date, price) in enumerate(zip(prices_bt.index, prices_bt.values)):
    ma = ma200_bt[date]

    # Add $1000 at the start of every 2-week cycle
    if week_num % 2 == 0:
        cash += 1000.0

    ratio = float(price) / float(ma)

    # Target investment this week: proportionally higher when closer to / below MA
    target = 500.0 / ratio   # $500 at MA, more below, less above

    if ratio < 1.0:
        # Below MA → use all available cash, then draw from savings
        from_cash    = min(cash, target)
        still_needed = max(0.0, target - from_cash)
        from_savings = min(still_needed, savings)
        actual       = from_cash + from_savings
        cash         -= from_cash
        savings      -= from_savings
    else:
        # Above MA → only spend from available cash, no savings draw
        actual = min(target, cash)
        cash  -= actual

    btc_s1       += actual / float(price)
    total_inv_s1 += actual

    # End of 2-week cycle: sweep remaining cash into savings
    if week_num % 2 == 1:
        savings += cash
        cash     = 0.0

    pv = btc_s1 * float(price) + cash + savings
    records_s1.append(dict(
        date=date, price=float(price), ma200=float(ma),
        ratio=ratio, invested=actual,
        btc_held=btc_s1, cash=cash, savings=savings,
        portfolio_value=pv, total_invested=total_inv_s1
    ))

df1 = pd.DataFrame(records_s1).set_index("date")

# ──────────────────────────────────────────────
# 5. Strategy 2 – Simple DCA $500 / week
# ──────────────────────────────────────────────
btc_s2       = 0.0
total_inv_s2 = 0.0
records_s2   = []

for date, price in zip(prices_bt.index, prices_bt.values):
    invest        = 500.0
    btc_s2       += invest / float(price)
    total_inv_s2 += invest
    records_s2.append(dict(
        date=date, price=float(price), invested=invest,
        btc_held=btc_s2,
        portfolio_value=btc_s2 * float(price),
        total_invested=total_inv_s2
    ))

df2 = pd.DataFrame(records_s2).set_index("date")

# ──────────────────────────────────────────────
# 6. Print summary
# ──────────────────────────────────────────────
final_price = float(prices_bt.iloc[-1])
n_cycles    = (len(prices_bt) + 1) // 2   # number of 2-week cycles
total_contrib_s1 = n_cycles * 1000

r1 = df1.iloc[-1]
r2 = df2.iloc[-1]

roi1 = (r1["portfolio_value"] / total_contrib_s1 - 1) * 100
roi2 = (r2["portfolio_value"] / r2["total_invested"] - 1) * 100

avg_buy_s1 = r1["total_invested"] / r1["btc_held"]
avg_buy_s2 = r2["total_invested"] / r2["btc_held"]

print("=" * 56)
print("  STRATEGY 1 : MA-based DCA (200-week MA signal)")
print("=" * 56)
print(f"  Capital contributed  : ${total_contrib_s1:>10,.2f} AUD")
print(f"  Total deployed       : ${r1['total_invested']:>10,.2f} AUD")
print(f"  Savings remaining    : ${r1['savings']:>10,.2f} AUD")
print(f"  BTC accumulated      : {r1['btc_held']:>14.6f} BTC")
print(f"  Avg buy price        : ${avg_buy_s1:>10,.2f} AUD/BTC")
print(f"  Final BTC value      : ${r1['btc_held']*final_price:>10,.2f} AUD")
print(f"  Total portfolio      : ${r1['portfolio_value']:>10,.2f} AUD")
print(f"  ROI on contributed   : {roi1:>+.1f}%")

print()
print("=" * 56)
print("  STRATEGY 2 : Simple DCA $500/week")
print("=" * 56)
print(f"  Capital contributed  : ${r2['total_invested']:>10,.2f} AUD")
print(f"  BTC accumulated      : {r2['btc_held']:>14.6f} BTC")
print(f"  Avg buy price        : ${avg_buy_s2:>10,.2f} AUD/BTC")
print(f"  Final BTC value      : ${r2['portfolio_value']:>10,.2f} AUD")
print(f"  Total portfolio      : ${r2['portfolio_value']:>10,.2f} AUD")
print(f"  ROI on contributed   : {roi2:>+.1f}%")

print()
print("=" * 56)
print("  WINNER")
print("=" * 56)
if r1["portfolio_value"] > r2["portfolio_value"]:
    diff = r1["portfolio_value"] - r2["portfolio_value"]
    print(f"  Strategy 1 (MA-based) wins by ${diff:,.2f} AUD  (+{diff/r2['portfolio_value']*100:.1f}%)")
else:
    diff = r2["portfolio_value"] - r1["portfolio_value"]
    print(f"  Strategy 2 (Simple DCA) wins by ${diff:,.2f} AUD  (+{diff/r1['portfolio_value']*100:.1f}%)")
print(f"  BTC price at end: ${final_price:,.2f} AUD")

# ──────────────────────────────────────────────
# 7. Charts
# ──────────────────────────────────────────────
fig, axes = plt.subplots(4, 1, figsize=(14, 18))
fig.suptitle("BTC DCA Backtest: MA-based vs Simple DCA\n(AUD, weekly, from 2024-01-15)",
             fontsize=14, fontweight="bold", y=0.98)

date_fmt = mdates.DateFormatter("%Y-%m")

# ── Chart A: Portfolio value ──
ax = axes[0]
ax.plot(df1.index, df1["portfolio_value"], label="Strategy 1: MA-based DCA", color="#2196F3", lw=2)
ax.plot(df2.index, df2["portfolio_value"], label="Strategy 2: Simple DCA $500/wk", color="#FF9800", lw=2, ls="--")
ax.fill_between(df1.index, df1["portfolio_value"], df2["portfolio_value"],
                where=df1["portfolio_value"] >= df2["portfolio_value"],
                alpha=0.1, color="#2196F3", label="S1 ahead")
ax.fill_between(df1.index, df1["portfolio_value"], df2["portfolio_value"],
                where=df1["portfolio_value"] < df2["portfolio_value"],
                alpha=0.1, color="#FF9800", label="S2 ahead")
ax.set_title("Portfolio Value (AUD)")
ax.set_ylabel("AUD")
ax.legend(loc="upper left")
ax.grid(True, alpha=0.3)
ax.xaxis.set_major_formatter(date_fmt)

# ── Chart B: BTC price vs MA200 ──
ax = axes[1]
ax.plot(prices_bt.index, prices_bt.values, label="BTC/AUD Price", color="#F7931A", lw=1.5)
ax.plot(ma200_bt.index, ma200_bt.values, label="200-week MA", color="#E91E63", lw=2, ls="--")
ax.fill_between(prices_bt.index, prices_bt.values, ma200_bt.values,
                where=prices_bt.values < ma200_bt.values,
                alpha=0.2, color="green", label="Below MA (buy zone)")
ax.set_title("BTC/AUD Price vs 200-Week Moving Average")
ax.set_ylabel("AUD / BTC")
ax.legend()
ax.grid(True, alpha=0.3)
ax.xaxis.set_major_formatter(date_fmt)

# ── Chart C: Weekly investment S1 vs S2 ──
ax = axes[2]
ax.bar(df1.index, df1["invested"], width=5, alpha=0.7,
       label="Strategy 1: weekly deployed", color="#2196F3")
ax.axhline(500, color="#FF9800", lw=1.5, ls="--", label="Strategy 2: $500/wk")
ax.plot(df1.index, df1["savings"], color="#4CAF50", lw=1.5, label="S1 savings balance")
ax.set_title("Weekly Investment Amount & Savings Balance (AUD)")
ax.set_ylabel("AUD")
ax.legend()
ax.grid(True, alpha=0.3)
ax.xaxis.set_major_formatter(date_fmt)

# ── Chart D: Cumulative BTC accumulated ──
ax = axes[3]
ax.plot(df1.index, df1["btc_held"], label="Strategy 1: MA-based", color="#2196F3", lw=2)
ax.plot(df2.index, df2["btc_held"], label="Strategy 2: Simple DCA", color="#FF9800", lw=2, ls="--")
ax.set_title("Cumulative BTC Accumulated")
ax.set_ylabel("BTC")
ax.legend()
ax.grid(True, alpha=0.3)
ax.xaxis.set_major_formatter(date_fmt)

for ax in axes:
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")

plt.tight_layout(rect=[0, 0, 1, 0.97])
out_path = "/home/user/CLAUDE-PLAYGROUND/btc_dca_backtest.png"
plt.savefig(out_path, dpi=150, bbox_inches="tight")
print(f"\nChart saved → {out_path}")
