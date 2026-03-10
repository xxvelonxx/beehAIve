"""
Generador de gráficos de precio como imágenes.
Genera candlestick charts con indicadores (RSI, MACD, Bollinger).
Manda el chart como imagen a Telegram/Discord.
"""

import asyncio
import logging
import io
from typing import Optional
import aiohttp
import pandas as pd

logger = logging.getLogger("beeatrix.charts")

COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "MATIC": "matic-network",
    "AVAX": "avalanche-2",
}


class ChartGenerator:

    async def get_ohlcv(self, symbol: str, days: int = 7) -> Optional[pd.DataFrame]:
        cg_id = COINGECKO_IDS.get(symbol.upper(), symbol.lower())
        url = f"https://api.coingecko.com/api/v3/coins/{cg_id}/ohlc"
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
            return df
        except Exception as e:
            logger.warning("OHLCV error for %s: %s", symbol, e)
            return None

    def generate_chart(self, df: pd.DataFrame, symbol: str, days: int = 7) -> Optional[bytes]:
        """Genera chart de precio con RSI y Bollinger Bands. Retorna PNG como bytes."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
            import ta

            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={"height_ratios": [3, 1]})
            fig.patch.set_facecolor("#0d1117")
            for ax in [ax1, ax2]:
                ax.set_facecolor("#0d1117")
                ax.tick_params(colors="#8b949e")
                ax.spines["bottom"].set_color("#30363d")
                ax.spines["top"].set_color("#30363d")
                ax.spines["left"].set_color("#30363d")
                ax.spines["right"].set_color("#30363d")

            close = df["close"]
            dates = df.index

            # Candlesticks (simulados con barras de precio)
            for i in range(len(df)):
                row = df.iloc[i]
                color = "#26a641" if row["close"] >= row["open"] else "#da3633"
                ax1.bar(dates[i], row["high"] - row["low"], bottom=row["low"],
                        width=pd.Timedelta(hours=2 if days <= 3 else 6), color=color, alpha=0.3)
                ax1.bar(dates[i], abs(row["close"] - row["open"]),
                        bottom=min(row["open"], row["close"]),
                        width=pd.Timedelta(hours=2 if days <= 3 else 6), color=color)

            # Bollinger Bands
            try:
                bb = ta.volatility.BollingerBands(close, window=20)
                ax1.plot(dates, bb.bollinger_hband(), color="#1f6feb", alpha=0.6, linewidth=0.8, linestyle="--", label="BB Upper")
                ax1.plot(dates, bb.bollinger_mavg(), color="#8b949e", alpha=0.6, linewidth=0.8, label="BB Mid")
                ax1.plot(dates, bb.bollinger_lband(), color="#1f6feb", alpha=0.6, linewidth=0.8, linestyle="--", label="BB Lower")
                ax1.fill_between(dates, bb.bollinger_hband(), bb.bollinger_lband(), alpha=0.05, color="#1f6feb")
            except Exception:
                pass

            # EMA 9 y 21
            try:
                ema9 = ta.trend.EMAIndicator(close, window=9).ema_indicator()
                ema21 = ta.trend.EMAIndicator(close, window=21).ema_indicator()
                ax1.plot(dates, ema9, color="#f0883e", linewidth=1.2, label="EMA 9")
                ax1.plot(dates, ema21, color="#a5d6ff", linewidth=1.2, label="EMA 21")
            except Exception:
                pass

            ax1.set_ylabel("Precio USD", color="#8b949e")
            ax1.legend(loc="upper left", facecolor="#161b22", edgecolor="#30363d",
                       labelcolor="#c9d1d9", fontsize=7)
            ax1.set_title(f"{symbol}/USD — {days}d", color="#c9d1d9", fontsize=14, pad=10)
            ax1.yaxis.label.set_color("#8b949e")

            # Precio actual
            last_price = close.iloc[-1]
            first_price = close.iloc[0]
            pct = (last_price - first_price) / first_price * 100
            color_pct = "#26a641" if pct >= 0 else "#da3633"
            ax1.text(0.02, 0.95, f"${last_price:,.4f}  {'+' if pct >= 0 else ''}{pct:.2f}%",
                     transform=ax1.transAxes, color=color_pct, fontsize=11, fontweight="bold")

            # RSI
            try:
                rsi = ta.momentum.RSIIndicator(close, window=14).rsi()
                ax2.plot(dates, rsi, color="#a5d6ff", linewidth=1.2, label="RSI 14")
                ax2.axhline(y=70, color="#da3633", alpha=0.5, linewidth=0.8, linestyle="--")
                ax2.axhline(y=30, color="#26a641", alpha=0.5, linewidth=0.8, linestyle="--")
                ax2.fill_between(dates, rsi, 70, where=(rsi >= 70), alpha=0.2, color="#da3633")
                ax2.fill_between(dates, rsi, 30, where=(rsi <= 30), alpha=0.2, color="#26a641")
                ax2.set_ylim(0, 100)
                ax2.set_ylabel("RSI", color="#8b949e")
                last_rsi = rsi.iloc[-1]
                rsi_color = "#da3633" if last_rsi > 70 else ("#26a641" if last_rsi < 30 else "#8b949e")
                ax2.text(0.02, 0.85, f"RSI: {last_rsi:.1f}", transform=ax2.transAxes,
                         color=rsi_color, fontsize=9)
            except Exception:
                pass

            ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
            plt.setp(ax2.xaxis.get_majorticklabels(), rotation=30, ha="right", color="#8b949e")
            ax1.xaxis.set_visible(False)

            plt.tight_layout(pad=0.5)

            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=120, bbox_inches="tight",
                        facecolor="#0d1117", edgecolor="none")
            plt.close(fig)
            buf.seek(0)
            return buf.getvalue()

        except Exception as e:
            logger.error("Chart generation error: %s", e)
            return None

    async def get_chart(self, symbol: str, days: int = 7) -> Optional[bytes]:
        df = await self.get_ohlcv(symbol, days)
        if df is None or len(df) < 10:
            return None
        return self.generate_chart(df, symbol.upper(), days)


chart_generator = ChartGenerator()
