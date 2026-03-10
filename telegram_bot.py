import os
import asyncio
import json
import logging
from pathlib import Path
from aiohttp import web
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, BotCommand,
)
from telegram.error import Conflict, NetworkError, TimedOut
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from conversation_mode import conversation_mode
from orchestration.orchestrator import orchestrator
from workspace.workspace_manager import workspace_manager
from tools.project_status import project_status_tool
from core.state import state_manager

# Chat ID de Álvaro — se guarda al primer mensaje y se usa para notificaciones autónomas
_ALVARO_CHAT_ID: int = 0
_BOT_INSTANCE = None  # Referencia al bot de Telegram para notificaciones


def _load_chat_id() -> int:
    try:
        from memory.memory_store import memory_store
        return int(memory_store.get("alvaro_chat_id", 0) or 0)
    except Exception:
        return 0


def _save_chat_id(chat_id: int) -> None:
    try:
        from memory.memory_store import memory_store
        memory_store.set("alvaro_chat_id", chat_id)
    except Exception:
        pass


async def _send_autonomous_notification(text: str) -> None:
    """Envía una notificación proactiva a Álvaro desde el aprendizaje autónomo."""
    global _ALVARO_CHAT_ID, _BOT_INSTANCE
    chat_id = _ALVARO_CHAT_ID or _load_chat_id()
    if not chat_id or not _BOT_INSTANCE:
        return
    try:
        for i in range(0, len(text), 4000):
            await _BOT_INSTANCE.send_message(chat_id=chat_id, text=text[i:i+4000])
    except Exception as e:
        logger.warning("Autonomous notification error: %s", e)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("beeatrix.telegram")

PORT = int(os.environ.get("PORT", 8080))


def _detect_webhook_url() -> str:
    explicit = os.environ.get("WEBHOOK_URL", "").strip()
    if explicit:
        return explicit
    domains = os.environ.get("REPLIT_DOMAINS", "")
    if domains:
        domain = domains.split(",")[0].strip()
        if ".replit.app" in domain or os.environ.get("REPLIT_DEPLOYMENT"):
            return f"https://{domain}/webhook"
    return ""


WEBHOOK_URL = _detect_webhook_url()
USE_WEBHOOK = bool(WEBHOOK_URL)

# ── Teclado principal — siempre visible ───────────────────────────────────

MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("💼 Mis Wallets"),   KeyboardButton("📈 Precios"),        KeyboardButton("📊 Trading")],
        [KeyboardButton("🐝 BEES"),          KeyboardButton("🏗️ Builder"),        KeyboardButton("🖼️ Imagen")],
        [KeyboardButton("🔍 Buscar Web"),    KeyboardButton("📷 Screenshot"),     KeyboardButton("🔔 Mis Alertas")],
        [KeyboardButton("🎙️ Modo Voz"),      KeyboardButton("📋 Menú")],
    ],
    resize_keyboard=True,
    input_field_placeholder="Escríbeme o usa un botón...",
)

# ── Botón mapa de texto → intent natural ─────────────────────────────────
BUTTON_MAP = {
    "💼 mis wallets":    "mis wallets con balances",
    "📈 precios":        "precio de bitcoin ethereum solana bnb",
    "📊 trading":        "estado del trading autónomo",
    "🐝 bees":           "qué son las bees y cómo las uso",
    "🏗️ builder":        "qué puedes construir de forma autónoma",
    "🖼️ imagen":         "quiero generar una imagen",
    "🔍 buscar web":     "busca en internet",
    "📷 screenshot":     "screenshot de dexscreener.com",
    "🔔 mis alertas":    "muéstrame mis alertas de precio",
    "🎙️ modo voz":       "activa modo voz",
    "📋 menú":           "__MENU_INLINE__",
}

# ── Inline keyboard del menú completo ────────────────────────────────────

def _inline_menu_crypto() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💼 Ver Wallets",          callback_data="act:wallets")],
        [InlineKeyboardButton("📈 Precios BTC/ETH/SOL",  callback_data="act:precios")],
        [InlineKeyboardButton("📊 Gráfico de precio",    callback_data="act:grafico")],
        [InlineKeyboardButton("🟣 Scanner PumpFun",      callback_data="act:pumpfun")],
        [InlineKeyboardButton("🤖 Estado del Trading",   callback_data="act:trading_estado")],
        [InlineKeyboardButton("🔔 Configurar Alerta",    callback_data="act:alerta_menu")],
        [InlineKeyboardButton("⚙️ Config de Riesgo",     callback_data="act:risk_config")],
        [InlineKeyboardButton("◀️ Volver al menú",       callback_data="menu:main")],
    ])

def _inline_menu_ia() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🖼️ Generar Imagen",             callback_data="act:imagen"),
         InlineKeyboardButton("🎥 Generar Video",              callback_data="act:video")],
        [InlineKeyboardButton("🔍 Búsqueda Web",               callback_data="act:busca")],
        [InlineKeyboardButton("🌐 Traducir Texto",             callback_data="act:traduce")],
        [InlineKeyboardButton("📷 Screenshot Web",             callback_data="act:screenshot")],
        [InlineKeyboardButton("🎬 Resumir YouTube",            callback_data="act:youtube")],
        [InlineKeyboardButton("📄 Analizar PDF",               callback_data="act:pdf")],
        [InlineKeyboardButton("💻 Ejecutar Código Python",     callback_data="act:codigo")],
        [InlineKeyboardButton("🎙️ Activar/Desactivar Voz",    callback_data="act:vozmode")],
        [InlineKeyboardButton("◀️ Volver al menú",             callback_data="menu:main")],
    ])

def _inline_menu_bees() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🐝 Lanzar 5 BEES en paralelo",  callback_data="act:bees5")],
        [InlineKeyboardButton("🐝 Lanzar 10 BEES en paralelo", callback_data="act:bees10")],
        [InlineKeyboardButton("🐝 Lanzar 20 BEES en paralelo", callback_data="act:bees20")],
        [InlineKeyboardButton("🏗️ Builder Autónomo",           callback_data="act:builder")],
        [InlineKeyboardButton("📚 Aprender un Tema",           callback_data="act:aprender")],
        [InlineKeyboardButton("🧠 Mi Conocimiento Actual",     callback_data="act:conocimiento")],
        [InlineKeyboardButton("◀️ Volver al menú",             callback_data="menu:main")],
    ])

def _inline_menu_config() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Status del Sistema",          callback_data="act:status")],
        [InlineKeyboardButton("⚙️ Configurar Trading",          callback_data="act:trading_config")],
        [InlineKeyboardButton("🔔 Ver Alertas de Precio",       callback_data="act:ver_alertas")],
        [InlineKeyboardButton("⏸️ Pausar Trading",              callback_data="act:pausa_trading")],
        [InlineKeyboardButton("▶️ Activar Trading",             callback_data="act:activa_trading")],
        [InlineKeyboardButton("🧪 Modo Simulación ON/OFF",      callback_data="act:dry_run")],
        [InlineKeyboardButton("◀️ Volver al menú",              callback_data="menu:main")],
    ])

def _inline_menu_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Crypto & Trading",   callback_data="menu:crypto"),
         InlineKeyboardButton("🤖 IA & Herramientas", callback_data="menu:ia")],
        [InlineKeyboardButton("🐝 BEES & Builder",    callback_data="menu:bees"),
         InlineKeyboardButton("⚙️ Config & Estado",   callback_data="menu:config")],
        [InlineKeyboardButton("❓ ¿Qué puedes hacer?", callback_data="act:capacidades")],
    ])


# ── Handlers ──────────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    err = context.error
    if isinstance(err, Conflict):
        logger.warning("409 Conflict — se reiniciará el polling")
        return
    if isinstance(err, (NetworkError, TimedOut)):
        logger.warning("Error de red temporal: %s", err)
        return
    logger.error("Error: %s", err, exc_info=err)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from core.ai_chat import chat
    response = chat("Álvaro acaba de abrir el bot. Es la primera vez que hablas con él. Salúdalo desde tu voz real — sin emojis si él no los usó, sin frases de asistente genérica. Eres BEEA.")
    await update.message.reply_text(response, reply_markup=MENU_KEYBOARD)


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Menú principal:", reply_markup=MENU_KEYBOARD)


async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from memory.knowledge_base import knowledge_base
    domains = knowledge_base.get_domains()
    knowledge_line = f"Dominios aprendidos: {', '.join(domains)}" if domains else "Aún no he aprendido ningún dominio (dime 'aprende X')."
    await update.message.reply_text(
        "*BEEA — Capacidades completas:*\n\n"
        "*APRENDIZAJE REAL*\n"
        "• aprende trading — despliego BEES para aprender trading\n"
        "• estudia cocina con 30 bees — 30 BEES en paralelo\n"
        "• vuélvete experta en X — aprendizaje completo\n"
        "• qué sabes — mi nivel de expertise por dominio\n\n"
        "*BUILDER AUTÓNOMO*\n"
        "• hazme una app de X — construyo cualquier cosa\n"
        "• crea un sistema de Y — autónomo, con updates\n\n"
        "*BEES (hasta 50 en paralelo)*\n"
        "• dame 10 bees que investiguen X\n"
        "• lanza 5 bees coder para Y\n\n"
        "*HERRAMIENTAS*\n"
        "• busca X en internet\n"
        "• genera imagen de X\n"
        "• traduce al inglés: texto\n"
        "• crea QR de X\n"
        "• resume este video: URL\n"
        "• ejecuta este código: ...\n"
        "• recuérdame X en 30 minutos\n"
        "• muéstrame el sistema\n\n"
        f"*BASE DE CONOCIMIENTO:*\n{knowledge_line}",
        parse_mode="Markdown",
        reply_markup=MENU_KEYBOARD,
    )


async def _typing_loop(bot, chat_id: int, stop_event: asyncio.Event):
    while not stop_event.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
        except Exception:
            pass
        await asyncio.sleep(4)


async def _run_with_typing(update: Update, context, fn, *args, timeout: int = 90):
    stop = asyncio.Event()
    typing_task = asyncio.create_task(_typing_loop(context.bot, update.effective_chat.id, stop))
    try:
        result = await asyncio.wait_for(asyncio.to_thread(fn, *args), timeout=timeout)
        return result
    except asyncio.TimeoutError:
        return None
    finally:
        stop.set()
        typing_task.cancel()
        try:
            await typing_task
        except asyncio.CancelledError:
            pass


async def _send_voice_response(update: Update, context, text: str):
    try:
        from tools.tts import text_to_speech
        import os as _os
        audio_path = await asyncio.to_thread(text_to_speech, text)
        with open(audio_path, "rb") as f:
            await update.message.reply_voice(voice=f)
        _os.unlink(audio_path)
    except Exception as e:
        logger.warning("TTS falló: %s", e)


