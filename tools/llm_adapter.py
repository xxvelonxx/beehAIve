"""
LLM Adapter — routing inteligente entre proveedores.

Prioridad para BEEs:
  1. Groq (gratis, rápido, soporta function-calling nativo)
  2. Together AI — pool de claves: TOG_API1..TOG_API20 + TOGETHER_API_KEY
  3. OpenAI (fallback premium)
  4. Anthropic (fallback extra)

Multi-key pools: cada proveedor puede tener N claves que rotan en round-robin.
Variables soportadas:
  Together AI : TOG_API1, TOG_API2, ... TOG_API20  o  TOGETHER_API_KEY
  Groq        : GROQ_API, GROQ_API_KEY, GROQ_API1 .. GROQ_API10
  OpenAI      : OPENAI_API_KEY, OPENAI_API_KEY_1 .. OPENAI_API_KEY_5
"""
from __future__ import annotations
import os
import itertools
import threading
import requests
from core.logger import logger


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


def _looks_like_api_key(value: str) -> bool:
    """Heurística: ¿este valor parece una API key real?"""
    v = value.strip()
    if len(v) < 20:
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


def _anthropic(messages: list, model: str = "claude-3-haiku-20240307") -> str:
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
    """Together AI — modelos sin censura, OpenAI-compatible."""
    key = TOGETHER_KEY()
    if not key:
        raise RuntimeError("No TOGETHER_API_KEY")
    import openai
    client = openai.OpenAI(api_key=key, base_url="https://api.together.xyz/v1")
    chosen_model = model or TOGETHER_UNCENSORED_MODELS[0]
    resp = client.chat.completions.create(
        model=chosen_model,
        messages=messages,
        max_tokens=2000,
        temperature=0.7,
    )
    return resp.choices[0].message.content.strip() or ""


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


# ── Funciones de alto nivel ───────────────────────────────────────────────────

def generate_with_fallback(messages: list) -> str:
    """Cascada completa: Groq → OpenAI → Anthropic."""
    providers = []
    if GROQ_KEY():
        providers.append(("Groq", lambda: _groq(messages)))
    if OPENAI_KEY():
        providers.append(("OpenAI", lambda: _openai(messages)))
    if ANTHROPIC_KEY():
        providers.append(("Anthropic", lambda: _anthropic(messages)))
    if not providers:
        return "Sin proveedor LLM disponible. Configura OPENAI_API_KEY o GROQ_API."

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
    LLM primario para BEEs — prioriza Groq (gratis + rápido).
    Si hay tools, usa Groq function-calling nativo.
    Fallback a OpenAI si Groq no está disponible.
    """
    if GROQ_KEY():
        try:
            model = GROQ_TOOL_MODEL if tools else GROQ_SMART_MODEL
            result = _groq(messages, model=model, tools=tools)
            if result:
                return result
        except Exception as e:
            logger.warning("Groq BEE falló: %s — usando OpenAI", e)

    if OPENAI_KEY():
        try:
            return _openai(messages, tools=tools)
        except Exception as e:
            logger.warning("OpenAI BEE falló: %s", e)

    return generate_with_fallback(messages)


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


# ── Smart routing por tipo de tarea ──────────────────────────────────────────

TASK_MODEL_MAP = {
    "chat":             ("groq_fast",  lambda m: _groq(m, GROQ_FAST_MODEL)),
    "price":            ("groq_fast",  lambda m: _groq(m, GROQ_FAST_MODEL)),
    "summary":          ("groq_smart", lambda m: _groq(m, GROQ_SMART_MODEL)),
    "analysis":         ("groq_smart", lambda m: _groq(m, GROQ_SMART_MODEL)),
    "trading_signal":   ("groq_smart", lambda m: _groq(m, GROQ_SMART_MODEL)),
    "code":             ("groq_tool",  lambda m: _groq(m, GROQ_TOOL_MODEL)),
    "complex":          ("openai",     lambda m: _openai(m, "gpt-4o")),
    "trading_strategy": ("openai",     lambda m: _openai(m, "gpt-4o")),
    "build":            ("openai",     lambda m: _openai(m, "gpt-4o")),
    "planning":         ("groq_smart", lambda m: _groq(m, GROQ_SMART_MODEL)),
    "uncensored":       ("together",   generate_uncensored),
}


def generate_smart(messages: list, task_type: str = "chat") -> str:
    tier_name, primary_fn = TASK_MODEL_MAP.get(task_type, ("groq_smart", lambda m: _groq(m, GROQ_SMART_MODEL)))

    # Verificar que el proveedor primario esté disponible
    has_provider = (
        (tier_name.startswith("groq") and GROQ_KEY()) or
        (tier_name.startswith("openai") and OPENAI_KEY()) or
        (tier_name == "together" and TOGETHER_KEY()) or
        tier_name not in ("groq_fast", "groq_smart", "groq_tool", "openai", "together")
    )

    if has_provider:
        try:
            result = primary_fn(messages)
            if result:
                return result
        except Exception as e:
            logger.warning("Smart routing primary (%s) failed: %s", tier_name, e)

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
