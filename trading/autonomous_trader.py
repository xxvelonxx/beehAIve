"""
Loop de trading 100% autónomo de BEEA.
- Escanea mercados cada N minutos
- Analiza señales técnicas y fundamentales
- Ejecuta trades con gestión de riesgo
- Monitorea posiciones abiertas (stop loss / take profit)
- Reporta todo a Telegram en tiempo real
"""

import asyncio
import logging
import json
from typing import Callable, Optional
from pathlib import Path

logger = logging.getLogger("beeatrix.auto_trader")

SCAN_INTERVAL   = 5 * 60     # Escaneo cada 5 minutos
MONITOR_INTERVAL = 60        # Monitoreo de posiciones cada 1 minuto
PUMPFUN_INTERVAL = 3 * 60    # Escaneo PumpFun cada 3 minutos

COINGECKO_IDS = {
    "SOL":  "solana",
    "ETH":  "ethereum",
    "BTC":  "bitcoin",
    "BNB":  "binancecoin",
}


class AutonomousTrader:
    def __init__(self):
        self._notify_fn: Optional[Callable] = None
        self._running = False
        self._scan_count = 0
        self._total_trades = 0
        self._total_pnl = 0.0

    def set_notify_fn(self, fn: Callable):
        self._notify_fn = fn

    async def _notify(self, msg: str):
        if self._notify_fn:
            try:
                await self._notify_fn(msg)
            except Exception as e:
                logger.warning("Notify error: %s", e)

    # ── Wallet balance ────────────────────────────────────────────────────

    async def _get_sol_balance(self) -> float:
        try:
            from crypto.wallet_manager import wallet_manager
            bal = await wallet_manager.get_balance_solana()
            return bal or 0.0
        except Exception:
            return 0.0

    # ── Scan loop principal ───────────────────────────────────────────────

    async def _scan_major_tokens(self):
        """Analiza BTC, ETH, SOL con TA y genera señales."""
        from crypto.price_feed import price_feed
        from crypto.analysis import analyzer
        from trading.risk_manager import risk_manager

        try:
            tokens_to_scan = [
                ("SOL",  "solana",    "So11111111111111111111111111111111111111112"),
                ("ETH",  "ethereum",  None),
                ("BTC",  "bitcoin",   None),
            ]

            for symbol, cg_id, mint in tokens_to_scan:
                try:
                    df = await analyzer.get_ohlcv_coingecko(cg_id, days=3)
                    if df is None or len(df) < 20:
                        continue

                    signal_data = analyzer.generate_signal(df)
                    signal = signal_data.get("signal", "HOLD")
                    confidence = signal_data.get("confidence", 0)

                    logger.info("Signal %s: %s (%.0f%%)", symbol, signal, confidence)

                    # Solo actuar si confianza alta y hay mint (solo SOL por ahora)
                    if signal != "HOLD" and confidence >= risk_manager.config["min_confidence"] and mint:
                        sol_balance = await self._get_sol_balance()
                        if sol_balance > 0.01:
                            from trading.trading_engine import trading_engine
                            prices = await price_feed.get_prices_coingecko([symbol])
                            token_info = {
                                "price_usd": prices.get(symbol, {}).get("price", 0),
                                "liquidity_usd": 999999999,  # SOL nativo — liquidez infinita
                                "name": symbol,
                            }
                            result = await trading_engine.autonomous_trade(
                                token_mint=mint,
                                signal_data=signal_data,
                                token_info=token_info,
                                portfolio_value_sol=sol_balance,
                                is_shitcoin=False,
                            )
                            if result.get("success"):
                                self._total_trades += 1
                                report = trading_engine.format_trade_report(result)
                                await self._notify(f"BEEA Trading Autonomo\n\n{report}")
                            elif not result.get("skipped"):
                                logger.warning("Trade failed for %s: %s", symbol, result.get("error"))
                except Exception as e:
                    logger.warning("Error scanning %s: %s", symbol, e)

        except Exception as e:
            logger.error("scan_major_tokens error: %s", e)

    async def _scan_pumpfun(self):
        """Escanea PumpFun buscando memecoins con alto potencial."""
        from trading.pumpfun import pumpfun_scanner
        from trading.risk_manager import risk_manager
        from trading.trading_engine import trading_engine

        if not risk_manager.config.get("enabled"):
            return

        try:
            opportunities = await pumpfun_scanner.scan_opportunities(min_score=50)
            if not opportunities:
                return

            best = opportunities[0]
            score = best.get("score", 0)
            name = best.get("name", "?")
            mint = best.get("mint", "")

            logger.info("PumpFun best: %s score=%d", name, score)

            # Notificar oportunidades encontradas
            if score >= 60:
                report = pumpfun_scanner.format_opportunity(best)
                await self._notify(f"Oportunidad PumpFun detectada (score {score}/100)\n\n{report}")

            # Ejecutar si el score es muy alto
            if score >= 75 and mint:
                sol_balance = await self._get_sol_balance()
                if sol_balance > 0.01:
                    token_info = {
                        "price_usd": 0,
                        "liquidity_usd": best.get("virtual_sol", 0) * 100,
                        "name": name,
                    }
                    signal_data = {
                        "signal": "BUY",
                        "confidence": score,
                        "reason": f"PumpFun score {score}/100",
                    }
                    result = await trading_engine.autonomous_trade(
                        token_mint=mint,
                        signal_data=signal_data,
                        token_info=token_info,
                        portfolio_value_sol=sol_balance,
                        is_shitcoin=True,
                    )
                    if result.get("success"):
                        self._total_trades += 1
                        trade_report = trading_engine.format_trade_report(result)
                        await self._notify(f"Compra PumpFun ejecutada\n\n{trade_report}")

        except Exception as e:
            logger.error("scan_pumpfun error: %s", e)

    async def _monitor_positions(self):
        """Monitorea posiciones abiertas — aplica stop loss / take profit."""
        from trading.risk_manager import risk_manager
        from crypto.price_feed import price_feed
        from trading.trading_engine import trading_engine

        if not risk_manager.open_positions:
            return

        for pos in list(risk_manager.open_positions):
            try:
                token = pos.get("token", "")
                token_name = pos.get("token_name", token[:8])
                entry_price = pos.get("entry_price", 0)
                stop_loss = pos.get("stop_loss", 0)
                take_profit = pos.get("take_profit", 0)

                # Obtener precio actual
                token_info = await price_feed.get_token_info_dexscreener(token)
                current_price = token_info.get("price_usd", 0) if token_info else 0

                if not current_price:
                    continue

                pct_change = (current_price - entry_price) / entry_price * 100 if entry_price else 0

                # Stop loss
                if stop_loss and current_price <= stop_loss:
                    pnl = risk_manager.close_position(token, current_price, "stop_loss")
                    self._total_pnl += pnl or 0
                    await self._notify(
                        f"STOP LOSS ejecutado\n"
                        f"Token: {token_name}\n"
                        f"Entrada: ${entry_price:.8f}\n"
                        f"Salida: ${current_price:.8f}\n"
                        f"P&L: {pnl:+.2f}%"
                    )

                # Take profit
                elif take_profit and current_price >= take_profit:
                    pnl = risk_manager.close_position(token, current_price, "take_profit")
                    self._total_pnl += pnl or 0
                    await self._notify(
                        f"TAKE PROFIT alcanzado\n"
                        f"Token: {token_name}\n"
                        f"Entrada: ${entry_price:.8f}\n"
                        f"Salida: ${current_price:.8f}\n"
                        f"P&L: {pnl:+.2f}%"
                    )

                # Update en curso
                elif abs(pct_change) >= 5:
                    logger.info(
                        "Position %s: %+.2f%% (entry: $%.8f, current: $%.8f)",
                        token_name, pct_change, entry_price, current_price
                    )

            except Exception as e:
                logger.warning("Monitor position error: %s", e)

    # ── Loops principales ──────────────────────────────────────────────────

    async def run(self):
        """Inicia el trading autónomo completo."""
        self._running = True
        logger.info("Autonomous trader iniciado")
        await self._notify(
            "Trading autonomo ACTIVADO\n"
            "Escaneando mercados cada 5 min.\n"
            "Te notificare cada trade en tiempo real."
        )

        # Tres loops paralelos
        await asyncio.gather(
            self._market_scan_loop(),
            self._position_monitor_loop(),
            self._pumpfun_scan_loop(),
            return_exceptions=True,
        )

    async def _market_scan_loop(self):
        while self._running:
            try:
                self._scan_count += 1
                logger.info("Market scan #%d", self._scan_count)
                await self._scan_major_tokens()
            except Exception as e:
                logger.error("Market scan loop error: %s", e)
            await asyncio.sleep(SCAN_INTERVAL)

    async def _position_monitor_loop(self):
        while self._running:
            try:
                await self._monitor_positions()
            except Exception as e:
                logger.error("Monitor loop error: %s", e)
            await asyncio.sleep(MONITOR_INTERVAL)

    async def _pumpfun_scan_loop(self):
        while self._running:
            try:
                await self._scan_pumpfun()
            except Exception as e:
                logger.error("PumpFun scan loop error: %s", e)
            await asyncio.sleep(PUMPFUN_INTERVAL)

    def stop(self):
        self._running = False

    def get_status(self) -> str:
        from trading.risk_manager import risk_manager
        estado = "ACTIVO" if self._running else "INACTIVO"
        dry = " [SIMULACION]" if risk_manager.config.get("dry_run") else " [REAL]"
        lines = [
            f"Trading autonomo: {estado}{dry}",
            f"Scans realizados: {self._scan_count}",
            f"Trades ejecutados: {self._total_trades}",
            f"P&L total: {'+' if self._total_pnl >= 0 else ''}{self._total_pnl:.2f}%",
            "",
            risk_manager.get_summary(),
        ]
        return "\n".join(lines)


autonomous_trader = AutonomousTrader()