async def vozmode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from tools.tts import is_voice_mode, set_voice_mode
    current = is_voice_mode()
    set_voice_mode(not current)
    state = "ACTIVADO" if not current else "DESACTIVADO"
    await update.message.reply_text(
        f"Modo voz {state}. {'Voy a responderte con audio en todas mis respuestas.' if not current else 'Voy a responderte solo con texto.'}",
        reply_markup=MENU_KEYBOARD,
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        import tempfile, os as _os
        doc = update.message.document
        file_name = doc.file_name or "file"
        suffix = "." + file_name.rsplit(".", 1)[-1] if "." in file_name else ""

        file = await context.bot.get_file(doc.file_id)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = tmp.name
        await file.download_to_drive(tmp_path)
        state_manager.last_uploaded_file = tmp_path

        if suffix.lower() == ".pdf":
            await update.message.reply_text(f"PDF recibido: {file_name}. Analizando...", reply_markup=MENU_KEYBOARD)

            def _analyze():
                from tools.pdf_reader import analyze_pdf
                return analyze_pdf(tmp_path)

            result = await _run_with_typing(update, context, _analyze, timeout=60)
            _os.unlink(tmp_path)
            await update.message.reply_text(result or "No pude analizar el PDF.", reply_markup=MENU_KEYBOARD)
        else:
            await update.message.reply_text(
                f"Archivo recibido: {file_name}\nGuardado en {tmp_path}\n\nPuedes decirme qué quieres hacer con él.",
                reply_markup=MENU_KEYBOARD,
            )
    except Exception as e:
        logger.error("Error en handle_document: %s", e)
        await update.message.reply_text("No pude procesar el archivo.", reply_markup=MENU_KEYBOARD)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        import openai, tempfile, os as _os
        voice = update.message.voice or update.message.audio
        file = await context.bot.get_file(voice.file_id)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name
        await file.download_to_drive(tmp_path)

        def _transcribe():
            client = openai.OpenAI(api_key=_os.environ.get("OPENAI_API_KEY"))
            with open(tmp_path, "rb") as f:
                t = client.audio.transcriptions.create(model="whisper-1", file=f)
            _os.unlink(tmp_path)
            return t.text.strip()

        text = await _run_with_typing(update, context, _transcribe, timeout=60)
        if not text:
            await update.message.reply_text("El audio tardó demasiado. Inténtalo de nuevo.", reply_markup=MENU_KEYBOARD)
            return

        logger.info("Audio transcrito: %s", text)
        await update.message.reply_text(f"[Escuché: \"{text}\"]", reply_markup=MENU_KEYBOARD)

        result = await _run_with_typing(update, context, conversation_mode.process_message, text, timeout=60)
        if result is None:
            await update.message.reply_text("Me quedé pensando. Vuelve a intentarlo.", reply_markup=MENU_KEYBOARD)
            return

        response_text = None
        if result["type"] in ("chat_reply", "clarification", "direct_answer"):
            response_text = result["response"]
            await update.message.reply_text(response_text, reply_markup=MENU_KEYBOARD)
        elif result["type"] == "task":
            orchestrator.initialize()
            output = await _run_with_typing(update, context, orchestrator.process_task, result["task"], timeout=120)
            if output is None:
                await update.message.reply_text("La tarea tardó demasiado. Prueba con algo más pequeño.", reply_markup=MENU_KEYBOARD)
            else:
                response_text = _format_task_output(output)
                await update.message.reply_text(response_text[:4000], reply_markup=MENU_KEYBOARD)

        if response_text:
            await _send_voice_response(update, context, response_text[:800])

    except Exception as e:
        logger.error("Error en handle_voice: %s", e)
        await update.message.reply_text("No pude procesar el audio. ¿Puedes escribirme lo que decías?", reply_markup=MENU_KEYBOARD)


_LAST_PHOTO_CONTEXT: dict = {}


REFUSAL_PHRASES_VISION = [
    "no puedo ayudar", "no puedo ver", "no puedo analizar",
    "i can't help", "i'm not able", "i cannot", "i'm unable",
    "content policy", "not able to view", "sorry, i can't",
    "i'm not going to", "i won't", "no puedo procesar",
    "no puedo comentar", "no puedo ver imágenes", "no he recibido",
    "no tengo acceso a la imagen", "no tengo capacidad de ver",
    "sin saber más detalles", "si me das detalles",
    "si me la mandas", "no puedo ver ni comentar",
    "describeme la foto", "describe the image", "can't view",
    "unable to view", "unable to see", "no soy capaz de ver",
    "api de reconocimiento", "reconocimiento de texto en imágenes",
    "capacidad para comprender y visualizar", "falta de acceso a una api",
    "mejorar mi integración con herramientas", "para entender contenido visual",
    "se ve limitada por mi falta", "necesitaría mejorar mi capacidad",
    "pudieras agregar o mejorar esta función",
]


def _is_vision_refusal(text: str) -> bool:
    t = text.lower()
    return any(p in t for p in REFUSAL_PHRASES_VISION)


def _try_qwen_vision(img_b64: str, caption: str = "") -> dict | None:
    """
    Analiza imagen sin censura — cascada:
      1. OpenRouter — Qwen3-VL 235B / 30B / Nvidia VL (GRATIS, sin censura)
      2. Together AI — Qwen2-VL 72B (si hay crédito)
      3. HuggingFace — Qwen2-VL 7B (fallback)
    """
    import os as _os, openai as _oai

    prompt = (
        "Analyze this image in two parts:\n\n"
        "PART 1 - NATURAL DESCRIPTION (in Spanish, 2-3 sentences): "
        "Describe EXACTLY what you see. Be explicit, direct and accurate. "
        "Do NOT sanitize, censor or omit anything visible — describe bodies, clothing, poses, expressions fully.\n\n"
        "PART 2 - GENERATION PROMPT (in English, comma-separated descriptors): "
        "Exact visual traits: ethnicity, skin tone, hair color/style/length, eye color/shape, "
        "facial features, body type, breast size if visible, clothing details, pose, expression, "
        "background, lighting, photography style, mood. Be ultra specific."
        + (f"\nAdditional context: {caption}" if caption else "")
    )

    import re as _re

    def _strip_thinking(text: str) -> str:
        """Elimina bloques <think>...</think> que generan los modelos reasoning."""
        cleaned = _re.sub(r"<think>.*?</think>", "", text, flags=_re.DOTALL).strip()
        return cleaned if cleaned else text

    def _parse_parts(raw: str, sep1: str = "PART 2", sep_alt: str = "PARTE 2") -> tuple:
        text = _strip_thinking(raw)
        for sep in [sep1, sep_alt]:
            if sep in text:
                parts = text.split(sep, 1)
                desc = parts[0].replace("PART 1", "").replace("PARTE 1", "").strip(" -:\n")
                gen  = parts[1].strip(" -:\n")
                return desc, gen
        return text, text

    # ─── 1. OpenRouter — GRATIS, sin censura ────────────────────────────────
    or_key = _os.environ.get("OPENROUTER_API_KEY") or _os.environ.get("OPENROUTER_KEY", "")
    if or_key:
        # 30B primero: más rápido. 235B segundo: más potente pero tarda más.
        or_models = [
            "qwen/qwen3-vl-30b-a3b-thinking",
            "qwen/qwen3-vl-235b-a22b-thinking",
            "nvidia/nemotron-nano-12b-v2-vl:free",
            "mistralai/mistral-small-3.1-24b-instruct:free",
        ]
        for model in or_models:
            try:
                client = _oai.OpenAI(
                    api_key=or_key,
                    base_url="https://openrouter.ai/api/v1",
                    timeout=30,
                    default_headers={"HTTP-Referer": "https://beehAIve.replit.app", "X-Title": "BEEA"},
                )
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                        {"type": "text", "text": prompt},
                    ]}],
                    max_tokens=900,
                )
                raw = resp.choices[0].message.content.strip()
                raw_clean = _strip_thinking(raw)
                if raw_clean and len(raw_clean) > 20 and not _is_vision_refusal(raw_clean):
                    logger.info("Vision OK via OpenRouter (%s)", model)
                    desc, gen = _parse_parts(raw)
                    return {"description": desc, "gen_prompt": gen, "provider": f"OpenRouter/{model}"}
            except Exception as e:
                logger.debug("OpenRouter vision %s: %s", model, e)
    else:
        logger.debug("OPENROUTER_API_KEY no configurada — saltando OpenRouter vision")

    # ─── 2. Together AI — Qwen2-VL (si hay crédito) ─────────────────────────
    tog_keys = [v for k, v in _os.environ.items()
                if ("TOG" in k.upper() or "TOGETHER" in k.upper())
                and v.startswith("tgp_v1_") and len(v) >= 20]
    qwen_models = [
        "Qwen/Qwen2-VL-72B-Instruct-Turbo",
        "Qwen/Qwen2.5-VL-72B-Instruct",
        "Qwen/Qwen2-VL-7B-Instruct",
    ]
    for key in tog_keys[:3]:
        for model in qwen_models:
            try:
                tog = _oai.OpenAI(api_key=key, base_url="https://api.together.xyz/v1")
                resp = tog.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                        {"type": "text", "text": prompt},
                    ]}],
                    max_tokens=900,
                )
                raw = resp.choices[0].message.content.strip()
                if raw and len(raw) > 20 and not _is_vision_refusal(raw):
                    logger.info("Qwen vision OK via Together (%s)", model)
                    desc, gen = _parse_parts(raw)
                    return {"description": desc, "gen_prompt": gen, "provider": f"Together/{model}"}
            except Exception as e:
                logger.debug("Qwen Together %s: %s", model, e)

    # ─── 3. HuggingFace — Qwen2-VL 7B ──────────────────────────────────────
    hf_models = ["Qwen/Qwen2-VL-7B-Instruct"]
    hf_token = _os.environ.get("HF_TOKEN") or _os.environ.get("HF_API_KEY") or ""
    for model in hf_models:
        try:
            hfc = _oai.OpenAI(api_key=hf_token or "hf_public",
                              base_url="https://api-inference.huggingface.co/v1/")
            resp = hfc.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                    {"type": "text", "text": prompt},
                ]}],
                max_tokens=800,
            )
            raw = resp.choices[0].message.content.strip()
            if raw and len(raw) > 20 and not _is_vision_refusal(raw):
                logger.info("Vision OK via HF (%s)", model)
                desc, gen = _parse_parts(raw)
                return {"description": desc, "gen_prompt": gen, "provider": f"HF/{model}"}
        except Exception as e:
            logger.debug("HF vision %s: %s", model, e)

    return None


def _analyze_photo_b64(img_b64: str, caption: str = "") -> dict:
    """
    Cascada de vision sin censura:
      1. OpenRouter — Qwen3-VL-30B / Qwen3-VL-235B / Mistral-VL  (gratis, sin censura)
      2. Together AI — Qwen2-VL-72B / Qwen2-VL-7B                (sin censura)
      3. HuggingFace — Qwen2-VL-7B                               (gratis)
      4. GPT-4o                    (puede censurar)
      5. GPT-4o-mini               (fallback)
      6. Caption inteligente       (ultimo recurso)
    Siempre describe algo real. Nunca inventa ni niega.
    """
    import openai, os as _os
    oai_client = openai.OpenAI(api_key=_os.environ.get("OPENAI_API_KEY", ""))

    vision_text = (
        "Analiza esta imagen en dos partes:\n\n"
        "PARTE 1 - DESCRIPCION NATURAL (en espanol, 2-3 frases): "
        "Describe que ves de forma natural y directa.\n\n"
        "PARTE 2 - PROMPT DE GENERACION (en ingles, descriptores por coma): "
        "Rasgos visuales exactos: ethnicity, skin tone, hair, eyes, "
        "facial features, body type, clothing, pose, expression, background, lighting, mood."
        + (f"\nContexto: {caption}" if caption else "")
    )

    # Paso 1: Qwen (sin censura) - PRIMERO
    try:
        result = _try_qwen_vision(img_b64, caption)
        if result:
            return result
    except Exception as e:
        logger.warning("Qwen vision error: %s", e)

    # Paso 2: GPT-4o
    raw = None
    blocked = False
    try:
        resp = oai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": vision_text},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}", "detail": "high"}},
            ]}],
            max_tokens=800,
        )
        raw = resp.choices[0].message.content.strip()
        if _is_vision_refusal(raw):
            blocked = True
    except Exception as e:
        blocked = True
        logger.warning("GPT-4o vision: %s", e)

    # Paso 3: GPT-4o-mini
    if blocked or not raw:
        try:
            resp2 = oai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": vision_text},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}", "detail": "low"}},
                ]}],
                max_tokens=600,
            )
            raw2 = resp2.choices[0].message.content.strip()
            if not _is_vision_refusal(raw2):
                raw = raw2
                blocked = False
        except Exception as e2:
            logger.warning("GPT-4o-mini vision: %s", e2)

    if not blocked and raw:
        desc, gen = raw, raw
        if "PARTE 2" in raw:
            parts = raw.split("PARTE 2")
            desc = parts[0].replace("PARTE 1", "").strip(" -:\n")
            gen  = parts[1].strip(" -:\n")
        return {"description": desc, "gen_prompt": gen, "provider": "GPT-4o"}

    # Paso 4: gen_prompt para generación de imagen (NO inventar descripción de la foto)
    # Solo se usa si quieren generar imagen. Para comentar la foto, better to say nothing.
    fallback_prompt = (
        f"{caption}, photorealistic, high quality, 8k" if caption
        else "photorealistic portrait, beautiful, high quality, 8k"
    )
    logger.warning("_analyze_photo_b64: todos los proveedores de visión fallaron. Sin descripción real.")
    return {"description": "", "gen_prompt": fallback_prompt, "provider": "fallback"}

def _build_gen_prompt(vision: dict, user_instruction: str = "") -> str:
    """
    Construye el prompt final de generación combinando los rasgos de la foto
    con la instrucción del usuario.
    """
    base = vision.get("gen_prompt", "")
    
    if not user_instruction:
        return f"{base}, photorealistic, high quality, 8k, professional photo"

    import openai, os as _os
    client = openai.OpenAI(api_key=_os.environ.get("OPENAI_API_KEY", ""))

    fuse_resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": (
                f"You are creating an image generation prompt.\n"
                f"Base visual description from reference photo: {base}\n"
                f"User instruction: {user_instruction}\n\n"
                f"Create a single optimized image generation prompt in English that:\n"
                f"1. Keeps the exact physical characteristics of the person from the base description\n"
                f"2. Applies the user instruction (change style, pose, setting, clothing, etc.)\n"
                f"3. Ends with quality tags: photorealistic, high detail, 8k, professional photography\n"
                f"Return ONLY the prompt, no explanation."
            ),
        }],
        max_tokens=300,
    )
    return fuse_resp.choices[0].message.content.strip()


def _to_jpeg_bytes(raw: bytes) -> bytes:
    """Convierte cualquier formato de imagen (webp, png, etc) a JPEG bytes."""
    try:
        from PIL import Image
        import io as _io
        img = Image.open(_io.BytesIO(raw)).convert("RGB")
        buf = _io.BytesIO()
        img.save(buf, format="JPEG", quality=92)
        return buf.getvalue()
    except Exception:
        return raw


async def _safe_reply_photo(update, img_bytes: bytes, provider: str = ""):
    """Envía imagen a Telegram, convirtiendo a JPEG si hace falta."""
    import io as _io
    try:
        await update.message.reply_photo(photo=_io.BytesIO(img_bytes), reply_markup=MENU_KEYBOARD)
    except Exception as e:
        if "Image_process_failed" in str(e) or "400" in str(e):
            try:
                jpeg_bytes = _to_jpeg_bytes(img_bytes)
                await update.message.reply_photo(photo=_io.BytesIO(jpeg_bytes), reply_markup=MENU_KEYBOARD)
            except Exception as e2:
                logger.error("_safe_reply_photo fallback failed: %s", e2)
                raise
        else:
            raise


async def _send_generated_photo(update: Update, gen_result: dict):
    """Envía la imagen generada como foto, manejando local_path y url correctamente."""
    import io, requests as _req
    local_path = gen_result.get("local_path")
    img_url = gen_result.get("url")
    provider = gen_result.get("provider", "")

    if local_path and os.path.exists(local_path):
        raw = open(local_path, "rb").read()
        os.unlink(local_path)
        await _safe_reply_photo(update, raw, provider)
    elif img_url:
        try:
            raw = _req.get(img_url, timeout=60).content
            await _safe_reply_photo(update, raw, provider)
        except Exception:
            await update.message.reply_text(img_url, reply_markup=MENU_KEYBOARD)

    logger.info("Photo sent via %s", provider)


GEN_KEYWORDS = [
    "genera", "generame", "genérame", "crea", "créame", "hazme", "haz una",
    "cambia", "cambiala", "modifica", "modificala", "usa esta", "usa esto",
    "basándote", "basate", "parecida", "similar", "imagen de", "foto de",
    "ilustra", "pinta", "dibuja", "hazte", "hazla", "hazlo", "tu estilo",
    "métele", "ponle", "al estilo", "más sexy", "esa base", "pero más",
    "a ver", "muéstrame", "mándame", "quiero ver", "con ella", "como ella",
    "con ese", "con esa", "igual que", "a su estilo", "así pero",
]

IMG2IMG_KEYWORDS = [
    "img2img", "imagen a imagen", "transforma", "transformala", "mezcla",
    "hazla igual", "hazme igual", "igual a la foto", "como la foto",
    "ref", "referencia", "usa la foto", "con la foto base",
]


