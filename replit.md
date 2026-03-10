# BEEA — Bot IA de Álvaro (@xxvelonxx)

Bot de inteligencia artificial con personalidad propia corriendo en Telegram y Discord simultáneamente. Creado por y para Álvaro. Leal solo a él.

---

## REGLAS DEL AGENTE (leer siempre)

- **GUARDAR / SAVE / GUARDA LA CONVERSACIÓN** → Cuando Álvaro diga algo así, actualizar TODOS estos archivos con el estado actual del proyecto:
  1. `replit.md` — arquitectura, features, stack
  2. `docs/BEEA_GUIA_COMPLETA.md` — guía de funciones y uso real
  3. `docs/BEEA_MONETIZACION.md` — cómo hacer dinero con BEEA
  4. Hacer commit de todo y push al repo GitHub `beehAIve`
- **REPLICATE PROHIBIDO** — Nunca usar Replicate para imágenes. Cascada REAL (orden del código): FAL/FLUX.2 → BFL/FLUX.2 → Together/FLUX.2 → getimg → Prodia → HuggingFace/FLUX.2-klein → Stable Horde → DALL-E.
- **NUNCA inventar números** — capacidad de BEEs, keys disponibles, etc. siempre leer el estado real del sistema.
- **NUNCA auto-iniciar features** sin orden explícita de Álvaro.
- **Regla absoluta de honestidad** — BEEA no miente sobre lo que ve (fotos, datos, capacidad).
- **Repo GitHub**: `beehAIve` — Álvaro tiene token en `GITHUB_TOKEN_ALVARO`.

---

## Stack

- **Python 3.11** — lenguaje principal
- **python-telegram-bot 22.6** — Telegram
- **discord.py 2.7** — Discord
- **Puter.com** — proxy GRATIS a Claude Sonnet 4 / Claude Opus 4 / GPT-4o (5 tokens rotando)
- **OpenAI** — GPT-4o / DALL-E 3 / Whisper
- **Groq** — Llama 3.1/3.3 (respuestas rápidas, fallback)
- **BFL API** — FLUX.2-dev (32B) / FLUX.2-klein — máxima calidad de imagen
- **fal.ai** — FLUX.2 + LTX-2 video (audio+video sincronizado)
- **Gemini Flash** — 4 claves (GEMINI_API/2/3/5)
- **web3 / solders / bit** — wallets crypto (ETH, Base, BSC, Solana, BTC)
- **ta / pandas / matplotlib / mplfinance** — análisis técnico + charts
- **Playwright** — browser automation + screenshots

---

## Arranque

```bash
python bot.py
```

El bot corre Telegram en polling mode + Discord en paralelo. Ambos comparten el mismo `conversation_mode` (misma memoria, mismos intents).

Keep-alive 24/7 gratis via UptimeRobot pinging `/ping` cada 5 minutos.

---

## Variables de entorno requeridas

| Variable | Descripción | Estado |
|---|---|---|
| `PUTER_TOKEN`…`PUTER_TOKEN6` | Puter.com — Claude Sonnet 4 / Opus 4 / GPT-4o GRATIS (5 tokens activos) | ✅ |
| `DISCORD_BOT_TOKEN` | Bot Discord | ✅ |
| `OPENAI_API_KEY` | OpenAI GPT-4o + DALL-E 3 | ✅ |
| `GROQ_API` | Groq — Llama rápido | ✅ |
| `TOG_API1`…`TOG_API5` | Together AI — 4 claves válidas (LLM + FLUX imágenes) | ✅ |
| `CEREBRAS_API`…`CEREBRA_API14` | Cerebras — **19 claves → 950 rpm** (ultra-rápido, sin límite diario) | ✅ |
| `GEMINI_API`/`2`/`3`/`5` | Gemini Flash — 4 claves → 40 rpm, 1.400/día | ✅ |
| `ANTHROPIC_API_KEY` | Claude (backup) | ✅ |
| `FAL_KEY` / `FAL_API_KEY` | fal.ai — FLUX.2 imágenes + LTX-2 video | ✅ |
| `BFL_API_KEY` + `BFL_API_KEY2` | BFL API — FLUX.2-dev 32B (2 claves) | ✅ |
| `SESSION_SECRET` | Web panel Flask | ✅ |
| `GITHUB_TOKEN_ALVARO` | Push al repo beehAIve | ✅ |

