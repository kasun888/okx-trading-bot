"""
🤖 OKX Smart Trading Bot — BTC + GOLD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Capital: $10,000 SGD
Target:  $20-30 SGD/day
Markets: BTC/USDT + XAU/USDT (Gold)
Mode:    Demo (flag="1") → change to "0" for live
"""

import os
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

# ─── Assets to Trade ─────────────────────────────────────────────────────────
ASSETS = {
    "BTC":  {"instId": "BTC-USDT",  "label": "Bitcoin",  "emoji": "₿"},
    "GOLD": {"instId": "XAUT-USDT", "label": "Gold",     "emoji": "🥇"},
}

# ─── Load Settings ────────────────────────────────────────────────────────────
def load_settings():
    default = {
        "position_size_pct": 0.30,
        "stop_loss_pct":     0.005,
        "take_profit_pct":   0.010,
        "max_trades_day":    3,
        "max_daily_loss":    50.0,
        "signal_threshold":  4,
        "demo_mode":         True,
        "trade_btc":         True,
        "trade_gold":        True
    }
    try:
        with open("settings.json") as f:
            saved = json.load(f)
            default.update(saved)
    except FileNotFoundError:
        with open("settings.json", "w") as f:
            json.dump(default, f, indent=2)
    return default

# ─── Trade One Asset ──────────────────────────────────────────────────────────
def trade_asset(asset, inst_id, settings, trader, signals, alert, today, trade_log_file):
    log.info(f"\n{'='*40}")
    log.info(f"🔍 Analyzing {asset}...")

    # Check open position
    position = trader.get_position(inst_id)
    if position:
        pnl = trader.check_pnl(position)
        log.info(f"📊 Open {asset} position | PnL: {pnl:.2f} USDT")
        tp = settings["take_profit_pct"] * 100
        sl = settings["stop_loss_pct"]   * 100
        if pnl >= tp or pnl <= -sl:
            trader.close_position(inst_id)
            emoji = "✅" if pnl > 0 else "❌"
            alert.send(
                f"{emoji} {ASSETS[asset]['emoji']} {asset} Trade CLOSED!\n"
                f"PnL: {pnl:+.2f} SGD\n"
                f"{'Target hit 🎯' if pnl > 0 else 'Stop loss hit 🛑'}"
            )
            today["daily_pnl"] += pnl
            with open(trade_log_file, "w") as f:
                json.dump(today, f, indent=2)
        return

    # Run signal analysis
    score, direction, details = signals.analyze(asset=asset)
    log.info(f"{asset} Score: {score}/5 | Direction: {direction}")
    log.info(details)

    threshold = settings["signal_threshold"]
    if score < threshold or direction == "NONE":
        log.info(f"⏸️ {asset}: Score {score} < {threshold}. Skipping.")
        alert.send(
            f"⏸️ {ASSETS[asset]['emoji']} {asset}: No trade\n"
            f"Score: {score}/5 | {direction}\n"
            f"{details}"
        )
        return

    # Place trade
    balance   = trader.get_balance()
    trade_amt = balance * settings["position_size_pct"]
    price     = trader.get_price(inst_id)
    if not price:
        log.error(f"Cannot get {asset} price!")
        return

    sl_price = price * (1 - settings["stop_loss_pct"])   if direction == "LONG" else price * (1 + settings["stop_loss_pct"])
    tp_price = price * (1 + settings["take_profit_pct"]) if direction == "LONG" else price * (1 - settings["take_profit_pct"])

    result = trader.place_order(inst_id, direction, trade_amt, sl_price, tp_price)

    if result["success"]:
        today["trades"] += 1
        with open(trade_log_file, "w") as f:
            json.dump(today, f, indent=2)

        arrow = "📈" if direction == "LONG" else "📉"
        alert.send(
            f"{arrow} {ASSETS[asset]['emoji']} {asset} Trade #{today['trades']} OPENED!\n"
            f"Direction: {direction}\n"
            f"Entry:  ${price:,.2f}\n"
            f"Target: ${tp_price:,.2f} (+{settings['take_profit_pct']*100:.1f}%)\n"
            f"Stop:   ${sl_price:,.2f} (-{settings['stop_loss_pct']*100:.1f}%)\n"
            f"Size:   ${trade_amt:,.0f} USDT\n"
            f"Score:  {score}/5\n"
            f"{'[DEMO]' if settings['demo_mode'] else '[LIVE 💰]'}"
        )
        log.info(f"✅ {asset} trade placed!")
    else:
        log.error(f"❌ {asset} trade failed: {result['error']}")
        alert.send(f"❌ {asset} trade failed: {result['error']}")

# ─── Main Bot ─────────────────────────────────────────────────────────────────
def run_bot():
    log.info("🤖 OKX Bot starting — BTC + GOLD")

    settings = load_settings()
    sg_tz    = pytz.timezone("Asia/Singapore")
    now      = datetime.now(sg_tz)

    log.info(f"📅 {now.strftime('%Y-%m-%d %H:%M SGT')} | Demo: {settings['demo_mode']}")

    # Trading hours 6am-6pm SGT
    if now.hour < 6 or now.hour >= 18:
        log.info("⏰ Outside trading hours (6am-6pm SGT). Skipping.")
        return

    flag   = "1" if settings["demo_mode"] else "0"
    trader = OKXTrader(flag=flag)
    signal = SignalEngine()
    alert  = TelegramAlert()

    # Load today's log
    trade_log_file = f"trades_{now.strftime('%Y%m%d')}.json"
    try:
        with open(trade_log_file) as f:
            today = json.load(f)
    except FileNotFoundError:
        today = {"trades": 0, "daily_pnl": 0.0, "stopped": False}

    # Daily loss limit
    if today["stopped"]:
        log.info("🛑 Daily loss limit hit. Stopped for today.")
        return

    if today["daily_pnl"] <= -settings["max_daily_loss"]:
        today["stopped"] = True
        with open(trade_log_file, "w") as f:
            json.dump(today, f, indent=2)
        alert.send(f"🛑 Daily loss limit ${settings['max_daily_loss']} SGD hit! Stopped.")
        return

    # Max trades
    if today["trades"] >= settings["max_trades_day"]:
        log.info(f"✅ Max {settings['max_trades_day']} trades done today.")
        return

    # ── Analyze and Trade BTC ─────────────────────────────────────────────
    if settings.get("trade_btc", True):
        trade_asset("BTC", "BTC-USDT", settings, trader, signal, alert, today, trade_log_file)

    # ── Analyze and Trade GOLD ────────────────────────────────────────────
    if settings.get("trade_gold", True) and today["trades"] < settings["max_trades_day"]:
        trade_asset("GOLD", "XAUT-USDT", settings, trader, signal, alert, today, trade_log_file)

    log.info(f"\n✅ Bot cycle done | Trades today: {today['trades']} | PnL: ${today['daily_pnl']:.2f}")

if __name__ == "__main__":
    run_bot()
