"""
LLM Adapter — routing inteligente entre proveedores.

Prioridad para BEEs/entrenamiento autónomo:
  1. Cerebras  — hardware dedicado, ~1000 tok/seg, 4 keys, 50 rpm sostenido
  2. Together AI — pool 4 keys válidas (tgp_v1_*), sin censura
  3. Groq      — 100K tokens/día free tier, function-calling nativo
  4. Gemini    — 1500 req/día free, contexto 1M tokens
  5. OpenAI    — pago, fallback premium
  6. Anthropic — pago, fallback creativo

Rate limiter global: cada proveedor tiene RPM y cuota diaria configurados.
50 BEEs × 1 llamada/min = 50 rpm → caben todas en Cerebras sin agotar nada.
Multi-key pools: cada proveedor puede tener N claves que rotan en round-robin.
Variables soportadas:
  Together AI : TOG_API1..TOG_API20  o  TOGETHER_API_KEY
  Groq        : GROQ_API, GROQ_API_KEY, GROQ_API1..GROQ_API10
  OpenAI      : OPENAI_API_KEY, OPENAI_API_KEY_1..OPENAI_API_KEY_5
  Cerebras    : CEREBRAS_API, CEREBRAS_API2..4, CEREBRA_API4
  Gemini      : GEMINI_API, GEMINI_API2..5, GOOGLE_AI_KEY
"""
from __future__ import annotations
import os
import time
import datetime
import itertools
import threading
import requests
from core.logger import logger


# ── Rate Limiter + Quota Tracker por proveedor ────────────────────────────────

class _ProviderQuota:
    """
    Limitador de velocidad (RPM) + contador de cuota diaria por proveedor.
    Permite correr 50 BEEs simultáneamente sin exceder los límites gratuitos.

    Cada llamada a un proveedor debe pasar por quota.acquire() antes de ejecutar.
    Si ya se alcanzó el límite por minuto, la llamada espera en cola.
    Si se alcanzó la cuota diaria, lanza QuotaExhaustedError.
    """

    class QuotaExhaustedError(RuntimeError):
        pass

    def __init__(self, name: str, rpm: int, daily: int | None = None):
        self.name  = name
        self.rpm   = rpm        # máximo requests por minuto
        self.daily = daily      # None = sin límite diario (proveedores de pago)
        self._lock        = threading.Lock()
        self._minute_ts: list[float] = []   # timestamps de llamadas en el último minuto
        self._daily_count = 0
        self._day_reset   = self._next_midnight()

    @staticmethod
    def _next_midnight() -> float:
        tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return tomorrow.timestamp()

    def _reset_if_new_day(self):
        now = time.time()
        if now >= self._day_reset:
            self._daily_count = 0
            self._day_reset   = self._next_midnight()
            logger.info("Quota %s: cuota diaria reiniciada (nuevo día)", self.name)

    def acquire(self, wait: bool = True, timeout: float = 120.0) -> bool:
        """
        Solicita permiso para hacer 1 llamada a este proveedor.
        Si wait=True, bloquea hasta que haya un slot (máx timeout segundos).
        Devuelve True si se concedió, False si timeout.
        Lanza QuotaExhaustedError si se agotó la cuota diaria.
        """
        deadline = time.time() + timeout
        while True:
            with self._lock:
                self._reset_if_new_day()
                # Cuota diaria agotada
                if self.daily is not None and self._daily_count >= self.daily:
                    raise _ProviderQuota.QuotaExhaustedError(
                        f"{self.name}: cuota diaria agotada ({self._daily_count}/{self.daily}). "
                        f"Se reinicia a las {datetime.datetime.fromtimestamp(self._day_reset).strftime('%H:%M')}"
                    )
                # Limpiar timestamps de hace más de 60s
                now = time.time()
                self._minute_ts = [t for t in self._minute_ts if now - t < 60.0]
                # Hay slot disponible
                if len(self._minute_ts) < self.rpm:
                    self._minute_ts.append(now)
                    self._daily_count += 1
                    return True
                # No hay slot — calcular cuánto esperar
                oldest = self._minute_ts[0]
                wait_secs = 60.0 - (now - oldest) + 0.1

            if not wait or time.time() + wait_secs > deadline:
                return False
            time.sleep(min(wait_secs, 2.0))

    def status(self) -> dict:
        with self._lock:
            self._reset_if_new_day()
            now = time.time()
            recent = [t for t in self._minute_ts if now - t < 60.0]
            return {
                "provider":    self.name,
                "rpm_used":    len(recent),
                "rpm_limit":   self.rpm,
                "daily_used":  self._daily_count,
                "daily_limit": self.daily,
                "resets_at":   datetime.datetime.fromtimestamp(self._day_reset).strftime("%H:%M"),
            }


# ── Configuración de cuotas ────────────────────────────────────────────────────
# rpm_per_key   = límite real por key (con 15% margen)
# daily_per_key = límite diario por key (None = proveedor de pago)
#
# El sistema escala RPM × número de keys activas automáticamente.
#
# MATEMÁTICA 126 BEES 24/7:
#   Cerebras: 4 keys × 50 rpm/key = 200 rpm total
#   126 BEEs × 1 llamada/min      = 126 rpm consumido
#   200 rpm > 126 rpm              → CABEN TODAS, 24/7, GRATIS ✅
#   Groq/Gemini/Together           → reservados 100% para tus requests directos
#
_QUOTA_PER_KEY = {
    "cerebras":  {"rpm": 50,  "daily": None},   # ~60 rpm real, dejamos 50 con margen
    "together":  {"rpm": 15,  "daily": 2000},   # $1 crédito ~5K llamadas por key
    "groq":      {"rpm": 25,  "daily": 90},     # 100K tok/día ÷ ~1K tok/call
    "gemini":    {"rpm": 10,  "daily": 350},    # 1500 req/día free por key con margen
    "openai":    {"rpm": 50,  "daily": None},   # pago
    "anthropic": {"rpm": 10,  "daily": None},   # pago
    "fireworks": {"rpm": 20,  "daily": None},
}

