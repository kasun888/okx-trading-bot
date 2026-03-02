# 🤖 OKX Smart Trading Bot

> Intelligent BTC/USDT Day Trading Bot for Singapore traders
> Target: $20-30 SGD profit daily | Capital: $10,000 SGD

---

## 📋 What This Bot Does

- ✅ Trades BTC/USDT automatically (LONG & SHORT)
- ✅ 5-layer signal intelligence (not just RSI/MACD)
- ✅ Runs 24/7 via GitHub Actions (free!)
- ✅ Sends Telegram alerts for every trade
- ✅ Self-tunes every Sunday automatically
- ✅ Max $50 SGD daily loss protection
- ✅ Starts in DEMO mode (safe!)

---

## 🧠 5-Layer Signal System

| Layer | Source | What It Checks |
|-------|--------|----------------|
| 1 | Alternative.me | Fear & Greed Index |
| 2 | Yahoo Finance | DXY (USD strength) |
| 3 | Yahoo Finance | S&P500 + Gold correlation |
| 4 | CoinGecko | BTC Dominance + Whale data |
| 5 | OKX Public API | RSI + MACD + Funding Rate |

**Score 4/5 or 5/5 required to place trade.**

---

## ⚙️ Bot Settings (settings.json)

```json
{
  "position_size_pct": 0.30,    // Use 30% of capital per trade
  "stop_loss_pct": 0.005,       // 0.5% stop loss
  "take_profit_pct": 0.010,     // 1.0% take profit
  "max_trades_day": 3,          // Max 3 trades per day
  "max_daily_loss": 50.0,       // Stop if lose $50 SGD
  "signal_threshold": 4,        // Need 4/5 signals to trade
  "demo_mode": true             // TRUE = demo, FALSE = live
}
```

---

## 🚀 Setup Guide

### Step 1: Clone This Repo
```bash
git clone https://github.com/YOURUSERNAME/okx-trading-bot.git
cd okx-trading-bot
```

### Step 2: Add GitHub Secrets
Go to: Settings → Secrets → Actions → New repository secret

```
OKX_API_KEY      → Your OKX API key
OKX_SECRET_KEY   → Your OKX secret key
OKX_PASSPHRASE   → Your OKX passphrase
TELEGRAM_TOKEN   → Your Telegram bot token
TELEGRAM_CHAT_ID → Your Telegram chat ID
```

### Step 3: Enable GitHub Actions
- Go to Actions tab in your repo
- Click "Enable Actions"
- Bot runs automatically Mon-Fri every 30 mins!

### Step 4: Test Manually
- Go to Actions → Daily Trading Bot → Run workflow
- Check your Telegram for signal message!

---

## 📱 Telegram Alerts You'll Receive

```
🤖 OKX Bot
────────────────────
📈 Trade #1 OPENED!
Direction: LONG
Entry:  $95,200
Target: $96,152 (+1.0%)
Stop:   $94,724 (-0.5%)
Size:   $3,000 USDT
Signal Score: 4/5
[DEMO MODE]
```

```
🤖 OKX Bot
────────────────────
✅ Trade CLOSED!
PnL: +$28.50 SGD
Reason: Target hit 🎯
```

---

## 🔄 Switch from Demo to Live

When ready for real money (after 4+ weeks profitable demo):

1. Open `settings.json`
2. Change `"demo_mode": true` → `"demo_mode": false`
3. Create NEW Live API keys on OKX
4. Update GitHub Secrets with live keys
5. Push changes

```json
{
  "demo_mode": false  // ← Change this only when ready!
}
```

---

## 📊 Bot Schedule

```
Mon-Fri 8:00am SGT  → First scan
Mon-Fri every 30min → Continuous monitoring
Mon-Fri 6:00pm SGT  → Force close all positions
Sunday  2:00am SGT  → Weekly auto-tune runs
```

---

## 🛡️ Risk Protection

- Max $50 SGD loss per day → bot stops automatically
- Max 3 trades per day → no overtrading
- 0.5% stop loss → small losses only
- All positions closed by 6pm SGT → no overnight risk

---

## ⚠️ Disclaimer

This bot is for educational purposes.
Cryptocurrency trading involves significant risk.
Never trade money you cannot afford to lose.
Past performance does not guarantee future results.
Singapore crypto gains may be taxable — keep records!

---

## 📅 Roadmap

- [x] Version 1.0 — 5-layer signals + auto-tune
- [ ] Version 2.0 — AI news sentiment (Month 3)
- [ ] Version 3.0 — Whale wallet tracking (Month 5)
- [ ] Version 4.0 — Machine learning (Month 7)
