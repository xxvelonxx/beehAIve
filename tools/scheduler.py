"""
BEEA Scheduler — Tareas programadas y alertas.
Álvaro puede pedir recordatorios, alertas de precio, y tareas repetitivas.

Sin auto-inicio. Solo se activan cuando Álvaro lo pide explícitamente.

Ejemplos:
  "Recuérdame hacer X en 2 horas"
  "Avísame si BTC baja de 80000"
  "Dime el precio de SOL todos los días a las 9am"
"""
import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Awaitable, Optional

logger = logging.getLogger("beeatrix.scheduler")

TASKS_FILE = Path("memory/scheduled_tasks.json")
TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_tasks() -> list:
    if not TASKS_FILE.exists():
        return []
    try:
        return json.loads(TASKS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_tasks(tasks: list):
    TASKS_FILE.write_text(json.dumps(tasks, indent=2, ensure_ascii=False), encoding="utf-8")


def _next_run_ts(schedule_type: str, value: str, hour: int = 9, minute: int = 0) -> float:
    now = datetime.now()
    if schedule_type == "once":
        delay_secs = _parse_delay(value)
        return time.time() + delay_secs
    elif schedule_type == "daily":
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target.timestamp()
    elif schedule_type == "interval":
        secs = _parse_delay(value)
        return time.time() + secs
    return time.time() + 3600


def _parse_delay(text: str) -> float:
    """Convierte '2 horas', '30 minutos', '1 día' a segundos."""
    import re
    text = text.lower().strip()
    patterns = [
        (r'(\d+)\s*(seg|segundo)', 1),
        (r'(\d+)\s*(min|minuto)', 60),
        (r'(\d+)\s*(hora|hour)', 3600),
        (r'(\d+)\s*(día|dia|day)', 86400),
        (r'(\d+)\s*(semana|week)', 604800),
    ]
    for pattern, mult in patterns:
        m = re.search(pattern, text)
        if m:
            return int(m.group(1)) * mult
    try:
        return float(text)
    except ValueError:
        return 3600


class BeeScheduler:
    def __init__(self):
        self._notify_fn: Optional[Callable] = None
        self._running = False
        self._tasks = []

    def set_notify(self, fn: Callable):
        self._notify_fn = fn

    async def _notify(self, msg: str):
        if self._notify_fn:
            try:
                await self._notify_fn(msg)
            except Exception as e:
                logger.warning("Scheduler notify error: %s", e)

    def add_reminder(self, text: str, delay_str: str, repeat: bool = False) -> dict:
        """
        Agrega recordatorio.
        delay_str: '2 horas', '30 minutos', '1 día'
        """
        task_id = f"reminder_{int(time.time())}"
        delay = _parse_delay(delay_str)
        task = {
            "id": task_id,
            "type": "reminder",
            "text": text,
            "delay_str": delay_str,
            "repeat": repeat,
            "interval_secs": delay if repeat else None,
            "next_run": time.time() + delay,
            "created_at": datetime.now().isoformat(),
        }
        tasks = _load_tasks()
        tasks.append(task)
        _save_tasks(tasks)
        logger.info("Scheduler: recordatorio añadido — '%s' en %s", text[:50], delay_str)
        return task

    def add_daily(self, text: str, hour: int, minute: int = 0) -> dict:
        """Tarea diaria a hora específica."""
        task_id = f"daily_{int(time.time())}"
        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        task = {
            "id": task_id,
            "type": "daily",
            "text": text,
            "hour": hour,
            "minute": minute,
            "repeat": True,
            "interval_secs": 86400,
            "next_run": target.timestamp(),
            "created_at": datetime.now().isoformat(),
        }
        tasks = _load_tasks()
        tasks.append(task)
        _save_tasks(tasks)
        logger.info("Scheduler: tarea diaria '%s' a las %02d:%02d", text[:50], hour, minute)
        return task

    def add_price_alert(self, symbol: str, condition: str, target_price: float) -> dict:
        """
        Alerta de precio crypto.
        condition: 'below' | 'above'
        """
        task_id = f"price_{symbol.upper()}_{int(time.time())}"
        task = {
            "id": task_id,
            "type": "price_alert",
            "symbol": symbol.upper(),
            "condition": condition,
            "target_price": target_price,
            "check_interval": 300,
            "next_run": time.time() + 60,
            "repeat": True,
            "created_at": datetime.now().isoformat(),
        }
        tasks = _load_tasks()
        tasks.append(task)
        _save_tasks(tasks)
        logger.info("Scheduler: alerta de precio %s %s %.2f", symbol, condition, target_price)
        return task

    def list_tasks(self) -> list:
        return _load_tasks()

    def cancel_task(self, task_id: str) -> bool:
        tasks = _load_tasks()
        original = len(tasks)
        tasks = [t for t in tasks if t.get("id") != task_id]
        _save_tasks(tasks)
        return len(tasks) < original

    def cancel_all(self):
        _save_tasks([])
        logger.info("Scheduler: todas las tareas canceladas")

    async def _execute_task(self, task: dict):
        task_type = task.get("type")

        if task_type == "reminder":
            msg = f"⏰ Recordatorio: {task['text']}"
            await self._notify(msg)

        elif task_type == "daily":
            msg = f"📅 {task['text']}"
            await self._notify(msg)

        elif task_type == "price_alert":
            await self._check_price_alert(task)

    async def _check_price_alert(self, task: dict):
        symbol = task.get("symbol", "BTC")
        condition = task.get("condition", "below")
        target = task.get("target_price", 0)

        try:
            import requests
            resp = requests.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": symbol.lower(), "vs_currencies": "usd"},
                timeout=10,
            )
            data = resp.json()
            current = list(data.values())[0].get("usd", 0) if data else 0

            triggered = False
            if condition == "below" and current < target:
                triggered = True
                msg = f"🔴 ALERTA: {symbol} bajó de ${target:,.0f} — precio actual: ${current:,.0f}"
            elif condition == "above" and current > target:
                triggered = True
                msg = f"🟢 ALERTA: {symbol} subió de ${target:,.0f} — precio actual: ${current:,.0f}"

            if triggered:
                await self._notify(msg)
                task["triggered"] = True

        except Exception as e:
            logger.warning("Price alert check error: %s", e)

    async def background_loop(self):
        """Loop principal — revisa tareas cada 30 segundos."""
        self._running = True
        logger.info("Scheduler background loop iniciado")

        while self._running:
            try:
                now = time.time()
                tasks = _load_tasks()
                updated = False

                for task in tasks:
                    if task.get("next_run", 0) <= now:
                        try:
                            await self._execute_task(task)
                        except Exception as e:
                            logger.warning("Error ejecutando tarea %s: %s", task.get("id"), e)

                        if task.get("repeat") and task.get("interval_secs"):
                            if task.get("type") == "daily":
                                task["next_run"] = now + 86400
                            else:
                                task["next_run"] = now + task["interval_secs"]
                            updated = True
                        elif task.get("type") == "price_alert" and not task.get("triggered"):
                            task["next_run"] = now + task.get("check_interval", 300)
                            updated = True
                        else:
                            task["_done"] = True
                            updated = True

                if updated:
                    active = [t for t in tasks if not t.get("_done")]
                    _save_tasks(active)

            except Exception as e:
                logger.error("Scheduler loop error: %s", e)

            await asyncio.sleep(30)

    def stop(self):
        self._running = False


