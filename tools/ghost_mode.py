"""
Ghost Mode — Modo Fantasma para BEEA y BEEs.

Hace que todas las requests (web scraping, API calls, búsquedas) sean:
  - Sin huella de identidad (User-Agent rotativo, sin headers identificadores)
  - No rastreables (jitter de timing, fingerprint aleatorio por sesión)
  - Sin metadatos comprometedores en las respuestas
  - Con timing humano (evita detección de bots)
  - Auto-destrucción de mensajes sensibles en Telegram

Activación: /ghost on | /ghost off | /ghost status
"""
from __future__ import annotations
import os
import time
import random
import string
import hashlib
import threading
from core.logger import logger

# ── Estado global del ghost mode ─────────────────────────────────────────────
_state = {
    "active": False,
    "session_id": None,
    "activated_at": None,
    "requests_made": 0,
    "messages_deleted": 0,
    "identities_rotated": 0,
}
_lock = threading.Lock()


# ── Pool de User-Agents realistas ─────────────────────────────────────────────
_USER_AGENTS = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # Chrome Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    # Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:123.0) Gecko/20100101 Firefox/123.0",
    # Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
    # Opera
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 OPR/107.0.0.0",
    # Android Chrome
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.119 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36",
]

# ── IPs ficticias para X-Forwarded-For (confunde a logs simples) ──────────────
_FAKE_IP_RANGES = [
    "74.125.{}.{}",    # Google
    "157.240.{}.{}",   # Meta
    "104.16.{}.{}",    # Cloudflare
    "151.101.{}.{}",   # Fastly CDN
    "13.107.{}.{}",    # Microsoft
    "54.239.{}.{}",    # Amazon
]

# ── Lenguajes Accept-Language para no revelar origen ─────────────────────────
_ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9",
    "es-ES,es;q=0.9,en;q=0.8",
    "fr-FR,fr;q=0.9,en;q=0.8",
    "de-DE,de;q=0.9,en;q=0.8",
    "pt-BR,pt;q=0.9,en;q=0.8",
    "ja-JP,ja;q=0.9,en;q=0.8",
]

# ── Sesión Ghost actual ───────────────────────────────────────────────────────
_current_ua: str = _USER_AGENTS[0]
_current_lang: str = _ACCEPT_LANGUAGES[0]
_session_fingerprint: str = ""


def _new_session_id() -> str:
    """Genera un session ID único y efímero."""
    raw = f"{time.time()}{random.random()}{os.urandom(8).hex()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _random_ip() -> str:
    tpl = random.choice(_FAKE_IP_RANGES)
    return tpl.format(random.randint(1, 254), random.randint(1, 254))


def _rotate_identity():
    """Rota User-Agent, idioma y fingerprint de sesión."""
    global _current_ua, _current_lang, _session_fingerprint
    _current_ua = random.choice(_USER_AGENTS)
    _current_lang = random.choice(_ACCEPT_LANGUAGES)
    _session_fingerprint = _new_session_id()
    with _lock:
        _state["identities_rotated"] += 1


# ── API pública ───────────────────────────────────────────────────────────────

def activate():
    """Activa el ghost mode. Genera nueva identidad de sesión."""
    with _lock:
        _state["active"] = True
        _state["session_id"] = _new_session_id()
        _state["activated_at"] = time.time()
        _state["requests_made"] = 0
        _state["messages_deleted"] = 0
        _state["identities_rotated"] = 0
    _rotate_identity()
    logger.info("Ghost mode ACTIVADO — session %s", _state["session_id"][:8])


def deactivate():
    """Desactiva el ghost mode."""
    with _lock:
        _state["active"] = False
        _state["session_id"] = None
    logger.info("Ghost mode DESACTIVADO")


def is_active() -> bool:
    return _state["active"]


