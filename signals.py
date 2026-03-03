"""
5-Layer Signal Engine
Uses OANDA real-time candles for Layer 5
Much more accurate than Yahoo Finance!
"""

import os
import requests
import logging
import math
from datetime import datetime
import pytz

log = logging.getLogger(__name__)

class SignalEngine:
    def __init__(self):
        self.sg_tz      = pytz.timezone("Asia/Singapore")
        self.asset      = "EURUSD"
        self.api_key    = os.environ.get("OANDA_API_KEY", "")
        self.account_id = os.environ.get("OANDA_ACCOUNT_ID", "")
        self.base_url   = "https://api-fxpractice.oanda.com"
        self.headers    = {"Authorization": f"Bearer {self.api_key}"}

    # OANDA instrument map
    OANDA_MAP = {
        "EURUSD": "EUR_USD",
        "GBPUSD": "GBP_USD",
        "XAUUSD": "XAU_USD"
    }

    def analyze(self, asset="EURUSD"):
        self.asset = asset
        log.info(f"Analyzing {asset}...")

        l1 = self._layer1_sentiment()
        l2 = self._layer2_macro()
        l3 = self._layer3_crossmarket()
        l4 = self._layer4_session()
        l5 = self._layer5_technical()

        layers = [l1, l2, l3, l4, l5]
        bull   = sum(1 for l in layers if l["signal"] == "BULL")
        bear   = sum(1 for l in layers if l["signal"] == "BEAR")

        log.info(f"L1:{l1['signal']} L2:{l2['signal']} L3:{l3['signal']} L4:{l4['signal']} L5:{l5['signal']}")
        log.info(f"Bull:{bull} Bear:{bear}")

        if bull > bear:
            score     = bull
            direction = "BUY"
        elif bear > bull:
            score     = bear
            direction = "SELL"
        else:
            score     = 0
            direction = "NONE"

        details = (
            f"L1 Sentiment: {l1['signal']} | {l1['reason']}\n"
            f"L2 Macro: {l2['signal']} | {l2['reason']}\n"
            f"L3 Market: {l3['signal']} | {l3['reason']}\n"
            f"L4 Session: {l4['signal']} | {l4['reason']}\n"
            f"L5 Technical: {l5['signal']} | {l5['reason']}"
        )

        return score, direction, details

    # LAYER 1: USD Sentiment via DXY
    def _layer1_sentiment(self):
        try:
            r = requests.get(
                "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB?interval=1d&range=5d",
                timeout=10, headers={"User-Agent": "Mozilla/5.0"}
            )
            closes = [c for c in r.json()["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c]
            if len(closes) >= 2:
                chg = ((closes[-1] - closes[-2]) / closes[-2]) * 100
                log.info(f"DXY change: {chg:+.3f}%")

                if self.asset == "XAUUSD":
                    if chg < -0.2:
                        return {"signal": "BULL", "reason": f"USD weak {chg:.2f}% = Gold up"}
                    elif chg > 0.2:
                        return {"signal": "BEAR", "reason": f"USD strong {chg:.2f}% = Gold down"}
                else:
                    if chg < -0.2:
                        return {"signal": "BULL", "reason": f"USD weak {chg:.2f}% = {self.asset} up"}
                    elif chg > 0.2:
                        return {"signal": "BEAR", "reason": f"USD strong {chg:.2f}% = {self.asset} down"}

            return {"signal": "NEUTRAL", "reason": "DXY flat"}
        except Exception as e:
            log.warning(f"L1 error: {e}")
            return {"signal": "NEUTRAL", "reason": "L1 unavailable"}

    # LAYER 2: Bond Yields (10Y Treasury)
    def _layer2_macro(self):
        try:
            r = requests.get(
                "https://query1.finance.yahoo.com/v8/finance/chart/^TNX?interval=1d&range=5d",
                timeout=10, headers={"User-Agent": "Mozilla/5.0"}
            )
            closes = [c for c in r.json()["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c]
            if len(closes) >= 2:
                chg = closes[-1] - closes[-2]
                log.info(f"10Y yield change: {chg:+.3f}")

                if self.asset == "XAUUSD":
                    if chg < -0.05:
                        return {"signal": "BULL", "reason": f"Yields falling = Gold up"}
                    elif chg > 0.05:
                        return {"signal": "BEAR", "reason": f"Yields rising = Gold down"}
                else:
                    if chg < -0.05:
                        return {"signal": "BULL", "reason": f"Yields falling = USD weak = {self.asset} up"}
                    elif chg > 0.05:
                        return {"signal": "BEAR", "reason": f"Yields rising = USD strong = {self.asset} down"}

            return {"signal": "NEUTRAL", "reason": "Yields flat"}
        except Exception as e:
            log.warning(f"L2 error: {e}")
            return {"signal": "NEUTRAL", "reason": "L2 unavailable"}

    # LAYER 3: SP500 Risk Sentiment
    def _layer3_crossmarket(self):
        try:
            r = requests.get(
                "https://query1.finance.yahoo.com/v8/finance/chart/^GSPC?interval=1d&range=5d",
                timeout=10, headers={"User-Agent": "Mozilla/5.0"}
            )
            closes = [c for c in r.json()["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c]
            if len(closes) >= 2:
                chg = ((closes[-1] - closes[-2]) / closes[-2]) * 100
                log.info(f"SP500 change: {chg:+.2f}%")

                if self.asset == "XAUUSD":
                    if chg < -0.5:
                        return {"signal": "BULL", "reason": f"Risk-off SP500 {chg:.1f}% = Gold safe haven"}
                    elif chg > 0.5:
                        return {"signal": "BEAR", "reason": f"Risk-on SP500 +{chg:.1f}% = Gold weak"}
                else:
                    if chg > 0.5:
                        return {"signal": "BULL", "reason": f"Risk-on SP500 +{chg:.1f}% = {self.asset} up"}
                    elif chg < -0.5:
                        return {"signal": "BEAR", "reason": f"Risk-off SP500 {chg:.1f}% = {self.asset} down"}

            return {"signal": "NEUTRAL", "reason": "SP500 flat"}
        except Exception as e:
            log.warning(f"L3 error: {e}")
            return {"signal": "NEUTRAL", "reason": "L3 unavailable"}

    # LAYER 4: Trading Session Strength
    def _layer4_session(self):
        try:
            now  = datetime.now(self.sg_tz)
            hour = now.hour

            # London open 3pm-5pm SGT = strongest moves
            if 15 <= hour <= 17:
                return {"signal": "BULL", "reason": f"London open {hour}:00 SGT = high volatility"}

            # London+NY overlap 9pm-11pm SGT = BEST session
            if 21 <= hour <= 23:
                return {"signal": "BULL", "reason": f"London+NY overlap {hour}:00 SGT = BEST session!"}

            # NY open 9:30pm SGT
            if hour == 20:
                return {"signal": "BULL", "reason": f"NY open {hour}:00 SGT = good momentum"}

            # Dead hours Asia 1am-7am SGT = avoid
            if 1 <= hour <= 7:
                return {"signal": "BEAR", "reason": f"Asia slow hours {hour}:00 SGT = low momentum"}

            # Friday afternoon = reduce risk
            if now.weekday() == 4 and hour >= 18:
                return {"signal": "BEAR", "reason": "Friday PM = position closing risk"}

            return {"signal": "NEUTRAL", "reason": f"Normal hours {hour}:00 SGT"}
        except Exception as e:
            log.warning(f"L4 error: {e}")
            return {"signal": "NEUTRAL", "reason": "L4 unavailable"}

    # LAYER 5: Technical Analysis using OANDA candles
    def _layer5_technical(self):
        try:
            instrument = self.OANDA_MAP.get(self.asset, "EUR_USD")

            # Get 100 candles of 15min data from OANDA
            url    = f"{self.base_url}/v3/instruments/{instrument}/candles"
            params = {"count": "100", "granularity": "M15", "price": "M"}
            r      = requests.get(url, headers=self.headers, params=params, timeout=10)

            if r.status_code != 200:
                log.warning(f"OANDA candles failed: {r.status_code} - falling back to Yahoo")
                return self._layer5_yahoo_fallback()

            candles = r.json()["candles"]
            closes  = [float(c["mid"]["c"]) for c in candles if c["complete"]]
            highs   = [float(c["mid"]["h"]) for c in candles if c["complete"]]
            lows    = [float(c["mid"]["l"]) for c in candles if c["complete"]]

            if len(closes) < 30:
                return {"signal": "NEUTRAL", "reason": "Not enough candles"}

            bull = 0
            bear = 0
            reasons = []

            # RSI
            rsi = self._rsi(closes, 14)
            log.info(f"RSI: {rsi:.1f}")
            if rsi < 35:
                bull += 1
                reasons.append(f"RSI oversold {rsi:.0f}")
            elif rsi > 65:
                bear += 1
                reasons.append(f"RSI overbought {rsi:.0f}")

            # MACD
            ema12     = self._ema(closes, 12)
            ema26     = self._ema(closes, 26)
            macd      = [a - b for a, b in zip(ema12[-len(ema26):], ema26)]
            sig       = self._ema(macd, 9)
            hist      = macd[-1] - sig[-1]
            prev_hist = macd[-2] - sig[-2]
            log.info(f"MACD hist: {hist:.6f}")
            if hist > 0 and prev_hist <= 0:
                bull += 1
                reasons.append("MACD bullish cross")
            elif hist < 0 and prev_hist >= 0:
                bear += 1
                reasons.append("MACD bearish cross")
            elif hist > 0:
                bull += 1
                reasons.append("MACD positive")
            elif hist < 0:
                bear += 1
                reasons.append("MACD negative")

            # Bollinger Bands
            bb_mid = sum(closes[-20:]) / 20
            bb_std = math.sqrt(sum((c - bb_mid)**2 for c in closes[-20:]) / 20)
            bb_up  = bb_mid + 2 * bb_std
            bb_dn  = bb_mid - 2 * bb_std
            pct_b  = (closes[-1] - bb_dn) / (bb_up - bb_dn) * 100 if bb_up != bb_dn else 50
            log.info(f"BB%B: {pct_b:.1f}")
            if pct_b < 20:
                bull += 1
                reasons.append(f"BB oversold {pct_b:.0f}%")
            elif pct_b > 80:
                bear += 1
                reasons.append(f"BB overbought {pct_b:.0f}%")

            # Stochastic
            stoch = self._stochastic(closes, highs, lows, 14)
            log.info(f"Stoch: {stoch:.1f}")
            if stoch < 25:
                bull += 1
                reasons.append(f"Stoch oversold {stoch:.0f}")
            elif stoch > 75:
                bear += 1
                reasons.append(f"Stoch overbought {stoch:.0f}")

            # MA trend
            if len(closes) >= 50:
                ma50 = sum(closes[-50:]) / 50
                ma20 = sum(closes[-20:]) / 20
                if ma20 > ma50:
                    bull += 1
                    reasons.append("MA20 > MA50 uptrend")
                else:
                    bear += 1
                    reasons.append("MA20 < MA50 downtrend")

            reason_str = " | ".join(reasons) if reasons else "No signals"
            log.info(f"Technical bull={bull} bear={bear}")

            if bull > bear:
                return {"signal": "BULL", "reason": reason_str}
            elif bear > bull:
                return {"signal": "BEAR", "reason": reason_str}
            return {"signal": "NEUTRAL", "reason": reason_str}

        except Exception as e:
            log.warning(f"L5 OANDA error: {e} - trying Yahoo")
            return self._layer5_yahoo_fallback()

    # Fallback if OANDA candles fail
    def _layer5_yahoo_fallback(self):
        try:
            ticker_map = {"EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "XAUUSD": "GC=F"}
            ticker     = ticker_map.get(self.asset, "EURUSD=X")
            r          = requests.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1h&range=5d",
                timeout=10, headers={"User-Agent": "Mozilla/5.0"}
            )
            quotes = r.json()["chart"]["result"][0]["indicators"]["quote"][0]
            closes = [c for c in quotes["close"] if c]
            if len(closes) < 20:
                return {"signal": "NEUTRAL", "reason": "No data"}

            rsi = self._rsi(closes, 14)
            if rsi < 35:
                return {"signal": "BULL", "reason": f"Yahoo RSI oversold {rsi:.0f}"}
            elif rsi > 65:
                return {"signal": "BEAR", "reason": f"Yahoo RSI overbought {rsi:.0f}"}
            return {"signal": "NEUTRAL", "reason": f"Yahoo RSI neutral {rsi:.0f}"}
        except:
            return {"signal": "NEUTRAL", "reason": "No technical data"}

    def _rsi(self, closes, period=14):
        gains, losses = [], []
        for i in range(1, len(closes)):
            d = closes[i] - closes[i-1]
            gains.append(max(d, 0))
            losses.append(max(-d, 0))
        if len(gains) < period:
            return 50
        ag = sum(gains[-period:]) / period
        al = sum(losses[-period:]) / period
        if al == 0:
            return 100
        return 100 - (100 / (1 + ag / al))

    def _ema(self, data, period):
        if len(data) < period:
            return [sum(data) / len(data)] * len(data)
        emas = [sum(data[:period]) / period]
        mult = 2 / (period + 1)
        for p in data[period:]:
            emas.append((p - emas[-1]) * mult + emas[-1])
        return emas

    def _stochastic(self, closes, highs, lows, period=14):
        if len(closes) < period:
            return 50
        h = max(highs[-period:])
        l = min(lows[-period:])
        if h == l:
            return 50
        return ((closes[-1] - l) / (h - l)) * 100