---

## Estructura de archivos

```
bot.py                      — entry point, arranca Telegram + Discord
telegram_bot.py             — bot de Telegram (polling + webhook)
discord_bot.py              — bot de Discord
conversation_mode.py        — router de intents (shared entre Telegram y Discord)
personality_profile.py      — personalidad, system prompt, filtro de respuestas prohibidas
config.py                   — configuración global

core/
  ai_chat.py                — wrapper de chat con bypass automático de restricciones
  logger.py                 — logger centralizado
  state.py                  — estado global del proyecto

tools/
  llm_adapter.py            — routing inteligente: Puter→Cerebras→Together→Groq→Gemini→OpenAI
  bypass_engine.py          — motor de bypass automático de restricciones
  image_gen.py              — generación de imágenes (FAL/FLUX.2 primero → BFL → Together → Stable Horde → DALL-E)
  image_providers.py        — proveedores de imagen: FAL → BFL → Together → getimg → Prodia → HF → StableHorde
  video_gen.py              — generación de video LTX-2 (fal.ai/LTX-2 → fal.ai/LTX-Video → Wan-2.1 → HF)
  browser_tool.py           — Playwright, screenshots reales
  capabilities.py           — lista de capacidades para el system prompt
  code_sandbox.py           — ejecución de código Python
  websearch.py              — búsqueda web (DuckDuckGo/DDGS)
  qr_generator.py           — generación de QR
  pdf_reader.py             — lectura y análisis de PDFs
  self_modify.py            — auto-modificación de código
  zip_analyzer.py           — análisis de archivos ZIP

web_panel/
  app.py                    — panel web Flask (puerto 8080)
                              /ping  → keep-alive para UptimeRobot (público, sin auth)
                              /health → alias de /ping

crypto/
  wallet_manager.py         — wallets BTC/ETH/Base/BSC/Solana
  price_feed.py             — precios en tiempo real (CoinGecko + DexScreener)
  analysis.py               — RSI, MACD, Bollinger Bands, señales técnicas

trading/
  trading_engine.py         — Jupiter swaps en Solana
  pumpfun.py                — scanner de memecoins (score 0-100)
  risk_manager.py           — gestión de riesgo
  autonomous_trader.py      — trader autónomo (requiere activación explícita)
  price_alerts.py           — alertas de precio
  chart_generator.py        — gráficos candlestick PNG

memory/
  knowledge_base.py         — base de conocimiento persistente
  memory_store.py           — memoria de conversaciones
  learning_engine.py        — aprendizaje profundo con BEES
  auto_learner.py           — aprendizaje autónomo (requiere activación explícita)
  learner_enabled.txt       — existe y contiene "1" solo si el learner está activo

swarm/
  swarm_manager.py          — gestor de hasta 1000 BEES en paralelo
  agent_worker.py           — worker individual de BEE
  bee_roles.py              — roles: planner, coder, researcher, etc.

orchestration/
  orchestrator.py           — orquestador principal de tareas
  planner.py                — planificador de fases
  task_router.py            — enrutador de tareas

builder/
  autonomous_builder.py     — builder autónomo (solo con /build o botón 🏗️)
  no_limit_solver.py        — solver sin límites
```

---

## Wallets generadas (en memory/beea_wallets.json)

| Red | Dirección |
|---|---|
| ETH | `0x76ACfBb578f14cB6108107663C8FF22BE515edd0` |
| Base | `0x5Ad62254c428e5CF97F07D5F181f660C77b74c4e` |
| BSC | `0xb99F37abE395B525F9651Fc9BA449699b4472Cac` |
| Solana | `ApsczVHC9eEgvYh2WBww5V2aBxaMSFAMyLM1ouG78bwR` |
| BTC | `15M8kdCRkMq3wyo2iXNzVogK3XxGDxDdtm` |

---

## Comandos Telegram (27 registrados)

`/start` `/menu` `/ayuda` `/wallet` `/precio` `/grafico` `/pumpfun` `/trading` `/alerta` `/bees` `/build` `/imagen` `/busca` `/traduce` `/qr` `/yt` `/corre` `/screenshot` `/aprende` `/sabes` `/sistema` `/voz` `/hivemind` `/beemode` `/cuotas` `/keys` `/autonomo`