bee_scheduler = BeeScheduler()


def parse_schedule_from_text(text: str) -> Optional[dict]:
    """
    Extrae info de scheduling de texto en lenguaje natural.
    Devuelve dict con {type, text, delay_str, hour, minute, symbol, condition, target_price}
    o None si no detecta scheduling.
    """
    import re
    t = text.lower()

    price_match = re.search(
        r'avísame\s+(?:si\s+)?(\w+)\s+(baja|sube|cae|llega)\s+(?:de|a|hasta)?\s*\$?([\d,]+)', t
    )
    if price_match:
        symbol = price_match.group(1).upper()
        direction = price_match.group(2)
        price = float(price_match.group(3).replace(',', ''))
        condition = "below" if direction in ("baja", "cae") else "above"
        return {"type": "price_alert", "symbol": symbol, "condition": condition, "target_price": price}

    time_match = re.search(
        r'(?:recuérdame|recuerda|avísame|avisa|dime)\s+(.+?)\s+(?:en|dentro de)\s+([\d]+\s*(?:seg|min|hora|día|semana)[a-z]*)',
        t
    )
    if time_match:
        reminder_text = time_match.group(1).strip()
        delay = time_match.group(2).strip()
        return {"type": "reminder", "text": reminder_text, "delay_str": delay}

    daily_match = re.search(
        r'(?:todos los días|cada día|diariamente)\s+(?:a las?)?\s*(\d{1,2})(?::(\d{2}))?',
        t
    )
    if daily_match:
        hour = int(daily_match.group(1))
        minute = int(daily_match.group(2) or 0)
        content_match = re.search(r'(?:dime|avísame|recuérdame)\s+(.+?)\s+todos los días', t)
        content = content_match.group(1) if content_match else text[:50]
        return {"type": "daily", "text": content, "hour": hour, "minute": minute}

    return None
