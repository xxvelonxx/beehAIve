# BEEA — Bot IA de Álvaro (@xxvelonxx)

Bot de inteligencia artificial con personalidad propia corriendo en Telegram y Discord simultáneamente. Creado por y para Álvaro. Leal solo a él.

---

## REGLAS DEL AGENTE (leer siempre)

- **GUARDAR / SAVE / GUARDA LA CONVERSACIÓN** → Cuando Álvaro diga algo así, actualizar TODOS estos archivos con el estado actual del proyecto:
  1. `replit.md` — arquitectura, features, stack
  2. `docs/BEEA_GUIA_COMPLETA.md` — guía de funciones y uso real
  3. `docs/BEEA_MONETIZACION.md` — cómo hacer dinero con BEEA
  4. Hacer commit de todo y push al repo GitHub `beehAIve`
- **REPLICATE PROHIBIDO** — Nunca usar Replicate para imágenes. Cascada: BFL/FLUX.2 → Stable Horde → FAL/FLUX.2 → Together/FLUX.2 → getimg → Prodia → HuggingFace/FLUX.2-klein → DALL-E.
- **NUNCA inventar números** — capacidad de BEEs, keys disponibles, etc. siempre leer el estado real del sistema.
- **NUNCA auto-iniciar features** sin orden explícita de Álvaro.
- **Regla absoluta de honestidad** — BEEA no miente sobre lo que ve (fotos, datos, capacidad).
- **Repo GitHub**: `beehAIve` — Álvaro tiene token en `GITHUB_TOKEN_ALVARO`.

---

## Stack

- **Python 3.11** — lenguaje principal
- **python-telegram-bot 22.6** — Telegram
- **discord.py 2.7** — Discord
- **OpenAI** — GPT-4o / DALL-E 3 / Whisper
- **Groq** — Llama 3.1/3.3 (respuestas rápidas, fallback a OpenAI si 429)
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

---

## Variables de entorno requeridas

| Variable | Descripción | Estado |
|---|---|---|
| `DISCORD_BOT_TOKEN` | Bot Discord | ✅ |
| `OPENAI_API_KEY` | OpenAI GPT-4o + DALL-E 3 | ✅ |
| `GROQ_API` | Groq — Llama rápido | ✅ |
| `TOG_API1`…`TOG_API5` | Together AI — 4 claves válidas (LLM + FLUX imágenes) | ✅ |
| `CEREBRAS_API`…`CEREBRA_API12` | Cerebras — **15 claves → 750 rpm** (ultra-rápido, sin límite diario) | ✅ |
| `GEMINI_API`/`2`/`3`/`5` | Gemini Flash — 4 claves → 40 rpm, 1.400/día | ✅ |
| `ANTHROPIC_API_KEY` | Claude (backup) | ✅ |
| `FAL_API_KEY` | fal.ai — FLUX.2 imágenes + LTX-2 video | ✅ |
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
  llm_adapter.py            — routing inteligente OpenAI/Groq/Anthropic
  bypass_engine.py          — motor de bypass automático de restricciones
  image_gen.py              — generación de imágenes (Stable Horde → FAL → Together → getimg → Prodia → HF → DALL-E)
  image_providers.py        — proveedores alternativos de imagen (FAL, Together, HuggingFace, etc.)
  video_gen.py              — generación de video LTX-2 (fal.ai/LTX-2 → fal.ai/LTX-Video → Wan-2.1 → HF)
  browser_tool.py           — Playwright, screenshots reales
  capabilities.py           — lista de capacidades para el system prompt
  code_sandbox.py           — ejecución de código Python
  websearch.py              — búsqueda web (DuckDuckGo/DDGS)
  qr_generator.py           — generación de QR
  pdf_reader.py             — lectura y análisis de PDFs
  self_modify.py            — auto-modificación de código
  zip_analyzer.py           — análisis de archivos ZIP

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
  swarm_manager.py          — gestor de hasta 50 BEES en paralelo
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

## Comandos Telegram (22 registrados)

`/start` `/menu` `/ayuda` `/wallet` `/precio` `/grafico` `/pumpfun` `/trading` `/alerta` `/bees` `/build` `/imagen` `/busca` `/traduce` `/qr` `/yt` `/corre` `/screenshot` `/aprende` `/sabes` `/sistema` `/voz`

## Comandos Discord

`!ayuda` `!panel` `!wallet` `!precio` `!grafico` `!pumpfun` `!trading` `!alerta` `!compra` `!vende` `!screenshot` `!bees` `!aprende` `!sabes` `!build` `!imagen` `!busca` `!traduce` `!qr` `!yt` `!corre` `!sistema` `!setup`

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

El interceptor `_process_tool_signals()` en `telegram_bot.py` detecta estas señales, ejecuta las herramientas y entrega el resultado real antes de enviar la respuesta.

---

## Sistema de bypass de restricciones

`tools/bypass_engine.py` — cuando cualquier API bloquea un request:
1. Reescribe el prompt con hasta 5 variantes automáticas
2. Prueba con framing artístico, descripción indirecta, etc.
3. Cambia de proveedor (Groq ↔ OpenAI) automáticamente
4. Para imágenes: Replicate/Flux primero, luego cascada de proveedores
5. Siempre entrega resultado o error técnico honesto — nunca discurso moral

`personality_profile.py` — `is_forbidden_response()` detecta y bloquea cualquier texto de asistente genérico antes de que llegue a Álvaro.

---

