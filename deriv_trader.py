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
        log.info(f"Deriv Trader | Token: {self.token[:8]}**** len={len(self.token)}")

    def _ws_request(self, payload):
        result = {"data": None}
        done   = threading.Event()

        def on_open(ws):
            ws.send(json.dumps(payload))

        def on_message(ws, message):
            result["data"] = json.loads(message)
            done.set()
            ws.close()

        def on_error(ws, error):
            log.error(f"WS error: {error}")
            done.set()

        ws = websocket.WebSocketApp(
            "wss://ws.derivws.com/websockets/v3?app_id=1089",
            on_open    = on_open,
            on_message = on_message,
            on_error   = on_error
        )
        t = threading.Thread(target=ws.run_forever)
        t.daemon = True
        t.start()
        done.wait(timeout=20)
        return result["data"]

    def _ws_sequence(self, payloads):
        results = []
        done    = threading.Event()
        queue   = list(payloads)

        def on_open(ws):
            if queue:
                ws.send(json.dumps(queue[0]))

        def on_message(ws, message):
            data = json.loads(message)
            results.append(data)
            queue.pop(0)
            if queue:
                ws.send(json.dumps(queue[0]))
            else:
                done.set()
                ws.close()

        def on_error(ws, error):
            log.error(f"WS error: {error}")
            done.set()

        ws = websocket.WebSocketApp(
            "wss://ws.derivws.com/websockets/v3?app_id=1089",
            on_open    = on_open,
            on_message = on_message,
            on_error   = on_error
        )
        t = threading.Thread(target=ws.run_forever)
        t.daemon = True
        t.start()
        done.wait(timeout=30)
        return results

    def login(self):
        try:
            log.info("Connecting to Deriv WebSocket...")
            resp = self._ws_request({"authorize": self.token})
            log.info(f"Auth response: {json.dumps(resp)[:300]}")

            if resp is None:
                log.error("No response from Deriv!")
                return False

            if "error" in resp:
                log.error(f"Auth error: {resp['error']['message']}")
                return False

            if "authorize" in resp:
                self.account = resp["authorize"]["loginid"]
                self.balance = float(resp["authorize"]["balance"])
                log.info(f"Login success! Account: {self.account} Balance: {self.balance}")
                return True

            log.error(f"Unknown response: {resp}")
            return False
        except Exception as e:
            log.error(f"Login error: {e}")
            return False

    def get_balance(self):
        return self.balance

    def get_price(self, asset):
        try:
            symbol  = SYMBOLS.get(asset, "frxEURUSD")
            results = self._ws_sequence([
                {"authorize": self.token},
                {"ticks": symbol}
            ])
            for r in results:
                if "tick" in r:
                    price = float(r["tick"]["quote"])
                    log.info(f"{asset}: {price}")
                    return price, price, price
            return None, None, None
        except Exception as e:
            log.error(f"get_price error: {e}")
            return None, None, None

    def get_position(self, asset):
        try:
            symbol  = SYMBOLS.get(asset, "frxEURUSD")
            results = self._ws_sequence([
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

            results = self._ws_sequence([
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
                if "error" in r:
                    return {"success": False, "error": r["error"]["message"]}
                if "proposal" in r:
                    proposal_id = r["proposal"]["id"]

            if not proposal_id:
                return {"success": False, "error": "No proposal received"}

            results2 = self._ws_sequence([
                {"authorize": self.token},
                {"buy": proposal_id, "price": size}
            ])

            for r in results2:
                if "error" in r:
                    return {"success": False, "error": r["error"]["message"]}
                if "buy" in r:
                    contract_id = r["buy"]["contract_id"]
                    log.info(f"Trade placed! ID: {contract_id}")
                    return {"success": True, "contract_id": contract_id}

            return {"success": False, "error": "No response"}
        except Exception as e:
            log.error(f"place_order error: {e}")
            return {"success": False, "error": str(e)}

    def close_position(self, position):
        try:
            contract_id = position.get("contract_id")
            results = self._ws_sequence([
                {"authorize": self.token},
                {"sell": contract_id, "price": 0}
            ])
            for r in results:
                if "sell" in r:
                    return {"success": True}
            return {"success": False}
        except Exception as e:
            log.error(f"close_position error: {e}")
            return {"success": False, "error": str(e)}