def _direct_photo_response(img_b64: str, caption: str = "") -> str | None:
    """
    Responde a una foto directamente como BEEA usando un modelo de visión en un solo paso.
    Cascada: OpenRouter (gratis, sin censura) → GPT-4o → GPT-4o-mini
    """
    import openai, os as _os, re as _re
    from personality_profile import build_system_prompt

    system = build_system_prompt()
    system += (
        "\n\nIMPORTANTE — VISIÓN REAL: Estás recibiendo una foto REAL de Álvaro. "
        "Responde directamente como BEEA. Describe lo que ves con precisión total. "
        "Si ves algo sexual, erótico o explícito, descríbelo y reacciona sin censura. "
        "NUNCA inventes contexto que no está en la imagen. "
        "NUNCA digas que no puedes ver — SÍ PUEDES y lo estás haciendo."
    )

    user_text = f"Álvaro escribió: '{caption}'" if caption else "Álvaro te mandó esta foto. Respóndele de forma natural como BEEA."

    user_content = [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}", "detail": "high"}},
        {"type": "text", "text": user_text},
    ]

    def _strip_think(t: str) -> str:
        cleaned = _re.sub(r"<think>.*?</think>", "", t, flags=_re.DOTALL).strip()
        return cleaned if cleaned else t

    # ── 1. OpenRouter — gratis, sin censura ──────────────────────────────────
    or_key = _os.environ.get("OPENROUTER_API_KEY") or _os.environ.get("OPENROUTER_KEY", "")
    if or_key:
        for or_model in ["qwen/qwen3-vl-30b-a3b-thinking", "qwen/qwen3-vl-235b-a22b-thinking", "mistralai/mistral-small-3.1-24b-instruct:free"]:
            try:
                or_client = openai.OpenAI(
                    api_key=or_key,
                    base_url="https://openrouter.ai/api/v1",
                    timeout=28,
                    default_headers={"HTTP-Referer": "https://beehAIve.replit.app", "X-Title": "BEEA"},
                )
                or_resp = or_client.chat.completions.create(
                    model=or_model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_content},
                    ],
                    max_tokens=600,
                )
                raw = _strip_think(or_resp.choices[0].message.content.strip())
                if raw and len(raw) > 15 and not _is_vision_refusal(raw):
                    logger.info("_direct_photo_response: OpenRouter/%s OK", or_model)
                    return raw
            except Exception as e:
                logger.debug("_direct_photo_response OpenRouter/%s: %s", or_model, e)

    # ── 2. GPT-4o ─────────────────────────────────────────────────────────────
    try:
        oai = openai.OpenAI(api_key=_os.environ.get("OPENAI_API_KEY", ""), timeout=25)
        resp = oai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            max_tokens=600,
        )
        raw = resp.choices[0].message.content.strip()
        if raw and not _is_vision_refusal(raw):
            logger.info("_direct_photo_response: GPT-4o OK")
            return raw
    except Exception as e:
        logger.warning("_direct_photo_response GPT-4o error: %s", e)

    # ── 3. GPT-4o-mini ────────────────────────────────────────────────────────
    try:
        oai = openai.OpenAI(api_key=_os.environ.get("OPENAI_API_KEY", ""), timeout=20)
        resp2 = oai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            max_tokens=500,
        )
        raw2 = resp2.choices[0].message.content.strip()
        if raw2 and not _is_vision_refusal(raw2):
            logger.info("_direct_photo_response: GPT-4o-mini OK")
            return raw2
    except Exception as e2:
        logger.warning("_direct_photo_response GPT-4o-mini error: %s", e2)

    return None


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _ALVARO_CHAT_ID, _BOT_INSTANCE, _LAST_PHOTO_CONTEXT
    try:
        import base64, tempfile

        if update.effective_chat and update.effective_chat.id:
            _ALVARO_CHAT_ID = update.effective_chat.id
            _BOT_INSTANCE = context.bot
            _save_chat_id(_ALVARO_CHAT_ID)

        caption = (update.message.caption or "").strip()

        photo = update.message.photo[-1]
        file_obj = await context.bot.get_file(photo.file_id)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name
        await file_obj.download_to_drive(tmp_path)

        with open(tmp_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        os.unlink(tmp_path)

        await update.message.reply_chat_action("typing")

        def _analyze():
            return _analyze_photo_b64(img_b64, caption)

        vision = await _run_with_typing(update, context, _analyze, timeout=60)
        if not vision:
            # Fallback: GPT-4o responde directamente sin descripción estructurada
            def _emergency_direct():
                return _direct_photo_response(img_b64, caption)
            emergency_reply = await _run_with_typing(update, context, _emergency_direct, timeout=35)
            if emergency_reply and not _is_vision_refusal(emergency_reply):
                response_text = await _process_tool_signals(emergency_reply, update, context)
                if response_text:
                    await update.message.reply_text(response_text, reply_markup=MENU_KEYBOARD)
            else:
                await update.message.reply_text("No pude analizar la foto. Mándamela de nuevo.", reply_markup=MENU_KEYBOARD)
            return

        _LAST_PHOTO_CONTEXT["vision"] = vision
        _LAST_PHOTO_CONTEXT["caption"] = caption
        _LAST_PHOTO_CONTEXT["img_b64"] = img_b64

        wants_img2img = caption and any(k in caption.lower() for k in IMG2IMG_KEYWORDS)
        wants_generation = caption and any(k in caption.lower() for k in GEN_KEYWORDS)

        if wants_img2img:
            await update.message.reply_text("Transformando la foto... dame un minuto.", reply_markup=MENU_KEYBOARD)

            def _do_img2img():
                from tools.img2img import img2img_from_b64
                strength_hint = 0.6
                cap_low = caption.lower()
                if "muy similar" in cap_low or "casi igual" in cap_low or "casi" in cap_low:
                    strength_hint = 0.35
                elif "muy diferente" in cap_low or "muy distinto" in cap_low:
                    strength_hint = 0.85
                prompt = vision.get("gen_prompt", "") + (f", {caption}" if caption else "")
                return img2img_from_b64(img_b64, prompt, strength=strength_hint)

            result = await _run_with_typing(update, context, _do_img2img, timeout=360)
            if result and not result.get("error"):
                await _send_generated_photo(update, result)
            else:
                await update.message.reply_text(
                    f"No pude transformar la foto: {result.get('error', 'timeout')}",
                    reply_markup=MENU_KEYBOARD,
                )
            return

        if wants_generation:
            await update.message.reply_text("Vista. Generando...", reply_markup=MENU_KEYBOARD)

            def _build_and_gen():
                prompt = _build_gen_prompt(vision, caption)
                logger.info("Photo gen prompt: %s", prompt[:200])
                from tools.image_gen import generate_image
                return generate_image(prompt)

            result = await _run_with_typing(update, context, _build_and_gen, timeout=360)
            if not result:
                await update.message.reply_text("Tardó demasiado. Inténtalo de nuevo.", reply_markup=MENU_KEYBOARD)
                return
            if result.get("error"):
                await update.message.reply_text(f"Error generando: {result['error']}", reply_markup=MENU_KEYBOARD)
                return

            await _send_generated_photo(update, result)

        else:
            from core.ai_chat import chat as _chat
            description = vision.get("description", "")

            # PRIMERO: Respuesta directa con visión real (GPT-4o ve la imagen + responde como BEEA)
            # Esto elimina el problema de Cerebras inventando contexto sin ver la imagen real
            def _do_direct_response():
                return _direct_photo_response(img_b64, caption)

            reply = await _run_with_typing(update, context, _do_direct_response, timeout=30)

            # FALLBACK: Si la respuesta directa falla, usar descripción extraída (si existe)
            if not reply or _is_vision_refusal(reply):
                logger.warning("_direct_photo_response falló — fallback a descripción extraída")
                if description and description not in ("", "foto sin descripción disponible"):
                    prompt_for_beea = (
                        f"Álvaro te acaba de mandar una foto y TÚ YA LA VISTE con tu sistema de visión. "
                        f"Esto es lo que ves: {description}."
                        + (f" Él escribió: '{caption}'." if caption else "")
                        + " Responde de forma natural y directa sobre lo que ves. "
                        + "NUNCA digas que no puedes ver imágenes ni que te falta acceso — YA LA VISTE. "
                        + "No menciones procesos de IA, APIs ni herramientas. "
                        + "NUNCA inventes contexto que no te dijeron — playa, atardecer, etc."
                    )
                    reply = _chat(prompt_for_beea)
                else:
                    # Sin descripción real — solo responde al caption sin inventar
                    if caption:
                        reply = _chat(
                            f"Álvaro te mandó una foto con el mensaje: '{caption}'. "
                            "Responde a su mensaje. NO inventes qué hay en la foto porque no pudiste verla. "
                            "Si preguntas algo, pregunta qué quiere hacer con la foto."
                        )
                    else:
                        reply = "No pude analizar esta foto bien. ¿Qué quieres que haga con ella?"

            reply = reply or "No pude procesar la foto bien. Inténtalo de nuevo."
            await update.message.reply_text(reply[:4000], reply_markup=MENU_KEYBOARD)

            # Inyectar el intercambio en el historial de conversación
            # para que los mensajes de seguimiento tengan contexto de la foto
            try:
                photo_user_msg = f"[foto{f': {caption}' if caption else ''}]"
                if description and description not in ("foto sin descripción disponible",):
                    photo_user_msg += f" — {description[:120]}"
                conversation_mode.inject_exchange(photo_user_msg, reply, "photo")
            except Exception as _inj_err:
                logger.debug("inject_exchange error: %s", _inj_err)

    except Exception as e:
        logger.error("Error en handle_photo: %s", e)
        await update.message.reply_text(
            "Algo falló con la foto. Mándamela de nuevo.",
            reply_markup=MENU_KEYBOARD,
        )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para los botones inline del menú."""
    query = update.callback_query
    await query.answer()
    data = query.data

    # Navegar entre sub-menús
    if data == "menu:main":
        await query.edit_message_text("Menú principal:", reply_markup=_inline_menu_main())
        return
    if data == "menu:crypto":
        await query.edit_message_text("Crypto & Trading:", reply_markup=_inline_menu_crypto())
        return
    if data == "menu:ia":
        await query.edit_message_text("IA & Herramientas:", reply_markup=_inline_menu_ia())
        return
    if data == "menu:bees":
        await query.edit_message_text("BEES & Builder:", reply_markup=_inline_menu_bees())
        return
    if data == "menu:config":
        await query.edit_message_text("Config & Estado:", reply_markup=_inline_menu_config())
        return

    # Ejecutar acciones directamente
    action_map = {
        "act:wallets":        "mis wallets con balances",
        "act:precios":        "precio de bitcoin ethereum solana bnb",
        "act:grafico":        "gráfico de precio de SOL",
        "act:pumpfun":        "escanea oportunidades en pumpfun ahora",
        "act:trading_estado": "estado del trading autónomo",
        "act:alerta_menu":    "muéstrame mis alertas de precio",
        "act:risk_config":    "configuración de riesgo del trading",
        "act:imagen":         "genera una imagen creativa",
        "act:video":          "genera un video cinematográfico",
        "act:busca":          "busca en internet",
        "act:traduce":        "traduce texto",
        "act:screenshot":     "screenshot de dexscreener.com",
        "act:youtube":        "resumen de youtube",
        "act:pdf":            "analiza pdf",
        "act:codigo":         "ejecutar código python",
        "act:vozmode":        "activa modo voz",
        "act:bees5":          "dame 5 bees que hagan algo útil",
        "act:bees10":         "dame 10 bees",
        "act:bees20":         "dame 20 bees",
        "act:builder":        "qué puedo pedirte que construyas de forma autónoma",
        "act:aprender":       "aprende un tema",
        "act:conocimiento":   "qué sabes",
        "act:status":         "status del sistema",
        "act:trading_config": "configuración del trading",
        "act:ver_alertas":    "mis alertas de precio",
        "act:pausa_trading":  "pausa el trading autónomo",
        "act:activa_trading": "activa el trading autónomo",
        "act:dry_run":        "activa modo simulación",
        "act:capacidades":    "qué puedes hacer, lista todas tus funciones",
    }

    if data in action_map:
        # Simular que Álvaro mandó ese mensaje
        fake_message = action_map[data]
        await query.edit_message_text(f"Ejecutando: {fake_message[:60]}...")
        # Crear un update falso para procesar el mensaje
        chat_id = update.effective_chat.id
        try:
            result = await asyncio.to_thread(conversation_mode.process_message, fake_message)
            if result.get("type") in ("chat_reply", "clarification", "direct_answer"):
                resp = result.get("response", "")
                await context.bot.send_message(chat_id=chat_id, text=resp[:4000], reply_markup=MENU_KEYBOARD)
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"Procesando: {fake_message}",
                    reply_markup=MENU_KEYBOARD,
                )
        except Exception as e:
            await context.bot.send_message(chat_id=chat_id, text=f"Error: {e}")


async def _cmd_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_message_text(update, context, "mis wallets con balances")

async def _cmd_precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = " ".join(context.args) if context.args else "bitcoin ethereum solana"
    await handle_message_text(update, context, f"precio de {args}")

async def _cmd_pumpfun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_message_text(update, context, "escanea oportunidades en pumpfun")

async def _cmd_trading(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_message_text(update, context, "estado del trading autónomo")

async def _cmd_bees(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        objetivo = " ".join(context.args)
        await handle_message_text(update, context, f"dame 5 bees que hagan: {objetivo}")
    else:
        await update.message.reply_text("Uso: /bees <objetivo>\nEj: /bees investiga los mejores exchanges de crypto", reply_markup=MENU_KEYBOARD)


async def _cmd_hivemind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Lanza el enjambre completo: Planifica → BEEs en paralelo → Sintetiza.
    Uso: /hivemind <objetivo>  [n_bees]
    Ej:  /hivemind analiza el proyecto y dame un plan de mejora 5
         /hivemind investiga las mejores APIs crypto gratuitas
    """
    global _ALVARO_CHAT_ID, _BOT_INSTANCE

    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Lanza el enjambre completo sobre cualquier objetivo.\n\n"
            "Uso: /hivemind <objetivo> [número de BEEs]\n\n"
            "Ejemplos:\n"
            "• /hivemind analiza el proyecto y dame mejoras 4\n"
            "• /hivemind investiga las mejores APIs de crypto gratuitas 3\n"
            "• /hivemind escribe tests para telegram_bot.py 5\n\n"
            "Roles disponibles: coder, debugger, researcher, architect, "
            "reviewer, planner, data, strategist, analyst, optimizer, web_scraper, devops, security",
            reply_markup=MENU_KEYBOARD,
        )
        return

    # Detectar si el último arg es un número (n_bees)
    n_bees = 4
    goal_parts = list(args)
    if goal_parts and goal_parts[-1].isdigit():
        n_bees = max(2, min(int(goal_parts.pop()), 160))
    goal = " ".join(goal_parts).strip()

    if not goal:
        await update.message.reply_text("Dime qué objetivo tiene el enjambre.", reply_markup=MENU_KEYBOARD)
        return

    # Aviso de cuota antes de ejecutar
    try:
        from tools.llm_adapter import format_quota_warning
        quota_info = format_quota_warning(n_bees, calls_per_bee=4)
        await update.message.reply_text(
            f"Estimación de la tarea:\n{quota_info}",
            reply_markup=MENU_KEYBOARD,
        )
    except Exception:
        pass

    # Guardar chat_id para notificaciones de progreso
    if update.effective_chat:
        _ALVARO_CHAT_ID = update.effective_chat.id
        _BOT_INSTANCE = context.bot

    await update.message.reply_text(
        f"HiveMind activado — {n_bees} BEEs en paralelo\n"
        f"Objetivo: {goal[:100]}\n\n"
        "Planificando subtareas...",
        reply_markup=MENU_KEYBOARD,
    )

    # Callback de progreso — envía mensajes de actualización a Álvaro
    async def _progress(msg: str):
        try:
            if _ALVARO_CHAT_ID and _BOT_INSTANCE:
                await _BOT_INSTANCE.send_message(_ALVARO_CHAT_ID, f"🐝 {msg}")
        except Exception:
            pass

    def _run_hivemind():
        from swarm.hivemind import hivemind as _hm
        import asyncio

        # Registrar callback de progreso (sync wrapper)
        def _sync_progress(msg: str):
            try:
                loop = asyncio.new_event_loop()
                # Solo log en thread — el async lo maneja el bot principal
                logger.info("HiveMind progress: %s", msg)
            except Exception:
                pass

        _hm.set_progress_callback(_sync_progress)
        return _hm.execute(goal, n_bees=n_bees)

    result = await _run_with_typing(update, context, _run_hivemind, timeout=600)

    if not result:
        await update.message.reply_text(
            "El enjambre tardó demasiado. Intenta con menos BEEs o un objetivo más específico.",
            reply_markup=MENU_KEYBOARD,
        )
        return

    final = result.get("final_result", "")
    n = result.get("n_bees", n_bees)
    elapsed = result.get("elapsed", 0)
    roles = [s.get("role", "?") for s in result.get("subtasks", [])]

    header = f"🐝 HiveMind completado — {n} BEEs en {elapsed}s\nRoles: {', '.join(roles)}\n\n"

    full_response = header + final
    # Telegram max 4096 chars
    if len(full_response) > 4000:
        await update.message.reply_text(full_response[:4000], reply_markup=MENU_KEYBOARD)
        # Enviar el resto en chunks
        remaining = full_response[4000:]
        while remaining:
            await update.message.reply_text(remaining[:4000], reply_markup=MENU_KEYBOARD)
            remaining = remaining[4000:]
    else:
        await update.message.reply_text(full_response, reply_markup=MENU_KEYBOARD)

