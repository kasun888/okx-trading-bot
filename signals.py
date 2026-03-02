"""
🧠 5-Layer Signal Intelligence Engine
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Layer 1: Fear & Greed Index (Market Sentiment)
Layer 2: Macro Events (Fed, DXY, CPI)
Layer 3: Cross-Market (S&P500, Gold, Asia)
Layer 4: On-Chain Whale Data
Layer 5: Technical (RSI, MACD, Funding Rate)
"""

import requests
import logging
import json
from datetime import datetime, timezone
import pytz

log = logging.getLogger(__name__)

class SignalEngine:
    def __init__(self):
        self.sg_tz = pytz.timezone("Asia/Singapore")

    # ─── MASTER ANALYSIS ────────────────────────────────────────────────────
    def analyze(self):
        """
        Returns: (score 0-5, direction 'LONG'/'SHORT'/'NONE', details dict)
        """
        results = {}

        results["sentiment"]   = self._layer1_sentiment()
        results["macro"]       = self._layer2_macro()
        results["crossmarket"] = self._layer3_crossmarket()
        results["onchain"]     = self._layer4_onchain()
        results["technical"]   = self._layer5_technical()

        # Count bullish vs bearish signals
        bull = sum(1 for v in results.values() if v["signal"] == "BULL")
        bear = sum(1 for v in results.values() if v["signal"] == "BEAR")

        score     = max(bull, bear)
        direction = "LONG" if bull > bear else ("SHORT" if bear > bull else "NONE")

        # Must have clear majority
        if bull == bear:
            direction = "NONE"
            score     = 0

        details = "\n".join([f"Layer {i+1} ({k}): {v['signal']} - {v['reason']}"
                             for i, (k, v) in enumerate(results.items())])

        log.info(f"Bull: {bull} | Bear: {bear} | Direction: {direction}")
        return score, direction, details

    # ─── LAYER 1: FEAR & GREED ───────────────────────────────────────────────
    def _layer1_sentiment(self):
        try:
            r    = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
            data = r.json()
            val  = int(data["data"][0]["value"])
            name = data["data"][0]["value_classification"]
            log.info(f"Fear & Greed: {val} ({name})")

            if val >= 65:
                return {"signal": "BULL", "reason": f"Greed={val} ({name}) → bullish momentum"}
            elif val <= 35:
                return {"signal": "BEAR", "reason": f"Fear={val} ({name}) → bearish momentum"}
            else:
                return {"signal": "NEUTRAL", "reason": f"Neutral={val} → no clear signal"}
        except Exception as e:
            log.warning(f"Layer 1 error: {e}")
            return {"signal": "NEUTRAL", "reason": "Data unavailable"}

    # ─── LAYER 2: MACRO (DXY + Economic Calendar) ───────────────────────────
    def _layer2_macro(self):
        try:
            # DXY via Yahoo Finance API (USD strength)
            r    = requests.get(
                "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB?interval=1d&range=5d",
                timeout=10, headers={"User-Agent": "Mozilla/5.0"}
            )
            data  = r.json()
            closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
            closes = [c for c in closes if c is not None]

            if len(closes) >= 2:
                dxy_change = ((closes[-1] - closes[-2]) / closes[-2]) * 100
                log.info(f"DXY change: {dxy_change:.2f}%")

                # DXY falls = BTC rises (inverse correlation)
                if dxy_change <= -0.3:
                    return {"signal": "BULL", "reason": f"DXY falling {dxy_change:.2f}% → BTC bullish"}
                elif dxy_change >= 0.3:
                    return {"signal": "BEAR", "reason": f"DXY rising {dxy_change:.2f}% → BTC bearish"}

            # Check day of week (avoid major news days)
            now = datetime.now(self.sg_tz)
            if now.weekday() == 2 and now.day <= 15:  # Wednesday mid-month = CPI risk
                return {"signal": "BEAR", "reason": "Possible CPI/Fed day → caution"}

            return {"signal": "NEUTRAL", "reason": "DXY stable, no macro events"}

        except Exception as e:
            log.warning(f"Layer 2 error: {e}")
            return {"signal": "NEUTRAL", "reason": "Macro data unavailable"}

    # ─── LAYER 3: CROSS-MARKET (S&P500 + Gold) ──────────────────────────────
    def _layer3_crossmarket(self):
        try:
            signals = []

            # S&P500 futures
            for ticker, name in [("^GSPC", "SP500"), ("GC=F", "Gold")]:
                r    = requests.get(
                    f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d",
                    timeout=10, headers={"User-Agent": "Mozilla/5.0"}
                )
                data   = r.json()
                closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
                closes = [c for c in closes if c is not None]

                if len(closes) >= 2:
                    chg = ((closes[-1] - closes[-2]) / closes[-2]) * 100
                    log.info(f"{name} change: {chg:.2f}%")
                    signals.append(chg)

            if signals:
                avg = sum(signals) / len(signals)
                if avg > 0.5:
                    return {"signal": "BULL", "reason": f"Risk assets up avg {avg:.1f}% → BTC likely follows"}
                elif avg < -0.5:
                    return {"signal": "BEAR", "reason": f"Risk assets down avg {avg:.1f}% → BTC likely follows"}

            return {"signal": "NEUTRAL", "reason": "Cross-market mixed signals"}

        except Exception as e:
            log.warning(f"Layer 3 error: {e}")
            return {"signal": "NEUTRAL", "reason": "Cross-market data unavailable"}

    # ─── LAYER 4: ON-CHAIN WHALE DATA ───────────────────────────────────────
    def _layer4_onchain(self):
        try:
            # BTC exchange netflow (positive = selling, negative = accumulating)
            r    = requests.get(
                "https://api.coinglass.com/api/index/btc-exchanges-reserve",
                timeout=10,
                headers={"accept": "application/json"}
            )

            if r.status_code == 200:
                data = r.json()
                # Simplified: check BTC on exchanges trend
                if "data" in data and data["data"]:
                    latest = data["data"][-1]
                    change = latest.get("change", 0)
                    if change < -1000:  # BTC leaving exchanges = bullish
                        return {"signal": "BULL", "reason": f"Whales withdrawing {abs(change):.0f} BTC from exchanges → bullish"}
                    elif change > 1000:  # BTC entering exchanges = bearish
                        return {"signal": "BEAR", "reason": f"Whales depositing {change:.0f} BTC to exchanges → bearish"}

            # Fallback: use BTC dominance
            r2   = requests.get("https://api.coingecko.com/api/v3/global", timeout=10)
            data = r2.json()
            btc_dom = data["data"]["market_cap_percentage"]["btc"]
            log.info(f"BTC Dominance: {btc_dom:.1f}%")

            if btc_dom > 55:
                return {"signal": "BULL", "reason": f"BTC dominance high {btc_dom:.1f}% → strong BTC market"}
            elif btc_dom < 45:
                return {"signal": "BEAR", "reason": f"BTC dominance low {btc_dom:.1f}% → altcoin season/risk off"}

            return {"signal": "NEUTRAL", "reason": f"BTC dominance neutral {btc_dom:.1f}%"}

        except Exception as e:
            log.warning(f"Layer 4 error: {e}")
            return {"signal": "NEUTRAL", "reason": "On-chain data unavailable"}

    # ─── LAYER 5: TECHNICAL + FUNDING RATE ──────────────────────────────────
    def _layer5_technical(self):
        try:
            # Get BTC OHLCV from OKX public API (no auth needed)
            r    = requests.get(
                "https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=1H&limit=50",
                timeout=10
            )
            data   = r.json()
            candles = data["data"]

            closes = [float(c[4]) for c in reversed(candles)]

            # RSI calculation
            rsi = self._calc_rsi(closes, 14)

            # Simple MACD
            ema12 = self._ema(closes, 12)
            ema26 = self._ema(closes, 26)
            macd  = ema12[-1] - ema26[-1]
            macd_prev = self._ema(closes[:-1], 12)[-1] - self._ema(closes[:-1], 26)[-1]
            macd_cross = macd > 0 and macd_prev <= 0  # bullish cross
            macd_cross_bear = macd < 0 and macd_prev >= 0  # bearish cross

            # Funding rate from OKX
            r2     = requests.get(
                "https://www.okx.com/api/v5/public/funding-rate?instId=BTC-USDT-SWAP",
                timeout=10
            )
            funding = float(r2.json()["data"][0]["fundingRate"])
            log.info(f"RSI: {rsi:.1f} | MACD: {macd:.0f} | Funding: {funding:.4f}")

            bull_signals = 0
            bear_signals = 0
            reasons      = []

            # RSI signals
            if rsi < 35:
                bull_signals += 1
                reasons.append(f"RSI oversold {rsi:.0f}")
            elif rsi > 65:
                bear_signals += 1
                reasons.append(f"RSI overbought {rsi:.0f}")

            # MACD signals
            if macd_cross:
                bull_signals += 1
                reasons.append("MACD bullish cross")
            elif macd_cross_bear:
                bear_signals += 1
                reasons.append("MACD bearish cross")
            elif macd > 0:
                bull_signals += 1
                reasons.append("MACD positive")
            else:
                bear_signals += 1
                reasons.append("MACD negative")

            # Funding rate signal (negative = shorts paying = bullish)
            if funding < -0.0001:
                bull_signals += 1
                reasons.append(f"Funding negative {funding:.4f} → short squeeze likely")
            elif funding > 0.0003:
                bear_signals += 1
                reasons.append(f"Funding high {funding:.4f} → overleveraged longs")

            reason_str = " | ".join(reasons)
            if bull_signals > bear_signals:
                return {"signal": "BULL", "reason": reason_str}
            elif bear_signals > bull_signals:
                return {"signal": "BEAR", "reason": reason_str}
            else:
                return {"signal": "NEUTRAL", "reason": reason_str}

        except Exception as e:
            log.warning(f"Layer 5 error: {e}")
            return {"signal": "NEUTRAL", "reason": "Technical data unavailable"}

    # ─── HELPERS ────────────────────────────────────────────────────────────
    def _calc_rsi(self, closes, period=14):
        gains, losses = [], []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i-1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            return 100
        rs  = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _ema(self, data, period):
        emas = [sum(data[:period]) / period]
        mult = 2 / (period + 1)
        for price in data[period:]:
            emas.append((price - emas[-1]) * mult + emas[-1])
        return emas
