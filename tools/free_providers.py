"""
FreeProviders — pool de proveedores g4f sin API key.

Cada BEE toma un proveedor diferente del pool en round-robin.
Si un proveedor falla → se marca como no disponible por 5 minutos → siguiente.
Resultado: ~70 proveedores disponibles, límite prácticamente ilimitado.
"""
from __future__ import annotations
import time
import itertools
import threading
from core.logger import logger

# ── Proveedores g4f que funcionan sin autenticación ──────────────────────────
# Ordenados por confiabilidad / velocidad
_PROVIDER_NAMES = [
    "Blackbox",
    "DeepInfra",
    "Cloudflare",
    "GeminiPro",
    "Copilot",
    "HuggingFace",
    "PollinationsAI",
    "Liaobots",
    "ChatGpt",
    "You",
    "AiChats",
    "FreeChatgpt",
    "FreeNetfly",
    "Chatai",
    "PerplexityLabs",
    "MagickPen",
    "Feedough",
    "FreeGpt",
    "GigaChat",
    "Gemini",
    "GLM",
    "HuggingFaceAPI",
    "AnyProvider",
    "ApiAirforce",
    "CablyAI",
    "Cerebras",
    "GradientNetwork",
    "Pizzagpt",
    "RubiksAI",
    "TeachAnything",
    "Upstage",
    "Yqcloud",
]

# Cooldown en segundos después de un fallo
_COOLDOWN = 300  # 5 minutos

_lock = threading.Lock()
_failures: dict[str, float] = {}   # provider_name → timestamp del fallo
_counter = itertools.count()        # contador global para round-robin


def _load_provider(name: str):
    """Importa el provider g4f por nombre, devuelve None si no existe."""
    try:
        import g4f.Provider as P
        return getattr(P, name, None)
    except Exception:
        return None


def _is_available(name: str) -> bool:
    with _lock:
        fail_time = _failures.get(name)
    if fail_time and (time.time() - fail_time) < _COOLDOWN:
        return False
    return True


def _mark_failed(name: str):
    with _lock:
        _failures[name] = time.time()
    logger.warning("FreeProviders: %s marcado como no disponible por %ds", name, _COOLDOWN)


def _mark_recovered(name: str):
    with _lock:
        _failures.pop(name, None)


def get_provider_for_bee(bee_id: int):
    """
    Devuelve un proveedor g4f para la BEE con el ID dado.
    Usa round-robin + salta los que están en cooldown.
    Devuelve (provider_object, provider_name) o (None, None) si no hay ninguno.
    """
    # Calcular offset base por bee_id para distribuir
    start = bee_id % len(_PROVIDER_NAMES)
    for i in range(len(_PROVIDER_NAMES)):
        name = _PROVIDER_NAMES[(start + i) % len(_PROVIDER_NAMES)]
        if not _is_available(name):
            continue
        provider = _load_provider(name)
        if provider is None:
            continue
        return provider, name
    return None, None


def call_g4f(messages: list, bee_id: int = 0, model: str = None) -> str:
    """
    Llama a g4f con el proveedor asignado a la BEE.
    Rota automáticamente si falla.
    """
    import g4f

    start = bee_id % len(_PROVIDER_NAMES)
    tried = 0

    for i in range(len(_PROVIDER_NAMES)):
        name = _PROVIDER_NAMES[(start + i) % len(_PROVIDER_NAMES)]
        if not _is_available(name):
            continue

        provider = _load_provider(name)
        if provider is None:
            _mark_failed(name)
            continue

        try:
            kwargs = dict(
                model=model or g4f.models.default,
                messages=messages,
                provider=provider,
            )
            response = g4f.ChatCompletion.create(**kwargs)
            text = str(response).strip()
            if text and len(text) > 5:
                logger.info("g4f BEE-%d via %s: OK (%d chars)", bee_id, name, len(text))
                _mark_recovered(name)
                return text
            else:
                _mark_failed(name)
        except Exception as e:
            err = str(e).lower()
            if "429" in err or "rate" in err or "limit" in err:
                logger.warning("g4f %s: rate limit — skip", name)
            else:
                logger.warning("g4f %s error: %s", name, str(e)[:80])
            _mark_failed(name)
            tried += 1

    raise RuntimeError(f"Todos los proveedores g4f fallaron (intentados: {tried})")


def available_count() -> int:
    """Cuántos proveedores están actualmente disponibles."""
    return sum(1 for n in _PROVIDER_NAMES if _is_available(n))


def status() -> dict:
    """Estado del pool para el panel web."""
    now = time.time()
    result = {}
    for name in _PROVIDER_NAMES:
        fail_t = _failures.get(name)
        if fail_t and (now - fail_t) < _COOLDOWN:
            remaining = int(_COOLDOWN - (now - fail_t))
            result[name] = f"cooldown {remaining}s"
        else:
            result[name] = "disponible"
    return result