# Se construirán después de cargar los pools (para escalar por nº de keys)
_QUOTAS: dict[str, _ProviderQuota] = {}


def _build_quotas(pools: dict) -> dict:
    """
    Construye los quota objects escalando por número de keys activas.
    4 Cerebras keys × 50 rpm = 200 rpm → soporta 126 BEEs simultáneas.
    """
    result = {}
    for name, cfg in _QUOTA_PER_KEY.items():
        pool = pools.get(name)
        num_keys = len(pool._keys) if pool and hasattr(pool, "_keys") else 1
        num_keys = max(num_keys, 1)
        scaled_rpm   = cfg["rpm"] * num_keys
        scaled_daily = cfg["daily"] * num_keys if cfg["daily"] is not None else None
        result[name] = _ProviderQuota(name, rpm=scaled_rpm, daily=scaled_daily)
        if num_keys > 1:
            logger.info(
                "Quota %s: %d keys → %d rpm%s",
                name, num_keys, scaled_rpm,
                f", {scaled_daily}/día" if scaled_daily else " (sin límite diario)"
            )
    return result


def quota_status() -> list[dict]:
    """Estado actual de todas las cuotas — para /sistema y dashboard."""
    return [q.status() for q in _QUOTAS.values()]


def estimate_task_quota(
    n_bees: int,
    calls_per_bee: int = 3,
    provider: str = "cerebras",
) -> dict:
    """
    Estima el coste de una tarea en BEEs y cuánto tiempo de cuota queda después.

    Parámetros:
        n_bees         — cuántas BEEs se van a usar
        calls_per_bee  — llamadas LLM estimadas por BEE (por defecto 3)
        provider       — proveedor principal para la tarea

    Devuelve un dict con:
        total_calls    — llamadas totales estimadas
        time_secs      — tiempo estimado de ejecución (segundos)
        quota_before   — estado de cuota antes (daily_used/daily_limit)
        quota_after    — estado proyectado después
        daily_pct_used — % de cuota diaria que usará esta tarea
        can_run        — True si hay suficiente cuota
        warning        — mensaje de aviso si queda poca cuota
    """
    total_calls = n_bees * calls_per_bee
    quota = _QUOTAS.get(provider)

    if quota is None:
        return {
            "total_calls": total_calls,
            "time_secs": total_calls * 1.5,
            "can_run": True,
            "warning": None,
        }

    with quota._lock:
        quota._reset_if_new_day()
        used_now  = quota._daily_count
        limit     = quota.daily
        rpm       = quota.rpm

    # Tiempo estimado (cola si supera RPM)
    time_secs = max(total_calls / max(rpm, 1) * 60, n_bees * 2.0)

    if limit is None:
        # Proveedor de pago o sin límite diario
        return {
            "total_calls":    total_calls,
            "time_secs":      round(time_secs),
            "quota_before":   {"used": used_now, "limit": "∞"},
            "quota_after":    {"used": used_now + total_calls, "limit": "∞"},
            "daily_pct_used": 0,
            "can_run":        True,
            "warning":        None,
        }

    remaining = limit - used_now
    after     = used_now + total_calls
    pct_task  = round(100 * total_calls / limit, 1)
    pct_after = round(100 * after / limit, 1)

    warning = None
    can_run = True
    if total_calls > remaining:
        can_run = False
        warning = (
            f"Cuota {provider} insuficiente: necesitas {total_calls} llamadas, "
            f"quedan {remaining}. Se reinicia a medianoche."
        )
    elif pct_after >= 90:
        warning = (
            f"Esta tarea usará {pct_task}% de la cuota diaria de {provider}. "
            f"Quedará {100 - pct_after:.0f}% hasta medianoche."
        )
    elif pct_after >= 70:
        warning = f"Cuota {provider} al {pct_after}% tras esta tarea."

    return {
        "total_calls":    total_calls,
        "time_secs":      round(time_secs),
        "quota_before":   {"used": used_now,    "limit": limit, "pct": round(100 * used_now / limit, 1)},
        "quota_after":    {"used": after,        "limit": limit, "pct": pct_after},
        "daily_pct_used": pct_task,
        "can_run":        can_run,
        "warning":        warning,
    }


def format_quota_warning(n_bees: int, calls_per_bee: int = 3) -> str:
    """
    Genera el mensaje de aviso de cuota para mostrar al usuario antes de una tarea BEE.
    Listo para enviar directamente por Telegram.
    """
    est = estimate_task_quota(n_bees, calls_per_bee, "cerebras")
    mins = est["time_secs"] // 60
    secs = est["time_secs"] % 60
    time_str = f"{mins}m {secs}s" if mins else f"{secs}s"

    qb = est.get("quota_before", {})
    qa = est.get("quota_after",  {})

    lines = [
        f"BEEs a usar: {n_bees}  |  Llamadas estimadas: {est['total_calls']}",
        f"Tiempo estimado: ~{time_str}",
    ]

    if qb.get("limit") != "∞" and qb.get("limit"):
        lines.append(
            f"Cerebras: {qb['used']}/{qb['limit']} → {qa['used']}/{qa['limit']} "
            f"({est['daily_pct_used']}% de la cuota diaria)"
        )
    else:
        lines.append("Cerebras: sin límite diario (uso libre)")

    if est["warning"]:
        lines.append(f"\n⚠️  {est['warning']}")

    return "\n".join(lines)


