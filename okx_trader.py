"""
💱 OKX Trade Executor
━━━━━━━━━━━━━━━━━━━━
Handles all OKX API interactions
flag="1" → Demo Trading
flag="0" → Live Trading
"""

import os
import hmac
import hashlib
import base64
import json
import logging
import requests
from datetime import datetime, timezone

log = logging.getLogger(__name__)

class OKXTrader:
    BASE_URL = "https://www.okx.com"

    def __init__(self, flag="1"):
        self.api_key    = os.environ.get("OKX_API_KEY", "")
        self.secret_key = os.environ.get("OKX_SECRET_KEY", "")
        self.passphrase = os.environ.get("OKX_PASSPHRASE", "")
        self.flag       = flag  # "1"=demo "0"=live
        log.info(f"OKX Trader init | Mode: {'DEMO' if flag=='1' else 'LIVE'}")

    def _sign(self, timestamp, method, path, body=""):
        msg = f"{timestamp}{method}{path}{body}"
        sig = hmac.new(
            self.secret_key.encode(),
            msg.encode(),
            hashlib.sha256
        ).digest()
        return base64.b64encode(sig).decode()

    def _headers(self, method, path, body=""):
        ts  = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        sig = self._sign(ts, method, path, body)
        return {
            "OK-ACCESS-KEY":        self.api_key,
            "OK-ACCESS-SIGN":       sig,
            "OK-ACCESS-TIMESTAMP":  ts,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
            "x-simulated-trading":  self.flag,  # demo flag
            "Content-Type":         "application/json"
        }

    def _get(self, path, params=""):
        url  = self.BASE_URL + path
        hdrs = self._headers("GET", path + (f"?{params}" if params else ""))
        r    = requests.get(url, headers=hdrs, params=params, timeout=15)
        return r.json()

    def _post(self, path, body: dict):
        body_str = json.dumps(body)
        hdrs     = self._headers("POST", path, body_str)
        r        = requests.post(
            self.BASE_URL + path,
            headers=hdrs,
            data=body_str,
            timeout=15
        )
        return r.json()

    # ─── Get BTC Price ───────────────────────────────────────────────────────
    def get_price(self, instId="BTC-USDT"):
        try:
            r = requests.get(
                f"{self.BASE_URL}/api/v5/market/ticker?instId={instId}",
                timeout=10
            )
            data = r.json()
            price = float(data["data"][0]["last"])
            log.info(f"BTC Price: ${price:,.2f}")
            return price
        except Exception as e:
            log.error(f"get_price error: {e}")
            return None

    # ─── Get Balance ────────────────────────────────────────────────────────
    def get_balance(self):
        try:
            data = self._get("/api/v5/account/balance")
            for detail in data["data"][0]["details"]:
                if detail["ccy"] == "USDT":
                    bal = float(detail["availBal"])
                    log.info(f"Balance: ${bal:,.2f} USDT")
                    return bal
            return 0
        except Exception as e:
            log.error(f"get_balance error: {e}")
            return 0

    # ─── Get Open Position ──────────────────────────────────────────────────
    def get_position(self, instId="BTC-USDT"):
        try:
            data = self._get("/api/v5/account/positions", f"instId={instId}")
            if data["data"]:
                pos = data["data"][0]
                if float(pos.get("pos", 0)) != 0:
                    return pos
            return None
        except Exception as e:
            log.error(f"get_position error: {e}")
            return None

    # ─── Check PnL ──────────────────────────────────────────────────────────
    def check_pnl(self, position):
        try:
            return float(position.get("upl", 0))
        except:
            return 0

    # ─── Place Order ────────────────────────────────────────────────────────
    def place_order(self, instId, direction, amount, sl_price, tp_price):
        try:
            price    = self.get_price(instId)
            if not price:
                return {"success": False, "error": "Cannot get price"}

            side     = "buy"  if direction == "LONG"  else "sell"
            pos_side = "long" if direction == "LONG"  else "short"
            sz       = round(amount / price, 6)  # BTC amount

            # Main order
            order = {
                "instId":   instId,
                "tdMode":   "cash",   # spot for demo; use "cross" for futures
                "side":     side,
                "ordType":  "market",
                "sz":       str(sz),
            }

            log.info(f"Placing order: {order}")
            result = self._post("/api/v5/trade/order", order)
            log.info(f"Order result: {result}")

            if result.get("code") == "0":
                return {"success": True, "orderId": result["data"][0]["ordId"]}
            else:
                return {"success": False, "error": result.get("msg", "Unknown error")}

        except Exception as e:
            log.error(f"place_order error: {e}")
            return {"success": False, "error": str(e)}

    # ─── Close Position ─────────────────────────────────────────────────────
    def close_position(self, instId="BTC-USDT"):
        try:
            position = self.get_position(instId)
            if not position:
                return {"success": False, "error": "No open position"}

            pos_size = abs(float(position["pos"]))
            side     = "sell" if float(position["pos"]) > 0 else "buy"

            order = {
                "instId":  instId,
                "tdMode":  "cash",
                "side":    side,
                "ordType": "market",
                "sz":      str(pos_size)
            }

            result = self._post("/api/v5/trade/order", order)
            log.info(f"Close result: {result}")
            return {"success": result.get("code") == "0"}

        except Exception as e:
            log.error(f"close_position error: {e}")
            return {"success": False, "error": str(e)}