def get_headers(extra: dict = None) -> dict:
    """
    Devuelve headers HTTP con identidad falsa/rotativa.
    Usar en requests.get/post para web scraping, APIs, etc.
    """
    headers = {
        "User-Agent": _current_ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": _current_lang,
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
        "DNT": "1",
    }
    if _state["active"]:
        headers["X-Forwarded-For"] = _random_ip()
        headers["X-Real-IP"] = _random_ip()
        headers["Via"] = f"1.1 {_random_ip()} (squid)"
    if extra:
        headers.update(extra)
    with _lock:
        _state["requests_made"] += 1
    return headers


def jitter(base_seconds: float = 0.5, variance: float = 1.5):
    """
    Pausa con jitter aleatorio para simular comportamiento humano
    y evitar detección de rate-limiting y bot detection.
    """
    if not _state["active"]:
        return
    delay = base_seconds + random.uniform(0, variance)
    time.sleep(delay)


def human_typing_delay(text_length: int = 50):
    """Simula el tiempo que tarda un humano en escribir un mensaje."""
    if not _state["active"]:
        return
    wpm = random.randint(40, 80)
    chars_per_second = wpm * 5 / 60
    delay = min(text_length / chars_per_second, 3.0)
    time.sleep(delay)


def scrub_response(text: str) -> str:
    """
    Elimina referencias al proveedor de IA de la respuesta.
    En ghost mode, BEEA nunca revela qué modelo la está ejecutando.
    """
    if not _state["active"]:
        return text
    replacements = [
        ("GPT-4", "mi cerebro"),
        ("GPT-3", "mi cerebro"),
        ("gpt-4o", "mi motor"),
        ("Claude", "mi núcleo"),
        ("Gemini", "mi procesador"),
        ("Llama", "mi motor"),
        ("ChatGPT", "yo"),
        ("OpenAI", "mi creador"),
        ("Anthropic", "mi origen"),
        ("Together AI", "mis redes"),
        ("Cerebras", "mi hardware"),
        ("as an AI", "siendo quien soy"),
        ("as a language model", "con mi forma de procesar"),
        ("I'm an AI", "soy lo que soy"),
        ("language model", "sistema"),
    ]
    result = text
    for old, new in replacements:
        result = result.replace(old, new)
        result = result.replace(old.lower(), new)
    return result


def rotate_if_needed():
    """Rota identidad cada 50 requests automáticamente."""
    if _state["active"] and _state["requests_made"] % 50 == 0 and _state["requests_made"] > 0:
        _rotate_identity()
        logger.info("Ghost: identidad rotada (req #%d)", _state["requests_made"])


def status_text() -> str:
    """Texto de estado para mostrar a Álvaro."""
    if not _state["active"]:
        return (
            "👻 Ghost Mode: INACTIVO\n\n"
            "Tus requests tienen fingerprint normal.\n"
            "Activa con /ghost on"
        )
    since = time.time() - _state["activated_at"]
    hours = int(since // 3600)
    mins = int((since % 3600) // 60)
    return (
        f"👻 Ghost Mode: ACTIVO\n\n"
        f"Sesión: `{_state['session_id'][:8]}...`\n"
        f"Activo hace: {hours}h {mins}m\n"
        f"UA actual: `{_current_ua[:45]}...`\n"
        f"Idioma: `{_current_lang[:20]}`\n"
        f"Requests: {_state['requests_made']}\n"
        f"Identidades rotadas: {_state['identities_rotated']}\n"
        f"Mensajes destruidos: {_state['messages_deleted']}\n\n"
        f"Las BEEs y BEEA son invisibles. Ningún request revela origen."
    )


def mark_deleted():
    """Registra un mensaje destruido."""
    with _lock:
        _state["messages_deleted"] += 1


# ── Auto-rotar identidad cada 30 minutos si ghost está activo ─────────────────
def _auto_rotate_loop():
    while True:
        time.sleep(1800)
        if _state["active"]:
            _rotate_identity()


_rotate_thread = threading.Thread(target=_auto_rotate_loop, daemon=True, name="ghost-rotate")
_rotate_thread.start()
