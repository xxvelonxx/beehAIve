import asyncio
import re
from datetime import datetime, timedelta
from typing import Callable


_pending_reminders: list = []


def parse_duration(text: str) -> int:
    """Devuelve segundos del texto como '30 minutos', '2 horas', '1 hora'."""
    text = text.lower()
    match = re.search(r'(\d+)\s*(segundo|minuto|hora|min|seg|hr|h|m|s)', text)
    if not match:
        return 0
    value = int(match.group(1))
    unit = match.group(2)
    if unit.startswith("seg") or unit == "s":
        return value
    if unit.startswith("min") or unit == "m":
        return value * 60
    if unit.startswith("hor") or unit in ("h", "hr"):
        return value * 3600
    return 0


async def schedule_reminder(
    send_fn: Callable,
    message: str,
    seconds: int,
    chat_id: int,
):
    """Espera N segundos y llama send_fn con el recordatorio."""
    await asyncio.sleep(seconds)
    await send_fn(chat_id=chat_id, text=f"Recordatorio: {message}")
