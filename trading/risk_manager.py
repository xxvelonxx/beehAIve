"""
Gestión de riesgo para trading autónomo 100%.
Reglas de riesgo configurables por Álvaro.
BEEA nunca arriesga más de lo configurado.
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("beeatrix.risk")

RISK_CONFIG_FILE = Path("memory/risk_config.json")

DEFAULT_CONFIG = {
    "max_position_pct": 10.0,       # Máximo % del portfolio por posición
    "max_daily_loss_pct": 5.0,       # Stop total diario si pérdida supera este %
    "stop_loss_pct": 5.0,            # Stop loss por operación
    "take_profit_pct": 15.0,         # Take profit por operación
    "max_open_positions": 5,         # Máximo de posiciones abiertas simultáneas
    "min_confidence": 60.0,          # Confianza mínima de la señal para entrar
    "min_liquidity_usd": 10000,      # Liquidez mínima del par
    "max_slippage_pct": 2.0,         # Slippage máximo aceptado
    "shitcoin_max_pct": 5.0,         # Máximo % en memecoins/shitcoins
    "enabled": True,                 # Trading autónomo ON/OFF
    "notify_all_trades": True,       # Notificar cada operación a Telegram
    "dry_run": False,                # Modo simulación (no ejecuta trades reales)
}


class RiskManager:
    def __init__(self):
        self.config = self._load_config()
        self.daily_pnl = 0.0
        self.open_positions: list = []
        self.trade_history: list = []

    def _load_config(self) -> dict:
        if RISK_CONFIG_FILE.exists():
            try:
                return {**DEFAULT_CONFIG, **json.loads(RISK_CONFIG_FILE.read_text())}
            except Exception:
                pass
        return DEFAULT_CONFIG.copy()

    def save_config(self):
        RISK_CONFIG_FILE.parent.mkdir(exist_ok=True)
        RISK_CONFIG_FILE.write_text(json.dumps(self.config, indent=2))

    def update_config(self, key: str, value) -> str:
        if key not in DEFAULT_CONFIG:
            return f"Parámetro desconocido: {key}"
        old = self.config.get(key)
        self.config[key] = value
        self.save_config()
        return f"Riesgo actualizado: {key} = {old} -> {value}"

    # ── Validaciones pre-trade ─────────────────────────────────────────────

    def can_trade(self) -> tuple[bool, str]:
        if not self.config.get("enabled"):
            return False, "Trading autónomo desactivado"
        if len(self.open_positions) >= self.config["max_open_positions"]:
            return False, f"Máximo de posiciones abiertas ({self.config['max_open_positions']})"
        if self.daily_pnl <= -self.config["max_daily_loss_pct"]:
            return False, f"Límite de pérdida diaria alcanzado ({self.daily_pnl:.2f}%)"
        return True, "OK"

    def validate_signal(self, signal_data: dict) -> tuple[bool, str]:
        confidence = signal_data.get("confidence", 0)
        min_conf = self.config["min_confidence"]
        if confidence < min_conf:
            return False, f"Confianza insuficiente: {confidence:.0f}% < {min_conf}%"
        return True, "Señal válida"

    def validate_liquidity(self, token_info: dict, is_shitcoin: bool = False) -> tuple[bool, str]:
        liq = token_info.get("liquidity_usd", 0) or 0
        min_liq = self.config["min_liquidity_usd"]
        if is_shitcoin:
            min_liq = max(min_liq * 0.1, 1000)  # Más flexible para memecoins
        if liq < min_liq:
            return False, f"Liquidez insuficiente: ${liq:,.0f} < ${min_liq:,.0f}"
        return True, "OK"

    def calculate_position_size(self, portfolio_value_usd: float, is_shitcoin: bool = False) -> float:
        max_pct = self.config["shitcoin_max_pct"] if is_shitcoin else self.config["max_position_pct"]
        return portfolio_value_usd * (max_pct / 100)

    def calculate_stops(self, entry_price: float, signal: str) -> dict:
        sl_pct = self.config["stop_loss_pct"] / 100
        tp_pct = self.config["take_profit_pct"] / 100
        if signal == "BUY":
            return {
                "stop_loss":   entry_price * (1 - sl_pct),
                "take_profit": entry_price * (1 + tp_pct),
            }
        else:  # SHORT
            return {
                "stop_loss":   entry_price * (1 + sl_pct),
                "take_profit": entry_price * (1 - tp_pct),
            }

    # ── Registro de trades ─────────────────────────────────────────────────

    def register_trade(self, trade: dict):
        self.trade_history.append(trade)
        if trade.get("status") == "open":
            self.open_positions.append(trade)
        logger.info("Trade registrado: %s", trade)

    def close_position(self, token: str, exit_price: float, reason: str = "manual"):
        for pos in self.open_positions:
            if pos.get("token") == token:
                entry = pos.get("entry_price", exit_price)
                pct = (exit_price - entry) / entry * 100
                if pos.get("side") == "BUY":
                    pnl = pct
                else:
                    pnl = -pct
                pos["exit_price"] = exit_price
                pos["pnl_pct"] = pnl
                pos["status"] = "closed"
                pos["close_reason"] = reason
                self.daily_pnl += pnl
                self.open_positions = [p for p in self.open_positions if p.get("token") != token]
                return pnl
        return None

    # ── Resumen ────────────────────────────────────────────────────────────

    def get_summary(self) -> str:
        enabled = "ACTIVO" if self.config.get("enabled") else "PAUSADO"
        dry = " [SIMULACION]" if self.config.get("dry_run") else ""
        lines = [
            f"Trading autonomo: {enabled}{dry}",
            f"Posicion max: {self.config['max_position_pct']}% | Shitcoins: {self.config['shitcoin_max_pct']}%",
            f"Stop loss: {self.config['stop_loss_pct']}% | Take profit: {self.config['take_profit_pct']}%",
            f"Confianza minima: {self.config['min_confidence']}%",
            f"Posiciones abiertas: {len(self.open_positions)}/{self.config['max_open_positions']}",
            f"P&L diario: {'+' if self.daily_pnl >= 0 else ''}{self.daily_pnl:.2f}%",
        ]
        if self.open_positions:
            lines.append("\nPosiciones abiertas:")
            for pos in self.open_positions:
                lines.append(f"  {pos.get('token')} | {pos.get('side')} @ ${pos.get('entry_price', 0):.6f}")
        return "\n".join(lines)

    def get_config_report(self) -> str:
        lines = ["Configuracion de riesgo:"]
        for k, v in self.config.items():
            lines.append(f"  {k}: {v}")
        return "\n".join(lines)


risk_manager = RiskManager()
