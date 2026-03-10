"""
Análisis técnico para trading autónomo.
Indicadores: RSI, MACD, Bollinger Bands, EMA, Volume, ATR, VWAP.
Generación de señales de compra/venta con scores de confianza.
"""

import asyncio
import logging
import aiohttp
import pandas as pd
import ta
from typing import Optional

logger = logging.getLogger("beeatrix.analysis")


class TechnicalAnalyzer:

    # ── Datos OHLCV ─────────────────────────────────────────────────────

    async def get_ohlcv_coingecko(self, coin_id: str, days: int = 7) -> Optional[pd.DataFrame]:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
        params = {"vs_currency": "usd", "days": days}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
            if not data:
                return None
            df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df = df.set_index("timestamp").sort_index()
            df["volume"] = 0.0  # CoinGecko OHLC no incluye volume en este endpoint
            return df
        except Exception as e:
            logger.warning("OHLCV error for %s: %s", coin_id, e)
            return None

    async def get_ohlcv_dexscreener(self, pair_address: str, chain: str = "solana") -> Optional[pd.DataFrame]:
        url = f"https://api.dexscreener.com/latest/dex/pairs/{chain}/{pair_address}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
            pairs = data.get("pairs", [])
            if not pairs:
                return None
            # DexScreener no ofrece OHLCV histórico directamente — devuelve info del par
            return None
        except Exception as e:
            logger.warning("DexScreener OHLCV error: %s", e)
            return None

    # ── Indicadores ──────────────────────────────────────────────────────

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        if len(df) < 20:
            return df
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df.get("volume", pd.Series([0] * len(df)))

        # RSI (14)
        try:
            df["rsi"] = ta.momentum.RSIIndicator(close, window=14).rsi()
        except Exception:
            df["rsi"] = 50.0

        # MACD
        try:
            macd_ind = ta.trend.MACD(close)
            df["macd"] = macd_ind.macd()
            df["macd_signal"] = macd_ind.macd_signal()
            df["macd_hist"] = macd_ind.macd_diff()
        except Exception:
            df["macd"] = df["macd_signal"] = df["macd_hist"] = 0.0

        # Bollinger Bands (20, 2)
        try:
            bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
            df["bb_upper"] = bb.bollinger_hband()
            df["bb_lower"] = bb.bollinger_lband()
            df["bb_mid"] = bb.bollinger_mavg()
            df["bb_pct"] = bb.bollinger_pband()
        except Exception:
            df["bb_upper"] = df["bb_lower"] = df["bb_mid"] = close
            df["bb_pct"] = 0.5

        # EMAs
        try:
            df["ema_9"]  = ta.trend.EMAIndicator(close, window=9).ema_indicator()
            df["ema_21"] = ta.trend.EMAIndicator(close, window=21).ema_indicator()
            df["ema_50"] = ta.trend.EMAIndicator(close, window=50).ema_indicator() if len(df) >= 50 else close
        except Exception:
            df["ema_9"] = df["ema_21"] = df["ema_50"] = close

        # ATR (14) — volatilidad
        try:
            df["atr"] = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range()
        except Exception:
            df["atr"] = 0.0

        # Stochastic RSI
        try:
            stoch = ta.momentum.StochRSIIndicator(close)
            df["stoch_k"] = stoch.stochrsi_k()
            df["stoch_d"] = stoch.stochrsi_d()
        except Exception:
            df["stoch_k"] = df["stoch_d"] = 0.5

        return df

    # ── Señales de trading ────────────────────────────────────────────────

    def generate_signal(self, df: pd.DataFrame) -> dict:
        """Genera señal de trading con score de confianza 0-100."""
        if len(df) < 20:
            return {"signal": "HOLD", "confidence": 0, "reason": "Datos insuficientes"}

        df = self.compute_indicators(df)
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last

        buy_signals = []
        sell_signals = []

        # RSI
        rsi = last.get("rsi", 50)
        if rsi < 30:
            buy_signals.append(f"RSI sobrevendido ({rsi:.1f})")
        elif rsi > 70:
            sell_signals.append(f"RSI sobrecomprado ({rsi:.1f})")

        # MACD crossover
        macd = last.get("macd", 0)
        macd_sig = last.get("macd_signal", 0)
        prev_macd = prev.get("macd", 0)
        prev_macd_sig = prev.get("macd_signal", 0)
        if prev_macd <= prev_macd_sig and macd > macd_sig:
            buy_signals.append("MACD cruce alcista")
        elif prev_macd >= prev_macd_sig and macd < macd_sig:
            sell_signals.append("MACD cruce bajista")
        if macd > 0:
            buy_signals.append("MACD positivo")
        else:
            sell_signals.append("MACD negativo")

        # Bollinger Bands
        bb_pct = last.get("bb_pct", 0.5)
        if bb_pct < 0.05:
            buy_signals.append("Precio en banda inferior BB")
        elif bb_pct > 0.95:
            sell_signals.append("Precio en banda superior BB")

        # EMA trend
        ema_9 = last.get("ema_9", 0)
        ema_21 = last.get("ema_21", 0)
        ema_50 = last.get("ema_50", 0)
        close = last.get("close", 0)
        if ema_9 > ema_21 > ema_50 and close > ema_9:
            buy_signals.append("EMA stack alcista")
        elif ema_9 < ema_21 < ema_50 and close < ema_9:
            sell_signals.append("EMA stack bajista")

        # Stochastic RSI
        stoch_k = last.get("stoch_k", 0.5)
        stoch_d = last.get("stoch_d", 0.5)
        if stoch_k < 0.2 and stoch_d < 0.2:
            buy_signals.append(f"Stoch RSI sobrevendido ({stoch_k*100:.0f})")
        elif stoch_k > 0.8 and stoch_d > 0.8:
            sell_signals.append(f"Stoch RSI sobrecomprado ({stoch_k*100:.0f})")

        total = len(buy_signals) + len(sell_signals)
        if total == 0:
            return {"signal": "HOLD", "confidence": 0, "reason": "Sin señales claras", "buy": [], "sell": []}

        buy_score = len(buy_signals) / total * 100
        sell_score = len(sell_signals) / total * 100

        if buy_score >= 60:
            signal = "BUY"
            confidence = buy_score
            reason = " | ".join(buy_signals)
        elif sell_score >= 60:
            signal = "SELL"
            confidence = sell_score
            reason = " | ".join(sell_signals)
        else:
            signal = "HOLD"
            confidence = max(buy_score, sell_score)
            reason = "Señales mixtas"

        return {
            "signal": signal,
            "confidence": confidence,
            "reason": reason,
            "buy_signals": buy_signals,
            "sell_signals": sell_signals,
            "rsi": rsi,
            "macd": macd,
            "bb_pct": bb_pct,
            "close": close,
            "atr": last.get("atr", 0),
        }

    def format_signal_report(self, token: str, signal_data: dict, token_info: dict = None) -> str:
        sig = signal_data.get("signal", "HOLD")
        conf = signal_data.get("confidence", 0)
        reason = signal_data.get("reason", "")
        rsi = signal_data.get("rsi", 50)
        macd = signal_data.get("macd", 0)
        bb_pct = signal_data.get("bb_pct", 0.5) * 100

        sig_emoji = {"BUY": "COMPRA", "SELL": "VENTA", "HOLD": "MANTENER"}.get(sig, sig)

        lines = [
            f"Analisis tecnico: {token}",
            f"Señal: {sig_emoji} (confianza: {conf:.0f}%)",
            f"Razon: {reason}",
            f"RSI: {rsi:.1f} | MACD: {macd:.6f} | BB: {bb_pct:.0f}%",
        ]
        if token_info:
            price = token_info.get("price_usd", 0)
            c1h = token_info.get("change_1h", 0)
            c24h = token_info.get("change_24h", 0)
            lines.insert(1, f"Precio: ${price:.8f}" if price < 0.01 else f"Precio: ${price:,.4f}")
            lines.append(f"1h: {'+' if c1h >= 0 else ''}{c1h:.2f}% | 24h: {'+' if c24h >= 0 else ''}{c24h:.2f}%")

        return "\n".join(lines)


analyzer = TechnicalAnalyzer()
