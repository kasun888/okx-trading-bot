"""
🤖 OKX Smart Trading Bot
━━━━━━━━━━━━━━━━━━━━━━━━
Capital: $10,000 SGD
Target:  $20-30 SGD/day
Market:  BTC/USDT
Mode:    Demo (flag="1") → change to "0" for live
"""

import os
import time
import json
import logging
from datetime import datetime
import pytz

from signals import SignalEngine
from okx_trader import OKXTrader
from auto_tune import AutoTuner
from telegram_alert import TelegramAlert

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("performance_log.txt"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ─── Load Settings ──────────────────────────────────────────────────────────
def load_settings():
    default = {
        "position_size_pct": 0.30,
        "stop_loss_pct":     0.005,
        "take_profit_pct":   0.010,
        "max_trades_day":    3,
        "max_daily_loss":    50.0,
        "signal_threshold":  4,
        "demo_mode":         True
    }
    try:
        with open("settings.json") as f:
            saved = json.load(f)
            default.update(saved)
    except FileNotFoundError:
        with open("settings.json", "w") as f:
            json.dump(default, f, indent=2)
    return default

# ─── Main Bot Logic ──────────────────────────────────────────────────────────
def run_bot():
    log.info("🤖 Bot starting up...")

    settings   = load_settings()
    sg_tz      = pytz.timezone("Asia/Singapore")
    now        = datetime.now(sg_tz)

    log.info(f"📅 Singapore Time: {now.strftime('%Y-%m-%d %H:%M:%S SGT')}")

    # Market hours check (6am - 6pm SGT for day trading)
    if now.hour < 6 or now.hour >= 18:
        log.info("⏰ Outside trading hours (6am-6pm SGT). Skipping.")
        return

    # Initialize components
    flag    = "1" if settings["demo_mode"] else "0"  # "1"=demo "0"=live
    trader  = OKXTrader(flag=flag)
    signals = SignalEngine()
    tuner   = AutoTuner(settings)
    alert   = TelegramAlert()

    # Load today's trade log
    trade_log_file = f"trades_{now.strftime('%Y%m%d')}.json"
    try:
        with open(trade_log_file) as f:
            today = json.load(f)
    except FileNotFoundError:
        today = {"trades": 0, "daily_pnl": 0.0, "stopped": False}

    # Daily loss limit check
    if today["stopped"]:
        log.info(f"🛑 Daily loss limit hit. Bot stopped for today.")
        return

    if today["daily_pnl"] <= -settings["max_daily_loss"]:
        today["stopped"] = True
        with open(trade_log_file, "w") as f:
            json.dump(today, f, indent=2)
        msg = f"🛑 Daily loss limit of ${settings['max_daily_loss']} SGD hit! Bot stopped for today."
        alert.send(msg)
        log.warning(msg)
        return

    # Max trades check
    if today["trades"] >= settings["max_trades_day"]:
        log.info(f"✅ Max {settings['max_trades_day']} trades reached for today.")
        return

    # ── Check for open positions first ──────────────────────────────────────
    position = trader.get_position("BTC-USDT")
    if position:
        log.info(f"📊 Open position exists: {position}")
        pnl = trader.check_pnl(position)
        log.info(f"💰 Current PnL: {pnl:.2f} USDT")

        # Close if target or stop hit
        tp = settings["take_profit_pct"]
        sl = settings["stop_loss_pct"]
        if pnl >= tp * 100 or pnl <= -sl * 100:
            result = trader.close_position("BTC-USDT")
            emoji  = "✅" if pnl > 0 else "❌"
            msg    = f"{emoji} Trade CLOSED!\nPnL: {pnl:+.2f} SGD\nReason: {'Target hit 🎯' if pnl > 0 else 'Stop loss 🛑'}"
            alert.send(msg)
            today["daily_pnl"] += pnl
            with open(trade_log_file, "w") as f:
                json.dump(today, f, indent=2)
        return

    # ── Run 5-Layer Signal Analysis ─────────────────────────────────────────
    log.info("🔍 Running 5-layer signal analysis...")
    score, direction, details = signals.analyze()

    log.info(f"📊 Signal Score: {score}/5 | Direction: {direction}")
    log.info(f"📋 Details: {details}")

    threshold = settings["signal_threshold"]

    if score < threshold:
        log.info(f"⏸️  Score {score} < threshold {threshold}. No trade today.")
        msg = f"⏸️ No trade signal today\nScore: {score}/5\n{details}"
        alert.send(msg)
        return

    # ── Place Trade ──────────────────────────────────────────────────────────
    balance   = trader.get_balance()
    trade_amt = balance * settings["position_size_pct"]
    btc_price = trader.get_price("BTC-USDT")

    sl_price = btc_price * (1 - settings["stop_loss_pct"])  if direction == "LONG" else btc_price * (1 + settings["stop_loss_pct"])
    tp_price = btc_price * (1 + settings["take_profit_pct"]) if direction == "LONG" else btc_price * (1 - settings["take_profit_pct"])

    log.info(f"🚀 Placing {direction} trade | Size: ${trade_amt:.0f} | Entry: {btc_price:.0f}")

    result = trader.place_order(
        instId    = "BTC-USDT",
        direction = direction,
        amount    = trade_amt,
        sl_price  = sl_price,
        tp_price  = tp_price
    )

    if result["success"]:
        today["trades"] += 1
        with open(trade_log_file, "w") as f:
            json.dump(today, f, indent=2)

        arrow = "📈" if direction == "LONG" else "📉"
        msg = (
            f"{arrow} Trade #{today['trades']} OPENED!\n"
            f"Direction: {direction}\n"
            f"Entry:  ${btc_price:,.0f}\n"
            f"Target: ${tp_price:,.0f} (+{settings['take_profit_pct']*100:.1f}%)\n"
            f"Stop:   ${sl_price:,.0f} (-{settings['stop_loss_pct']*100:.1f}%)\n"
            f"Size:   ${trade_amt:,.0f} USDT\n"
            f"Signal Score: {score}/5\n"
            f"{'[DEMO MODE]' if settings['demo_mode'] else '[LIVE]'}"
        )
        alert.send(msg)
        log.info(f"✅ Trade placed successfully!")
    else:
        log.error(f"❌ Trade failed: {result['error']}")
        alert.send(f"❌ Trade failed!\nError: {result['error']}")

if __name__ == "__main__":
    run_bot()