def _acquire_quota(provider: str, wait: bool = True, timeout: float = 120.0) -> bool:
    """
    Reserva un slot de cuota para el proveedor indicado.
    Si el proveedor no tiene quota configurada, siempre devuelve True.
    Lanza _ProviderQuota.QuotaExhaustedError si cuota diaria agotada.
    """
    quota = _QUOTAS.get(provider)
    if quota is None:
        return True
    return quota.acquire(wait=wait, timeout=timeout)


# ── Pool de claves multi-key ───────────────────────────────────────────────────

class _KeyPool:
    """Round-robin sobre un conjunto de claves del mismo proveedor."""
    def __init__(self, keys: list[str]):
        self._keys   = [k for k in keys if k]
        self._cycle  = itertools.cycle(self._keys) if self._keys else iter([])
        self._lock   = threading.Lock()

    def next(self) -> str:
        with self._lock:
            try:
                return next(self._cycle)
            except StopIteration:
                return ""

    def first(self) -> str:
        return self._keys[0] if self._keys else ""

    def all(self) -> list[str]:
        return list(self._keys)

    def __bool__(self):
        return bool(self._keys)

    def __len__(self):
        return len(self._keys)


# ── Auto-discovery de claves por patrón ───────────────────────────────────────
#
# El sistema escanea TODAS las variables de entorno buscando claves por patrón.
# Añade TOG_API99, GROQ_MY_KEY, OPENAI_KEY_WORK — se detectan solas al reiniciar.
# No hay listas fijas. No hay límite de número. No hay que tocar el código.
#
# Patrones por proveedor (busca en el NOMBRE de la variable):
_PROVIDER_PATTERNS: dict[str, list[str]] = {
    "together":  ["TOG_API", "TOGETHER"],
    "groq":      ["GROQ"],
    "openai":    ["OPENAI"],
    "anthropic": ["ANTHROPIC"],
    "fireworks": ["FIREWORKS"],
    "mistral":   ["MISTRAL"],
    "cerebras":  ["CEREBRAS", "CEREBRA"],
    "openrouter":["OPENROUTER"],
    "cohere":    ["COHERE"],
    "gemini":    ["GEMINI", "GOOGLE_AI", "GOOGLE_API"],
}

# Variables de entorno que se deben ignorar (no son API keys)
_IGNORE_VARS = {
    "PATH", "HOME", "USER", "SHELL", "TERM", "LANG", "LC_ALL",
    "PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "VIRTUAL_ENV",
    "SESSION_SECRET", "DISCORD_BOT_TOKEN", "TELEGRAM_BOT_TOKEN",
    "PANEL_PASSWORD", "PANEL_PORT",
}

# Sufijos de variables que claramente NO son API keys (son URLs, IDs, etc.)
_IGNORE_SUFFIXES = ("_BASE_URL", "_URL", "_ENDPOINT", "_HOST", "_PORT", "_ID", "_SECRET_KEY")


def _looks_like_api_key(value: str) -> bool:
    """Heurística: ¿este valor parece una API key real?"""
    v = value.strip()
    if len(v) < 20:
        return False
    # Rechazar URLs — nunca son API keys
    if v.startswith("http://") or v.startswith("https://"):
        return False
    # Prefijos conocidos de API keys reales
    known_prefixes = (
        "sk-", "gsk_", "tog_", "tgp_", "r8_", "key_",
        "fc-", "fw_", "sk_ant_", "AIza", "claude", "eyJ",
    )
    if any(v.lower().startswith(p.lower()) for p in known_prefixes):
        return True
    # Si tiene más de 32 chars y no tiene espacios → probablemente es una key
    if len(v) >= 32 and " " not in v and "\n" not in v:
        return True
    return False


def _scan_env_for_provider(patterns: list[str]) -> list[str]:
    """
    Escanea os.environ buscando variables cuyo NOMBRE contenga alguno de los patrones.
    Devuelve lista de valores que parecen API keys válidas, sin duplicados.
    """
    keys = []
    env = os.environ
    for var_name, var_value in env.items():
        if var_name in _IGNORE_VARS:
            continue
        name_upper = var_name.upper()
        # Ignorar variables que claramente no son keys (URLs, endpoints, etc.)
        if any(name_upper.endswith(sfx) for sfx in _IGNORE_SUFFIXES):
            continue
        if any(p.upper() in name_upper for p in patterns):
            # Puede ser coma-separado (varias keys en una variable)
            for part in var_value.split(","):
                part = part.strip()
                if part and _looks_like_api_key(part):
                    keys.append(part)
    return list(dict.fromkeys(keys))  # deduplicar


# ── Pools dinámicos ────────────────────────────────────────────────────────────