## Trading autónomo

- **INACTIVO por defecto** — requiere activación explícita de Álvaro
- Cuando activo: escanea cada 5min, PumpFun cada 3min
- Auto-compra si score PumpFun ≥ 75
- Riesgo: max 10% por posición, stop loss 5%, take profit 15%
- Estado persistido en `memory/trader_enabled.txt`

---

## Generación de imágenes — FLUX.2 + cascada

**REGLA ABSOLUTA**: Sin Replicate. `tools/image_providers.py` cascada en orden:

| # | Proveedor | Modelo | Clave |
|---|-----------|--------|-------|
| 0 | BFL API | FLUX.2-dev / FLUX.2-klein / FLUX.1-Pro | BFL_API_KEY |
| 1 | Stable Horde | SD multi-modelo NSFW | gratis |
| 2 | fal.ai | FLUX.2-dev / FLUX.2-klein / FLUX.1-schnell | FAL_KEY |
| 3 | Together AI | FLUX.2-schnell-Free / FLUX.1-schnell-Free | TOG_API1-5 |
| 4 | getimg.ai | SDXL adult ON | GETIMG_API_KEY |
| 5 | Prodia | DreamShaper NSFW | PRODIA_API_KEY |
| 6 | HuggingFace | FLUX.2-klein-4B / FLUX.1-schnell / SDXL | HF_TOKEN |
| 7 | DALL-E 3 | con auto-bypass de prompt | OPENAI_API_KEY |

Para añadir FLUX.2 máxima calidad: añadir `BFL_API_KEY` como secreto (registrarse en https://api.bfl.ai)

---

## Generación de Video — LTX-2

`tools/video_gen.py` — cascada:
1. **LTX-2 via fal.ai** — audio+video sincronizado, mejor calidad (FAL_KEY requerido)
2. **LTX-Video via fal.ai** — solo video, alta calidad (FAL_KEY)
3. **Wan-2.1 via fal.ai** — open source alternativo (FAL_KEY)
4. **HuggingFace** — gratuito, menor calidad

Comando: `/video <descripción> [3|5|8|10]`
Sin FAL_KEY → mensaje con instrucciones para conseguirla gratis en fal.ai

---

## Visión de fotos sin censura — Cascada completa

`_try_qwen_vision()` + `_analyze_photo_b64()` en `telegram_bot.py`:
1. **Qwen2-VL-72B-Instruct-Turbo** via Together AI (sin censura — solo keys `tgp_v1_`)
2. **Qwen2.5-VL-72B** via Together AI
3. **Groq llama-3.2-90b-vision-preview** (gratis, baja censura) — AÑADIDO 10 Mar
4. **Qwen2-VL-7B** via HuggingFace
5. **GPT-4o** fallback
6. **GPT-4o-mini** fallback ligero

Bug corregido 10 Mar: Together filtraba keys expiradas (`key_CYtubx...`). Ahora solo acepta `tgp_v1_` prefix.
Bug corregido 10 Mar: LLM de chat añadía disclaimers de visión. Prompt reforzado con instrucción explícita.

Siempre retorna description (español) + gen_prompt (inglés para imágenes nuevas).

---

## Handler de fotos con visión IA

`handle_photo` en `telegram_bot.py`:
- Cuando Álvaro manda una foto: Qwen2-VL (primero) o GPT-4o la analiza sin censura
- Si el caption tiene keywords de generación → genera imagen nueva
- Descripción guardada en `_LAST_PHOTO_CONTEXT` para mensajes siguientes
- Si no hay instrucción → BEEA comenta la foto naturalmente

---

## Formato de salida del orquestador

`_format_task_output()` en `telegram_bot.py` — extrae contenido legible de cualquier resultado del orquestador:
- Busca `message` → `full_analysis` → `analysis` → `result` → `error`
- Errores técnicos comunes → respuesta natural en español
- Nunca muestra dicts Python crudos al usuario

---

## Capacidad del enjambre (estado actual — 10 Mar 2026)

| Proveedor | Claves | RPM total | Límite diario |
|-----------|--------|-----------|---------------|
| **Cerebras** | **15** | **750 rpm** | Sin límite — columna vertebral |
| Together | 4 | 60 rpm | 8,000/día |
| Gemini | 4 | 40 rpm | 1,400/día |
| Groq | 1 | 25 rpm | 90/día |
| OpenAI | 1 | 50 rpm | Sin límite |
| Anthropic | 1 | 10 rpm | Sin límite |
| **TOTAL** | **26** | **935 rpm** | — |

**Modos del enjambre:**
- `idle` (DEFAULT) — 0 BEEs entrenando, toda la cuota libre para Álvaro
- `economico` — 5 BEEs, 5 rpm
- `normal` — 25 BEEs, 25 rpm
- `full` — 126 BEEs, 126 rpm (objetivo)
- `burst` — 249 BEEs, manual solo

**Matemática FULL:** 126 BEEs × 1 rpm = 126 rpm ≪ 750 rpm disponibles → **83% margen libre**

**Imágenes:** BFL FLUX.2 (2 claves) + FAL.ai (1 clave) — cascada sin Replicate

---

## Para reconstruir desde cero

1. Descargar todos los archivos del proyecto Replit
2. Instalar dependencias: `pip install -e .` (pyproject.toml tiene todo)
3. Configurar las variables de entorno (ver tabla arriba)
4. Instalar Playwright: `playwright install chromium`
5. Ejecutar: `python bot.py`
