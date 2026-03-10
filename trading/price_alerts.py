"""
Sistema de alertas de precio.
Álvaro configura alertas: "avísame cuando SOL llegue a $250"
BEEA monitorea en background y notifica en Telegram y Discord.
"""

import asyncio
import json
import logging
from typing import Callable, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("beeatrix.alerts")

ALERTS_FILE = Path("memory/price_alerts.json")
CHECK_INTERVAL = 60  # segundos entre checks


class PriceAlertManager:
    def __init__(self):
        self._alerts: list = []
        self._notify_fn: Optional[Callable] = None
        self._running = False
        self._load()

    def _load(self):
        if ALERTS_FILE.exists():
            try:
                self._alerts = json.loads(ALERTS_FILE.read_text())
            except Exception:
                self._alerts = []

    def _save(self):
        ALERTS_FILE.parent.mkdir(exist_ok=True)
        ALERTS_FILE.write_text(json.dumps(self._alerts, indent=2))

    def set_notify_fn(self, fn: Callable):
        self._notify_fn = fn

    def add_alert(self, symbol: str, target_price: float, direction: str, note: str = "") -> str:
        """
        direction: "above" (precio > target) o "below" (precio < target)
        """
        symbol = symbol.upper()
        alert = {
            "id": len(self._alerts) + 1,
            "symbol": symbol,
            "target_price": target_price,
            "direction": direction,
            "note": note,
            "created_at": datetime.now().isoformat(),
            "triggered": False,
        }
        self._alerts.append(alert)
        self._save()
        arrow = "suba a" if direction == "above" else "baje a"
        return f"Alerta configurada: te aviso cuando {symbol} {arrow} ${target_price:,.4f}"

    def remove_alert(self, alert_id: int) -> str:
        before = len(self._alerts)
        self._alerts = [a for a in self._alerts if a.get("id") != alert_id]
        self._save()
        if len(self._alerts) < before:
            return f"Alerta #{alert_id} eliminada."
        return f"No encontré la alerta #{alert_id}."

    def list_alerts(self) -> str:
        active = [a for a in self._alerts if not a.get("triggered")]
        if not active:
            return "No tienes alertas de precio activas."
        lines = ["Alertas activas:"]
        for a in active:
            arrow = "suba a" if a["direction"] == "above" else "baje a"
            note = f" ({a['note']})" if a.get("note") else ""
            lines.append(f"#{a['id']} {a['symbol']} {arrow} ${a['target_price']:,.4f}{note}")
        return "\n".join(lines)

    async def _notify(self, msg: str):
        if self._notify_fn:
            try:
                await self._notify_fn(msg)
            except Exception as e:
                logger.warning("Alert notify error: %s", e)

    async def check_alerts(self):
        from crypto.price_feed import price_feed
        active = [a for a in self._alerts if not a.get("triggered")]
        if not active:
            return

        symbols = list(set(a["symbol"] for a in active))
        try:
            prices = await price_feed.get_prices_coingecko(symbols)
        except Exception as e:
            logger.warning("Alert price check error: %s", e)
            return

        triggered_any = False
        for alert in active:
            sym = alert["symbol"]
            price_data = prices.get(sym, {})
            current = price_data.get("price", 0)
            if not current:
                continue

            triggered = False
            if alert["direction"] == "above" and current >= alert["target_price"]:
                triggered = True
            elif alert["direction"] == "below" and current <= alert["target_price"]:
                triggered = True

            if triggered:
                alert["triggered"] = True
                alert["triggered_at"] = datetime.now().isoformat()
                alert["triggered_price"] = current
                triggered_any = True
                arrow = "subió a" if alert["direction"] == "above" else "bajó a"
                change = price_data.get("change_24h", 0)
                note = f" — {alert['note']}" if alert.get("note") else ""
                msg = (
                    f"ALERTA DE PRECIO{note}\n"
                    f"{sym} {arrow} ${current:,.4f}\n"
                    f"Objetivo era: ${alert['target_price']:,.4f}\n"
                    f"Cambio 24h: {'+' if change >= 0 else ''}{change:.2f}%"
                )
                logger.info("Alert triggered: %s", msg)
                await self._notify(msg)

        if triggered_any:
            self._save()

    async def run(self):
        self._running = True
        logger.info("PriceAlertManager: monitoring loop started")
        while self._running:
            try:
                await self.check_alerts()
            except Exception as e:
                logger.error("Alert monitor error: %s", e)
            await asyncio.sleep(CHECK_INTERVAL)

    def stop(self):
        self._running = False

    @staticmethod
    def parse_alert_from_text(text: str) -> Optional[dict]:
        """Parsea frases como 'avísame cuando SOL llegue a $250' o 'alerta BTC baja de 80000'"""
        import re
        text_lower = text.lower()

        # Buscar símbolo
        symbols = ["BTC", "ETH", "SOL", "BNB", "USDC", "USDT"]
        found_symbol = None
        for sym in symbols:
            if sym.lower() in text_lower:
                found_symbol = sym
                break

        if not found_symbol:
            return None

        # Buscar precio
        price_match = re.search(r'\$?([\d,]+(?:\.\d+)?)', text)
        if not price_match:
            return None
        price = float(price_match.group(1).replace(",", ""))

        # Detectar dirección
        above_words = ["llegue a", "suba a", "supere", "llegue", "alcance", "rompa"]
        below_words = ["baje a", "caiga a", "baje de", "caiga por debajo", "baje"]
        direction = "above"
        for w in below_words:
            if w in text_lower:
                direction = "below"
                break

        return {"symbol": found_symbol, "price": price, "direction": direction}


price_alert_manager = PriceAlertManager()
