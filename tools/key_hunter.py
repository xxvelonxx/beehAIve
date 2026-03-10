"""
KeyHunter — BEE especializada en encontrar APIs gratuitas y notificar a Álvaro.

Flujo completo:
  1. BEE key_hunter busca proveedores con free tier vía web_search
  2. Documenta: nombre, URL registro, límites, modelos, si necesita tarjeta
  3. Guarda hallazgos en memory/key_discoveries.json
  4. Notifica a Álvaro por Telegram con lista clickeable
  5. Álvaro se registra manualmente (email/captcha lo requieren)
  6. Álvaro añade la key en Replit Secrets
  7. BEEA la detecta automáticamente al siguiente ciclo (key scanner)
  8. BEE api_integrator verifica que funciona y la añade al fallback chain

Comando Telegram: /keys → ejecuta búsqueda ahora
                  /keys status → ve providers descubiertos no integrados
                  /keys integrar <provider> → lanza BEE api_integrator
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Optional

from core.logger import logger

ROOT         = Path(__file__).resolve().parent.parent
MEMORY_DIR   = ROOT / "memory"
DISCOVERIES  = MEMORY_DIR / "key_discoveries.json"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

# ── Proveedores ya conocidos (para no re-reportar siempre los mismos) ─────────
KNOWN_PROVIDERS = {
    "cerebras":   {"url": "https://cloud.cerebras.ai", "free": "sin límite diario (rate limit 60rpm)", "models": ["llama3.1-8b", "gpt-oss-120b"], "card": False},
    "groq":       {"url": "https://console.groq.com", "free": "100K tokens/día", "models": ["llama-3.3-70b", "mixtral-8x7b"], "card": False},
    "gemini":     {"url": "https://aistudio.google.com", "free": "1500 req/día", "models": ["gemini-2.0-flash", "gemini-1.5-pro"], "card": False},
    "together":   {"url": "https://api.together.ai", "free": "$1 crédito gratis", "models": ["llama-3.3-70b", "mixtral"], "card": False},
    "openrouter": {"url": "https://openrouter.ai", "free": "$1 crédito sin tarjeta", "models": ["llama", "mistral", "gemma"], "card": False},
    "cohere":     {"url": "https://dashboard.cohere.com", "free": "5 req/min trial key", "models": ["command-r", "command-r-plus"], "card": False},
    "mistral":    {"url": "https://console.mistral.ai", "free": "1 req/seg free tier", "models": ["mistral-7b", "mistral-8x7b"], "card": False},
    "huggingface":{"url": "https://huggingface.co/settings/tokens", "free": "~500 req/día inference API", "models": ["zephyr", "falcon", "llama"], "card": False},
    "deepinfra":  {"url": "https://deepinfra.com/dash", "free": "$1.80 crédito gratis", "models": ["llama-3.3-70b", "qwen"], "card": False},
    "ai21":       {"url": "https://studio.ai21.com", "free": "$10 crédito 3 meses", "models": ["jamba-1.5", "j2-ultra"], "card": False},
    "fireworks":  {"url": "https://fireworks.ai/account/api-keys", "free": "$1 crédito sin tarjeta", "models": ["llama-3.1-70b", "mixtral"], "card": False},
    "novita":     {"url": "https://novita.ai", "free": "$0.50 crédito gratis", "models": ["llama-3.1", "qwen2"], "card": False},
    "sambanova":  {"url": "https://cloud.sambanova.ai", "free": "free tier beta, modelos grandes", "models": ["llama-3.1-405b", "llama-3.2-90b"], "card": False},
    "nvidia_nim": {"url": "https://build.nvidia.com", "free": "1000 créditos/mes gratis", "models": ["llama-3.1-70b", "mixtral", "phi-3"], "card": False},
    "cloudflare_ai": {"url": "https://dash.cloudflare.com", "free": "10K inferencias/día con Workers AI", "models": ["llama-3.1-8b", "mistral-7b"], "card": False},
    "google_vertex": {"url": "https://cloud.google.com/vertex-ai", "free": "free tier limitado + $300 crédito nuevo usuario", "models": ["gemini-pro", "palm"], "card": False},
    "perplexity": {"url": "https://www.perplexity.ai/settings/api", "free": "$5 crédito gratis al registrarse", "models": ["pplx-7b", "pplx-70b"], "card": False},
}

# Categorías de búsqueda activa para el key_hunter
SEARCH_QUERIES = [
    "free AI API key no credit card 2025",
    "free LLM API tier generous limits 2025",
    "free image generation API unlimited",
    "free speech to text API 2025",
    "free text to speech API unlimited",
    "free embedding API 2025",
    "free vision AI API 2025",
    "free code generation API 2025",
    "open source LLM API free hosted",
    "free AI API for developers 2025",
]


def load_discoveries() -> list[dict]:
    """Carga hallazgos guardados."""
    if DISCOVERIES.exists():
        try:
            return json.loads(DISCOVERIES.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save_discovery(provider: dict):
    """Guarda un nuevo proveedor descubierto."""
    discoveries = load_discoveries()
    # Evitar duplicados por nombre
    names = {d.get("name", "").lower() for d in discoveries}
    if provider.get("name", "").lower() not in names:
        provider["discovered_at"] = time.strftime("%Y-%m-%d %H:%M")
        provider["integrated"] = False
        discoveries.append(provider)
        DISCOVERIES.write_text(
            json.dumps(discoveries, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("KeyHunter: nuevo proveedor guardado — %s", provider.get("name"))


def get_pending_providers() -> list[dict]:
    """Proveedores descubiertos aún no integrados."""
    return [d for d in load_discoveries() if not d.get("integrated")]


def mark_integrated(name: str):
    """Marca un proveedor como integrado."""
    discoveries = load_discoveries()
    for d in discoveries:
        if d.get("name", "").lower() == name.lower():
            d["integrated"] = True
    DISCOVERIES.write_text(
        json.dumps(discoveries, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def format_known_providers_report() -> str:
    """
    Genera reporte de todos los proveedores conocidos para Álvaro.
    Incluye estado de integración actual.
    """
    try:
        from tools.llm_adapter import key_pool_status
        pools = key_pool_status()
    except Exception:
        pools = {}

    lines = ["🔑 PROVEEDORES DE IA — GUÍA COMPLETA\n"]
    lines.append("=" * 45 + "\n")

    integrated = []
    not_integrated = []

    for name, info in KNOWN_PROVIDERS.items():
        has_key = pools.get(name, {}).get("has", False)
        entry = {
            "name": name,
            "has_key": has_key,
            **info
        }
        if has_key:
            integrated.append(entry)
        else:
            not_integrated.append(entry)

    if integrated:
        lines.append(f"✅ INTEGRADOS ({len(integrated)} proveedores activos):\n")
        for p in integrated:
            keys_count = pools.get(p["name"], {}).get("keys", 0)
            lines.append(
                f"  • {p['name'].upper()} ({keys_count} keys)\n"
                f"    Free: {p['free']}\n"
                f"    Modelos: {', '.join(p['models'][:2])}\n"
            )

    if not_integrated:
        lines.append(f"\n🔓 DISPONIBLES GRATIS — NO INTEGRADOS ({len(not_integrated)}):\n")
        for p in not_integrated:
            card_txt = "sin tarjeta" if not p.get("card") else "requiere tarjeta"
            lines.append(
                f"  • {p['name'].upper()} ({card_txt})\n"
                f"    Registro: {p['url']}\n"
                f"    Free: {p['free']}\n"
                f"    Modelos: {', '.join(p['models'][:2])}\n"
            )

    pending = get_pending_providers()
    if pending:
        lines.append(f"\n🆕 DESCUBIERTOS POR BEES ({len(pending)} nuevos):\n")
        for p in pending:
            lines.append(
                f"  • {p.get('name', '?').upper()}\n"
                f"    {p.get('url', '')}\n"
                f"    {p.get('free_tier', 'ver detalles')}\n"
            )

    lines.append(
        "\n💡 Para añadir una key:\n"
        "   1. Regístrate en el proveedor\n"
        "   2. Añade la key en Replit Secrets (ej: OPENROUTER_API_KEY)\n"
        "   3. BEEA la detecta sola al reiniciar\n"
        "   4. Envía /keys integrar <proveedor> para verificar\n"
    )

    return "".join(lines)


def get_integration_instructions(provider_name: str) -> str:
    """Instrucciones específicas para integrar un proveedor."""
    p = KNOWN_PROVIDERS.get(provider_name.lower())
    if not p:
        return f"Proveedor '{provider_name}' no reconocido. Usa /keys para ver la lista completa."

    instructions = {
        "openrouter": (
            "OpenRouter: Registro → https://openrouter.ai/keys\n"
            "Nombre de variable: OPENROUTER_API_KEY\n"
            "Formato de key: sk-or-v1-XXXXXXXX\n"
            "Modelos: llama, mistral, gemma, claude (según créditos)"
        ),
        "cohere": (
            "Cohere: Registro → https://dashboard.cohere.com/api-keys\n"
            "Nombre de variable: COHERE_API_KEY\n"
            "Formato de key: XXXXXXXXXXXXXXXX (32 chars)\n"
            "Free tier: 5 req/min — ideal para análisis de texto"
        ),
        "mistral": (
            "Mistral AI: Registro → https://console.mistral.ai/api-keys\n"
            "Nombre de variable: MISTRAL_API_KEY\n"
            "Free tier: 1 req/seg, límite mensual de tokens"
        ),
        "huggingface": (
            "HuggingFace: Registro → https://huggingface.co/settings/tokens\n"
            "Nombre de variable: HUGGINGFACE_API_KEY o HF_TOKEN\n"
            "Tipo de token: 'Read' es suficiente para inference API"
        ),
        "deepinfra": (
            "DeepInfra: Registro → https://deepinfra.com/dash/api_keys\n"
            "Nombre de variable: DEEPINFRA_API_KEY\n"
            "$1.80 crédito gratis — compatible con OpenAI SDK"
        ),
        "sambanova": (
            "SambaNova: Registro → https://cloud.sambanova.ai\n"
            "Nombre de variable: SAMBANOVA_API_KEY\n"
            "DESTACA: acceso a Llama-3.1-405B GRATIS en beta"
        ),
        "nvidia_nim": (
            "NVIDIA NIM: Registro → https://build.nvidia.com\n"
            "Nombre de variable: NVIDIA_API_KEY\n"
            "1000 créditos/mes gratis — acceso a modelos premium"
        ),
        "cloudflare_ai": (
            "Cloudflare Workers AI: Registro → https://dash.cloudflare.com\n"
            "Nombre de variable: CLOUDFLARE_API_KEY y CLOUDFLARE_ACCOUNT_ID\n"
            "10K inferencias/día GRATIS — requiere cuenta Cloudflare"
        ),
    }

    specific = instructions.get(provider_name.lower(), "")
    base = (
        f"PROVEEDOR: {provider_name.upper()}\n"
        f"URL: {p['url']}\n"
        f"Free tier: {p['free']}\n"
        f"Modelos: {', '.join(p['models'])}\n"
        f"Tarjeta: {'Sí' if p.get('card') else 'No necesaria'}\n"
    )
    if specific:
        base += f"\nInstrucciones:\n{specific}"
    return base


class KeyHunterBee:
    """
    Controlador de la BEE key_hunter.
    Se integra con el sistema de BEE trainer para ejecutar búsquedas periódicas.
    """

    HUNT_INTERVAL = 86400  # 24 horas entre búsquedas automáticas
    _last_hunt: float = 0.0

    def __init__(self, notify_fn: Optional[Callable] = None):
        self._notify = notify_fn or (lambda msg: None)

    def should_hunt(self) -> bool:
        return time.time() - self._last_hunt > self.HUNT_INTERVAL

    def run_hunt(self) -> str:
        """
        Ejecuta una búsqueda de nuevas APIs gratuitas.
        Devuelve el reporte para enviar a Álvaro.
        """
        self._last_hunt = time.time()
        logger.info("KeyHunter: iniciando búsqueda de nuevas APIs gratuitas")

        try:
            from tools.websearch import search_web
            results = []
            for query in SEARCH_QUERIES[:3]:  # Solo 3 queries para no gastar cuota
                try:
                    found = search_web(query)
                    if found:
                        results.append({"query": query, "result": str(found)[:500]})
                except Exception as e:
                    logger.debug("KeyHunter: search falló para '%s': %s", query, e)

            # Analizar resultados con una BEE key_hunter
            if results:
                from tools.llm_adapter import generate_smart
                prompt = (
                    "Analiza estos resultados de búsqueda y extrae una lista de proveedores de IA "
                    "con free tier que NO estén en esta lista ya conocida: "
                    + ", ".join(KNOWN_PROVIDERS.keys()) +
                    "\n\nResultados de búsqueda:\n" +
                    json.dumps(results, ensure_ascii=False)[:2000] +
                    "\n\nFormato: una línea por proveedor: NOMBRE | URL | FREE_TIER | MODELOS"
                )
                analysis = generate_smart(
                    [{"role": "user", "content": prompt}],
                    task_type="bulk"
                )
                # Parsear y guardar nuevos descubrimientos
                for line in analysis.split("\n"):
                    if "|" in line:
                        parts = [p.strip() for p in line.split("|")]
                        if len(parts) >= 3:
                            save_discovery({
                                "name":      parts[0],
                                "url":       parts[1] if len(parts) > 1 else "",
                                "free_tier": parts[2] if len(parts) > 2 else "",
                                "models":    parts[3].split(",") if len(parts) > 3 else [],
                            })

        except Exception as e:
            logger.warning("KeyHunter: error en búsqueda: %s", e)

        report = format_known_providers_report()
        self._notify(f"KeyHunter completó búsqueda:\n{report[:1000]}")
        return report


# Instancia global
key_hunter = KeyHunterBee()
