"""
Deriv Trade Executor
Uses WebSocket API with API token
"""

import os
import json
import logging
import websocket
import threading
import time

log = logging.getLogger(__name__)

DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"

SYMBOLS = {
    "EURUSD": "frxEURUSD",
    "GBPUSD": "frxGBPUSD",
    "XAUUSD": "frxXAUUSD"
}

class DerivTrader:
    def __init__(self):
        self.token   = os.environ.get("DERIV_TOKEN", "")
        self.account = None
        self.balance = 0
        self.authorized = False
        log.info(f"Deriv Trader | Token: {self.token[:8]}****  len={len(self.token)}")

    def _send_request(self, request):
        import websocket as ws_lib
        result = {}
        event  = threading.Event()

        def on_message(ws, message):
            result["data"] = json.loads(message)
            event.set()

        def on_error(ws, error):
            result["error"] = str(error)
            event.set()

        wsapp = ws_lib.WebSocketApp(
            DERIV_WS_URL,
            on_message = on_message,
            on_error   = on_error
        )

        t = threading.Thread(target=wsapp.run_forever)
        t.daemon = True
        t.start()
        time.sleep(1)
        wsapp.send(json.dumps(request))
        event.wait(timeout=15)
        wsapp.close()
        return result.get("data", {})

    def _send_sequence(self, requests):
        import websocket as ws_lib
        results = []
        event   = threading.Event()
        q       = list(requests)

        def on_open(ws):
            if q:
                ws.send(json.dumps(q[0]))

        def on_message(ws, message):
            data = json.loads(message)
            results.append(data)
            q.pop(0)
            if q:
                ws.send(json.dumps(q[0]))
            else:
                event.set()

        def on_error(ws, error):
            log.error(f"WS error: {error}")
            event.set()

        wsapp = ws_lib.WebSocketApp(
            DERIV_WS_URL,
            on_open    = on_open,
            on_message = on_message,
            on_error   = on_error
        )
        t = threading.Thread(target=wsapp.run_forever)
        t.daemon = True
        t.start()
        event.wait(timeout=30)
        wsapp.close()
        return results

    def login(self):
        try:
            log.info("Authorizing with Deriv...")
            resp = self._send_request({"authorize": self.token})
            log.info(f"Auth response: {json.dumps(resp)[:300]}")

            if "error" in resp:
                log.error(f"Auth failed: {resp['error']['message']}")
                return False

            if "authorize" in resp:
                self.account    = resp["authorize"]["loginid"]
                self.balance    = float(resp["authorize"]["balance"])
                self.authorized = True
                log.info(f"Authorized! Account: {self.account} Balance: {self.balance}")
                return True

            log.error(f"Unexpected response: {resp}")
            return False
        except Exception as e:
            log.error(f"Login error: {e}")
            return False

    def get_balance(self):
        return self.balance

    def get_price(self, asset):
        try:
            symbol = SYMBOLS.get(asset, "frxEURUSD")
            results = self._send_sequence([
                {"authorize": self.token},
                {"ticks": symbol}
            ])
            for r in results:
                if "tick" in r:
                    price = float(r["tick"]["quote"])
                    log.info(f"{asset} price: {price}")
                    return price, price, price
            return None, None, None
        except Exception as e:
            log.error(f"get_price error: {e}")
            return None, None, None

    def get_position(self, asset):
        try:
            symbol  = SYMBOLS.get(asset, "frxEURUSD")
            results = self._send_sequence([
                {"authorize": self.token},
                {"portfolio": 1}
            ])
            for r in results:
                if "portfolio" in r:
                    for c in r["portfolio"].get("contracts", []):
                        if c.get("symbol") == symbol:
                            return c
            return None
        except Exception as e:
            log.error(f"get_position error: {e}")
            return None

    def check_pnl(self, position):
        try:
            return float(position.get("profit", 0))
        except:
            return 0

    def place_order(self, asset, direction, size, stop_distance, limit_distance, currency="USD"):
        try:
            symbol        = SYMBOLS.get(asset, "frxEURUSD")
            contract_type = "CALL" if direction == "BUY" else "PUT"

            results = self._send_sequence([
                {"authorize": self.token},
                {
                    "proposal":      1,
                    "amount":        size,
                    "basis":         "stake",
                    "contract_type": contract_type,
                    "currency":      currency,
                    "duration":      5,
                    "duration_unit": "m",
                    "symbol":        symbol
                }
            ])

            proposal_id = None
            for r in results:
                if "proposal" in r:
                    if "error" in r:
                        return {"success": False, "error": r["error"]["message"]}
                    proposal_id = r["proposal"]["id"]
                    log.info(f"Proposal ID: {proposal_id}")

            if not proposal_id:
                return {"success": False, "error": "No proposal received"}

            results2 = self._send_sequence([
                {"authorize": self.token},
                {"buy": proposal_id, "price": size}
            ])

            for r in results2:
                if "buy" in r:
                    if "error" in r:
                        return {"success": False, "error": r["error"]["message"]}
                    contract_id = r["buy"]["contract_id"]
                    log.info(f"Contract placed! ID: {contract_id}")
                    return {"success": True, "contract_id": contract_id}

            return {"success": False, "error": "No buy response"}
        except Exception as e:
            log.error(f"place_order error: {e}")
            return {"success": False, "error": str(e)}

    def close_position(self, position):
        try:
            contract_id = position.get("contract_id")
            results = self._send_sequence([
                {"authorize": self.token},
                {"sell": contract_id, "price": 0}
            ])
            for r in results:
                if "sell" in r:
                    return {"success": True}
            return {"success": False, "error": "Close failed"}
        except Exception as e:
            log.error(f"close_position error: {e}")
            return {"success": False, "error": str(e)}