_TOGETHER_POOL   = _KeyPool(_scan_env_for_provider(_PROVIDER_PATTERNS["together"]))
_GROQ_POOL       = _KeyPool(_scan_env_for_provider(_PROVIDER_PATTERNS["groq"]))
_OPENAI_POOL     = _KeyPool(_scan_env_for_provider(_PROVIDER_PATTERNS["openai"]))
_ANTHROPIC_POOL  = _KeyPool(_scan_env_for_provider(_PROVIDER_PATTERNS["anthropic"]))
_FIREWORKS_POOL  = _KeyPool(_scan_env_for_provider(_PROVIDER_PATTERNS["fireworks"]))
_MISTRAL_POOL    = _KeyPool(_scan_env_for_provider(_PROVIDER_PATTERNS["mistral"]))
_CEREBRAS_POOL   = _KeyPool(_scan_env_for_provider(_PROVIDER_PATTERNS["cerebras"]))
_OPENROUTER_POOL = _KeyPool(_scan_env_for_provider(_PROVIDER_PATTERNS["openrouter"]))
_COHERE_POOL     = _KeyPool(_scan_env_for_provider(_PROVIDER_PATTERNS["cohere"]))
_GEMINI_POOL     = _KeyPool(_scan_env_for_provider(_PROVIDER_PATTERNS["gemini"]))

_ALL_POOLS: dict[str, _KeyPool] = {
    "together":   _TOGETHER_POOL,
    "groq":       _GROQ_POOL,
    "openai":     _OPENAI_POOL,
    "anthropic":  _ANTHROPIC_POOL,
    "fireworks":  _FIREWORKS_POOL,
    "mistral":    _MISTRAL_POOL,
    "cerebras":   _CEREBRAS_POOL,
    "openrouter": _OPENROUTER_POOL,
    "cohere":     _COHERE_POOL,
    "gemini":     _GEMINI_POOL,
}

# Construir quotas escaladas por número de keys (4 Cerebras = 200 rpm → 126 BEEs)
_QUOTAS.update(_build_quotas(_ALL_POOLS))


def refresh_pools() -> dict:
    """
    Reescanea los secrets y reconstruye todos los pools.
    Se llama automáticamente cada 5 minutos y también manualmente
    desde el panel web o desde Telegram con /refresh_keys.
    Retorna el nuevo estado.
    """
    global _TOGETHER_POOL, _GROQ_POOL, _OPENAI_POOL, _ANTHROPIC_POOL
    global _FIREWORKS_POOL, _MISTRAL_POOL, _CEREBRAS_POOL
    global _OPENROUTER_POOL, _COHERE_POOL, _GEMINI_POOL

    for name, patterns in _PROVIDER_PATTERNS.items():
        new_keys = _scan_env_for_provider(patterns)
        pool = _ALL_POOLS[name]
        if new_keys != pool.all():
            _ALL_POOLS[name] = _KeyPool(new_keys)
            logger.info("Pool %s actualizado: %d clave(s)", name, len(new_keys))

    # Reasignar variables globales desde el dict actualizado
    _TOGETHER_POOL   = _ALL_POOLS["together"]
    _GROQ_POOL       = _ALL_POOLS["groq"]
    _OPENAI_POOL     = _ALL_POOLS["openai"]
    _ANTHROPIC_POOL  = _ALL_POOLS["anthropic"]
    _FIREWORKS_POOL  = _ALL_POOLS["fireworks"]
    _MISTRAL_POOL    = _ALL_POOLS["mistral"]
    _CEREBRAS_POOL   = _ALL_POOLS["cerebras"]
    _OPENROUTER_POOL = _ALL_POOLS["openrouter"]
    _COHERE_POOL     = _ALL_POOLS["cohere"]
    _GEMINI_POOL     = _ALL_POOLS["gemini"]

    return key_pool_status()


def _auto_refresh_loop():
    """Hilo background: refresca pools cada 5 minutos."""
    import time
    while True:
        time.sleep(300)
        try:
            refresh_pools()
            logger.info("Key pools auto-refresh completado")
        except Exception as e:
            logger.warning("Key pools auto-refresh error: %s", e)


# Arrancar auto-refresh en background
import threading as _threading
_refresh_thread = _threading.Thread(target=_auto_refresh_loop, daemon=True, name="key-pool-refresh")
_refresh_thread.start()


# Funciones de clave (API pública — compatibles con código existente)
# Usan lambdas que leen del dict _ALL_POOLS para que siempre reflejen el estado más reciente
OPENAI_KEY    = lambda: _ALL_POOLS["openai"].next()
ANTHROPIC_KEY = lambda: _ALL_POOLS["anthropic"].next()
GROQ_KEY      = lambda: _ALL_POOLS["groq"].next()
TOGETHER_KEY  = lambda: _ALL_POOLS["together"].next()
FIREWORKS_KEY = lambda: _ALL_POOLS["fireworks"].next()
MISTRAL_KEY   = lambda: _ALL_POOLS["mistral"].next()
CEREBRAS_KEY  = lambda: _ALL_POOLS["cerebras"].next()


def key_pool_status() -> dict:
    """Estado de todos los pools — para el panel web y /refresh_keys."""
    return {
        name: {"keys": len(pool), "has": bool(pool)}
        for name, pool in _ALL_POOLS.items()
    }


def log_key_pools():
    s = key_pool_status()
    active = {k: v["keys"] for k, v in s.items() if v["has"]}
    logger.info("Key pools activos: %s", active)


log_key_pools()

# ── Modelos Groq ──────────────────────────────────────────────────────────────
# llama3-groq-70b-8192-tool-use-preview: optimizado para function-calling
GROQ_TOOL_MODEL  = "llama3-groq-70b-8192-tool-use-preview"
GROQ_FAST_MODEL  = "llama-3.1-8b-instant"
GROQ_SMART_MODEL = "llama-3.3-70b-versatile"