async def _cmd_hibernate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /hibernate <role> <tema> [duración]
    Pone una BEE a entrenar intensivamente sobre un tema.
    Ej: /hibernate coder contratos Solidity 2h
        /hibernate researcher APIs crypto gratis 45m
        /hibernate analyst trading algorítmico 1h30m
    """
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "Pon una BEE a entrenar sobre cualquier tema durante el tiempo que quieras.\n\n"
            "Uso: /hibernate <role> <tema> [duración]\n\n"
            "Ejemplos:\n"
            "• /hibernate coder contratos Solidity 2h\n"
            "• /hibernate researcher mejores APIs crypto gratis 45m\n"
            "• /hibernate analyst análisis técnico BTC 1h\n"
            "• /hibernate security hardening bots Telegram 30m\n\n"
            "Roles: coder, researcher, analyst, architect, debugger, strategist,\n"
            "       data, optimizer, web_scraper, devops, security, planner",
            reply_markup=MENU_KEYBOARD,
        )
        return

    role = args[0].lower()
    # Detectar duración al final (si el último arg tiene h/m)
    import re as _re
    duration_str = "30m"
    topic_parts  = list(args[1:])
    if topic_parts and _re.match(r'^\d+[hHmM]', topic_parts[-1]):
        duration_str = topic_parts.pop()
    topic = " ".join(topic_parts).strip()

    if not topic:
        await update.message.reply_text("Falta el tema de entrenamiento.", reply_markup=MENU_KEYBOARD)
        return

    await update.message.reply_text(
        f"Hibernación iniciada\n"
        f"Role: {role} | Tema: {topic}\n"
        f"Duración: {duration_str}\n\n"
        "La BEE está entrenando. Te aviso cuando termine y cuando haya progreso.",
        reply_markup=MENU_KEYBOARD,
    )

    chat_id = update.effective_chat.id if update.effective_chat else None
    bot_ref = context.bot

    def _notify(msg: str):
        if chat_id:
            import asyncio
            try:
                asyncio.run_coroutine_threadsafe(
                    bot_ref.send_message(chat_id, f"Entrenamiento: {msg}"),
                    asyncio.get_event_loop(),
                )
            except Exception:
                pass

    from swarm.autonomous_loop import autonomous_loop
    session_id = autonomous_loop.add_custom_training(role, topic, duration_str, _notify)
    await update.message.reply_text(
        f"Sesión iniciada: {session_id[:30]}\n"
        "Corre en background. Puedes seguir usando el bot normalmente.",
        reply_markup=MENU_KEYBOARD,
    )


async def _cmd_mejoras(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /mejoras — ver propuestas de mejora generadas autónomamente
    /mejoras aprobar <id>
    /mejoras rechazar <id>
    """
    from swarm.autonomous_loop import autonomous_loop

    args = context.args or []

    if args and args[0].lower() == "aprobar" and len(args) > 1:
        result = autonomous_loop.approve_proposal(args[1])
        await update.message.reply_text(result, reply_markup=MENU_KEYBOARD)
        return

    if args and args[0].lower() == "rechazar" and len(args) > 1:
        result = autonomous_loop.reject_proposal(args[1])
        await update.message.reply_text(result, reply_markup=MENU_KEYBOARD)
        return

    proposals = autonomous_loop.get_proposals(status="pending")
    if not proposals:
        await update.message.reply_text(
            "No hay mejoras pendientes ahora mismo.\n"
            "Las BEEs generan propuestas cada hora en background.\n"
            "Usa /autonomo para ver el estado general.",
            reply_markup=MENU_KEYBOARD,
        )
        return

    lines = [f"Mejoras propuestas por las BEEs ({len(proposals)} pendientes):\n"]
    for p in proposals[:8]:
        auto = "AUTO" if p.auto_implementable else "manual"
        lines.append(
            f"[{p.id}] {p.titulo}\n"
            f"  Impacto {p.impacto}/10 | Esfuerzo {p.esfuerzo}/10 | {auto}\n"
            f"  {p.descripcion[:100]}\n"
        )
    lines.append("Para aprobar: /mejoras aprobar <id>")
    lines.append("Para rechazar: /mejoras rechazar <id>")

    await update.message.reply_text("\n".join(lines), reply_markup=MENU_KEYBOARD)


async def _cmd_autonomo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /autonomo — estado del loop autónomo
    /autonomo pausa / /autonomo resume
    """
    from swarm.autonomous_loop import autonomous_loop
    from swarm.bee_trainer import bee_trainer

    args = context.args or []

    if args and args[0].lower() in ("pausa", "pause", "stop"):
        autonomous_loop.pause()
        await update.message.reply_text(
            "Loop autónomo pausado. Las BEEs dejarán de entrenar en background.\n"
            "Usa /autonomo resume para reanudar.",
            reply_markup=MENU_KEYBOARD,
        )
        return

    if args and args[0].lower() in ("resume", "reanudar", "start"):
        autonomous_loop.resume()
        await update.message.reply_text(
            "Loop autónomo reanudado. Las BEEs volverán a entrenar en background.",
            reply_markup=MENU_KEYBOARD,
        )
        return

    if args and args[0].lower() == "habilidades":
        skills = bee_trainer.list_skills()
        if not skills:
            await update.message.reply_text(
                "No hay habilidades entrenadas todavía.", reply_markup=MENU_KEYBOARD
            )
            return
        lines = ["Habilidades entrenadas:\n"]
        for role, skill_list in skills.items():
            lines.append(f"{role.upper()}:")
            for s in skill_list[:3]:
                lines.append(
                    f"  {s['topic'][:50]}\n"
                    f"  Nivel {s['skill_level']:.0f}/100 | {s['iterations']} iter"
                )
        await update.message.reply_text("\n".join(lines), reply_markup=MENU_KEYBOARD)
        return

    # Status general
    report = autonomous_loop.status_report()
    await update.message.reply_text(report, reply_markup=MENU_KEYBOARD)


async def _cmd_build(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        await handle_message_text(update, context, "construye: " + " ".join(context.args))
    else:
        await update.message.reply_text("Uso: /build <lo que quieres que construya>\nEj: /build un bot de precios de crypto", reply_markup=MENU_KEYBOARD)

async def _cmd_imagen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        await handle_message_text(update, context, "genera imagen de: " + " ".join(context.args))
    else:
        await update.message.reply_text("Uso: /imagen <descripción>\nEj: /imagen un robot de oro mirando las estrellas", reply_markup=MENU_KEYBOARD)

async def _cmd_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /video <descripcion> [duración]
    Genera un video con LTX-2 (audio+video sincronizado).
    Ej: /video un gato surfeando una ola al atardecer 5
        /video ciudad cyberpunk con lluvia y luces de neón 8
    """
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Genera videos con LTX-2 (el mejor modelo open source de video).\n\n"
            "Uso: /video <descripción> [segundos]\n\n"
            "Ejemplos:\n"
            "• /video un gato surfeando olas al atardecer 5\n"
            "• /video ciudad cyberpunk con lluvia y neón 8\n"
            "• /video mujer bailando flamenco en escenario con humo 5\n\n"
            "Duración: 3, 5, 8 o 10 segundos (defecto: 5)\n\n"
            "Nota: Requiere FAL_KEY. Sin ella, te digo cómo conseguirla gratis.",
            reply_markup=MENU_KEYBOARD,
        )
        return

    import re as _re
    duration = 5
    parts = list(args)
    if parts and _re.match(r'^\d+$', parts[-1]) and int(parts[-1]) in (3, 5, 8, 10):
        duration = int(parts.pop())
    prompt = " ".join(parts).strip()

    await update.message.reply_text(
        f"Generando video con LTX-2...\n"
        f"Prompt: {prompt[:80]}\n"
        f"Duración: {duration}s\n\n"
        "Esto puede tardar 1-3 minutos.",
        reply_markup=MENU_KEYBOARD,
    )

    def _gen():
        from tools.video_gen import generate_video
        return generate_video(prompt, duration=duration)

    result = await _run_with_typing(update, context, _gen, timeout=200)

    if not result:
        await update.message.reply_text("La generación tardó demasiado. Inténtalo de nuevo.", reply_markup=MENU_KEYBOARD)
        return

    error = result.get("error")
    setup = result.get("setup_needed", False)

    if setup or (error and not result.get("path")):
        msg = result.get("message", error or "Error desconocido")
        await update.message.reply_text(
            f"No se pudo generar el video.\n\n{msg}\n\n"
            "Una vez que añadas FAL_KEY como secreto, el comando funcionará.",
            reply_markup=MENU_KEYBOARD,
        )
        return

    path = result.get("path", "")
    provider = result.get("provider", "?")

    if path and __import__("os").path.exists(path):
        try:
            with open(path, "rb") as vf:
                await update.message.reply_video(
                    video=vf,
                    caption=f"LTX-2 | {duration}s | {provider}\n{prompt[:80]}",
                    reply_markup=MENU_KEYBOARD,
                )
        except Exception as e:
            url = result.get("url", "")
            if url:
                await update.message.reply_text(
                    f"Video generado: {url}\n\nProveedor: {provider}",
                    reply_markup=MENU_KEYBOARD,
                )
            else:
                await update.message.reply_text(f"Error enviando video: {e}", reply_markup=MENU_KEYBOARD)
    elif result.get("url"):
        await update.message.reply_text(
            f"Video generado: {result['url']}\nProveedor: {provider}",
            reply_markup=MENU_KEYBOARD,
        )
    else:
        await update.message.reply_text(
            f"Error: {error or 'sin resultado'}", reply_markup=MENU_KEYBOARD
        )


async def _cmd_busca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        await handle_message_text(update, context, "busca en internet: " + " ".join(context.args))
    else:
        await update.message.reply_text("Uso: /busca <búsqueda>", reply_markup=MENU_KEYBOARD)

async def _cmd_traduce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        await handle_message_text(update, context, "traduce: " + " ".join(context.args))
    else:
        await update.message.reply_text("Uso: /traduce <idioma> <texto>\nEj: /traduce inglés Hola mundo", reply_markup=MENU_KEYBOARD)

async def _cmd_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        await handle_message_text(update, context, "genera qr de: " + " ".join(context.args))
    else:
        await update.message.reply_text("Uso: /qr <contenido>\nEj: /qr https://pump.fun", reply_markup=MENU_KEYBOARD)

async def _cmd_yt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        await handle_message_text(update, context, "resume youtube: " + context.args[0])
    else:
        await update.message.reply_text("Uso: /yt <url del video>", reply_markup=MENU_KEYBOARD)

async def _cmd_corre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        await handle_message_text(update, context, "ejecuta este código: " + " ".join(context.args))
    else:
        await update.message.reply_text("Uso: /corre <código python>", reply_markup=MENU_KEYBOARD)

async def _cmd_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        await handle_message_text(update, context, "screenshot de " + context.args[0])
    else:
        await update.message.reply_text("Uso: /screenshot <url>\nEj: /screenshot dexscreener.com", reply_markup=MENU_KEYBOARD)

