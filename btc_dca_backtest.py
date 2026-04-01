"""
BTC DCA Backtest: 3-way comparison
====================================
All strategies start 2024-01-15 with $0, $1000 AUD arrives every 2 weeks.

Strategy 1 – MA-based DCA (buy only):
  Each week invest $500 / ratio  (ratio = price / MA200)
  · ratio < 1 (below MA): invest >$500, draw extra from savings
  · ratio > 1 (above MA): invest <$500 (leftover stays in cash pool)
  End of each 2-week cycle: unspent cash swept into savings

Strategy 2 – Simple DCA:
  $500 every week, no conditions

Strategy 3 – Dynamic Buy & Sell:
  Same buy logic as S1, PLUS:
  · ratio > 1 (above MA): also SELL  $500 * (ratio - 1)  worth of BTC
    → sell proceeds go directly into savings
  This takes profit when price is stretched above MA and recycles it
  into heavy purchases when price dips below MA.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ──────────────────────────────────────────────
# 1. Download & prep data
# ──────────────────────────────────────────────
print("Downloading BTC/AUD weekly data…")
raw = yf.download("BTC-AUD", start="2019-01-01", interval="1wk",
                  progress=False, auto_adjust=True)

close = (raw["Close"]["BTC-AUD"] if isinstance(raw.columns, pd.MultiIndex)
         else raw["Close"])
close = close.dropna().sort_index()

ma200 = close.rolling(window=200).mean()

START       = pd.Timestamp("2024-01-15")
prices_all  = close[close.index >= START]
ma200_all   = ma200[close.index >= START]

valid      = ma200_all.notna()
prices_bt  = prices_all[valid]
ma200_bt   = ma200_all[valid]

print(f"Window : {prices_bt.index[0].date()} → {prices_bt.index[-1].date()}")
print(f"Weeks  : {len(prices_bt)}\n")


# ──────────────────────────────────────────────
# helper: run one strategy loop
# ──────────────────────────────────────────────
def run_strategy(prices, ma200, sell_above_ma=False):
    """
    sell_above_ma=False → Strategy 1 (buy-only MA DCA)
    sell_above_ma=True  → Strategy 3 (buy+sell MA DCA)
    """
    cash = 0.0
    savings = 0.0
    btc = 0.0
    total_bought = 0.0   # cumulative AUD spent buying
    total_sold   = 0.0   # cumulative AUD received from selling
    records = []

    for week_num, (date, price) in enumerate(zip(prices.index, prices.values)):
        price = float(price)
        ma    = float(ma200[date])
        ratio = price / ma

        # ── inject $1000 every 2 weeks ──
        if week_num % 2 == 0:
            cash += 1000.0

        # ── BUY logic ──
        target_buy = 500.0 / ratio   # more when cheap, less when expensive

        if ratio < 1.0:
            from_cash    = min(cash, target_buy)
            from_savings = min(max(0.0, target_buy - from_cash), savings)
            buy_amt      = from_cash + from_savings
            cash        -= from_cash
            savings     -= from_savings
        else:
            buy_amt = min(target_buy, cash)
            cash   -= buy_amt

        btc          += buy_amt / price
        total_bought += buy_amt

        # ── SELL logic (Strategy 3 only) ──
        sell_amt = 0.0
        if sell_above_ma and ratio > 1.0:
            target_sell = 500.0 * (ratio - 1.0)   # sell more the further above MA
            sell_btc    = min(target_sell / price, btc)   # can't sell more than we have
            sell_amt    = sell_btc * price
            btc        -= sell_btc
            savings    += sell_amt    # proceeds into savings
            total_sold += sell_amt

        # ── end-of-cycle sweep ──
        if week_num % 2 == 1:
            savings += cash
            cash     = 0.0

        pv = btc * price + cash + savings
        records.append(dict(
            date=date, price=price, ma200=ma, ratio=ratio,
            buy_amt=buy_amt, sell_amt=sell_amt,
            btc_held=btc, cash=cash, savings=savings,
            portfolio_value=pv,
            total_bought=total_bought, total_sold=total_sold,
            net_invested=total_bought - total_sold,
        ))

    return pd.DataFrame(records).set_index("date")


# ──────────────────────────────────────────────
# 2. Run strategies
# ──────────────────────────────────────────────
df1 = run_strategy(prices_bt, ma200_bt, sell_above_ma=False)   # S1: buy-only MA
df3 = run_strategy(prices_bt, ma200_bt, sell_above_ma=True)    # S3: buy+sell MA

# Strategy 2 – simple DCA
btc_s2 = 0.0
records_s2 = []
for date, price in zip(prices_bt.index, prices_bt.values):
    price   = float(price)
    btc_s2 += 500.0 / price
    records_s2.append(dict(
        date=date, price=price, btc_held=btc_s2,
        portfolio_value=btc_s2 * price,
        net_invested=500.0 * (len(records_s2) + 1),
    ))
df2 = pd.DataFrame(records_s2).set_index("date")


# ──────────────────────────────────────────────
# 3. Print results
# ──────────────────────────────────────────────
final_price   = float(prices_bt.iloc[-1])
n_cycles      = (len(prices_bt) + 1) // 2
total_contrib = n_cycles * 1000   # same for S1 & S3; S2 = len*500 ≈ equal

r1, r2, r3 = df1.iloc[-1], df2.iloc[-1], df3.iloc[-1]

def roi(portfolio, contributed):
    return (portfolio / contributed - 1) * 100

roi1 = roi(r1["portfolio_value"], total_contrib)
roi2 = roi(r2["portfolio_value"], r2["net_invested"])
roi3 = roi(r3["portfolio_value"], total_contrib)

lines = [
    ("STRATEGY 1", "MA-based DCA  (buy only)",    r1, total_contrib, False),
    ("STRATEGY 2", "Simple DCA  $500/week",        r2, r2["net_invested"], False),
    ("STRATEGY 3", "Dynamic Buy+Sell  (MA signal)", r3, total_contrib, True),
]

for label, desc, r, contrib, has_sell in lines:
    print("=" * 58)
    print(f"  {label} : {desc}")
    print("=" * 58)
    print(f"  Capital contributed  : ${contrib:>10,.2f} AUD")
    if has_sell:
        print(f"  Total bought         : ${r['total_bought']:>10,.2f} AUD")
        print(f"  Total sold           : ${r['total_sold']:>10,.2f} AUD")
        print(f"  Net deployed         : ${r['net_invested']:>10,.2f} AUD")
    liquid = r.get('savings', 0) + r.get('cash', 0)
    print(f"  Savings / cash       : ${liquid:>10,.2f} AUD")
    print(f"  BTC held             : {r['btc_held']:>14.6f} BTC")
    avg = r["net_invested"] / r["btc_held"] if r["btc_held"] > 0 else 0
    print(f"  Avg net cost / BTC   : ${avg:>10,.2f} AUD")
    print(f"  BTC market value     : ${r['btc_held']*final_price:>10,.2f} AUD")
    print(f"  Total portfolio      : ${r['portfolio_value']:>10,.2f} AUD")
    print(f"  ROI on contributed   : {roi(r['portfolio_value'], contrib):>+.1f}%")
    print()

print("=" * 58)
print("  RANKING")
print("=" * 58)
results = [
    ("Strategy 1 (MA buy-only)", r1["portfolio_value"]),
    ("Strategy 2 (Simple DCA)",  r2["portfolio_value"]),
    ("Strategy 3 (Dynamic B+S)", r3["portfolio_value"]),
]
for rank, (name, pv) in enumerate(sorted(results, key=lambda x: -x[1]), 1):
    print(f"  #{rank}  {name:<30}  ${pv:>10,.2f} AUD")
print(f"\n  BTC price at end: ${final_price:,.2f} AUD")


# ──────────────────────────────────────────────
# 4. Charts
# ──────────────────────────────────────────────
fig, axes = plt.subplots(4, 1, figsize=(14, 20))
fig.suptitle(
    "BTC DCA Backtest — 3-Strategy Comparison (AUD, weekly, from 2024-01-15)\n"
    "S1: MA buy-only | S2: Simple DCA | S3: Dynamic Buy+Sell",
    fontsize=13, fontweight="bold", y=0.99,
)
date_fmt = mdates.DateFormatter("%Y-%m")
C1, C2, C3 = "#2196F3", "#FF9800", "#4CAF50"

# A: Portfolio value
ax = axes[0]
ax.plot(df1.index, df1["portfolio_value"], label="S1: MA buy-only",     color=C1, lw=2)
ax.plot(df2.index, df2["portfolio_value"], label="S2: Simple DCA",      color=C2, lw=2, ls="--")
ax.plot(df3.index, df3["portfolio_value"], label="S3: Dynamic Buy+Sell",color=C3, lw=2, ls="-.")
ax.axhline(total_contrib, color="grey", lw=1, ls=":", label=f"Total contributed (${total_contrib:,.0f})")
ax.set_title("Portfolio Value (AUD)  — includes BTC + savings + cash")
ax.set_ylabel("AUD")
ax.legend(loc="upper left", fontsize=9)
ax.grid(True, alpha=0.3)

# B: BTC price vs MA200
ax = axes[1]
ax.plot(prices_bt.index, prices_bt.values,  label="BTC/AUD", color="#F7931A", lw=1.5)
ax.plot(ma200_bt.index,  ma200_bt.values,   label="200-week MA", color="#E91E63", lw=2, ls="--")
ax.fill_between(prices_bt.index, prices_bt.values, ma200_bt.values,
                where=prices_bt.values < ma200_bt.values,
                alpha=0.15, color="green", label="Below MA (buy aggressively)")
ax.fill_between(prices_bt.index, prices_bt.values, ma200_bt.values,
                where=prices_bt.values >= ma200_bt.values,
                alpha=0.07, color="red", label="Above MA (buy less / sell in S3)")
ax.set_title("BTC/AUD Price vs 200-Week Moving Average")
ax.set_ylabel("AUD / BTC")
ax.legend(fontsize=9)
ax.grid(True, alpha=0.3)

# C: Weekly action for S3 (buy vs sell bars)
ax = axes[2]
buy_vals  = df3["buy_amt"].values
sell_vals = -df3["sell_amt"].values   # negative for visual
ax.bar(df3.index, buy_vals,  width=5, alpha=0.8, color=C1,  label="S3 weekly buy")
ax.bar(df3.index, sell_vals, width=5, alpha=0.8, color="red", label="S3 weekly sell (negative)")
ax.plot(df3.index, df3["savings"], color=C3, lw=1.5, label="S3 savings balance")
ax.axhline(0, color="black", lw=0.5)
ax.axhline(500, color=C2, lw=1, ls="--", alpha=0.6, label="S2 fixed $500/wk")
ax.set_title("Strategy 3 — Weekly Buy/Sell Amount & Savings Balance")
ax.set_ylabel("AUD")
ax.legend(fontsize=9)
ax.grid(True, alpha=0.3)

# D: Cumulative BTC held
ax = axes[3]
ax.plot(df1.index, df1["btc_held"], label="S1: MA buy-only",      color=C1, lw=2)
ax.plot(df2.index, df2["btc_held"], label="S2: Simple DCA",        color=C2, lw=2, ls="--")
ax.plot(df3.index, df3["btc_held"], label="S3: Dynamic Buy+Sell",  color=C3, lw=2, ls="-.")
ax.set_title("Cumulative BTC Held")
ax.set_ylabel("BTC")
ax.legend(fontsize=9)
ax.grid(True, alpha=0.3)

for ax in axes:
    ax.xaxis.set_major_formatter(date_fmt)
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")

plt.tight_layout(rect=[0, 0, 1, 0.97])
out_path = "/home/user/CLAUDE-PLAYGROUND/btc_dca_backtest.png"
plt.savefig(out_path, dpi=150, bbox_inches="tight")
print(f"\nChart saved → {out_path}")