# ── Modelos Together AI sin censura ───────────────────────────────────────────
TOGETHER_UNCENSORED_MODELS = [
    "NousResearch/Nous-Hermes-2-Mixtral-8x7B-DPO",   # sin censura, muy capaz
    "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",   # free tier, permisivo
    "mistralai/Mixtral-8x7B-Instruct-v0.1",           # fallback
]


# ── Funciones base ────────────────────────────────────────────────────────────

def _openai(messages: list, model: str = "gpt-4o-mini", tools: list = None) -> str:
    _acquire_quota("openai")
    key = OPENAI_KEY()
    if not key:
        raise RuntimeError("No OPENAI_API_KEY")
    import openai
    client = openai.OpenAI(api_key=key)
    kwargs = dict(model=model, messages=messages, max_tokens=2000, temperature=0.7)
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content.strip() or ""


def _anthropic(messages: list, model: str = "claude-3-5-haiku-20241022") -> str:
    _acquire_quota("anthropic")
    key = ANTHROPIC_KEY()
    if not key:
        raise RuntimeError("No ANTHROPIC_API_KEY")
    system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
    user_msgs = [m for m in messages if m["role"] != "system"]
    payload = {"model": model, "max_tokens": 2048, "messages": user_msgs}
    if system_msg:
        payload["system"] = system_msg
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json=payload, timeout=60,
    )
    resp.raise_for_status()
    parts = [x.get("text", "") for x in resp.json().get("content", []) if x.get("type") == "text"]
    return "\n".join(parts).strip()


def _groq(messages: list, model: str = GROQ_SMART_MODEL, tools: list = None) -> str:
    """Groq — API compatible con OpenAI, soporta function-calling nativo."""
    _acquire_quota("groq")
    key = GROQ_KEY()
    if not key:
        raise RuntimeError("No GROQ_API_KEY")
    import openai
    client = openai.OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")
    kwargs = dict(model=model, messages=messages, max_tokens=2000, temperature=0.7)
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content.strip() or ""


def _groq_with_tools(messages: list, tools: list, model: str = GROQ_TOOL_MODEL):
    """
    Groq con function-calling completo. Devuelve el objeto completion completo
    (no solo texto) para que el caller pueda procesar tool_calls.
    """
    key = GROQ_KEY()
    if not key:
        raise RuntimeError("No GROQ_API_KEY")
    import openai
    client = openai.OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=tools,
        tool_choice="auto",
        max_tokens=2000,
        temperature=0.2,
    )
    return resp


def _together(messages: list, model: str = None) -> str:
    """
    Together AI — modelos sin censura, OpenAI-compatible.
    Solo usa keys con prefijo tgp_v1_ o togapi_ (formato actual).
    Las keys antiguas key_XXXX están expiradas y se saltan automáticamente.
    """
    _acquire_quota("together")
    import openai

    together_pool = _ALL_POOLS["together"]
    all_keys = together_pool._keys if hasattr(together_pool, "_keys") else []

    # Filtrar solo keys válidas del formato actual de Together
    valid_keys = [k for k in all_keys if k.startswith("tgp_v1_") or k.startswith("togapi_")]
    if not valid_keys:
        # Si no hay keys válidas, intentar con lo que haya (última opción)
        valid_keys = all_keys

    last_err = None
    chosen_model = model or TOGETHER_UNCENSORED_MODELS[0]

    for key in valid_keys:
        try:
            client = openai.OpenAI(api_key=key, base_url="https://api.together.xyz/v1")
            resp = client.chat.completions.create(
                model=chosen_model,
                messages=messages,
                max_tokens=2000,
                temperature=0.7,
            )
            text = resp.choices[0].message.content
            if text and text.strip():
                return text.strip()
        except Exception as e:
            last_err = str(e)
            continue

    raise RuntimeError(f"Together: ninguna key válida respondió. Último error: {last_err}")


def _fireworks(messages: list, model: str = "accounts/fireworks/models/llama-v3p1-70b-instruct") -> str:
    """Fireworks AI — free tier, permisivo."""
    key = FIREWORKS_KEY()
    if not key:
        raise RuntimeError("No FIREWORKS_API_KEY")
    import openai
    client = openai.OpenAI(api_key=key, base_url="https://api.fireworks.ai/inference/v1")
    resp = client.chat.completions.create(
        model=model, messages=messages, max_tokens=2000, temperature=0.7
    )
    return resp.choices[0].message.content.strip() or ""


def _cerebras(messages: list, model: str = "llama3.1-8b") -> str:
    """
    Cerebras — hardware AI dedicado, inferencia ultra-rápida (~1000 tok/seg).
    Modelos disponibles: llama3.1-8b (rápido), gpt-oss-120b (potente).
    Rate limiter: 50 rpm — aguanta 50 BEEs en paralelo exactas.
    """
    _acquire_quota("cerebras")
    key = CEREBRAS_KEY()
    if not key:
        raise RuntimeError("No CEREBRAS_API_KEY")
    import openai
    client = openai.OpenAI(api_key=key, base_url="https://api.cerebras.ai/v1")
    try:
        resp = client.chat.completions.create(
            model=model, messages=messages, max_tokens=2000, temperature=0.7
        )
        return resp.choices[0].message.content.strip() or ""
    except Exception:
        resp = client.chat.completions.create(
            model="gpt-oss-120b", messages=messages, max_tokens=2000, temperature=0.7
        )
        return resp.choices[0].message.content.strip() or ""


