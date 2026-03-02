"""
🔄 Auto-Tuner — Self Learning Engine
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Runs every Sunday 2am SGT
Analyses past week performance
Adjusts settings automatically
Gets smarter every week!
"""

import json
import logging
import glob
from datetime import datetime
import pytz

log = logging.getLogger(__name__)

class AutoTuner:
    def __init__(self, settings):
        self.settings = settings
        self.sg_tz    = pytz.timezone("Asia/Singapore")

    def run_weekly_tune(self):
        log.info("🔄 Starting weekly auto-tune...")

        # Load all trade logs from past week
        trade_files = glob.glob("trades_*.json")
        all_trades  = []

        for f in trade_files:
            try:
                with open(f) as fp:
                    data = json.load(fp)
                    all_trades.append(data)
            except:
                pass

        if not all_trades:
            log.info("No trade data yet. Skipping tune.")
            return

        # Calculate performance
        total_pnl    = sum(t.get("daily_pnl", 0) for t in all_trades)
        total_trades = sum(t.get("trades", 0) for t in all_trades)
        winning_days = sum(1 for t in all_trades if t.get("daily_pnl", 0) > 0)
        total_days   = len(all_trades)
        win_rate     = (winning_days / total_days * 100) if total_days > 0 else 0

        log.info(f"📊 Weekly Stats | PnL: ${total_pnl:.2f} | Trades: {total_trades} | Win rate: {win_rate:.0f}%")

        new_settings = self.settings.copy()

        # ── Auto-Adjust Rules ─────────────────────────────────────────────
        # Win rate too low → be more selective
        if win_rate < 40:
            new_settings["signal_threshold"] = min(5, self.settings["signal_threshold"] + 1)
            new_settings["position_size_pct"] = max(0.15, self.settings["position_size_pct"] - 0.05)
            log.info(f"⬆️ Win rate low ({win_rate:.0f}%) → raising threshold to {new_settings['signal_threshold']}")

        # Win rate good → can be slightly more aggressive
        elif win_rate > 65:
            new_settings["signal_threshold"] = max(3, self.settings["signal_threshold"] - 1)
            new_settings["position_size_pct"] = min(0.40, self.settings["position_size_pct"] + 0.05)
            log.info(f"⬇️ Win rate great ({win_rate:.0f}%) → lowering threshold to {new_settings['signal_threshold']}")

        # Too many losses → tighten stop loss
        if total_pnl < -100:
            new_settings["stop_loss_pct"]  = max(0.003, self.settings["stop_loss_pct"] - 0.001)
            new_settings["max_trades_day"] = max(1, self.settings["max_trades_day"] - 1)
            log.info("🛡️ Big losses → tightening stop loss and reducing max trades")

        # Good profit → slightly widen take profit
        if total_pnl > 100:
            new_settings["take_profit_pct"] = min(0.02, self.settings["take_profit_pct"] + 0.001)
            log.info("🎯 Good profit → widening take profit target")

        # Save updated settings
        with open("settings.json", "w") as f:
            json.dump(new_settings, f, indent=2)

        log.info(f"✅ Settings updated: {new_settings}")
        self._save_weekly_report(win_rate, total_pnl, total_trades, new_settings)
        return new_settings

    def _save_weekly_report(self, win_rate, pnl, trades, settings):
        now    = datetime.now(self.sg_tz)
        report = {
            "date":      now.strftime("%Y-%m-%d"),
            "win_rate":  win_rate,
            "total_pnl": pnl,
            "trades":    trades,
            "new_settings": settings
        }
        fname = f"weekly_report_{now.strftime('%Y%m%d')}.json"
        with open(fname, "w") as f:
            json.dump(report, f, indent=2)
        log.info(f"📄 Weekly report saved: {fname}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        with open("settings.json") as f:
            settings = json.load(f)
    except:
        settings = {}
    tuner = AutoTuner(settings)
    tuner.run_weekly_tune()
