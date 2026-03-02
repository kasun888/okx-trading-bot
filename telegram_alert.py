"""
📱 Telegram Alert System
━━━━━━━━━━━━━━━━━━━━━━━
Sends trade notifications to your Telegram
"""

import os
import requests
import logging

log = logging.getLogger(__name__)

class TelegramAlert:
    def __init__(self):
        self.token   = os.environ.get("TELEGRAM_TOKEN", "")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    def send(self, message: str):
        if not self.token or not self.chat_id:
            log.warning("Telegram not configured")
            return False
        try:
            url  = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = {
                "chat_id":    self.chat_id,
                "text":       f"🤖 OKX Bot\n{'─'*20}\n{message}",
                "parse_mode": "HTML"
            }
            r = requests.post(url, data=data, timeout=10)
            if r.status_code == 200:
                log.info("✅ Telegram alert sent!")
                return True
            else:
                log.warning(f"Telegram error: {r.text}")
                return False
        except Exception as e:
            log.error(f"Telegram send error: {e}")
            return False

    def send_daily_summary(self, trades, pnl, win_rate):
        emoji = "✅" if pnl > 0 else "❌"
        msg = (
            f"📊 DAILY SUMMARY\n"
            f"{'─'*20}\n"
            f"Trades today: {trades}\n"
            f"Total PnL: {pnl:+.2f} SGD {emoji}\n"
            f"Win rate: {win_rate:.0f}%\n"
            f"{'─'*20}\n"
            f"{'Great day! 🎉' if pnl > 0 else 'Better tomorrow! 💪'}"
        )
        self.send(msg)