def _gemini(messages: list, model: str = "gemini-2.0-flash") -> str:
    """
    Gemini Flash — Google AI, contexto 1M tokens, 4 claves en rotación.
    Usa la API REST nativa v1beta.
    Cascada de modelos: gemini-2.0-flash → gemini-2.0-flash-lite → gemini-2.0-flash-exp
    Cuota gratuita se reinicia cada día a medianoche PST.
    """
    gemini_pool = _ALL_POOLS["gemini"]
    num_keys = len(gemini_pool._keys) if hasattr(gemini_pool, "_keys") else 4
    last_err = None

    # Construir payload una sola vez
    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    user_parts = [
        {"role": "user" if m["role"] == "user" else "model",
         "parts": [{"text": m["content"]}]}
        for m in messages if m["role"] != "system"
    ]
    payload = {
        "contents": user_parts,
        "generationConfig": {"maxOutputTokens": 2000, "temperature": 0.7},
    }
    if system_parts:
        payload["systemInstruction"] = {"parts": [{"text": " ".join(system_parts)}]}

    # Modelos a intentar en orden
    model_cascade = [
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash-exp",
    ]

    # Intentar cada clave × cada modelo hasta obtener respuesta
    for attempt in range(num_keys):
        key = gemini_pool.next()
        if not key:
            break
        for mdl in model_cascade:
            try:
                url = (
                    f"https://generativelanguage.googleapis.com/v1beta"
                    f"/models/{mdl}:generateContent?key={key}"
                )
                resp = requests.post(url, json=payload, timeout=30)
                if resp.status_code == 429:
                    last_err = f"429 quota ({mdl})"
                    continue
                resp.raise_for_status()
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    text = "".join(p.get("text", "") for p in parts)
                    if text.strip():
                        return text.strip()
            except Exception as e:
                last_err = str(e)
                continue

    raise RuntimeError(f"Gemini: todos los modelos/claves fallaron. Último error: {last_err}")


# ── Funciones de alto nivel ───────────────────────────────────────────────────

def generate_with_fallback(messages: list) -> str:
    """
    Cascada completa por prioridad real:
    Together(5 keys) → Cerebras(4 keys) → Gemini(4 keys) → Groq → OpenAI → Anthropic
    Usa los proveedores más baratos primero, los premium como último recurso.
    """
    providers = []
    if _ALL_POOLS["together"]:
        providers.append(("Together", lambda: _together(messages)))
    if _ALL_POOLS["cerebras"]:
        providers.append(("Cerebras", lambda: _cerebras(messages)))
    if _ALL_POOLS["gemini"]:
        providers.append(("Gemini", lambda: _gemini(messages)))
    if GROQ_KEY():
        providers.append(("Groq", lambda: _groq(messages)))
    if OPENAI_KEY():
        providers.append(("OpenAI", lambda: _openai(messages)))
    if ANTHROPIC_KEY():
        providers.append(("Anthropic", lambda: _anthropic(messages)))
    if not providers:
        return "Sin proveedor LLM disponible."

    last_error = None
    for name, fn in providers:
        try:
            result = fn()
            if result:
                return result
        except Exception as e:
            last_error = e
            logger.warning("Proveedor %s falló: %s", name, e)

    logger.error("Todos los proveedores fallaron. Último: %s", last_error)
    return "Todos los proveedores de IA fallaron. Intenta de nuevo."


def generate_uncensored(messages: list) -> str:
    """
    Modelo sin censura para tareas que GPT rechaza.
    Cascada: Together AI → Groq (Llama, menos restrictivo) → OpenAI fallback.
    """
    # 1. Together AI — modelos sin filtros
    if TOGETHER_KEY():
        for model in TOGETHER_UNCENSORED_MODELS:
            try:
                result = _together(messages, model=model)
                if result:
                    logger.info("Uncensored via Together AI [%s]", model)
                    return result
            except Exception as e:
                logger.warning("Together [%s] falló: %s", model, e)

    # 2. Groq Llama — mucho más permisivo que GPT
    if GROQ_KEY():
        try:
            result = _groq(messages, model=GROQ_SMART_MODEL)
            if result:
                logger.info("Uncensored via Groq Llama")
                return result
        except Exception as e:
            logger.warning("Groq uncensored falló: %s", e)

    # 3. Fireworks fallback
    if FIREWORKS_KEY():
        try:
            result = _fireworks(messages)
            if result:
                return result
        except Exception as e:
            logger.warning("Fireworks falló: %s", e)

    # 4. OpenAI último recurso
    if OPENAI_KEY():
        try:
            return _openai(messages)
        except Exception as e:
            logger.warning("OpenAI fallback falló: %s", e)

    return "Sin proveedor disponible para esta tarea."


