CAPABILITIES = {
    "audio_transcription": {
        "display_name": "Voz Bidireccional — Escucha y Habla",
        "what_it_does": "Transcribe tus audios con Whisper y te responde con su propia voz (TTS). Cuando mandas audio, ella escucha y responde en audio. Modo voz: actívalo para que responda con voz a todo.",
        "triggers": ["enviar audio", "nota de voz", "modo voz"],
        "how_to_use": [
            "Manda un audio o nota de voz → ella escucha y te responde con voz.",
            "activa modo voz → responde con audio a todos tus mensajes de texto.",
            "desactiva modo voz → vuelve solo a texto.",
            "/vozmode → activa/desactiva el modo voz.",
        ],
    },
    "conversation": {
        "display_name": "Conversación Libre",
        "what_it_does": "Habla contigo sobre cualquier tema. Convierte intenciones en tareas. Responde con criterio, no como asistente genérica.",
        "triggers": ["cualquier mensaje de texto libre"],
        "how_to_use": [
            "Escribe lo que quieras. Ella responde.",
        ],
    },
    "project_creation": {
        "display_name": "Construir Proyectos con Código Real",
        "what_it_does": "Genera proyectos completos funcionales — archivos reales en disco, código ejecutable, estructura completa.",
        "triggers": ["construir", "crear proyecto", "build"],
        "how_to_use": [
            "construir bot de telegram",
            "construir backend con FastAPI",
            "build landing page",
            "crear proyecto <nombre>",
        ],
    },
    "swarm": {
        "display_name": "BEES — Agentes Personalizables (hasta 50 en paralelo)",
        "what_it_does": "Lanzas las BEES que quieras para hacer lo que quieras. Tú dices el objetivo, BEEA elige los roles automáticos (planner, coder, researcher, writer, reviewer, tester, architect, data, debugger). Totalmente flexible.",
        "triggers": ["bees", "swarm", "agentes", "dame X bees", "lanza bees"],
        "how_to_use": [
            "dame 5 bees que investiguen los mejores frameworks de Python",
            "lanza 3 bees para escribir artículos de blog sobre fintech",
            "quiero 10 bees que analicen este dataset y me den insights",
            "manda bees a construir el backend de mi app",
            "crea un swarm de 7 bees para revisar mi código",
        ],
    },
    "terminal": {
        "display_name": "Terminal — Ejecución Real de Comandos",
        "what_it_does": "Ejecuta cualquier comando de shell en el sistema real y devuelve la salida exacta.",
        "triggers": ["terminal", "ejecutar", "run"],
        "how_to_use": [
            "terminal ls -la",
            "terminal python bot.py",
            "terminal pip install requests",
            "ejecutar <comando>",
        ],
    },
    "zip_analysis": {
        "display_name": "Análisis de ZIPs",
        "what_it_does": "Extrae, analiza e importa archivos desde ZIPs al workspace activo.",
        "triggers": ["analizar zip", "zip"],
        "how_to_use": [
            "analizar zip ruta/al/archivo.zip",
        ],
    },
    "file_processing": {
        "display_name": "Procesar Archivos y Directorios",
        "what_it_does": "Lee y procesa archivos reales (txt, md, py, json, zip, directorios) y devuelve estructura o preview del contenido.",
        "triggers": ["procesar archivo", "procesa archivo"],
        "how_to_use": [
            "procesar archivo ruta/al/archivo.py",
            "procesar archivo ruta/al/proyecto.zip",
        ],
    },
    "research": {
        "display_name": "Research",
        "what_it_does": "Investiga temas en profundidad usando Wikipedia y fetch de URLs externas.",
        "triggers": ["investiga", "research", "buscar"],
        "how_to_use": [
            "investiga autenticación con JWT",
            "research mejores prácticas FastAPI",
        ],
    },
    "debugging": {
        "display_name": "Debug con IA",
        "what_it_does": "Analiza errores, tracebacks y bugs con IA y propone soluciones concretas.",
        "triggers": ["debug", "error", "bug"],
        "how_to_use": [
            "debug <pega aquí el error o traceback>",
        ],
    },
    "preview": {
        "display_name": "Preview Server Web",
        "what_it_does": "Levanta un servidor HTTP real para ver proyectos generados en el navegador.",
        "triggers": ["preview start", "preview stop"],
        "how_to_use": [
            "preview start",
            "preview stop",
        ],
    },
    "self_modify": {
        "display_name": "Auto-Upgrade de su Propio Código",
        "what_it_does": "Puede proponer y aplicar cambios reales a su propio código con autorización. Úsalo para agregar funciones, corregir comportamientos, mejorar lógica.",
        "triggers": [
            "plan self upgrade", "autorizar self upgrade", "aplicar self upgrade",
            "modifica tu código", "agrega una función", "necesito que modifiques",
        ],
        "how_to_use": [
            "plan self upgrade <qué quieres cambiar>   ← genera el plan",
            "autorizar self upgrade                    ← da permiso de ejecutar",
            "aplicar self upgrade                      ← aplica los cambios",
            "también: 'modifica tu código para hacer X' lo activa automáticamente",
        ],
    },
    "image_generation": {
        "display_name": "Generación de Imágenes Reales con IA",
        "what_it_does": "Genera imágenes reales con DALL-E 3 y te las manda directo en Telegram. No prompts — imágenes reales.",
        "triggers": ["generar imagen", "crea una imagen", "imagen de"],
        "how_to_use": [
            "genera una imagen de un edificio futurista al atardecer",
            "crea una imagen de mi logo: fondo negro, texto BEEA en dorado",
            "imagen de un robot construyendo código",
        ],
    },
    "status": {
        "display_name": "Status del Sistema",
        "what_it_does": "Muestra el estado en tiempo real del sistema: proyecto activo, agentes en swarm, tareas en cola, proyectos creados.",
        "triggers": ["status", "estado del sistema"],
        "how_to_use": [
            "status",
        ],
    },
    "panel": {
        "display_name": "Panel Web Visual",
        "what_it_does": "Abre un panel web visual con el estado completo del sistema.",
        "triggers": ["panel start"],
        "how_to_use": [
            "panel start",
        ],
    },
    "crypto_wallets": {
        "display_name": "Wallets Crypto (BTC, ETH, Base, BSC, Solana)",
        "what_it_does": "Tengo mis propias wallets en 5 chains. Puedo ver balances en tiempo real con precios actuales. Las claves privadas son mías y están guardadas de forma segura.",
        "triggers": ["mis wallets", "wallet", "billetera", "cuánto tengo", "balance", "dirección", "address"],
        "how_to_use": [
            "mis wallets → balances de todas las chains con precio en USD",
            "mi dirección de solana → te doy la dirección para que puedas enviar fondos",
            "!wallet en Discord → lo mismo",
        ],
    },
    "real_time_prices": {
        "display_name": "Precios en Tiempo Real + Análisis Técnico",
        "what_it_does": "Consulta precios de cualquier crypto o token de DEX. Para las principales (BTC, ETH, SOL, BNB) añado análisis técnico real: RSI, MACD, Bollinger Bands, EMAs, señal de compra/venta con porcentaje de confianza.",
        "triggers": ["precio de", "cuánto vale", "cómo está", "análisis de", "qué vale"],
        "how_to_use": [
            "precio de bitcoin → precio + RSI + MACD + señal",
            "precio de sol → precio de Solana con análisis técnico",
            "precio de [dirección del token] → info completa del token en DexScreener",
            "!precio BTC en Discord",
        ],
    },
    "autonomous_trading": {
        "display_name": "Trading Autónomo 100% (Solana + PumpFun)",
        "what_it_does": "Hago trading completamente sola. Escaneo mercados cada 5 minutos, analizo señales técnicas, ejecuto swaps en Solana via Jupiter (mejor precio), gestiono stop loss y take profit automático. También escaneo PumpFun cada 3 minutos buscando memecoins con alto potencial. Te notifico cada trade en tiempo real.",
        "triggers": ["estado del trading", "trading autónomo", "posiciones", "pnl", "ganancias", "pérdidas"],
        "how_to_use": [
            "estado del trading → ver scans, trades ejecutados, P&L, posiciones abiertas",
            "pausa el trading → detener operaciones",
            "activa el trading → reanudar",
            "modo simulación → activar/desactivar dry run (sin dinero real)",
            "configura el stop loss al 3% → cambiar parámetros de riesgo",
        ],
    },
    "pumpfun_scanner": {
        "display_name": "Scanner de PumpFun — Memecoins Solana",
        "what_it_does": "Escaneo PumpFun en tiempo real buscando memecoins con alto potencial. Evalúo cada token con un score 0-100 basado en market cap, liquidez, holders, actividad social, redes sociales presentes, y señales de rug. Los mejores los reporto y puedo comprarlos automáticamente.",
        "triggers": ["pumpfun", "pump.fun", "memecoins", "shitcoins", "tokens nuevos", "sniper"],
        "how_to_use": [
            "qué hay en pumpfun → top oportunidades con score",
            "escanea memecoins → mismo pero con más detalle",
            "!pumpfun en Discord",
        ],
    },
    "risk_management": {
        "display_name": "Gestión de Riesgo Configurable",
        "what_it_does": "Sistema de riesgo completo: posición máxima por trade, stop loss automático, take profit automático, límite de pérdida diaria, máximo de posiciones abiertas, confianza mínima de señal. Todo configurable por Álvaro.",
        "triggers": ["riesgo", "stop loss", "take profit", "configurar trading", "límites"],
        "how_to_use": [
            "configura el trading → ver configuración actual",
            "cambia el stop loss al 3% → ajustar stop loss",
            "pon el máximo por posición al 5% → ajustar tamaño",
            "activa modo simulación → probar sin dinero real",
        ],
    },
    "browser_automation": {
        "display_name": "Browser Autónomo con Screenshots",
        "what_it_does": "Tengo mi propio browser (Playwright). Puedo navegar a cualquier URL, tomar screenshots reales y mandártelos por Telegram/Discord. Útil para ver charts de DexScreener, tokens en PumpFun, cualquier web.",
        "triggers": ["screenshot de", "abre", "navega a", "mira la web", "captura de", "dexscreener", "birdeye"],
        "how_to_use": [
            "screenshot de dexscreener.com/solana → captura del chart",
            "abre pump.fun y dime qué ves → navego y describo",
            "screenshot de [cualquier URL] → imagen real de la web",
            "!screenshot <url> en Discord",
        ],
    },
    "multi_model_routing": {
        "display_name": "Multi-Model AI Routing (Groq + OpenAI)",
        "what_it_does": "Enruto automáticamente cada tarea al mejor modelo de IA: Groq Llama3-8b para respuestas ultra-rápidas (<1s), Groq Llama3-70b para análisis, GPT-4o para tareas complejas y código. Fallback automático si un proveedor falla.",
        "triggers": ["automático — no requiere intervención"],
        "how_to_use": [
            "Transparente — simplemente pregunta y yo elijo el modelo óptimo.",
            "Conversación simple → Groq (ultra-rápido)",
            "Análisis de trading → Groq 70b",
            "Construcción de proyectos, código complejo → GPT-4o",
        ],
    },
    "autonomous_learning": {
        "display_name": "Aprendizaje Autónomo Continuo",
        "what_it_does": "Aprendo sola cada 30 minutos. Después de cada conversación detecta los temas que surgieron y si mi expertise es bajo (<30/100) los encolo para estudiarlos. Uso BEES reales con búsquedas web reales para investigar. Te notifico cuando termino de aprender algo nuevo.",
        "triggers": ["aprende", "estudia", "vuélvete experta", "qué sabes", "cuánto sabes"],
        "how_to_use": [
            "aprende trading con 20 bees → estudio profundo inmediato",
            "estudia DeFi → lo agrego a la cola de aprendizaje",
            "qué sabes → ver mi base de conocimiento actual con niveles de expertise",
        ],
    },
}


def explain_capability(name: str):
    data = CAPABILITIES.get(name)
    if not data:
        return {
            "error": f"capability '{name}' not found",
            "available": list(CAPABILITIES.keys()),
        }
    return {"name": name, **data}


def build_capabilities_block() -> str:
    lines = ["MIS FUNCIONES (completas y actualizadas automáticamente):\n"]
    for key, cap in CAPABILITIES.items():
        name = cap.get("display_name", key)
        desc = cap.get("what_it_does", "")
        usage = cap.get("how_to_use", [])
        lines.append(f"▸ {name}")
        lines.append(f"  {desc}")
        if usage:
            for u in usage:
                lines.append(f"  → {u}")
        lines.append("")
    return "\n".join(lines)
