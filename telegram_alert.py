"""
Telegram Alert System - All alert methods for OANDA EUR/USD Bot
"""
import os
import requests
import logging

log = logging.getLogger(__name__)


class TelegramAlert:
    def __init__(self):
        self.token   = os.environ.get("TELEGRAM_TOKEN", "")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    def send(self, message: str) -> bool:
        if not self.token or not self.chat_id:
            log.warning("Telegram not configured — TELEGRAM_TOKEN or TELEGRAM_CHAT_ID missing")
            return False
        try:
            url  = f"https://api.telegram.org/bot{self.token}/sendMessage"
            text = f"🤖 OANDA Bot\n{'─'*22}\n{message}"
            data = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}
            r    = requests.post(url, data=data, timeout=10)
            if r.status_code == 200:
                log.info("Telegram sent!")
                return True
            log.warning(f"Telegram error {r.status_code}: {r.text[:200]}")
            return False
        except Exception as e:
            log.error(f"Telegram send error: {e}")
            return False

    # ── Trade lifecycle ──────────────────────────────────────────────

    def send_trade_open(self, direction, entry_price, sl_pips, tp_pips,
                        sl_sgd, tp_sgd, spread, score, session_label,
                        layer_breakdown, balance_sgd, trades_today):
        emoji = "🟢 BUY" if direction == "BUY" else "🔴 SELL"
        breakdown_str = ""
        if layer_breakdown:
            breakdown_str = "\n" + "\n".join(
                f"  {k}: {v}" for k, v in layer_breakdown.items()
            )
        msg = (
            f"{emoji} TRADE OPEN\n"
            f"Pair:    EUR/USD | {session_label}\n"
            f"Entry:   {entry_price:.5f}\n"
            f"SL:      {sl_pips} pip  (−SGD {sl_sgd:.2f})\n"
            f"TP:      {tp_pips} pip  (+SGD {tp_sgd:.2f})\n"
            f"Spread:  {spread:.2f} pip\n"
            f"Score:   {score}/4{breakdown_str}\n"
            f"Balance: SGD {balance_sgd:.2f}\n"
            f"Trade #: {trades_today} today"
        )
        return self.send(msg)

    def send_tp_hit(self, pnl_usd, pnl_sgd, balance_sgd, wins, losses,
                    open_price, close_price):
        msg = (
            f"✅ TAKE PROFIT HIT\n"
            f"EUR/USD closed at profit\n"
            f"Entry:   {open_price:.5f} → {close_price:.5f}\n"
            f"P&L:     +SGD {abs(pnl_sgd):.2f}  (+${abs(pnl_usd):.2f})\n"
            f"Balance: SGD {balance_sgd:.2f}\n"
            f"Record:  {wins}W / {losses}L\n"
            f"🏁 WIN-STOP: Done trading today. Protecting profit."
        )
        return self.send(msg)

    def send_sl_hit(self, pnl_usd, pnl_sgd, balance_sgd, wins, losses,
                    open_price, close_price):
        msg = (
            f"❌ STOP LOSS HIT\n"
            f"EUR/USD stopped out\n"
            f"Entry:   {open_price:.5f} → {close_price:.5f}\n"
            f"P&L:     −SGD {abs(pnl_sgd):.2f}  (−${abs(pnl_usd):.2f})\n"
            f"Balance: SGD {balance_sgd:.2f}\n"
            f"Record:  {wins}W / {losses}L\n"
            f"⏳ 30-min cooldown active."
        )
        return self.send(msg)

    def send_timeout_close(self, minutes, pnl_usd, pnl_sgd, balance_sgd):
        sign = "+" if pnl_sgd >= 0 else "-"
        msg = (
            f"⏱️ TIMEOUT CLOSE (45 min)\n"
            f"EUR/USD force-closed after {round(minutes, 1)} min\n"
            f"P&L:     {sign}SGD {abs(pnl_sgd):.2f}  ({sign}${abs(pnl_usd):.2f})\n"
            f"Balance: SGD {balance_sgd:.2f}"
        )
        return self.send(msg)

    # ── Session alerts ───────────────────────────────────────────────

    def send_session_open(self, session_label, session_hours,
                          balance_sgd, trades_today, wins, losses):
        msg = (
            f"🔔 {session_label} Session Open\n"
            f"⏰ {session_hours}\n"
            f"Balance: SGD {balance_sgd:.2f}\n"
            f"Today:   {trades_today} trade(s) | {wins}W {losses}L\n"
            f"Scanning EUR/USD..."
        )
        return self.send(msg)

    def send_session_close(self, session_label, balance_sgd,
                           session_trades, session_pnl_sgd, wins, losses):
        sign = "+" if session_pnl_sgd >= 0 else "-"
        msg = (
            f"🔕 {session_label} Session Closed\n"
            f"Trades:  {session_trades}\n"
            f"Session P&L: {sign}SGD {abs(session_pnl_sgd):.2f}\n"
            f"Balance: SGD {balance_sgd:.2f}\n"
            f"Record:  {wins}W / {losses}L"
        )
        return self.send(msg)

    # ── Error / system alerts ────────────────────────────────────────

    def send_login_fail(self, api_key_hint, account_id):
        msg = (
            f"⚠️ LOGIN FAILED\n"
            f"OANDA API key: {api_key_hint}\n"
            f"Account ID:    {account_id or 'MISSING'}\n"
            f"Check Railway env vars!"
        )
        return self.send(msg)

    def send_news_block(self, instrument, reason):
        msg = (
            f"📰 NEWS BLOCK — {instrument}\n"
            f"{reason}\n"
            f"Skipping trade. Will resume after news window."
        )
        return self.send(msg)