def generate_for_bees(messages: list, tools: list = None) -> str:
    """
    LLM para BEEs — prioridad: velocidad + coste cero.
    Orden: Cerebras (más rápido) → Together (5 keys) → Gemini → Groq → OpenAI
    Si hay tools: Groq tool-use primero (soporta function-calling nativo).
    """
    # Con tools: Groq primero porque soporta function-calling nativo
    if tools and GROQ_KEY():
        try:
            result = _groq(messages, model=GROQ_TOOL_MODEL, tools=tools)
            if result:
                return result
        except Exception as e:
            logger.warning("Groq tool-use BEE falló: %s", e)

    # Sin tools o Groq falló: Cerebras primero (inferencia ultra-rápida)
    if not tools and _ALL_POOLS["cerebras"]:
        try:
            result = _cerebras(messages)
            if result:
                return result
        except Exception as e:
            logger.warning("Cerebras BEE falló: %s", e)

    # Together AI — 5 keys en rotación, buena calidad
    if _ALL_POOLS["together"]:
        try:
            result = _together(messages)
            if result:
                return result
        except Exception as e:
            logger.warning("Together BEE falló: %s", e)

    # Gemini Flash — 4 keys, rápido, contexto largo
    if _ALL_POOLS["gemini"]:
        try:
            result = _gemini(messages)
            if result:
                return result
        except Exception as e:
            logger.warning("Gemini BEE falló: %s", e)

    # Groq (sin tools)
    if GROQ_KEY():
        try:
            result = _groq(messages, model=GROQ_SMART_MODEL)
            if result:
                return result
        except Exception as e:
            logger.warning("Groq BEE falló: %s", e)

    # OpenAI último recurso
    if OPENAI_KEY():
        try:
            return _openai(messages, tools=tools)
        except Exception as e:
            logger.warning("OpenAI BEE falló: %s", e)

    return "Sin proveedor disponible para BEE."


def generate_for_bees_with_response(messages: list, tools: list):
    """
    Como generate_for_bees pero devuelve el objeto completion completo
    para procesar tool_calls en el loop agéntico.
    """
    import openai as _openai_mod

    # Groq primero
    if GROQ_KEY():
        try:
            return _groq_with_tools(messages, tools, model=GROQ_TOOL_MODEL)
        except Exception as e:
            logger.warning("Groq tool-use falló: %s — usando OpenAI", e)

    # OpenAI fallback
    if OPENAI_KEY():
        try:
            client = _openai_mod.OpenAI(api_key=OPENAI_KEY())
            return client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=2000,
                temperature=0.2,
            )
        except Exception as e:
            logger.warning("OpenAI tool-use falló: %s", e)

    raise RuntimeError("Sin proveedor disponible para tool-use")


# ── Routing inteligente por tipo de tarea ─────────────────────────────────────
#
#  TIERS por prioridad real:
#   SPEED    — Cerebras  (hardware AI, ~1000 tokens/seg, sin latencia)
#   BULK     — Together  (5 keys en rotación, coste ~cero, BEEs)
#   CONTEXT  — Gemini Flash (128K ctx, 4 keys, multimodal)
#   SMART    — Groq Llama 70B (rápido, open-source, financial ok)
#   PREMIUM  — OpenAI GPT-4o (mejor razonamiento)
#   NUANCED  — Anthropic Claude (mejor escritura, ética, análisis profundo)
#   UNCENSORED — Together AI (sin filtros)
#
#  Regla: nunca gastar GPT-4o/Claude en tareas simples.
#  Regla: usar Cerebras cuando la velocidad importa más que la calidad.
#  Regla: usar Together para todas las BEEs (5 keys = sin límite efectivo).
# ─────────────────────────────────────────────────────────────────────────────

def _route_speed(m):
    """Cerebras → Groq → Together — máxima velocidad, calidad secundaria."""
    if _ALL_POOLS["cerebras"]:
        try:
            return _cerebras(m)
        except Exception:
            pass
    if GROQ_KEY():
        try:
            return _groq(m, GROQ_FAST_MODEL)
        except Exception:
            pass
    return _together(m)

def _route_bulk(m):
    """
    Proveedor para BEEs en paralelo y entrenamiento autónomo.
    Cerebras PRIMERO — ultra-rápido y no consume cuotas de Together/Gemini/Groq
    que Álvaro necesita para sus requests directos.
    Cascada: Cerebras(4 keys) → Together(valid tgp_v1_ keys) → OpenAI-mini
    """
    if _ALL_POOLS["cerebras"]:
        try:
            return _cerebras(m)
        except Exception:
            pass
    # Together — solo las keys válidas (tgp_v1_ prefix), ignorar key_ expiradas
    if _ALL_POOLS["together"]:
        try:
            return _together(m)
        except Exception:
            pass
    # Último recurso: gpt-4o-mini (más barato de OpenAI)
    if OPENAI_KEY():
        try:
            return _openai(m, "gpt-4o-mini")
        except Exception:
            pass
    raise RuntimeError("_route_bulk: todos los proveedores fallaron")

def _route_context(m):
    """Gemini Flash → Together — para documentos largos (128K ctx)."""
    if _ALL_POOLS["gemini"]:
        try:
            return _gemini(m)
        except Exception:
            pass
    return _together(m) if _ALL_POOLS["together"] else generate_with_fallback(m)

def _route_analysis(m):
    """Together Llama → Groq → Gemini — análisis y research."""
    if _ALL_POOLS["together"]:
        try:
            return _together(m, model="meta-llama/Llama-3.3-70B-Instruct-Turbo")
        except Exception:
            pass
    if GROQ_KEY():
        try:
            return _groq(m, GROQ_SMART_MODEL)
        except Exception:
            pass
    return _gemini(m) if _ALL_POOLS["gemini"] else generate_with_fallback(m)

def _route_code(m):
    """Groq tool-use → GPT-4o → Together — para código con function-calling."""
    if GROQ_KEY():
        try:
            return _groq(m, GROQ_TOOL_MODEL)
        except Exception:
            pass
    if OPENAI_KEY():
        try:
            return _openai(m, "gpt-4o-mini")
        except Exception:
            pass
    return generate_with_fallback(m)

