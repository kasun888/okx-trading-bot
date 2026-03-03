"""
OANDA Trading Bot
EUR/USD + GBP/USD + Gold (XAU_USD)
"""

import os
import json
import logging
from datetime import datetime
import pytz

from oanda_trader import OandaTrader
from signals import SignalEngine
from telegram_alert import TelegramAlert
from auto_tune import AutoTuner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("performance_log.txt"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# OANDA uses underscore format: EUR_USD not EURUSD
ASSETS = {
    "EUR_USD": {
        "instrument": "EUR_USD",
        "asset":      "EURUSD",
        "label":      "Euro/USD",
        "emoji":      "💱",
        "setting":    "trade_eurusd",
        "size":       1000,    # 1000 units = micro lot
        "stop":       15,      # 15 pips
        "limit":      30,      # 30 pips
    },
    "GBP_USD": {
        "instrument": "GBP_USD",
        "asset":      "GBPUSD",
        "label":      "GBP/USD",
        "emoji":      "💷",
        "setting":    "trade_gbpusd",
        "size":       1000,
        "stop":       20,
        "limit":      40,
    },
    "XAU_USD": {
        "instrument": "XAU_USD",
        "asset":      "XAUUSD",
        "label":      "Gold",
        "emoji":      "🥇",
        "setting":    "trade_gold",
        "size":       1,       # 1 oz gold
        "stop":       150,
        "limit":      300,
    },
}

def load_settings():
    default = {
        "max_trades_day":   5,
        "max_daily_loss":   50.0,
        "signal_threshold": 4,
        "demo_mode":        True,
        "trade_eurusd":     True,
        "trade_gbpusd":     True,
        "trade_gold":       True
    }
    try:
        with open("settings.json") as f:
            saved = json.load(f)
            default.update(saved)
    except FileNotFoundError:
        with open("settings.json", "w") as f:
            json.dump(default, f, indent=2)
    return default

def run_bot():
    log.info("OANDA Bot starting!")
    settings = load_settings()
    sg_tz    = pytz.timezone("Asia/Singapore")
    now      = datetime.now(sg_tz)
    alert    = TelegramAlert()

    # Detect session
    hour = now.hour
    if 5 <= hour < 7:
        session = "Sydney"
    elif 7 <= hour < 15:
        session = "Tokyo/Asia"
    elif 15 <= hour < 20:
        session = "London"
    elif 20 <= hour <= 23 or hour < 1:
        session = "London+NY BEST!"
    else:
        session = "New York"

    # Skip Saturday + early Sunday
    if now.weekday() == 5:
        alert.send("Saturday - markets closed!")
        return
    if now.weekday() == 6 and now.hour < 5:
        alert.send("Sunday early - markets opening soon!")
        return

    alert.send(
        f"OANDA Bot starting!\n"
        f"Time: {now.strftime('%H:%M SGT')}\n"
        f"Session: {session}"
    )

    # Login
    trader = OandaTrader(demo=settings["demo_mode"])
    if not trader.login():
        alert.send(
            f"OANDA Login failed!\n"
            f"Check GitHub Secrets:\n"
            f"OANDA_API_KEY correct?\n"
            f"OANDA_ACCOUNT_ID correct?"
        )
        return

    balance = trader.get_balance()
    alert.send(
        f"OANDA Login success!\n"
        f"Balance: ${balance:.2f}\n"
        f"Scanning markets..."
    )

    signals = SignalEngine()

    # Load today log
    trade_log = f"trades_{now.strftime('%Y%m%d')}.json"
    try:
        with open(trade_log) as f:
            today = json.load(f)
    except FileNotFoundError:
        today = {"trades": 0, "daily_pnl": 0.0, "stopped": False}

    if today.get("stopped"):
        alert.send("Daily loss limit hit! Stopped for today.")
        return

    if today["daily_pnl"] <= -settings["max_daily_loss"]:
        today["stopped"] = True
        with open(trade_log, "w") as f:
            json.dump(today, f, indent=2)
        alert.send(f"Daily loss ${settings['max_daily_loss']} hit! Stopped.")
        return

    if today["trades"] >= settings["max_trades_day"]:
        alert.send(f"Max {settings['max_trades_day']} trades reached!")
        return

    # Scan all assets
    scan_results = []
    for name, config in ASSETS.items():
        if not settings.get(config["setting"], True):
            continue
        if today["trades"] >= settings["max_trades_day"]:
            break

        log.info(f"Scanning {name}...")

        # Check existing position
        position = trader.get_position(name)
        if position:
            pnl = trader.check_pnl(position)
            log.info(f"{name} open position PnL: {pnl:.2f}")

            # Close if target or stop hit
            if pnl >= config["limit"] * 0.01 or pnl <= -config["stop"] * 0.01:
                trader.close_position(name)
                emoji = "Win!" if pnl > 0 else "Stop loss"
                alert.send(
                    f"{config['emoji']} {name} CLOSED\n"
                    f"PnL: ${pnl:.2f}\n"
                    f"{emoji}"
                )
                today["daily_pnl"] += pnl
                with open(trade_log, "w") as f:
                    json.dump(today, f, indent=2)
            else:
                scan_results.append(f"{config['emoji']} {name}: open PnL=${pnl:.2f}")
            continue

        # Get signal
        score, direction, details = signals.analyze(asset=config["asset"])
        log.info(f"{name}: {score}/5 -> {direction}")

        if score < settings["signal_threshold"] or direction == "NONE":
            scan_results.append(f"{config['emoji']} {name}: {score}/5 skip")
            continue

        # Place trade
        result = trader.place_order(
            instrument    = name,
            direction     = direction,
            size          = config["size"],
            stop_distance = config["stop"],
            limit_distance= config["limit"]
        )

        if result["success"]:
            today["trades"] += 1
            with open(trade_log, "w") as f:
                json.dump(today, f, indent=2)

            price, _, _ = trader.get_price(name)
            alert.send(
                f"{config['emoji']} {name} TRADE!\n"
                f"Direction: {direction}\n"
                f"Entry: {price}\n"
                f"Score: {score}/5\n"
                f"Trade #{today['trades']}\n"
                f"DEMO mode"
            )
            scan_results.append(f"{config['emoji']} {name}: {direction} PLACED!")
        else:
            log.error(f"{name} order failed: {result['error']}")
            scan_results.append(f"{config['emoji']} {name}: failed")

    # Send summary
    summary = "\n".join(scan_results) if scan_results else "No signals"
    alert.send(
        f"Scan Done!\n"
        f"Time: {now.strftime('%H:%M SGT')}\n"
        f"Session: {session}\n"
        f"Trades today: {today['trades']}/{settings['max_trades_day']}\n"
        f"Daily PnL: ${today['daily_pnl']:.2f}\n"
        f"---\n"
        f"{summary}"
    )

if __name__ == "__main__":
    run_bot()
