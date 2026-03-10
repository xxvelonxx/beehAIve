"""
Feed de precios en tiempo real.
APIs gratuitas: CoinGecko, DexScreener, Birdeye (Solana)
Sin API key requerida para uso básico.
"""

import asyncio
import logging
import aiohttp
from typing import Optional

logger = logging.getLogger("beeatrix.prices")

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
DEXSCREENER_BASE = "https://api.dexscreener.com"
BIRDEYE_BASE = "https://public-api.birdeye.so"

COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "USDC": "usd-coin",
    "USDT": "tether",
}


class PriceFeed:
    def __init__(self):
        self._cache: dict = {}
        self._cache_time: dict = {}

    async def _get(self, url: str, params: dict = None, headers: dict = None) -> Optional[dict]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, params=params, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception as e:
            logger.warning("Price feed error %s: %s", url, e)
        return None

    # ── CoinGecko ─────────────────────────────────────────────────────────

    async def get_prices_coingecko(self, symbols: list[str]) -> dict:
        ids = [COINGECKO_IDS.get(s.upper(), s.lower()) for s in symbols]
        ids_str = ",".join(ids)
        data = await self._get(
            f"{COINGECKO_BASE}/simple/price",
            params={"ids": ids_str, "vs_currencies": "usd", "include_24hr_change": "true", "include_24hr_vol": "true"}
        )
        if not data:
            return {}
        result = {}
        for sym in symbols:
            cg_id = COINGECKO_IDS.get(sym.upper(), sym.lower())
            if cg_id in data:
                d = data[cg_id]
                result[sym.upper()] = {
                    "price": d.get("usd", 0),
                    "change_24h": d.get("usd_24h_change", 0),
                    "volume_24h": d.get("usd_24h_vol", 0),
                    "source": "coingecko",
                }
        return result

    async def get_price(self, symbol: str) -> Optional[float]:
        prices = await self.get_prices_coingecko([symbol])
        return prices.get(symbol.upper(), {}).get("price")

    # ── DexScreener ───────────────────────────────────────────────────────

    async def get_token_info_dexscreener(self, token_address: str) -> Optional[dict]:
        data = await self._get(f"{DEXSCREENER_BASE}/latest/dex/tokens/{token_address}")
        if not data or not data.get("pairs"):
            return None
        # Toma el par con mayor liquidez
        pairs = sorted(data["pairs"], key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0), reverse=True)
        pair = pairs[0]
        return {
            "name": pair.get("baseToken", {}).get("name", "Unknown"),
            "symbol": pair.get("baseToken", {}).get("symbol", "?"),
            "price_usd": float(pair.get("priceUsd", 0) or 0),
            "price_native": float(pair.get("priceNative", 0) or 0),
            "change_5m": pair.get("priceChange", {}).get("m5", 0),
            "change_1h": pair.get("priceChange", {}).get("h1", 0),
            "change_6h": pair.get("priceChange", {}).get("h6", 0),
            "change_24h": pair.get("priceChange", {}).get("h24", 0),
            "volume_24h": pair.get("volume", {}).get("h24", 0),
            "liquidity_usd": pair.get("liquidity", {}).get("usd", 0),
            "market_cap": pair.get("marketCap", 0),
            "fdv": pair.get("fdv", 0),
            "dex": pair.get("dexId", "unknown"),
            "chain": pair.get("chainId", "unknown"),
            "pair_address": pair.get("pairAddress", ""),
            "source": "dexscreener",
            "url": pair.get("url", ""),
        }

    async def search_token_dexscreener(self, query: str) -> list:
        data = await self._get(f"{DEXSCREENER_BASE}/latest/dex/search", params={"q": query})
        if not data or not data.get("pairs"):
            return []
        return data["pairs"][:5]

    # ── Trending & PumpFun tokens ─────────────────────────────────────────

    async def get_trending_solana(self) -> list:
        try:
            data = await self._get(f"{DEXSCREENER_BASE}/token-boosts/top/v1")
            if data:
                sol_tokens = [t for t in data if t.get("chainId") == "solana"]
                return sol_tokens[:20]
        except Exception:
            pass
        return []

    async def get_new_pairs_solana(self) -> list:
        data = await self._get(f"{DEXSCREENER_BASE}/latest/dex/pairs/solana")
        if not data:
            return []
        return data.get("pairs", [])[:20]

    # ── Multi-price ───────────────────────────────────────────────────────

    async def get_portfolio_prices(self) -> dict:
        symbols = ["BTC", "ETH", "SOL", "BNB"]
        return await self.get_prices_coingecko(symbols)

    def format_price_report(self, prices: dict) -> str:
        lines = []
        for sym, data in prices.items():
            p = data.get("price", 0)
            c = data.get("change_24h", 0)
            arrow = "+" if c >= 0 else ""
            lines.append(f"{sym}: ${p:,.2f} ({arrow}{c:.2f}%)")
        return "\n".join(lines) if lines else "Sin datos de precio"

    def format_token_info(self, info: dict) -> str:
        if not info:
            return "Token no encontrado"
        name = info.get("name", "Unknown")
        sym = info.get("symbol", "?")
        price = info.get("price_usd", 0)
        c1h = info.get("change_1h", 0)
        c24h = info.get("change_24h", 0)
        liq = info.get("liquidity_usd", 0)
        vol = info.get("volume_24h", 0)
        mcap = info.get("market_cap", 0)
        dex = info.get("dex", "?")
        chain = info.get("chain", "?")

        lines = [
            f"{name} ({sym})",
            f"Precio: ${price:.8f}" if price < 0.01 else f"Precio: ${price:,.4f}",
            f"1h: {'+' if c1h >= 0 else ''}{c1h:.2f}% | 24h: {'+' if c24h >= 0 else ''}{c24h:.2f}%",
            f"Liquidez: ${liq:,.0f} | Vol 24h: ${vol:,.0f}",
        ]
        if mcap:
            lines.append(f"Market Cap: ${mcap:,.0f}")
        lines.append(f"DEX: {dex} | Chain: {chain}")
        if info.get("url"):
            lines.append(info["url"])
        return "\n".join(lines)


price_feed = PriceFeed()