def _route_complex(m):
    """GPT-4o → Together Llama — razonamiento complejo, matemáticas, planificación."""
    if OPENAI_KEY():
        try:
            return _openai(m, "gpt-4o")
        except Exception:
            pass
    if _ALL_POOLS["together"]:
        try:
            return _together(m, model="meta-llama/Llama-3.3-70B-Instruct-Turbo")
        except Exception:
            pass
    return generate_with_fallback(m)

def _route_creative(m):
    """Anthropic Claude → Together → GPT-4o — escritura, creatividad, matices."""
    if ANTHROPIC_KEY():
        try:
            return _anthropic(m, model="claude-3-5-haiku-20241022")
        except Exception:
            pass
    if _ALL_POOLS["together"]:
        try:
            return _together(m, model="NousResearch/Nous-Hermes-2-Mixtral-8x7B-DPO")
        except Exception:
            pass
    return generate_with_fallback(m)


TASK_MODEL_MAP: dict = {
    # ── Velocidad crítica ──────────────────────────────────────────────────────
    "speed":            ("cerebras",   _route_speed),
    "ping":             ("cerebras",   _route_speed),
    "quick":            ("cerebras",   _route_speed),

    # ── Chat y conversación general ───────────────────────────────────────────
    "chat":             ("cerebras",   _route_speed),
    "conversation":     ("cerebras",   _route_speed),

    # ── BEEs en paralelo (bulk) ────────────────────────────────────────────────
    # Cerebras PRIMARY: 4 keys, ultra-rápido, no consume cuotas de otros providers
    "bulk":             ("cerebras",   _route_bulk),
    "bee":              ("cerebras",   _route_bulk),
    "parallel":         ("cerebras",   _route_bulk),
    "swarm":            ("cerebras",   _route_bulk),

    # ── Contexto largo / documentos ───────────────────────────────────────────
    "long_context":     ("gemini",     _route_context),
    "document":         ("gemini",     _route_context),
    "pdf":              ("gemini",     _route_context),
    "book":             ("gemini",     _route_context),

    # ── Research y análisis ───────────────────────────────────────────────────
    "analysis":         ("together",   _route_analysis),
    "research":         ("together",   _route_analysis),
    "summary":          ("gemini",     _route_context),
    "translation":      ("gemini",     _route_context),
    "trading_signal":   ("together",   _route_analysis),

    # ── Código y herramientas ─────────────────────────────────────────────────
    "code":             ("groq_tool",  _route_code),
    "debug":            ("groq_tool",  _route_code),
    "tool_use":         ("groq_tool",  _route_code),

    # ── Razonamiento complejo ─────────────────────────────────────────────────
    "complex":          ("openai_4o",  _route_complex),
    "reasoning":        ("openai_4o",  _route_complex),
    "planning":         ("openai_4o",  _route_complex),
    "strategy":         ("openai_4o",  _route_complex),
    "trading_strategy": ("openai_4o",  _route_complex),
    "build":            ("openai_4o",  _route_complex),

    # ── Escritura creativa y matices ──────────────────────────────────────────
    "creative":         ("claude",     _route_creative),
    "writing":          ("claude",     _route_creative),
    "story":            ("claude",     _route_creative),

    # ── Sin censura ───────────────────────────────────────────────────────────
    "uncensored":       ("together",   generate_uncensored),
    "explicit":         ("together",   generate_uncensored),
    "nsfw":             ("together",   generate_uncensored),
}


def generate_smart(messages: list, task_type: str = "chat") -> str:
    """
    Routing inteligente: elige el modelo óptimo por tipo de tarea.
    Nunca gasta GPT-4o en tareas simples.
    Prioriza velocidad y coste cero cuando la calidad no es crítica.
    """
    _, primary_fn = TASK_MODEL_MAP.get(task_type, ("cerebras", _route_speed))
    try:
        result = primary_fn(messages)
        if result:
            return result
    except Exception as e:
        logger.warning("Smart routing [%s] falló: %s — usando fallback", task_type, e)

    return generate_with_fallback(messages)


# ── Adapter class ─────────────────────────────────────────────────────────────

class LLMAdapter:
    def generate_text(self, prompt: str, max_tokens: int = 2000, system_prompt: str = None,
                      messages: list = None, task_type: str = "chat") -> str:
        if messages is not None:
            return generate_smart(messages, task_type)
        sys = system_prompt or "Eres un asistente técnico experto. Responde de forma directa y precisa."
        return generate_smart([
            {"role": "system", "content": sys},
            {"role": "user", "content": prompt},
        ], task_type)

    def generate_code(self, prompt: str, language: str = "python") -> str:
        return self.generate_text(
            prompt=f"Escribe código {language} para: {prompt}. Solo código, sin explicación.",
            task_type="code",
        )

    def summarize(self, text: str) -> str:
        return self.generate_text(
            prompt=f"Resume esto brevemente:\n\n{text[:3000]}",
            task_type="summary",
        )

    def analyze_trading(self, token_data: str) -> str:
        return self.generate_text(
            system_prompt=(
                "Eres un analista de trading cripto experto. Analiza los datos del token y genera "
                "recomendación BUY/SELL/HOLD con nivel de confianza. Sé directo y conciso."
            ),
            prompt=f"Datos del token:\n{token_data}",
            task_type="trading_signal",
        )

    def plan_complex_task(self, task: str) -> str:
        return self.generate_text(prompt=task, task_type="planning")


llm_adapter = LLMAdapter()