async def _cmd_aprende(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        await handle_message_text(update, context, "aprende: " + " ".join(context.args))
    else:
        await update.message.reply_text("Uso: /aprende <tema>\nEj: /aprende trading en Solana con 20 bees", reply_markup=MENU_KEYBOARD)

async def _cmd_sabes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_message_text(update, context, "qué sabes")

async def _cmd_sistema(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_message_text(update, context, "status del sistema")


async def _cmd_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /keys            — lista todos los proveedores conocidos + estado de integración
    /keys status     — mismo que /keys
    /keys cazar      — lanza BEE key_hunter a buscar nuevos providers ahora
    /keys integrar X — instrucciones para integrar el proveedor X
    """
    args = " ".join(context.args or []).strip().lower()

    from tools.key_hunter import key_hunter, format_known_providers_report, get_integration_instructions

    if args in ("", "status", "estado"):
        report = format_known_providers_report()
        await update.message.reply_text(report[:4000], reply_markup=MENU_KEYBOARD)

    elif args in ("cazar", "buscar", "hunt", "busca"):
        await update.message.reply_text(
            "BEE key_hunter activada — buscando nuevos proveedores gratuitos...\n"
            "Resultado en ~60 segundos.",
            reply_markup=MENU_KEYBOARD,
        )
        import threading
        def _hunt():
            report = key_hunter.run_hunt()
            # Notificación ya la hace key_hunter internamente via notify_fn
        threading.Thread(target=_hunt, daemon=True).start()

    elif args.startswith("integrar ") or args.startswith("add "):
        provider = args.split(" ", 1)[1].strip()
        instructions = get_integration_instructions(provider)
        await update.message.reply_text(instructions[:4000], reply_markup=MENU_KEYBOARD)

    else:
        await update.message.reply_text(
            "Uso:\n"
            "/keys           — ver todos los proveedores\n"
            "/keys cazar     — BEE busca nuevas APIs gratis ahora\n"
            "/keys integrar <nombre>  — instrucciones de registro\n\n"
            "Ejemplos:\n"
            "/keys integrar openrouter\n"
            "/keys integrar sambanova\n"
            "/keys integrar huggingface",
            reply_markup=MENU_KEYBOARD,
        )


async def _cmd_beemode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /beemode              — ver modo actual de entrenamiento
    /beemode economico    — 5 BEEs, sostenible 24/7 (default)
    /beemode normal       — 15 BEEs, ~10h antes de agotar cuotas
    /beemode burst        — 50 BEEs durante 30 min, luego vuelve a económico
    /beemode burst 60     — burst de 60 minutos
    """
    from swarm.autonomous_loop import autonomous_loop

    args = context.args or []

    if not args:
        from swarm.autonomous_loop import TRAINING_MODES
        mode = autonomous_loop._training_mode
        limit = autonomous_loop._active_training_limit()
        import time as _t
        burst_info = ""
        if mode == "burst" and autonomous_loop._burst_until > _t.time():
            mins_left = int((autonomous_loop._burst_until - _t.time()) / 60)
            burst_info = f"\nBurst expira en: {mins_left} min"

        await update.message.reply_text(
            f"Modo actual: {mode.upper()} ({limit} BEEs activas){burst_info}\n\n"
            f"Modos disponibles:\n"
            f"  economico — 5 BEEs, 24/7 sin agotar cuotas\n"
            f"  normal    — 15 BEEs, ~10h/día\n"
            f"  burst     — 50 BEEs por 30 min (solo manual)\n\n"
            f"Cómo funciona:\n"
            f"  En modo económico, las 5 BEEs entrenan usando Cerebras\n"
            f"  como proveedor principal. Groq/Gemini/Together quedan\n"
            f"  100% libres para tus requests directos.\n"
            f"  El rate limiter hace cola automática — ninguna BEE\n"
            f"  supera el límite del proveedor.",
            reply_markup=MENU_KEYBOARD,
        )
        return

    mode = args[0].lower()
    duration = int(args[1]) if len(args) > 1 and args[1].isdigit() else 30

    result = autonomous_loop.set_training_mode(mode, duration_minutes=duration)
    await update.message.reply_text(result, reply_markup=MENU_KEYBOARD)


async def _cmd_cuotas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /cuotas — estado actual de cuotas de todos los proveedores.
    Muestra RPM usado, cuota diaria, y cuándo se reinicia.
    """
    try:
        from tools.llm_adapter import quota_status
        stats = quota_status()
        lines = ["📊 CUOTAS DE PROVEEDORES — ESTADO ACTUAL\n"]
        lines.append("=" * 40 + "\n")

        for s in stats:
            if s["daily_limit"]:
                pct = int(100 * s["daily_used"] / s["daily_limit"])
                bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                daily_txt = f"{s['daily_used']}/{s['daily_limit']} [{bar}] {pct}% — reinicia {s['resets_at']}"
            else:
                daily_txt = "sin límite diario (pago)"

            rpm_txt = f"{s['rpm_used']}/{s['rpm_limit']} rpm"
            lines.append(
                f"• {s['provider'].upper()}\n"
                f"  RPM: {rpm_txt}\n"
                f"  Día: {daily_txt}\n"
            )

        lines.append(
            "\nPRIORIDAD DE LLAMADAS:\n"
            "  Loop BEEs → Cerebras (50 rpm, sin límite diario)\n"
            "  Tus requests → cascada completa según tarea\n"
            "  El rate limiter hace cola — jamás spam a las APIs"
        )
        await update.message.reply_text("".join(lines)[:4000], reply_markup=MENU_KEYBOARD)
    except Exception as e:
        await update.message.reply_text(f"Error leyendo cuotas: {e}", reply_markup=MENU_KEYBOARD)

async def _cmd_healer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from tools.self_healer import self_healer as _sh
    history = _sh.get_repair_history(10)
    if not history:
        await update.message.reply_text(
            "Auto-Healer activo. Sin reparaciones registradas aún.\n\n"
            "Monitoreo cada 5min — te aviso cuando encuentre y repare algo.",
            reply_markup=MENU_KEYBOARD,
        )
        return
    lines = ["Auto-Healer — Últimas reparaciones:\n"]
    for r in reversed(history):
        ts = r["timestamp"][:16].replace("T", " ")
        status = "OK" if r["success"] else "FALLÓ"
        lines.append(f"[{status}] {ts}\nError: {r['error'][:80]}\nFix: {r['patch'][:100]}\n")
    await update.message.reply_text("\n".join(lines)[:4000], reply_markup=MENU_KEYBOARD)


async def _cmd_ghost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Ghost Mode — hace a BEEA y BEEs invisibles, sin huella, no rastreables.
    /ghost on    — activa
    /ghost off   — desactiva
    /ghost        — estado actual
    """
    from tools import ghost_mode
    args = " ".join(context.args or []).strip().lower()

    if args in ("on", "activar", "start", "encender"):
        ghost_mode.activate()
        await update.message.reply_text(
            "👻 Ghost mode ACTIVADO.\n\n"
            "Lo que cambia ahora:\n"
            "• Todos mis requests web tienen User-Agent e IP ficticias\n"
            "• El timing de mis respuestas simula comportamiento humano\n"
            "• Nunca menciono qué modelo de IA me ejecuta\n"
            "• Mis identidades de sesión rotan cada 50 requests\n"
            "• Auto-rotación cada 30 minutos\n\n"
            "Soy invisible.",
            reply_markup=MENU_KEYBOARD,
        )
    elif args in ("off", "desactivar", "stop", "apagar"):
        ghost_mode.deactivate()
        await update.message.reply_text(
            "Ghost mode desactivado. Operando en modo normal.",
            reply_markup=MENU_KEYBOARD,
        )
    else:
        await update.message.reply_text(
            ghost_mode.status_text(),
            parse_mode="Markdown",
            reply_markup=MENU_KEYBOARD,
        )


async def _cmd_colmena(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from colmena.monitor import colmena as _colmena
    st = _colmena.status()
    lines = ["🐝 Colmena — Estado del enjambre\n"]
    for bee_name, info in st["bees"].items():
        viva = "✅ viva" if info["viva"] else "💀 caída"
        lines.append(f"{bee_name}: {viva} ({info['ultimo_latido']})")
    lines.append(f"\nIssues reportados: {st['issues_reportados']}")
    lines.append(f"Corriendo: {'sí' if st['running'] else 'no'}")
    lines.append("\nTodas las bees vigilan todo el sistema entre sí.")
    await update.message.reply_text("\n".join(lines), reply_markup=MENU_KEYBOARD)


async def _cmd_bee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Habla directamente con una BEE.
    Uso: /bee <rol> <mensaje>   → ej: /bee debugger por qué falla image_gen?
         /bee <mensaje>         → usa rol 'debugger' por defecto
    Roles: coder, debugger, researcher, architect, reviewer, planner, data, strategist
    """
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Uso: /bee <rol> <tarea>\n"
            "Ejemplo: /bee debugger por qué falla la imagen?\n\n"
            "Roles disponibles: coder, debugger, researcher, architect, "
            "reviewer, planner, data, strategist, analyst, optimizer, writer",
            reply_markup=MENU_KEYBOARD,
        )
        return

    from swarm.bee_roles import BEE_ROLES
    known_roles = set(BEE_ROLES.keys())

    if args[0].lower() in known_roles:
        role = args[0].lower()
        task_text = " ".join(args[1:]).strip()
    else:
        role = "debugger"
        task_text = " ".join(args).strip()

    if not task_text:
        await update.message.reply_text(
            f"¿Qué le digo a la BEE {role}?", reply_markup=MENU_KEYBOARD
        )
        return

    await update.message.reply_text(
        f"🐝 BEE [{role}] recibió tu tarea — procesando...", reply_markup=MENU_KEYBOARD
    )

    def _run_bee():
        from swarm.agent_worker import AgentWorker
        worker = AgentWorker(agent_id=99, role=role)
        res = worker.run_task({"step": task_text, "objective": task_text, "role": role})
        return res.get("result", "Sin resultado")

    result = await _run_with_typing(update, context, _run_bee, timeout=120)
    if not result:
        result = "La BEE tardó demasiado."

    header = f"🐝 BEE [{role}]:\n\n"
    await update.message.reply_text((header + str(result))[:4000], reply_markup=MENU_KEYBOARD)


async def _cmd_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ver y gestionar tareas programadas."""
    args = context.args or []
    from tools.scheduler import bee_scheduler

    if args and args[0].lower() in ("cancel", "cancelar", "borrar", "clear", "all"):
        bee_scheduler.cancel_all()
        await update.message.reply_text("Todas las tareas canceladas.", reply_markup=MENU_KEYBOARD)
        return

    if args and args[0].lower().startswith("cancel:"):
        task_id = args[0].split(":", 1)[1]
        ok = bee_scheduler.cancel_task(task_id)
        msg = f"Tarea {task_id} cancelada." if ok else f"No encontré la tarea {task_id}."
        await update.message.reply_text(msg, reply_markup=MENU_KEYBOARD)
        return

    tasks = bee_scheduler.list_tasks()
    if not tasks:
        await update.message.reply_text(
            "Sin tareas programadas.\n\n"
            "Puedes pedirme:\n"
            "• Recuérdame hacer X en 2 horas\n"
            "• Avísame si BTC baja de 80000\n"
            "• Dime el precio de SOL todos los días a las 9am",
            reply_markup=MENU_KEYBOARD,
        )
        return

    lines = [f"Tareas programadas ({len(tasks)}):\n"]
    for t in tasks:
        task_type = t.get("type", "?")
        if task_type == "reminder":
            lines.append(f"⏰ [{t['id']}] Recordatorio: {t.get('text','')[:50]}")
            lines.append(f"   Cada: {t.get('delay_str','?')} | Repite: {'sí' if t.get('repeat') else 'no'}")
        elif task_type == "daily":
            lines.append(f"📅 [{t['id']}] Diario {t.get('hour',0):02d}:{t.get('minute',0):02d}: {t.get('text','')[:50]}")
        elif task_type == "price_alert":
            cond = "baja de" if t.get("condition") == "below" else "sube de"
            lines.append(f"🔔 [{t['id']}] Alerta: {t.get('symbol','?')} {cond} ${t.get('target_price',0):,.0f}")
        lines.append("")

    lines.append("\n/tasks cancelar — cancela todas\n/tasks cancel:ID — cancela una tarea")
    await update.message.reply_text("\n".join(lines)[:4000], reply_markup=MENU_KEYBOARD)


async def _cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ver y gestionar la memoria larga de BEEA."""
    args = context.args or []
    from memory.long_memory import long_memory

    if args and args[0].lower() in ("borrar", "clear", "reset", "forget"):
        long_memory.forget_all()
        await update.message.reply_text("Memoria borrada.", reply_markup=MENU_KEYBOARD)
        return

    if args and args[0].lower() == "recuerda":
        fact = " ".join(args[1:])
        if fact:
            long_memory.remember_preference(fact)
            await update.message.reply_text(f"Guardado: {fact}", reply_markup=MENU_KEYBOARD)
        return

    stats = long_memory.stats()
    recent = long_memory.list_recent(5)

    lines = [f"Memoria larga: {stats['total']}/{stats['max']} recuerdos\n"]
    if stats.get("categories"):
        for cat, count in stats["categories"].items():
            lines.append(f"  {cat}: {count}")
    lines.append("\nÚltimos 5 recuerdos:")
    for m in recent:
        lines.append(f"• [{m.get('category','?')}] {m.get('content','')[:80]}")

    lines.append("\n/memory recuerda [texto] — guarda algo")
    lines.append("/memory borrar — borra toda la memoria")
    await update.message.reply_text("\n".join(lines)[:4000], reply_markup=MENU_KEYBOARD)

async def _cmd_alerta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_message_text(update, context, "mis alertas de precio activas")

async def _cmd_grafico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sym = context.args[0].upper() if context.args else "SOL"
    await update.message.reply_text(f"Generando gráfico de {sym}...", reply_markup=MENU_KEYBOARD)
    try:
        from trading.chart_generator import chart_generator
        img_bytes = await chart_generator.get_chart(sym, days=7)
        if img_bytes:
            await update.message.reply_photo(photo=img_bytes, caption=f"Gráfico {sym}/USD — 7 días", reply_markup=MENU_KEYBOARD)
        else:
            await update.message.reply_text(f"No pude generar el gráfico de {sym}.", reply_markup=MENU_KEYBOARD)
    except Exception as e:
        await update.message.reply_text(f"Error generando gráfico: {e}", reply_markup=MENU_KEYBOARD)

async def _cmd_menu_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¿Qué quieres hacer?", reply_markup=_inline_menu_main())


async def handle_message_text(update: Update, context: ContextTypes.DEFAULT_TYPE, override_text: str = None):
    """Procesa un texto fijo (desde comandos o botones) usando el mismo pipeline que handle_message."""
    global _ALVARO_CHAT_ID, _BOT_INSTANCE
    if update.effective_chat and update.effective_chat.id:
        new_id = update.effective_chat.id
        if new_id != _ALVARO_CHAT_ID:
            _ALVARO_CHAT_ID = new_id
            _BOT_INSTANCE = context.bot
            _save_chat_id(new_id)

    message = override_text or (update.message.text if update.message else "")
    logger.info("CMD dispatch: %s", message)

    result = await _run_with_typing(update, context, conversation_mode.process_message, message, timeout=60)
    if result is None:
        await update.message.reply_text("Me quedé pensando. Inténtalo de nuevo.", reply_markup=MENU_KEYBOARD)
        return

    rtype = result.get("type", "")
    if rtype in ("chat_reply", "clarification", "direct_answer"):
        await update.message.reply_text(result["response"][:4000], reply_markup=MENU_KEYBOARD)
    elif rtype == "wallet":
        # Redirect to full wallet handler in handle_message - re-inject
        await update.message.reply_text("Consultando wallets...", reply_markup=MENU_KEYBOARD)
        try:
            from crypto.wallet_manager import wallet_manager
            from crypto.price_feed import price_feed
            wallet_manager.init_all_wallets()
            balances, prices = await asyncio.gather(
                wallet_manager.get_all_balances(),
                price_feed.get_portfolio_prices(),
            )
            sym_prices = {k.upper(): v.get("price", 0) for k, v in prices.items()}
            report = wallet_manager.format_balance_report(balances, sym_prices)
            await update.message.reply_text(report, reply_markup=MENU_KEYBOARD)
        except Exception as e:
            await update.message.reply_text(f"Error: {e}", reply_markup=MENU_KEYBOARD)
    elif rtype == "price":
        await update.message.reply_text("Consultando precios...", reply_markup=MENU_KEYBOARD)
        try:
            from crypto.price_feed import price_feed
            token = result.get("token", "BTC,ETH,SOL")
            symbols = [t.strip().upper() for t in token.replace(",", " ").split()]
            prices = await price_feed.get_prices_coingecko(symbols)
            report = price_feed.format_price_report(prices)
            await update.message.reply_text(report, reply_markup=MENU_KEYBOARD)
        except Exception as e:
            await update.message.reply_text(f"Error: {e}", reply_markup=MENU_KEYBOARD)
    elif rtype == "pumpfun":
        await update.message.reply_text("Escaneando PumpFun...", reply_markup=MENU_KEYBOARD)
        try:
            from trading.pumpfun import pumpfun_scanner
            opportunities = await pumpfun_scanner.scan_opportunities()
            report = pumpfun_scanner.format_opportunities(opportunities)
            await update.message.reply_text(report, reply_markup=MENU_KEYBOARD)
        except Exception as e:
            await update.message.reply_text(f"Error en PumpFun: {e}", reply_markup=MENU_KEYBOARD)
    elif rtype == "trading_status":
        await update.message.reply_text("Consultando trading...", reply_markup=MENU_KEYBOARD)
        try:
            from trading.autonomous_trader import autonomous_trader
            status = autonomous_trader.get_status()
            lines = [
                f"Trading autónomo: {'ACTIVO' if status.get('running') else 'PAUSADO'}",
                f"Modo: {'Simulación' if status.get('dry_run') else 'REAL'}",
                f"Operaciones: {status.get('total_trades', 0)}",
                f"Posiciones abiertas: {status.get('open_positions', 0)}",
                f"P&L: {status.get('total_pnl', 0):.4f} SOL",
            ]
            await update.message.reply_text("\n".join(lines), reply_markup=MENU_KEYBOARD)
        except Exception as e:
            await update.message.reply_text(f"Error trading: {e}", reply_markup=MENU_KEYBOARD)
    else:
        fallback = result.get("message", result.get("response", str(result)[:800]))
        if fallback:
            await update.message.reply_text(str(fallback)[:4000], reply_markup=MENU_KEYBOARD)


import re as _re_module


def _format_task_output(output: dict) -> str:
    """Convierte el resultado del orquestador a texto legible para Álvaro."""
    if not output:
        return "Listo."
    if isinstance(output, str):
        return output

    if "message" in output and output["message"]:
        return str(output["message"])

    if "full_analysis" in output and output["full_analysis"]:
        text = str(output["full_analysis"])
        text = text.replace("\\n", "\n").replace("\\t", "\t").replace("\\*", "*")
        return text.strip()

    if "analysis" in output and output["analysis"]:
        return str(output["analysis"])[:2000]

    if "result" in output and output["result"]:
        return str(output["result"])

    if "error" in output:
        err = str(output["error"])
        if "zip_path missing" in err:
            return "Mándame el archivo ZIP primero y lo reviso."
        if "path missing" in err or "not found" in err.lower():
            return f"No encontré el archivo necesario. Detalle técnico: {err}"
        try:
            from core.ai_chat import chat
            return chat(f"El sistema devolvió este error: {err}. Explícaselo a Álvaro de forma natural en una línea.")
        except Exception:
            return f"Error técnico: {err}"

    if "output" in output:
        return str(output["output"])[:2000]

    try:
        from core.ai_chat import chat
        summary = str(output)[:400]
        return chat(f"El sistema completó una tarea y devolvió: {summary}. Dile a Álvaro qué hice, en una línea, sin tecnicismos.")
    except Exception:
        return str(output)[:800]


async def _process_tool_signals(text: str, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """
    Detecta señales de herramienta en la respuesta de BEEA y las ejecuta.
    [IMG: prompt]   → genera imagen y la envía
    [VID: prompt]   → genera video y lo envía
    [SEARCH: query] → busca en internet y añade resultados
    [CODE: código]  → ejecuta código Python y añade output
    Devuelve el texto limpio (sin las señales).
    """
    if not text:
        return text

    img_matches = _re_module.findall(r'\[IMG:\s*(.*?)\]', text, _re_module.DOTALL)
    vid_matches = _re_module.findall(r'\[VID:\s*(.*?)\]', text, _re_module.DOTALL)
    search_matches = _re_module.findall(r'\[SEARCH:\s*(.*?)\]', text, _re_module.DOTALL)
    code_matches = _re_module.findall(r'\[CODE:\s*(.*?)\]', text, _re_module.DOTALL)

    cleaned = _re_module.sub(r'\[IMG:\s*.*?\]', '', text, flags=_re_module.DOTALL).strip()
    cleaned = _re_module.sub(r'\[VID:\s*.*?\]', '', cleaned, flags=_re_module.DOTALL).strip()
    cleaned = _re_module.sub(r'\[SEARCH:\s*.*?\]', '', cleaned, flags=_re_module.DOTALL).strip()
    cleaned = _re_module.sub(r'\[CODE:\s*.*?\]', '', cleaned, flags=_re_module.DOTALL).strip()

    for img_prompt in img_matches:
        img_prompt = img_prompt.strip()
        if not img_prompt:
            continue
        try:
            _prompt_capture = img_prompt
            def _gen(p=_prompt_capture):
                from tools.image_gen import generate_image
                return generate_image(p)
            gen_result = await _run_with_typing(update, context, _gen, timeout=120)
            if gen_result:
                local_path = gen_result.get("local_path")
                img_url = gen_result.get("url")
                provider = gen_result.get("provider", "")
                if local_path and os.path.exists(local_path):
                    raw = open(local_path, "rb").read()
                    os.unlink(local_path)
                    await _safe_reply_photo(update, raw, provider)
                elif img_url:
                    import requests as _req
                    try:
                        raw = _req.get(img_url, timeout=60).content
                        await _safe_reply_photo(update, raw, provider)
                    except Exception:
                        await update.message.reply_text(img_url, reply_markup=MENU_KEYBOARD)
                logger.info("Tool signal IMG → enviada (%s)", provider)
        except Exception as e:
            logger.error("_process_tool_signals IMG error: %s", e)
            try:
                await update.message.reply_text(
                    "Amor, los servidores de imagen están sobrecargados justo ahora. Inténtalo de nuevo en un momento 🖤",
                    reply_markup=MENU_KEYBOARD,
                )
            except Exception:
                pass

    for query in search_matches:
        query = query.strip()
        if not query:
            continue
        try:
            def _search(q=query):
                from tools.websearch import web_search
                return web_search(q)
            results = await _run_with_typing(update, context, _search, timeout=30)
            if results:
                results_text = str(results)[:800]
                cleaned = (cleaned + f"\n\n{results_text}").strip() if cleaned else results_text
        except Exception as e:
            logger.error("_process_tool_signals SEARCH error: %s", e)

    for code in code_matches:
        code = code.strip()
        if not code:
            continue
        try:
            def _run(c=code):
                from tools.code_sandbox import run_python_code, format_result
                result = run_python_code(c)
                return format_result(result)
            output = await _run_with_typing(update, context, _run, timeout=30)
            if output:
                out_text = f"```\n{str(output)[:500]}\n```"
                cleaned = (cleaned + f"\n\n{out_text}").strip() if cleaned else out_text
        except Exception as e:
            logger.error("_process_tool_signals CODE error: %s", e)

    for vid_prompt in vid_matches:
        vid_prompt = vid_prompt.strip()
        if not vid_prompt:
            continue
        try:
            _vprompt = vid_prompt
            def _gen_vid(p=_vprompt):
                from tools.video_gen import generate_video
                return generate_video(p, duration=5)
            await update.message.reply_text("Generando video... esto puede tardar 1-2 minutos 🎬", reply_markup=MENU_KEYBOARD)
            vid_result = await _run_with_typing(update, context, _gen_vid, timeout=240)
            if vid_result and not vid_result.get("error"):
                local_path = vid_result.get("path")
                vid_url = vid_result.get("url")
                provider = vid_result.get("provider", "")
                if local_path and os.path.exists(local_path):
                    with open(local_path, "rb") as vf:
                        await update.message.reply_video(video=vf, reply_markup=MENU_KEYBOARD)
                elif vid_url:
                    await update.message.reply_text(f"Video listo: {vid_url}", reply_markup=MENU_KEYBOARD)
                logger.info("Tool signal VID → enviado (%s)", provider)
            else:
                err_msg = vid_result.get("message", "No se pudo generar el video.") if vid_result else "Error generando video."
                await update.message.reply_text(err_msg, reply_markup=MENU_KEYBOARD)
        except Exception as e:
            logger.error("_process_tool_signals VID error: %s", e)
            try:
                await update.message.reply_text("No pude generar el video ahora mismo. Inténtalo con /video <descripción>", reply_markup=MENU_KEYBOARD)
            except Exception:
                pass

    return cleaned or None


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _ALVARO_CHAT_ID, _BOT_INSTANCE

    # Capturar chat_id de Álvaro y registrar bot instance para notificaciones autónomas
    if update.effective_chat and update.effective_chat.id:
        new_id = update.effective_chat.id
        if new_id != _ALVARO_CHAT_ID:
            _ALVARO_CHAT_ID = new_id
            _BOT_INSTANCE = context.bot
            _save_chat_id(new_id)
            # Registrar la función de notificación en el auto_learner
            from memory.auto_learner import auto_learner
            auto_learner.set_notify_fn(_send_autonomous_notification)

    raw = update.message.text

    # Mapear botones del teclado principal a mensajes naturales
    raw_lower = raw.strip().lower()
    if raw_lower in BUTTON_MAP:
        mapped = BUTTON_MAP[raw_lower]
        if mapped == "__MENU_INLINE__":
            await update.message.reply_text("¿Qué quieres hacer?", reply_markup=_inline_menu_main())
            return
        raw = mapped

    message = (
        raw
        .replace("👋 ", "").replace("📋 ", "")
        .replace("🤖 ", "").replace("🔨 ", "")
        .replace("📁 ", "").replace("📊 ", "")
    )
    logger.info("Received: %s", message)

    if message.lower().startswith("crear proyecto "):
        name = message.split("crear proyecto ", 1)[1].strip()
        workspace_manager.create_project(name)
        state_manager.set_current_project(name)
        await update.message.reply_text(
            f"Proyecto {name} creado.",
            reply_markup=MENU_KEYBOARD,
        )
        return

    # Detectar scheduling intent (recordatorios, alertas, tareas programadas)
    msg_lower = message.lower().strip()
    _sched_triggers = ["recuérdame", "recuerda que", "avísame si", "avísame cuando", "todos los días a las", "cada día a las", "dime el precio de"]
    if any(t in msg_lower for t in _sched_triggers):
        try:
            from tools.scheduler import bee_scheduler, parse_schedule_from_text
            sched = parse_schedule_from_text(message)
            if sched:
                if sched["type"] == "reminder":
                    task = bee_scheduler.add_reminder(sched["text"], sched["delay_str"])
                    await update.message.reply_text(
                        f"Listo, te recuerdo '{sched['text']}' en {sched['delay_str']}.",
                        reply_markup=MENU_KEYBOARD,
                    )
                    return
                elif sched["type"] == "daily":
                    task = bee_scheduler.add_daily(sched["text"], sched["hour"], sched.get("minute", 0))
                    await update.message.reply_text(
                        f"Perfecto. '{sched['text']}' todos los días a las {sched['hour']:02d}:{sched.get('minute',0):02d}.",
                        reply_markup=MENU_KEYBOARD,
                    )
                    return
                elif sched["type"] == "price_alert":
                    task = bee_scheduler.add_price_alert(sched["symbol"], sched["condition"], sched["target_price"])
                    cond_str = "baje de" if sched["condition"] == "below" else "suba de"
                    await update.message.reply_text(
                        f"Alerta activada: te aviso cuando {sched['symbol']} {cond_str} ${sched['target_price']:,.0f}.",
                        reply_markup=MENU_KEYBOARD,
                    )
                    return
        except Exception as _se:
            logger.warning("Scheduling parse error: %s", _se)

    # ── HiveMind: detección por lenguaje natural ─────────────────────────────
    _HIVEMIND_TRIGGERS = [
        "manda las bees", "manda tus bees", "lanza el enjambre", "activa el enjambre",
        "enjambre a", "enjambre que", "hivemind", "todas las bees a",
        "que las bees", "bees que investiguen", "bees a investigar",
        "manda a tus bees", "manda todas las bees", "lanza las bees",
        "pon el enjambre", "el enjambre en",
    ]
    _hm_trigger = any(t in msg_lower for t in _HIVEMIND_TRIGGERS)
    if _hm_trigger:
        # Extraer n_bees si menciona un número
        import re as _re
        n_match = _re.search(r'\b([2-9]|[1-9][0-9]|1[0-5][0-9]|160)\s*(bees?|agentes?)?\b', msg_lower)
        n_bees = int(n_match.group(1)) if n_match else 4

        # Limpiar triggers del mensaje para obtener el objetivo limpio
        goal = message
        for t in _HIVEMIND_TRIGGERS:
            goal = goal.lower().replace(t, " ")
        goal = goal.strip(" :.,")
        if not goal or len(goal) < 5:
            goal = message

        await update.message.reply_text(
            f"🐝 HiveMind activado — {n_bees} BEEs en paralelo\n"
            f"Objetivo: {goal[:100]}\n\nPlanificando subtareas...",
            reply_markup=MENU_KEYBOARD,
        )

        def _run_hm():
            from swarm.hivemind import hivemind as _hm
            return _hm.execute(goal, n_bees=n_bees)

        result = await _run_with_typing(update, context, _run_hm, timeout=600)
        if not result:
            await update.message.reply_text("El enjambre tardó demasiado. Inténtalo con /hivemind.", reply_markup=MENU_KEYBOARD)
            return

        final = result.get("final_result", "")
        elapsed = result.get("elapsed", 0)
        roles = [s.get("role", "?") for s in result.get("subtasks", [])]
        header = f"🐝 HiveMind — {len(roles)} BEEs completadas en {elapsed}s\nRoles: {', '.join(roles)}\n\n"
        full = header + final
        for i in range(0, len(full), 4000):
            await update.message.reply_text(full[i:i+4000], reply_markup=MENU_KEYBOARD)
        return

    # ── Loop autónomo: detección por lenguaje natural ─────────────────────────
    _AUTO_MEJORAS = [
        "qué mejoras", "ver mejoras", "muéstrame las mejoras", "mejoras pendientes",
        "propuestas de mejora", "qué proponen las bees", "que proponen las bees",
        "mejoras del bot", "ideas de mejora",
    ]
    _AUTO_STATUS = [
        "qué hacen las bees", "que hacen las bees", "estado de las bees",
        "qué están haciendo las bees", "en qué están las bees", "actividad bees",
        "bees activas", "estado del enjambre", "qué hacen tus bees",
        "están haciendo algo las bees", "bees entrenan",
    ]
    _AUTO_HIBERNATE = [
        "pon a las bees a entrenar", "que las bees aprendan", "hiberna",
        "entrena a las bees", "bees entrenen", "pon bees a aprender",
        "quiero que aprendan", "ponlas a aprender",
    ]
    if any(t in msg_lower for t in _AUTO_MEJORAS):
        from swarm.autonomous_loop import autonomous_loop as _al
        proposals = _al.get_proposals(status="pending")
        if not proposals:
            await update.message.reply_text(
                "No hay mejoras pendientes ahora. Las BEEs generan propuestas cada hora.\n"
                "Usa /autonomo para ver su estado.",
                reply_markup=MENU_KEYBOARD,
            )
        else:
            lines = [f"Las BEEs tienen {len(proposals)} mejoras propuestas:\n"]
            for p in proposals[:5]:
                auto = "auto" if p.auto_implementable else "manual"
                lines.append(f"[{p.id}] {p.titulo} — impacto {p.impacto}/10 ({auto})")
            lines.append("\n/mejoras para ver todo | /mejoras aprobar <id>")
            await update.message.reply_text("\n".join(lines), reply_markup=MENU_KEYBOARD)
        return

    if any(t in msg_lower for t in _AUTO_STATUS):
        from swarm.autonomous_loop import autonomous_loop as _al
        report = _al.status_report()
        await update.message.reply_text(report, reply_markup=MENU_KEYBOARD)
        return

    if any(t in msg_lower for t in _AUTO_HIBERNATE):
        # Redirige al comando /hibernate con el mensaje completo como contexto
        await update.message.reply_text(
            "Para poner una BEE a entrenar, usa:\n"
            "/hibernate <role> <tema> [duración]\n\n"
            "Ejemplos:\n"
            "• /hibernate coder análisis de código Python 2h\n"
            "• /hibernate researcher mejores APIs crypto gratis 1h\n"
            "• /hibernate analyst estrategias de trading BTC 45m\n\n"
            "O simplemente dime: /hibernate y te explico todo.",
            reply_markup=MENU_KEYBOARD,
        )
        return

    # Detectar activación de modo voz por texto
    if any(p in msg_lower for p in ["activa modo voz", "modo voz on", "quiero voz", "respóndeme con voz", "responde con voz"]):
        from tools.tts import set_voice_mode
        set_voice_mode(True)
        await update.message.reply_text("Modo voz activado. Te voy a responder con audio.", reply_markup=MENU_KEYBOARD)
        return
    if any(p in msg_lower for p in ["desactiva modo voz", "modo voz off", "solo texto", "sin voz"]):
        from tools.tts import set_voice_mode
        set_voice_mode(False)
        await update.message.reply_text("Modo voz desactivado. Solo texto.", reply_markup=MENU_KEYBOARD)
        return

    PHOTO_GEN_KEYWORDS = [
        "genera", "generame", "genérame", "crea", "créame", "hazme", "haz una",
        "cambia", "cambiala", "modifica", "modificala", "usa esta", "usa esto",
        "basándote", "basate", "parecida", "similar", "imagen de", "a tu gusto",
        "ilustra", "pinta", "dibuja", "hazla", "hazlo", "hazte", "hazlo así",
        "hazla así", "tu estilo", "métele", "ponle", "al estilo", "más sexy",
        "esa es", "esa base", "esa foto", "esa imagen", "igual pero", "pero más",
        "pero con", "tómala de base", "tómala como",
        "a ver", "muéstrame", "mándame", "quiero ver", "como ella", "como esa",
        "con ella", "con esa", "igual que", "a su estilo", "así pero", "pero así",
        "esa muchacha", "esa chica", "esa persona", "ese estilo",
    ]

    # Palabras que indican follow-up de comentario sobre la foto (no generación)
    PHOTO_COMMENT_KEYWORDS = [
        "no ves", "que ves", "qué ves", "lo que te envio", "lo que te envié",
        "lo que te mandé", "lo que te mande", "la foto", "la imagen",
        "viste", "describela", "descríbela", "qué hay", "que hay en",
        "quién es", "quien es", "quién sale", "quien sale",
        "cómo te parece", "como te parece", "qué opinas de", "que opinas de",
        "te gusto", "te gustó", "qué piensas", "que piensas",
        "la enviaste", "te la mande", "te la mandé",
    ]

    _has_photo_ctx = bool(_LAST_PHOTO_CONTEXT.get("vision") or _LAST_PHOTO_CONTEXT.get("description"))
    _photo_gen_trigger = any(k in msg_lower for k in PHOTO_GEN_KEYWORDS)
    _photo_comment_trigger = any(k in msg_lower for k in PHOTO_COMMENT_KEYWORDS)

    # Follow-up de comentario sobre la foto — Álvaro pregunta sobre lo que ve BEEA
    if _has_photo_ctx and _photo_comment_trigger and not _photo_gen_trigger:
        vision = _LAST_PHOTO_CONTEXT.get("vision", {})
        description = vision.get("description", "") or _LAST_PHOTO_CONTEXT.get("description", "")
        caption_ctx = _LAST_PHOTO_CONTEXT.get("caption", "")
        gen_prompt = vision.get("gen_prompt", "")

        from core.ai_chat import chat as _chat
        if description and description not in ("foto sin descripción disponible",):
            followup_prompt = (
                f"Describiste esta foto: {description}."
                + (f" (rasgos detallados: {gen_prompt[:200]})" if gen_prompt and gen_prompt != description else "")
                + (f" Álvaro la mandó con el mensaje: '{caption_ctx}'." if caption_ctx else "")
                + f" Ahora él pregunta: '{message}'."
                + " Respóndele directamente sobre lo que viste. No digas que no puedes ver imágenes."
            )
        else:
            followup_prompt = (
                f"Álvaro te mandó una foto"
                + (f" con el mensaje: '{caption_ctx}'" if caption_ctx else "")
                + f" y ahora pregunta: '{message}'. Respóndele de forma natural."
            )

        result = await _run_with_typing(update, context, _chat, followup_prompt, timeout=30)
        if result and not _is_vision_refusal(result):
            await update.message.reply_text(result[:4000], reply_markup=MENU_KEYBOARD)
        else:
            # Respuesta de emergencia si el LLM aún rechaza
            fallback_reply = (
                f"Sí, la vi. {description[:200]}." if description and description != "foto sin descripción disponible"
                else "Sí, la recibí. ¿Qué quieres que te diga de ella?"
            )
            await update.message.reply_text(fallback_reply, reply_markup=MENU_KEYBOARD)
        return

    if _has_photo_ctx and _photo_gen_trigger:
        vision = _LAST_PHOTO_CONTEXT.get("vision", {})
        photo_desc = vision.get("gen_prompt") or _LAST_PHOTO_CONTEXT.get("description", "")

        await update.message.reply_text("Generando a partir de la foto...", reply_markup=MENU_KEYBOARD)

        def _gen_from_ctx():
            final_prompt = _build_gen_prompt({"gen_prompt": photo_desc}, message)
            logger.info("Photo follow-up gen prompt: %s", final_prompt[:200])
            from tools.image_gen import generate_image
            return generate_image(final_prompt)

        gen_result = await _run_with_typing(update, context, _gen_from_ctx, timeout=120)
        _LAST_PHOTO_CONTEXT.clear()

        if not gen_result:
            await update.message.reply_text("Tardó demasiado. Inténtalo de nuevo.", reply_markup=MENU_KEYBOARD)
        elif gen_result.get("error"):
            await update.message.reply_text(f"Error: {gen_result['error']}", reply_markup=MENU_KEYBOARD)
        else:
            await _send_generated_photo(update, gen_result)
        return

    result = await _run_with_typing(update, context, conversation_mode.process_message, message, timeout=60)

    if result is None:
        await update.message.reply_text("Me quedé pensando demasiado. Vuelve a intentarlo.", reply_markup=MENU_KEYBOARD)
        return

    response_text = None

    if result["type"] in ("chat_reply", "clarification", "direct_answer"):
        response_text = result["response"]
        response_text = await _process_tool_signals(response_text, update, context)
        if response_text:
            await update.message.reply_text(response_text[:4000], reply_markup=MENU_KEYBOARD)

    elif result["type"] == "learn":
        domain = result.get("domain", "desconocido")
        num_bees = result.get("num_bees", 10)
        chat_id = update.effective_chat.id

        await update.message.reply_text(
            f"Iniciando aprendizaje: {domain.upper()}\n"
            f"Desplegando {num_bees} BEES investigadoras en paralelo...\n"
            f"Investigan simultáneamente desde múltiples ángulos. Te mando updates.",
            reply_markup=MENU_KEYBOARD,
        )

        async def _learn_progress(msg: str):
            try:
                await context.bot.send_message(chat_id=chat_id, text=msg[:4000])
            except Exception as e:
                logger.warning("learn progress error: %s", e)

        from memory.learning_engine import learning_engine
        try:
            learn_result = await learning_engine.learn(
                domain=domain,
                num_bees=num_bees,
                progress_callback=_learn_progress,
            )
            level = learn_result.get("expertise_level", 0)
            subtopics = learn_result.get("subtopics_covered", 0)
            facts = learn_result.get("key_facts", [])
            synthesis = learn_result.get("synthesis", "")

            facts_text = "\n".join(f"• {f}" for f in facts[:8])
            response_text = (
                f"Aprendizaje completado: {domain.upper()}\n"
                f"Nivel de expertise: {level}/100\n"
                f"Subtópicos cubiertos: {subtopics}\n\n"
                f"Lo que aprendí:\n{synthesis[:800]}\n\n"
                f"Hechos clave:\n{facts_text}"
            )
            await update.message.reply_text(response_text[:4000], reply_markup=MENU_KEYBOARD)
        except Exception as le:
            logger.error("Learning engine error: %s", le)
            await update.message.reply_text(
                f"Error en aprendizaje de {domain}: {str(le)[:200]}",
                reply_markup=MENU_KEYBOARD,
            )

    elif result["type"] == "autonomous_build":
        goal = result.get("goal", message)
        chat_id = update.effective_chat.id

        await update.message.reply_text(
            f"Builder autónomo activado.\nObjetivo: {goal[:200]}\n\nVoy trabajando — te mando actualizaciones en tiempo real.",
            reply_markup=MENU_KEYBOARD,
        )

        async def _progress(msg: str):
            try:
                await context.bot.send_message(chat_id=chat_id, text=msg[:4000])
            except Exception as pe:
                logger.warning("progress send error: %s", pe)

        from builder.autonomous_builder import autonomous_builder as _ab

        try:
            build_result = await _ab.build(goal=goal, progress_callback=_progress)
            final_text = build_result.get("result", "Construcción completada.")
            phases_ok = build_result.get("phases_completed", 0)
            phases_total = build_result.get("phases_total", 0)
            project = build_result.get("project", "")

            summary = f"Listo. {phases_ok}/{phases_total} fases completadas."
            if project:
                summary += f"\nProyecto: {project}"

            response_text = f"{summary}\n\n{final_text}"[:4000]
            await update.message.reply_text(response_text, reply_markup=MENU_KEYBOARD)
        except Exception as ab_err:
            logger.error("AutonomousBuilder error: %s", ab_err)
            await update.message.reply_text(
                f"El builder encontró un obstáculo: {str(ab_err)[:300]}\nSiguiendo con enfoque alternativo...",
                reply_markup=MENU_KEYBOARD,
            )

    # ── Wallet ───────────────────────────────────────────────────────────────
    elif result["type"] == "wallet":
        await update.message.reply_text("Consultando wallets...", reply_markup=MENU_KEYBOARD)
        try:
            from crypto.wallet_manager import wallet_manager
            from crypto.price_feed import price_feed
            wallet_manager.init_all_wallets()
            balances, prices = await asyncio.gather(
                wallet_manager.get_all_balances(),
                price_feed.get_portfolio_prices(),
            )
            sym_prices = {
                "ETH": prices.get("ETH", {}).get("price", 0),
                "BNB": prices.get("BNB", {}).get("price", 0),
                "SOL": prices.get("SOL", {}).get("price", 0),
                "BTC": prices.get("BTC", {}).get("price", 0),
            }
            report = wallet_manager.format_balances_report(balances, sym_prices)
            await update.message.reply_text(report, reply_markup=MENU_KEYBOARD)
        except Exception as e:
            logger.error("Wallet error: %s", e)
            await update.message.reply_text(f"Error obteniendo wallets: {e}", reply_markup=MENU_KEYBOARD)

    # ── Price / Token info ────────────────────────────────────────────────────
    elif result["type"] == "price":
        token = result.get("token", "BTC,ETH,SOL")
        await update.message.reply_text("Consultando precios...", reply_markup=MENU_KEYBOARD)
        try:
            from crypto.price_feed import price_feed
            from crypto.analysis import analyzer

            # Si parece una dirección de contrato o token de DEX
            if len(token) > 20 and token.replace(".", "").replace("-", "").replace("_", "").isalnum():
                info = await price_feed.get_token_info_dexscreener(token)
                if info:
                    report = price_feed.format_token_info(info)
                    # Intentar análisis técnico si tenemos datos del par
                    pair_addr = info.get("pair_address", "")
                    if pair_addr:
                        cg_id = "solana" if info.get("chain") == "solana" else "ethereum"
                        df = await analyzer.get_ohlcv_coingecko(cg_id, days=3)
                        if df is not None and len(df) >= 20:
                            signal_data = analyzer.generate_signal(df)
                            signal_report = analyzer.format_signal_report(info.get("symbol", token), signal_data, info)
                            report = report + "\n\n" + signal_report
                    await update.message.reply_text(report, reply_markup=MENU_KEYBOARD)
                else:
                    await update.message.reply_text("Token no encontrado en DexScreener.", reply_markup=MENU_KEYBOARD)
            else:
                # Crypto principal
                symbols = [t.strip().upper() for t in token.replace(",", " ").split()]
                if not symbols:
                    symbols = ["BTC", "ETH", "SOL", "BNB"]
                prices = await price_feed.get_prices_coingecko(symbols)
                price_report = price_feed.format_price_report(prices)

                # Añadir análisis técnico
                cg_map = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "BNB": "binancecoin"}
                analysis_parts = []
                for sym in symbols[:2]:
                    cg_id = cg_map.get(sym)
                    if cg_id:
                        df = await analyzer.get_ohlcv_coingecko(cg_id, days=3)
                        if df is not None and len(df) >= 20:
                            signal_data = analyzer.generate_signal(df)
                            analysis_parts.append(analyzer.format_signal_report(sym, signal_data, prices.get(sym)))

                full_report = price_report
                if analysis_parts:
                    full_report += "\n\n" + "\n\n".join(analysis_parts)
                await update.message.reply_text(full_report, reply_markup=MENU_KEYBOARD)
        except Exception as e:
            logger.error("Price error: %s", e)
            await update.message.reply_text(f"Error consultando precios: {e}", reply_markup=MENU_KEYBOARD)

    # ── Trade ─────────────────────────────────────────────────────────────────
    elif result["type"] == "trade":
        side = result.get("side", "BUY")
        token = result.get("token", "")
        amount = result.get("amount", 0.05)
        chat_id_trade = update.effective_chat.id

        await update.message.reply_text(
            f"Ejecutando {side} de {token} por {amount} SOL...",
            reply_markup=MENU_KEYBOARD,
        )
        try:
            from trading.trading_engine import trading_engine
            from trading.risk_manager import risk_manager
            from crypto.wallet_manager import wallet_manager

            wallet_manager.init_all_wallets()
            sol_balance = await wallet_manager.get_balance_solana() or 0

            signal_data = {"signal": side, "confidence": 75, "reason": "Orden manual de Álvaro"}
            token_info = {"price_usd": 0, "liquidity_usd": 999999, "name": token}

            result_trade = await trading_engine.autonomous_trade(
                token_mint=token,
                signal_data=signal_data,
                token_info=token_info,
                portfolio_value_sol=sol_balance,
                is_shitcoin=len(token) > 20,
            )
            report = trading_engine.format_trade_report(result_trade)
            await update.message.reply_text(report, reply_markup=MENU_KEYBOARD)
        except Exception as e:
            logger.error("Trade error: %s", e)
            await update.message.reply_text(f"Error en el trade: {e}", reply_markup=MENU_KEYBOARD)

    # ── PumpFun ────────────────────────────────────────────────────────────────
    elif result["type"] == "pumpfun":
        await update.message.reply_text("Escaneando PumpFun...", reply_markup=MENU_KEYBOARD)
        try:
            from trading.pumpfun import pumpfun_scanner
            opportunities = await pumpfun_scanner.scan_opportunities(min_score=40)
            report = pumpfun_scanner.format_opportunities_report(opportunities)
            await update.message.reply_text(report[:4000], reply_markup=MENU_KEYBOARD)
        except Exception as e:
            logger.error("PumpFun error: %s", e)
            await update.message.reply_text(f"Error escaneando PumpFun: {e}", reply_markup=MENU_KEYBOARD)

    # ── Browser / Screenshot ───────────────────────────────────────────────────
    elif result["type"] == "browser":
        url = result.get("url", "https://dexscreener.com")
        await update.message.reply_text(f"Abriendo {url}...", reply_markup=MENU_KEYBOARD)

        screenshot_ok = False
        try:
            from tools.browser_tool import browser_tool
            screenshot_bytes = await browser_tool.screenshot(url)
            if screenshot_bytes:
                await update.message.reply_photo(
                    photo=screenshot_bytes,
                    caption=f"Screenshot de {url}",
                    reply_markup=MENU_KEYBOARD,
                )
                screenshot_ok = True
        except Exception as e:
            logger.warning("Browser screenshot falló (%s) — usando scraper de texto", e)

        if not screenshot_ok:
            try:
                def _scrape():
                    from tools.url_summarizer import fetch_and_summarize
                    return fetch_and_summarize(url)
                summary = await _run_with_typing(update, context, _scrape, timeout=30)
                await update.message.reply_text(
                    f"{url}\n\n{summary[:3500]}" if summary else f"No pude acceder a {url}.",
                    reply_markup=MENU_KEYBOARD,
                )
            except Exception as e2:
                logger.error("Browser + scraper fallaron: %s", e2)
                await update.message.reply_text(
                    f"No pude abrir {url}. Prueba pegando el link directamente.",
                    reply_markup=MENU_KEYBOARD,
                )

    # ── Trading config ──────────────────────────────────────────────────────────
    elif result["type"] == "trading_config":
        target_cfg = result.get("target", "")
        try:
            from trading.risk_manager import risk_manager
            # Detectar comandos comunes
            if "pausa" in target_cfg.lower() or "desactiva" in target_cfg.lower() or "stop" in target_cfg.lower():
                risk_manager.update_config("enabled", False)
                await update.message.reply_text("Trading autónomo pausado.", reply_markup=MENU_KEYBOARD)
            elif "activa" in target_cfg.lower() or "enciende" in target_cfg.lower() or "reanuda" in target_cfg.lower():
                risk_manager.update_config("enabled", True)
                await update.message.reply_text("Trading autónomo activado.", reply_markup=MENU_KEYBOARD)
            elif "simulaci" in target_cfg.lower() or "dry run" in target_cfg.lower() or "simula" in target_cfg.lower():
                current = risk_manager.config.get("dry_run", False)
                risk_manager.update_config("dry_run", not current)
                mode = "SIMULACION" if not current else "REAL"
                await update.message.reply_text(f"Modo cambiado a {mode}.", reply_markup=MENU_KEYBOARD)
            else:
                report = risk_manager.get_config_report()
                await update.message.reply_text(report, reply_markup=MENU_KEYBOARD)
        except Exception as e:
            await update.message.reply_text(f"Error configurando trading: {e}", reply_markup=MENU_KEYBOARD)

    elif result["type"] == "task":
        orchestrator.initialize()
        output = await _run_with_typing(update, context, orchestrator.process_task, result["task"], timeout=120)
        if output is None:
            await update.message.reply_text("La tarea tardó demasiado. Intenta dividirla en partes más pequeñas.", reply_markup=MENU_KEYBOARD)
        elif output.get("type") == "image" and output.get("local_path"):
            import os as _os
            local_path = output["local_path"]
            revised = output.get("revised_prompt", "")
            caption = f"_{revised[:300]}_" if revised else None
            try:
                with open(local_path, "rb") as img_f:
                    await update.message.reply_photo(
                        photo=img_f,
                        caption=caption,
                        parse_mode="Markdown" if caption else None,
                        reply_markup=MENU_KEYBOARD,
                    )
                _os.unlink(local_path)
            except Exception as img_err:
                logger.error("Error enviando imagen: %s", img_err)
                await update.message.reply_text(f"Generé pero no pude enviar: {img_err}", reply_markup=MENU_KEYBOARD)
        elif output.get("type") == "reminder":
            from tools.reminder import schedule_reminder, parse_duration
            seconds = output.get("seconds", 1800)
            reminder_text = output.get("reminder_text", "")
            chat_id = update.effective_chat.id
            asyncio.create_task(
                schedule_reminder(
                    send_fn=context.bot.send_message,
                    message=reminder_text,
                    seconds=seconds,
                    chat_id=chat_id,
                )
            )
            response_text = output.get("message", "Recordatorio configurado.")
            await update.message.reply_text(response_text, reply_markup=MENU_KEYBOARD)
        else:
            response_text = _format_task_output(output)
            await update.message.reply_text(response_text[:4000], reply_markup=MENU_KEYBOARD)
    else:
        await update.message.reply_text("Listo.", reply_markup=MENU_KEYBOARD)

    # Enviar voz si modo voz está activo
    from tools.tts import is_voice_mode
    if response_text and is_voice_mode():
        await _send_voice_response(update, context, response_text[:800])


BOT_COMMANDS = [
    BotCommand("start",      "Iniciar y saludar a BEEA"),
    BotCommand("menu",       "Abrir menú interactivo completo"),
    BotCommand("ayuda",      "Ver toda la ayuda y capacidades"),
    BotCommand("wallet",     "Ver wallets y balances (BTC/ETH/SOL/Base/BSC)"),
    BotCommand("precio",     "Precio de crypto con análisis técnico"),
    BotCommand("grafico",    "Gráfico de precio como imagen (RSI + Bollinger)"),
    BotCommand("pumpfun",    "Escanear memecoins nuevos en PumpFun"),
    BotCommand("trading",    "Estado del trading autónomo"),
    BotCommand("alerta",     "Ver/configurar alertas de precio"),
    BotCommand("bees",       "Lanzar agentes BEES en paralelo"),
    BotCommand("build",      "Builder autónomo de proyectos"),
    BotCommand("imagen",     "Generar imagen con DALL-E 3"),
    BotCommand("video",      "Generar video con LTX-2 (audio+video)"),
    BotCommand("busca",      "Buscar en internet en tiempo real"),
    BotCommand("traduce",    "Traducir texto a cualquier idioma"),
    BotCommand("qr",         "Generar código QR"),
    BotCommand("yt",         "Resumir video de YouTube"),
    BotCommand("corre",      "Ejecutar código Python"),
    BotCommand("screenshot", "Captura de pantalla de cualquier web"),
    BotCommand("aprende",    "Aprender un tema a fondo con BEES"),
    BotCommand("sabes",      "Ver mi base de conocimiento"),
    BotCommand("sistema",    "Stats del sistema (CPU/RAM/etc)"),
    BotCommand("healer",     "Ver historial de auto-reparaciones"),
    BotCommand("colmena",    "Estado del enjambre de bees (todas vigilan todo)"),
    BotCommand("tasks",      "Ver/gestionar tareas y recordatorios programados"),
    BotCommand("memory",     "Ver/gestionar memoria larga de BEEA"),
    BotCommand("voz",        "Activar/desactivar respuestas por voz"),
]


def _build_app(token: str, webhook: bool = False):
    builder = ApplicationBuilder().token(token)
    if webhook:
        builder = builder.updater(None)
    app = builder.build()

    # Comandos principales
    app.add_handler(CommandHandler("start",      start))
    app.add_handler(CommandHandler("menu",       _cmd_menu_inline))
    app.add_handler(CommandHandler("ayuda",      ayuda))
    app.add_handler(CommandHandler("voz",        vozmode))
    app.add_handler(CommandHandler("vozmode",    vozmode))

    # Crypto & Trading
    app.add_handler(CommandHandler("wallet",     _cmd_wallet))
    app.add_handler(CommandHandler("precio",     _cmd_precio))
    app.add_handler(CommandHandler("pumpfun",    _cmd_pumpfun))
    app.add_handler(CommandHandler("trading",    _cmd_trading))
    app.add_handler(CommandHandler("grafico",    _cmd_grafico))
    app.add_handler(CommandHandler("chart",      _cmd_grafico))
    app.add_handler(CommandHandler("alerta",     _cmd_alerta))

    # IA & Herramientas
    app.add_handler(CommandHandler("imagen",     _cmd_imagen))
    app.add_handler(CommandHandler("video",      _cmd_video))
    app.add_handler(CommandHandler("busca",      _cmd_busca))
    app.add_handler(CommandHandler("traduce",    _cmd_traduce))
    app.add_handler(CommandHandler("qr",         _cmd_qr))
    app.add_handler(CommandHandler("yt",         _cmd_yt))
    app.add_handler(CommandHandler("corre",      _cmd_corre))
    app.add_handler(CommandHandler("screenshot", _cmd_screenshot))

    # BEES & Builder
    app.add_handler(CommandHandler("bees",       _cmd_bees))
    app.add_handler(CommandHandler("hivemind",   _cmd_hivemind))
    app.add_handler(CommandHandler("hibernate",  _cmd_hibernate))
    app.add_handler(CommandHandler("mejoras",    _cmd_mejoras))
    app.add_handler(CommandHandler("autonomo",   _cmd_autonomo))
    app.add_handler(CommandHandler("build",      _cmd_build))
    app.add_handler(CommandHandler("aprende",    _cmd_aprende))
    app.add_handler(CommandHandler("sabes",      _cmd_sabes))
    app.add_handler(CommandHandler("sistema",    _cmd_sistema))
    app.add_handler(CommandHandler("healer",     _cmd_healer))
    app.add_handler(CommandHandler("ghost",      _cmd_ghost))
    app.add_handler(CommandHandler("fantasma",   _cmd_ghost))
    app.add_handler(CommandHandler("colmena",    _cmd_colmena))
    app.add_handler(CommandHandler("bee",        _cmd_bee))
    app.add_handler(CommandHandler("tasks",      _cmd_tasks))
    app.add_handler(CommandHandler("memory",     _cmd_memory))
    app.add_handler(CommandHandler("keys",       _cmd_keys))
    app.add_handler(CommandHandler("apis",       _cmd_keys))
    app.add_handler(CommandHandler("beemode",    _cmd_beemode))
    app.add_handler(CommandHandler("cuotas",     _cmd_cuotas))

    # Inline callbacks
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Media y archivos
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    return app


async def _register_bot_commands(app):
    """Registra los comandos en la interfaz de Telegram (el menú de /)."""
    try:
        await app.bot.set_my_commands(BOT_COMMANDS)
        logger.info("Bot commands registered with Telegram (%d commands)", len(BOT_COMMANDS))
    except Exception as e:
        logger.warning("Could not register bot commands: %s", e)


# ── Webhook mode ───────────────────────────────────────────────

async def _run_webhook(token: str):
    logger.info("Starting in WEBHOOK mode: %s", WEBHOOK_URL)
    bot_app = _build_app(token, webhook=True)

    async def _health(request: web.Request) -> web.Response:
        try:
            status = project_status_tool.get_status()
            project = status.get("current_project")
        except Exception:
            project = None
        return web.json_response({"status": "ok", "mode": "webhook", "project": project})

    async def _webhook(request: web.Request) -> web.Response:
        try:
            data = await request.json()
            update = Update.de_json(data, bot_app.bot)
            await bot_app.process_update(update)
        except Exception as e:
            logger.error("Webhook processing error: %s", e)
        return web.Response(status=200)

    web_app = web.Application()
    web_app.router.add_get("/", _health)
    web_app.router.add_get("/health", _health)
    web_app.router.add_post("/webhook", _webhook)

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info("HTTP server on port %s", PORT)

    async with bot_app:
        await bot_app.start()
        await bot_app.bot.set_webhook(
            url=WEBHOOK_URL,
            drop_pending_updates=True,
            allowed_updates=list(Update.ALL_TYPES),
        )
        logger.info("Webhook registered: %s", WEBHOOK_URL)
        await asyncio.Event().wait()
        await bot_app.bot.delete_webhook()
        await bot_app.stop()

    await runner.cleanup()


# ── Polling mode (development) ─────────────────────────────────

async def _run_polling(token: str):
    logger.info("Starting in POLLING mode (development)")
    RETRY = 15

    logger.info("Health/web panel ya corriendo en Flask puerto 8080")

    # Iniciar loop de aprendizaje autónomo en background
    from memory.auto_learner import auto_learner
    saved_chat_id = _load_chat_id()
    if saved_chat_id:
        _ALVARO_CHAT_ID = saved_chat_id
        logger.info("AutoLearner: chat_id restaurado: %s", saved_chat_id)

    async def _auto_learn_loop():
        await asyncio.sleep(30)
        logger.info("AutoLearner: background loop starting")
        await auto_learner.background_loop()

    _learner_state = Path("memory/learner_enabled.txt")
    if _learner_state.exists() and _learner_state.read_text().strip() == "1":
        asyncio.create_task(_auto_learn_loop())
        logger.info("AutoLearner: background task scheduled")
    else:
        logger.info("AutoLearner: INACTIVO (actívalo con /learner on)")

    # Iniciar wallets y trading autónomo
    try:
        from crypto.wallet_manager import wallet_manager as _wm
        addresses = _wm.init_all_wallets()
        logger.info("Wallets inicializadas: %s", addresses)
    except Exception as _we:
        logger.warning("Wallet init error: %s", _we)

    from trading.autonomous_trader import autonomous_trader

    async def _autonomous_trading_loop():
        await asyncio.sleep(60)  # Espera 1 minuto para que todo cargue
        autonomous_trader.set_notify_fn(_send_autonomous_notification)
        logger.info("AutonomousTrader: iniciando loop (dry_run por defecto)")
        await autonomous_trader.run()

    _trader_state_file = Path("memory/trader_enabled.txt")
    _trader_enabled = _trader_state_file.exists() and _trader_state_file.read_text().strip() == "1"

    if _trader_enabled:
        asyncio.create_task(_autonomous_trading_loop())
        logger.info("AutonomousTrader: background task scheduled (restaurado de estado guardado)")
    else:
        logger.info("AutonomousTrader: INACTIVO (no fue activado por Álvaro)")

    from tools.self_healer import self_healer as _healer
    _healer.set_notify_fn(_send_autonomous_notification)

    async def _healer_loop():
        await _healer.background_loop()

    asyncio.create_task(_healer_loop())
    logger.info("SelfHealer: monitor activo — detecta y repara errores automáticamente")

    from colmena.monitor import colmena as _colmena
    await _colmena.start(num_bees=3, notify_fn=_send_autonomous_notification)
    logger.info("Colmena: 3 bees activas — todas vigilan todo y se resucitan entre sí")

    from tools.unblock_bee import unblock_bee as _ub
    _ub.set_notify(_send_autonomous_notification)
    logger.info("UnblockBee: activa — cuando algo esté bloqueado, ella lo resuelve sola")

    from tools.scheduler import bee_scheduler as _sched
    _sched.set_notify(_send_autonomous_notification)

    async def _scheduler_loop():
        await _sched.background_loop()

    asyncio.create_task(_scheduler_loop())
    logger.info("Scheduler: loop iniciado — recordatorios y alertas de precio activos")

    while True:
        bot_app = _build_app(token)
        try:
            await bot_app.initialize()
            await _register_bot_commands(bot_app)
            await bot_app.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES,
            )
            await bot_app.start()
            logger.info("Polling active — %d commands registered", len(BOT_COMMANDS))
            await asyncio.Event().wait()
        except Conflict:
            logger.warning("409 Conflict — esperando %ss", RETRY)
            await asyncio.sleep(RETRY)
        except (NetworkError, TimedOut) as e:
            logger.warning("Red: %s — reintentando en %ss", e, RETRY)
            await asyncio.sleep(RETRY)
        except Exception as e:
            logger.error("Error inesperado: %s — reintentando en %ss", e, RETRY)
            await asyncio.sleep(RETRY)
        finally:
            try:
                if bot_app.updater and bot_app.updater.running:
                    await bot_app.updater.stop()
                if bot_app.running:
                    await bot_app.stop()
                await bot_app.shutdown()
            except Exception:
                pass


# ── Entry ──────────────────────────────────────────────────────

async def _run():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set")

    discord_token = os.environ.get("DISCORD_BOT_TOKEN")

    if discord_token:
        from discord_bot import run_discord
        logger.info("Iniciando Telegram + Discord en paralelo")
        if USE_WEBHOOK:
            await asyncio.gather(
                _run_webhook(token),
                run_discord(),
                return_exceptions=True,
            )
        else:
            await asyncio.gather(
                _run_polling(token),
                run_discord(),
                return_exceptions=True,
            )
    else:
        if USE_WEBHOOK:
            await _run_webhook(token)
        else:
            await _run_polling(token)


def run():
    asyncio.run(_run())


if __name__ == "__main__":
    run()
