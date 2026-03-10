"""
Integración con PumpFun — memecoins de Solana.
Detecta nuevos tokens, evalúa momentum, ejecuta via Jupiter.
"""

import asyncio
import logging
import aiohttp
from typing import Optional

logger = logging.getLogger("beeatrix.pumpfun")

PUMPFUN_API = "https://frontend-api.pump.fun"
PUMPFUN_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"


class PumpFunScanner:

    async def _get(self, url: str, params: dict = None) -> Optional[dict]:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers,
                                       timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception as e:
            logger.warning("PumpFun API error %s: %s", url, e)
        return None

    async def get_trending(self, limit: int = 20) -> list:
        """Tokens trending en PumpFun ahora."""
        data = await self._get(
            f"{PUMPFUN_API}/coins",
            params={"limit": limit, "sort": "last_trade_timestamp", "order": "DESC", "includeNsfw": "false"}
        )
        if not data:
            return []
        return data if isinstance(data, list) else data.get("coins", [])

    async def get_new_tokens(self, limit: int = 20) -> list:
        """Tokens recién creados en PumpFun."""
        data = await self._get(
            f"{PUMPFUN_API}/coins",
            params={"limit": limit, "sort": "created_timestamp", "order": "DESC"}
        )
        if not data:
            return []
        return data if isinstance(data, list) else data.get("coins", [])

    async def get_token_info(self, mint: str) -> Optional[dict]:
        """Info completa de un token en PumpFun."""
        return await self._get(f"{PUMPFUN_API}/coins/{mint}")

    async def get_king_of_hill(self) -> list:
        """Tokens en zona de King of the Hill (cerca de graduarse a Raydium)."""
        data = await self._get(
            f"{PUMPFUN_API}/coins",
            params={"limit": 10, "sort": "king_of_the_hill_timestamp", "order": "DESC"}
        )
        if not data:
            return []
        return data if isinstance(data, list) else []

    # ── Filtros de calidad ─────────────────────────────────────────────────

    def score_token(self, token: dict) -> dict:
        """
        Score de calidad de un memecoin de PumpFun.
        Retorna score 0-100 y razones.
        """
        score = 0
        reasons = []
        warnings = []

        market_cap = token.get("usd_market_cap", 0) or 0
        reply_count = token.get("reply_count", 0) or 0
        holder_count = token.get("holder_count", 0) or 0
        virtual_sol = token.get("virtual_sol_reserves", 0) or 0
        virtual_sol_norm = virtual_sol / 1e9 if virtual_sol > 1000 else virtual_sol
        complete = token.get("complete", False)
        name = token.get("name", "")
        symbol = token.get("symbol", "")
        description = token.get("description", "")
        twitter = token.get("twitter")
        telegram_link = token.get("telegram")
        website = token.get("website")

        # Market cap en rango interesante (sniper zone: <50k, swing: 50k-500k)
        if 1000 < market_cap < 50000:
            score += 30
            reasons.append(f"Sniper zone (${market_cap:,.0f} mcap)")
        elif 50000 <= market_cap < 500000:
            score += 20
            reasons.append(f"Swing zone (${market_cap:,.0f} mcap)")
        elif market_cap >= 500000:
            score += 5
            warnings.append("Mcap alto — riesgo de dump")
        else:
            warnings.append("Mcap muy bajo o nulo")

        # Social signals
        if reply_count > 50:
            score += 20
            reasons.append(f"{reply_count} replies (comunidad activa)")
        elif reply_count > 10:
            score += 10
            reasons.append(f"{reply_count} replies")

        # Holders
        if holder_count and holder_count > 100:
            score += 15
            reasons.append(f"{holder_count} holders")
        elif holder_count and holder_count > 30:
            score += 8

        # Redes sociales
        if twitter:
            score += 10
            reasons.append("Twitter presente")
        if telegram_link:
            score += 5
            reasons.append("Telegram presente")
        if website:
            score += 5
            reasons.append("Website presente")

        # Bonding curve (liquidez virtual)
        if virtual_sol_norm > 20:
            score += 10
            reasons.append(f"{virtual_sol_norm:.0f} SOL en bonding curve")
        elif virtual_sol_norm > 5:
            score += 5

        # Advertencias
        if complete:
            score -= 10
            warnings.append("Ya graduado a Raydium (menos volatilidad)")

        # Keywords sospechosos en el nombre
        rug_words = ["rug", "scam", "fake", "test", "airdrop"]
        if any(w in name.lower() or w in symbol.lower() for w in rug_words):
            score -= 30
            warnings.append("Posible rug — nombre sospechoso")

        score = max(0, min(100, score))

        return {
            "mint": token.get("mint", ""),
            "name": name,
            "symbol": symbol,
            "score": score,
            "market_cap": market_cap,
            "reply_count": reply_count,
            "holder_count": holder_count,
            "reasons": reasons,
            "warnings": warnings,
            "twitter": twitter,
            "telegram": telegram_link,
            "description": description[:100] if description else "",
            "complete": complete,
            "virtual_sol": virtual_sol_norm,
        }

    async def scan_opportunities(self, min_score: int = 40) -> list:
        """Escanea PumpFun buscando oportunidades con score >= min_score."""
        trending = await self.get_trending(30)
        new_tokens = await self.get_new_tokens(20)

        all_tokens = {}
        for t in trending + new_tokens:
            mint = t.get("mint")
            if mint and mint not in all_tokens:
                all_tokens[mint] = t

        scored = [self.score_token(t) for t in all_tokens.values()]
        opportunities = [s for s in scored if s["score"] >= min_score]
        opportunities.sort(key=lambda x: x["score"], reverse=True)
        return opportunities[:10]

    def format_opportunity(self, opp: dict) -> str:
        score = opp.get("score", 0)
        name = opp.get("name", "Unknown")
        sym = opp.get("symbol", "?")
        mcap = opp.get("market_cap", 0)
        replies = opp.get("reply_count", 0)
        holders = opp.get("holder_count", 0)
        mint = opp.get("mint", "")
        reasons = " | ".join(opp.get("reasons", []))
        warnings = " | ".join(opp.get("warnings", []))

        lines = [
            f"{name} ({sym}) — Score: {score}/100",
            f"Mint: {mint[:8]}...{mint[-4:]}",
            f"Mcap: ${mcap:,.0f} | Replies: {replies} | Holders: {holders}",
        ]
        if reasons:
            lines.append(f"Positivo: {reasons}")
        if warnings:
            lines.append(f"Riesgo: {warnings}")
        lines.append(f"PumpFun: https://pump.fun/{mint}")
        return "\n".join(lines)

    def format_opportunities_report(self, opportunities: list) -> str:
        if not opportunities:
            return "No hay oportunidades con score suficiente ahora mismo."
        lines = [f"Oportunidades PumpFun ({len(opportunities)} tokens)\n"]
        for i, opp in enumerate(opportunities, 1):
            lines.append(f"--- #{i} ---")
            lines.append(self.format_opportunity(opp))
            lines.append("")
        return "\n".join(lines)


pumpfun_scanner = PumpFunScanner()