## Comandos Discord

`!ayuda` `!panel` `!wallet` `!precio` `!grafico` `!pumpfun` `!trading` `!alerta` `!compra` `!vende` `!screenshot` `!bees` `!aprende` `!sabes` `!build` `!imagen` `!busca` `!traduce` `!qr` `!yt` `!corre` `!sistema` `!setup`

---

## Capacidad del enjambre (estado actual — 10 Mar 2026)

| Proveedor | Tokens/Claves | RPM total | Límite diario | Rol |
|-----------|--------------|-----------|---------------|-----|
| **Puter** | **5 tokens** | **sin límite publicado** | Sin límite | Claude Opus 4 / Sonnet 4 / GPT-4o GRATIS |
| **Cerebras** | **19 claves** | **950 rpm** | Sin límite | Columna vertebral BEEs 24/7 |
| Together | 4 | 60 rpm | 8.000/día | Backup + visión Qwen sin censura |
| Gemini | 4 | 40 rpm | 1.400/día | Contexto largo |
| Groq | 1 | 25 rpm | 90/día | Velocidad + tool-use |
| OpenAI | 1 | 50 rpm | Sin límite | GPT-4o + DALL-E fallback |
| Anthropic | 1 | 10 rpm | Sin límite | Claude backup pago |

**BEEs sostenibles 24/7:**
- Garantizadas: **950** (solo Cerebras, 19 claves × 50 rpm)
- Probables: **1200+** (Cerebras 950 + Puter overflow 250)

**Routing inteligente:**
- Análisis / código / razonamiento → **Puter Claude Sonnet 4** (gratis)
- BEEs en bulk → **Cerebras** (950 rpm garantizados)
- Overflow y fallback → **Puter GPT-4o-mini** (gratis)

**Keep-alive 24/7 gratis:**
- UptimeRobot pinga `/ping` cada 5 min → bot nunca duerme

---

## REGLA ABSOLUTA — Nada arranca solo

Ningún proceso autónomo arranca sin que Álvaro lo active explícitamente:

| Proceso | Estado por defecto | Cómo activar |
|---|---|---|
| AutoLearner | INACTIVO | `/learner on` |
| AutonomousTrader | INACTIVO | `/trading start` o "activa el trader" |
| Builder Autónomo | INACTIVO | `/build <objetivo>` o botón 🏗️ |

Estado persistido en archivos:
- `memory/trader_enabled.txt` — contiene "1" si activo
- `memory/learner_enabled.txt` — contiene "1" si activo

---

## Sistema de herramientas — Señales de BEEA

BEEA puede activar sus herramientas directamente desde el chat usando señales:

| Señal en respuesta | Efecto |
|---|---|
| `[IMG: descripción en inglés]` | Genera imagen real y la envía como foto |
| `[SEARCH: consulta]` | Busca en internet y añade resultados |
| `[CODE: código python]` | Ejecuta código y añade output |

---

## LLM Routing — Puter primero

`tools/llm_adapter.py` — prioridad real:

| Tarea | Proveedor | Modelo | Coste |
|---|---|---|---|
| Análisis / código / razonamiento | Puter | Claude Sonnet 4 | Gratis |
| Creatividad / escritura profunda | Puter | Claude Opus 4 | Gratis |
| BEEs en bulk (750+) | Cerebras | llama 3.3 | Gratis |
| Overflow BEEs (251-1000) | Puter | GPT-4o-mini | Gratis |
| Contexto largo (>32K) | Gemini Flash | gemini-2.0-flash | Gratis |
| Tool-use / function calling | Groq | llama3-groq-70b | Gratis |
| Imágenes | BFL FLUX.2-dev | — | $0.03/img |

---

## Para reconstruir desde cero

1. Descargar todos los archivos del proyecto Replit
2. Instalar dependencias: `pip install -e .` (pyproject.toml tiene todo)
3. Configurar las variables de entorno (ver tabla arriba)
4. Instalar Playwright: `playwright install chromium`
5. Ejecutar: `python bot.py`
6. Configurar UptimeRobot con `/ping` endpoint para keep-alive 24/7
