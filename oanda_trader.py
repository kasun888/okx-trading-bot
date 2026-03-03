"""
OANDA Trade Executor
Demo: api-fxpractice.oanda.com
Live: api-trade.oanda.com
"""

import os
import requests
import logging

log = logging.getLogger(__name__)

class OandaTrader:
    def __init__(self, demo=True):
        self.api_key    = os.environ.get("OANDA_API_KEY", "")
        self.account_id = os.environ.get("OANDA_ACCOUNT_ID", "")
        self.demo       = demo
        self.base_url   = "https://api-fxpractice.oanda.com" if demo else "https://api-trade.oanda.com"
        self.headers    = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/json"
        }
        log.info(f"OANDA Trader | Mode: {'DEMO' if demo else 'LIVE'}")
        log.info(f"Account: {self.account_id}")
        log.info(f"API Key: {self.api_key[:8]}****")

    # ── Login / Test Connection ───────────────────────────────────────────────
    def login(self):
        try:
            url = f"{self.base_url}/v3/accounts/{self.account_id}"
            log.info(f"Testing connection: {url}")
            r   = requests.get(url, headers=self.headers, timeout=15)
            log.info(f"Response status: {r.status_code}")
            log.info(f"Response: {r.text[:300]}")

            if r.status_code == 200:
                data    = r.json()
                balance = float(data["account"]["balance"])
                log.info(f"Login success! Balance: {balance}")
                return True
            else:
                log.error(f"Login failed! {r.status_code}: {r.text}")
                return False
        except Exception as e:
            log.error(f"Login error: {e}")
            return False

    # ── Get Balance ───────────────────────────────────────────────────────────
    def get_balance(self):
        try:
            url  = f"{self.base_url}/v3/accounts/{self.account_id}"
            r    = requests.get(url, headers=self.headers, timeout=10)
            data = r.json()
            bal  = float(data["account"]["balance"])
            log.info(f"Balance: {bal}")
            return bal
        except Exception as e:
            log.error(f"get_balance error: {e}")
            return 0

    # ── Get Price ─────────────────────────────────────────────────────────────
    def get_price(self, instrument):
        try:
            url  = f"{self.base_url}/v3/accounts/{self.account_id}/pricing"
            r    = requests.get(url, headers=self.headers, params={"instruments": instrument}, timeout=10)
            data = r.json()
            price = data["prices"][0]
            bid   = float(price["bids"][0]["price"])
            ask   = float(price["asks"][0]["price"])
            mid   = (bid + ask) / 2
            log.info(f"{instrument}: bid={bid} ask={ask}")
            return mid, bid, ask
        except Exception as e:
            log.error(f"get_price error: {e}")
            return None, None, None

    # ── Get Open Position ─────────────────────────────────────────────────────
    def get_position(self, instrument):
        try:
            url  = f"{self.base_url}/v3/accounts/{self.account_id}/positions/{instrument}"
            r    = requests.get(url, headers=self.headers, timeout=10)
            if r.status_code == 200:
                data     = r.json()
                long_units  = int(float(data["position"]["long"]["units"]))
                short_units = int(float(data["position"]["short"]["units"]))
                if long_units != 0 or short_units != 0:
                    return data["position"]
            return None
        except Exception as e:
            log.error(f"get_position error: {e}")
            return None

    # ── Check PnL ─────────────────────────────────────────────────────────────
    def check_pnl(self, position):
        try:
            long_pnl  = float(position["long"].get("unrealizedPL", 0))
            short_pnl = float(position["short"].get("unrealizedPL", 0))
            return long_pnl + short_pnl
        except:
            return 0

    # ── Place Order ───────────────────────────────────────────────────────────
    def place_order(self, instrument, direction, size, stop_distance, limit_distance, currency="USD"):
        try:
            units = size if direction == "BUY" else -size
            price_mid, _, _ = self.get_price(instrument)

            if price_mid is None:
                return {"success": False, "error": "Could not get price"}

            # Calculate stop and limit prices
            pip_size = 0.0001 if "JPY" not in instrument else 0.01
            if instrument == "XAU_USD":
                pip_size = 0.1

            stop_loss  = round(price_mid - (stop_distance  * pip_size) if direction == "BUY" else price_mid + (stop_distance  * pip_size), 5)
            take_profit= round(price_mid + (limit_distance * pip_size) if direction == "BUY" else price_mid - (limit_distance * pip_size), 5)

            url     = f"{self.base_url}/v3/accounts/{self.account_id}/orders"
            payload = {
                "order": {
                    "type":          "MARKET",
                    "instrument":    instrument,
                    "units":         str(units),
                    "timeInForce":   "FOK",
                    "stopLossOnFill": {
                        "price": str(stop_loss)
                    },
                    "takeProfitOnFill": {
                        "price": str(take_profit)
                    }
                }
            }

            log.info(f"Placing {direction} order: {instrument} units={units}")
            r    = requests.post(url, headers=self.headers, json=payload, timeout=15)
            data = r.json()
            log.info(f"Order result: {data}")

            if r.status_code in [200, 201]:
                if "orderFillTransaction" in data:
                    trade_id = data["orderFillTransaction"]["tradeOpened"]["tradeID"]
                    return {"success": True, "trade_id": trade_id}
                return {"success": True}
            else:
                error = data.get("errorMessage", "Unknown error")
                return {"success": False, "error": error}
        except Exception as e:
            log.error(f"place_order error: {e}")
            return {"success": False, "error": str(e)}

    # ── Close Position ────────────────────────────────────────────────────────
    def close_position(self, instrument):
        try:
            url  = f"{self.base_url}/v3/accounts/{self.account_id}/positions/{instrument}/close"
            payload = {
                "longUnits":  "ALL",
                "shortUnits": "ALL"
            }
            r    = requests.put(url, headers=self.headers, json=payload, timeout=15)
            data = r.json()
            log.info(f"Close result: {data}")
            return {"success": r.status_code == 200}
        except Exception as e:
            log.error(f"close_position error: {e}")
            return {"success": False, "error": str(e)}
