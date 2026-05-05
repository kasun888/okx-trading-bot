"""
main.py — EUR/USD 24/5 Scalp Bot Entry Point
=============================================
BUGS FIXED:
  BUG 1/5: Wrong bot name in logs → EUR/USD
  BUG 2/11: News checked GBP_USD → removed (bot.py handles EUR_USD)
  BUG 3:  send_startup() wrong args → fixed
  BUG 6:  Wrong SL/TP in logs → SL=13 TP=26
  BUG 8:  fresh_day_state missing fields → all added
  WARN 15: l2_pending now reset on new day
"""

import os, time, logging, traceback
from datetime import datetime
import pytz

from bot            import run_bot
from oanda_trader   import OandaTrader
from telegram_alert import TelegramAlert

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
log = logging.getLogger(__name__)

UTC              = pytz.utc
INTERVAL_MINUTES = 5
STATE            = {}
STATE_FILE       = 'bot_state.json'


def load_state():
    import json
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE) as f:
                s = json.load(f)
                log.info(f"State loaded: {s.get('date')} | trades={s.get('trades',0)}")
                return s
    except Exception as e:
        log.warning(f'State load failed: {e}')
    return {}


def save_state(state):
    import json
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f)
    except Exception as e:
        log.warning(f'State save failed: {e}')


def fresh_day_state(today_str, balance):
    """BUG 8 + WARN 15 FIX: All fields bot.py needs, l2_pending reset."""
    return {
        'date':               today_str,
        'trades':             0,
        'start_balance':      balance,
        'daily_pnl':          0.0,
        'wins':               0,
        'losses':             0,
        'consec_losses':      0,
        'stopped':            False,
        'l2_pending':         {},
        'cooldowns':          {},
        'open_times':         {},
        'pause_until':        None,
        'last_trade_direction': '',
        'news_alerted':       {},
        'session_alerted':    {},
        'login_fail_alerted': {},
    }


def check_env_vars():
    api_key    = os.environ.get('OANDA_API_KEY', '')
    account_id = os.environ.get('OANDA_ACCOUNT_ID', '')
    if not api_key or not account_id:
        log.error('MISSING ENV VARS: OANDA_API_KEY or OANDA_ACCOUNT_ID not set')
        return False
    tg_token = os.environ.get('TELEGRAM_TOKEN', '')
    tg_chat  = os.environ.get('TELEGRAM_CHAT_ID', '')
    if not tg_token or not tg_chat:
        log.warning('Telegram not configured')
    log.info(f'Env OK | Key: {api_key[:8]}**** | Account: {account_id}')
    return True


def run_once(state):
    """BUG 2/11 FIX: No GBP_USD news check here — bot.py handles EUR_USD news."""
    global STATE
    now_utc = datetime.now(UTC)
    today   = now_utc.strftime('%Y-%m-%d')
    log.info(f'UTC: {now_utc.strftime("%Y-%m-%d %H:%M")}')

    if state.get('date') != today:
        log.info('New UTC day — resetting state...')

        # Daily summary before reset
        if state.get('date') and state.get('trades', 0) > 0:
            try:
                trader_tmp = OandaTrader(demo=True)
                bal_now    = trader_tmp.get_balance() if trader_tmp.login() else 0.0
                TelegramAlert().send_daily_summary(
                    balance_sgd=round(bal_now, 2),
                    start_balance_sgd=round(state.get('start_balance', bal_now), 2),
                    trades=state.get('trades', 0),
                    wins=state.get('wins', 0),
                    losses=state.get('losses', 0),
                    pnl_sgd=round(state.get('daily_pnl', 0.0), 2),
                )
            except Exception as e:
                log.warning(f'Daily summary error: {e}')

        try:
            trader  = OandaTrader(demo=True)
            balance = trader.get_balance() if trader.login() else 0.0
        except Exception as e:
            log.warning(f'Balance fetch error: {e}')
            balance = 0.0

        # Preserve circuit breaker + open positions across day boundary
        preserve = {
            'pause_until':          state.get('pause_until'),
            'consec_losses':        state.get('consec_losses', 0),
            'last_trade_direction': state.get('last_trade_direction', ''),
            'open_times':           state.get('open_times', {}),
            'cooldowns':            state.get('cooldowns', {}),
        }

        state = fresh_day_state(today, balance)
        for k, v in preserve.items():
            if v:
                state[k] = v

        STATE = state
        log.info(f'New day: {today} | Balance: SGD {balance:.2f}')
        TelegramAlert().send_new_day(balance, today)

    run_bot(state=state)
    return state


def main():
    global STATE

    # BUG 1/5/6 FIX: Correct name and params
    log.info('=' * 55)
    log.info('EUR/USD 24/5 Scalp Bot — All Sessions')
    log.info('SL: 13 pips | TP: 26 pips | R:R 2:1')
    log.info('Signal: 4/4 layers | Chaos + H4 3-bar filters')
    log.info('Hours: 24/5 Mon-Fri SGT')
    log.info('=' * 55)

    if not check_env_vars():
        return

    is_railway = os.environ.get('RAILWAY', '').lower() in ('true', '1', 'yes')

    if is_railway:
        log.info('Railway mode — polling every 5 minutes')
        try:
            trader  = OandaTrader(demo=True)
            balance = trader.get_balance() if trader.login() else 0.0
        except Exception:
            balance = 0.0

        # BUG 3 FIX: correct signature send_startup(balance_sgd, mode)
        TelegramAlert().send_startup(balance_sgd=round(balance, 2), mode='DEMO')

        STATE = load_state()
        while True:
            try:
                STATE = run_once(STATE)
                save_state(STATE)
            except Exception as e:
                log.error(f'Bot error: {e}')
                log.error(traceback.format_exc())
                time.sleep(30)
            log.info(f'Sleeping {INTERVAL_MINUTES} min...')
            time.sleep(INTERVAL_MINUTES * 60)
    else:
        log.info('GitHub Actions mode — single run')
        STATE = load_state()
        try:
            STATE = run_once(STATE)
            save_state(STATE)
        except Exception as e:
            log.error(f'Bot error: {e}')
            log.error(traceback.format_exc())


if __name__ == '__main__':
    main()
