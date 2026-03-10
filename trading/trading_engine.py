"""
Motor de trading autónomo.
- Solana: Jupiter aggregator (mejor precio garantizado)
- EVM (ETH/Base/BSC): 1inch o ejecución directa Uniswap V3
- PumpFun: memecoins de Solana via pump.fun
"""

import os
import json
import logging
import asyncio
import aiohttp
from typing import Optional
from crypto.wallet_manager import wallet_manager
from trading.risk_manager import risk_manager

logger = logging.getLogger("beeatrix.trading")

JUPITER_API = "https://quote-api.jup.ag/v6"
SOL_MINT    = "So11111111111111111111111111111111111111112"
USDC_SOL    = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


class TradingEngine:

    # ── Jupiter (Solana DEX aggregator) ────────────────────────────────────

    async def get_jupiter_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount_lamports: int,
        slippage_bps: int = 50,
    ) -> Optional[dict]:
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount_lamports),
            "slippageBps": slippage_bps,
            "onlyDirectRoutes": "false",
            "asLegacyTransaction": "false",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{JUPITER_API}/quote", params=params,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    logger.warning("Jupiter quote error %s", resp.status)
        except Exception as e:
            logger.error("Jupiter quote error: %s", e)
        return None

    async def execute_jupiter_swap(self, quote: dict, user_public_key: str) -> Optional[dict]:
        """Obtiene la transacción de Jupiter lista para firmar."""
        payload = {
            "quoteResponse": quote,
            "userPublicKey": user_public_key,
            "wrapAndUnwrapSol": True,
            "dynamicComputeUnitLimit": True,
            "prioritizationFeeLamports": "auto",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{JUPITER_API}/swap",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=20)
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception as e:
            logger.error("Jupiter swap error: %s", e)
        return None

    async def sign_and_send_solana(self, transaction_b64: str) -> Optional[str]:
        """Firma y envía una transacción Solana. Retorna el tx hash."""
        if risk_manager.config.get("dry_run"):
            logger.info("[DRY RUN] Transacción simulada")
            return "dry_run_tx_" + "0" * 32

        try:
            import base64
            from solders.transaction import VersionedTransaction
            from solders.keypair import Keypair
            import aiohttp

            kp = wallet_manager.get_keypair_solana()
            if not kp:
                logger.error("No Solana keypair available")
                return None

            tx_bytes = base64.b64decode(transaction_b64)
            tx = VersionedTransaction.from_bytes(tx_bytes)
            tx = VersionedTransaction(tx.message, [kp])

            serialized = bytes(tx)
            import base64 as b64
            encoded = b64.b64encode(serialized).decode()

            payload = {
                "jsonrpc": "2.0", "id": 1,
                "method": "sendTransaction",
                "params": [encoded, {"encoding": "base64", "preflightCommitment": "confirmed"}]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.mainnet-beta.solana.com",
                    json=payload, timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    data = await resp.json()
                    if "result" in data:
                        return data["result"]
                    logger.error("Solana send error: %s", data)
        except Exception as e:
            logger.error("sign_and_send_solana error: %s", e)
        return None

    async def buy_token_solana(
        self,
        token_mint: str,
        sol_amount: float,
        slippage_pct: float = None,
    ) -> dict:
        slippage_pct = slippage_pct or risk_manager.config.get("max_slippage_pct", 2.0)
        slippage_bps = int(slippage_pct * 100)
        lamports = int(sol_amount * 1e9)
        wallet_pk = wallet_manager.get_address("solana")
        if not wallet_pk:
            return {"success": False, "error": "Solana wallet no inicializada"}

        quote = await self.get_jupiter_quote(SOL_MINT, token_mint, lamports, slippage_bps)
        if not quote:
            return {"success": False, "error": "No se pudo obtener quote de Jupiter"}

        out_amount = int(quote.get("outAmount", 0))
        price_impact = float(quote.get("priceImpactPct", 0))
        logger.info("Jupiter quote: %s SOL -> %s tokens (impact: %.2f%%)", sol_amount, out_amount, price_impact)

        swap_data = await self.execute_jupiter_swap(quote, wallet_pk)
        if not swap_data:
            return {"success": False, "error": "Error al construir swap"}

        tx_hash = await self.sign_and_send_solana(swap_data.get("swapTransaction", ""))
        if not tx_hash:
            return {"success": False, "error": "Error al enviar transacción"}

        result = {
            "success": True,
            "action": "BUY",
            "chain": "solana",
            "token_mint": token_mint,
            "sol_spent": sol_amount,
            "tokens_received": out_amount,
            "price_impact_pct": price_impact,
            "tx_hash": tx_hash,
            "explorer": f"https://solscan.io/tx/{tx_hash}",
            "dry_run": risk_manager.config.get("dry_run", False),
        }
        logger.info("BUY ejecutado: %s", result)
        return result

    async def sell_token_solana(
        self,
        token_mint: str,
        token_amount: int,
        slippage_pct: float = None,
    ) -> dict:
        slippage_pct = slippage_pct or risk_manager.config.get("max_slippage_pct", 2.0)
        slippage_bps = int(slippage_pct * 100)
        wallet_pk = wallet_manager.get_address("solana")
        if not wallet_pk:
            return {"success": False, "error": "Solana wallet no inicializada"}

        quote = await self.get_jupiter_quote(token_mint, SOL_MINT, token_amount, slippage_bps)
        if not quote:
            return {"success": False, "error": "No se pudo obtener quote"}

        out_lamports = int(quote.get("outAmount", 0))
        sol_received = out_lamports / 1e9

        swap_data = await self.execute_jupiter_swap(quote, wallet_pk)
        if not swap_data:
            return {"success": False, "error": "Error al construir swap"}

        tx_hash = await self.sign_and_send_solana(swap_data.get("swapTransaction", ""))
        if not tx_hash:
            return {"success": False, "error": "Error al enviar transacción"}

        result = {
            "success": True,
            "action": "SELL",
            "chain": "solana",
            "token_mint": token_mint,
            "tokens_sold": token_amount,
            "sol_received": sol_received,
            "tx_hash": tx_hash,
            "explorer": f"https://solscan.io/tx/{tx_hash}",
            "dry_run": risk_manager.config.get("dry_run", False),
        }
        logger.info("SELL ejecutado: %s", result)
        return result

    # ── EVM Trading (ETH / Base / BSC) ────────────────────────────────────

    async def get_1inch_quote(
        self, chain_id: int, from_token: str, to_token: str, amount: str
    ) -> Optional[dict]:
        api_key = os.environ.get("ONEINCH_API_KEY", "")
        url = f"https://api.1inch.dev/swap/v6.0/{chain_id}/quote"
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        params = {"src": from_token, "dst": to_token, "amount": amount, "includeTokensInfo": "true"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers,
                                       timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception as e:
            logger.warning("1inch quote error: %s", e)
        return None

    async def execute_evm_trade(
        self, chain: str, token_in: str, token_out: str,
        amount_wei: int, wallet_address: str
    ) -> dict:
        chain_ids = {"eth": 1, "base": 8453, "bsc": 56}
        chain_id = chain_ids.get(chain, 1)

        if risk_manager.config.get("dry_run"):
            return {
                "success": True, "dry_run": True,
                "chain": chain, "chain_id": chain_id,
                "amount_wei": amount_wei,
                "note": "[SIMULACION] Trade EVM no ejecutado"
            }

        # TODO: Ejecutar swap EVM via 1inch o Uniswap router
        # Requiere: gas estimation, firma, broadcast
        return {"success": False, "error": "EVM trading en implementación — usa Solana por ahora"}

    # ── Autonomous trade decision ──────────────────────────────────────────

    async def autonomous_trade(
        self,
        token_mint: str,
        signal_data: dict,
        token_info: dict,
        portfolio_value_sol: float,
        is_shitcoin: bool = False,
    ) -> dict:
        """
        Punto central de trading autónomo.
        Valida riesgo, calcula tamaño, ejecuta.
        """
        # 1. Verificar si puede tradear
        can, reason = risk_manager.can_trade()
        if not can:
            return {"success": False, "skipped": True, "reason": reason}

        # 2. Validar señal
        signal = signal_data.get("signal", "HOLD")
        if signal == "HOLD":
            return {"success": False, "skipped": True, "reason": "Señal HOLD — sin acción"}

        valid, val_reason = risk_manager.validate_signal(signal_data)
        if not valid:
            return {"success": False, "skipped": True, "reason": val_reason}

        # 3. Validar liquidez
        liq_ok, liq_reason = risk_manager.validate_liquidity(token_info, is_shitcoin)
        if not liq_ok:
            return {"success": False, "skipped": True, "reason": liq_reason}

        # 4. Calcular tamaño de posición
        sol_price = await self._get_sol_price()
        portfolio_usd = portfolio_value_sol * sol_price
        position_usd = risk_manager.calculate_position_size(portfolio_usd, is_shitcoin)
        position_sol = position_usd / sol_price

        if position_sol < 0.001:
            return {"success": False, "skipped": True, "reason": "Portfolio insuficiente para operar"}

        # 5. Calcular stops
        entry_price = token_info.get("price_usd", 0)
        stops = risk_manager.calculate_stops(entry_price, signal)

        # 6. Ejecutar
        if signal == "BUY":
            result = await self.buy_token_solana(token_mint, position_sol)
        else:
            # SELL — asumiendo que ya tenemos tokens
            result = await self.sell_token_solana(token_mint, int(position_sol * 1e9))

        if result.get("success"):
            trade = {
                "token": token_mint,
                "token_name": token_info.get("name", "Unknown"),
                "side": signal,
                "entry_price": entry_price,
                "position_sol": position_sol,
                "position_usd": position_usd,
                "stop_loss": stops["stop_loss"],
                "take_profit": stops["take_profit"],
                "confidence": signal_data.get("confidence", 0),
                "tx_hash": result.get("tx_hash"),
                "status": "open",
            }
            risk_manager.register_trade(trade)
            result["trade"] = trade

        return result

    async def _get_sol_price(self) -> float:
        try:
            from crypto.price_feed import price_feed
            prices = await price_feed.get_prices_coingecko(["SOL"])
            return prices.get("SOL", {}).get("price", 100.0)
        except Exception:
            return 100.0

    def format_trade_report(self, result: dict) -> str:
        if result.get("skipped"):
            return f"Trade omitido: {result.get('reason', 'desconocido')}"
        if not result.get("success"):
            return f"Trade fallido: {result.get('error', 'error desconocido')}"
        trade = result.get("trade", {})
        dry = " [SIMULACION]" if result.get("dry_run") else ""
        lines = [
            f"Trade ejecutado{dry}",
            f"Token: {trade.get('token_name', trade.get('token', '?'))}",
            f"Accion: {trade.get('side')}",
            f"Precio entrada: ${trade.get('entry_price', 0):.8f}",
            f"Posicion: ${trade.get('position_usd', 0):,.2f} ({trade.get('position_sol', 0):.4f} SOL)",
            f"Stop Loss: ${trade.get('stop_loss', 0):.8f}",
            f"Take Profit: ${trade.get('take_profit', 0):.8f}",
            f"Confianza señal: {trade.get('confidence', 0):.0f}%",
        ]
        if result.get("tx_hash") and not result.get("dry_run"):
            lines.append(f"TX: {result.get('explorer', result.get('tx_hash', ''))}")
        return "\n".join(lines)


trading_engine = TradingEngine()
