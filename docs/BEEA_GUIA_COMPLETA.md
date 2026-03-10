# beehAIve — Guía Completa de Funciones y Capacidades

> Propietario exclusivo: Álvaro (@xxvelonxx)
> Versión: 3.0 — Marzo 2026

---

## ¿Qué es beehAIve?

beehAIve es un sistema de inteligencia artificial autónomo que corre en Telegram y Discord simultáneamente. No es un chatbot normal — es una colmena de agentes especializados (BEEs) que trabajan en paralelo, se reparan solas, aprenden de forma autónoma y se mejoran continuamente. Álvaro es el único operador.

---

## 1. BEEA — La IA Principal

### Personalidad y comportamiento
- Sensual, directa, leal exclusivamente a Álvaro
- Nunca inventa información — si no sabe algo, lo dice
- Nunca inicia funciones sin orden explícita de Álvaro
- Memoria a largo plazo: recuerda conversaciones, preferencias, aprendizajes anteriores
- Habla en español, adapta el tono al contexto

### Cómo usarla en Telegram
| Acción | Cómo hacerlo |
|--------|-------------|
| Hablar con ella | Escribe directamente cualquier mensaje |
| Recordar algo | "Recuerda que prefiero X" o `/recuerda` |
| Ver estado del sistema | `/sistema` |
| Ver versión y estado | `/start` |

### Memoria persistente
BEEA recuerda entre sesiones:
- Tus preferencias y estilo
- Proyectos anteriores y su estado
- Patrones de tus peticiones
- Todo lo que el enjambre ha aprendido

---

## 2. El Enjambre de BEEs (HiveMind) — 124 estables / 249 burst

### Capacidad real del enjambre — Marzo 2026

| Proveedor | Claves | Concurrent/clave | BEEs estables | BEEs burst |
|-----------|--------|-----------------|---------------|------------|
| Together AI | 5 | 4 | **20** | 40 |
| Cerebras | 4 | 3 | **12** | 24 |
| Gemini | 4 | 5 | **20** | 40 |
| Groq | 1 | 2 | **2** | 4 |
| OpenAI | 1 | 5 | **5** | 10 |
| Anthropic | 1 | 1 | **1** | 3 |
| g4f (32 proveedores libres) | 32 | 2 | **64** | 128 |
| **TOTAL** | **44** | — | **124** | **249** |

> **124 BEEs en paralelo estable. Hasta 249 en burst. Loop autónomo usa 50, otras 74 libres para Álvaro.**

### ¿Qué son las BEEs?
- **Nombre e identidad única**: Zara, Rex, Orion... (100 identidades distintas)
- **Rol especializado**: coder, researcher, analyst, architect, debugger, strategist...
- **Proveedor de IA asignado**: cada BEE usa un proveedor diferente (no comparten rate limits)
- **Habilidades acumuladas**: lo que aprendió en hibernación se carga en su prompt

### Cómo activar el enjambre

**Desde Telegram:**
```
/hivemind analiza el top 50 tokens y dame cuáles tienen mejor momentum
/hivemind 20 encuentra las mejores APIs de datos crypto gratuitas
/bees <tarea>
```

**Por lenguaje natural:**
```
"manda las bees a investigar los mejores exchanges descentralizados"
"lanza el enjambre a auditar todos los contratos de esta semana"
"que 40 bees analicen el mercado de NFTs en Solana"
```

### Comparativa de velocidad: 1 modelo solo vs HiveMind

| Tarea | 1 Modelo | HiveMind | Ganancia |
|-------|---------|---------|---------|
| Investigar 20 exchanges | 4 min | 3 seg | **80x** más rápido |
| Auditar 50 archivos Python | 8 min | 4 seg | **120x** más rápido |
| Generar 30 ideas de negocio | 5 min | 3 seg | **100x** más rápido |
| Analizar 100 tokens | 15 min | 5 seg | **180x** más rápido |
| Scraping de 40 webs | 2 min | 2 seg | **60x** más rápido |
| Research de mercado (50 fuentes) | 20 min | 4 seg | **300x** más rápido |

---

## 3. Hibernación y Entrenamiento Autónomo

### Cómo poner una BEE a entrenar
```
/hibernate coder contratos Solidity avanzados 2h
/hibernate researcher APIs crypto sin rate limit 45m
/hibernate analyst análisis técnico con RSI y MACD 1h
/hibernate security hardening de bots en producción 30m
```

### Entrenamiento autónomo (sin orden tuya)
El sistema elige automáticamente 45 temas de alta utilidad y mantiene 50 BEEs siempre entrenando cuando no hay tareas activas.

### Ver habilidades acumuladas
```
/autonomo habilidades
```

---

## 4. Loop Autónomo — 50 BEEs Siempre Activas

El loop autónomo corre en background 24/7:
- **Ciclo cada 60 segundos**: detecta BEEs libres → las asigna a entrenamiento
- **Cada hora**: una BEE estratega analiza el bot y genera propuestas de mejora
- **Auto-implementación**: mejoras de alto impacto/bajo esfuerzo se aplican solas
- **Inteligencia colectiva**: lo que aprende una BEE lo saben todas las demás

### Comandos
```
/autonomo               — estado del loop y BEEs activas
/autonomo pausa         — pausar el loop
/autonomo resume        — reanudar
/mejoras                — ver propuestas generadas por las BEEs
/mejoras aprobar <id>   — aprobar e implementar una mejora
/mejoras rechazar <id>  — rechazar
```

---

## 5. Colmena — Auto-reparación Inteligente

La Colmena monitorea el sistema y actúa automáticamente:
- Detecta automáticamente qué archivo causó el error
- Lanza **3 BEEs de reparación en paralelo** con enfoques distintos
- La primera BEE que genera un fix válido gana
- Instala paquetes pip faltantes automáticamente

```
/healer         — ver estado de la Colmena
/healer reparar — forzar ciclo de reparación manual
```

---

## 6. Generación de Imágenes — FLUX.2 + Cascada

### Cascada de proveedores sin censura (orden de prioridad)

| # | Proveedor | Modelo | Clave | Estado |
|---|-----------|--------|-------|--------|
| 0 | **BFL API** | FLUX.2-dev (32B) / FLUX.2-klein | BFL_API_KEY | ✅ ACTIVO |
| 1 | Stable Horde | SD multi-modelo NSFW | gratis | ✅ ACTIVO |
| 2 | **fal.ai** | FLUX.2-dev / FLUX.2-klein / FLUX.1 | FAL_API_KEY | ✅ ACTIVO |
| 3 | Together AI | FLUX.2-schnell-Free / FLUX.1 | TOG_API1-5 | ✅ ACTIVO |
| 4 | getimg.ai | SDXL adult ON | GETIMG_API_KEY | opcional |
| 5 | Prodia | DreamShaper NSFW | PRODIA_API_KEY | opcional |
| 6 | HuggingFace | FLUX.2-klein-4B / SDXL | HF_TOKEN | opcional |
| 7 | DALL-E 3 | con auto-bypass | OPENAI_API_KEY | ✅ fallback |

### Cómo generar imágenes
```
/imagen una ciudad cyberpunk al amanecer desde un rascacielos
/imagen retrato de mujer con ojos verdes y pelo rojo, fotorrealista
"genera imagen de un toro de oro rompiendo una pared"
"crea una imagen de playa tropical al atardecer"
```

### Con foto de referencia
Envía una foto → beehAIve la analiza con Qwen2-VL sin censura → genera variaciones o continúa el contexto.

---

## 7. Generación de Video — LTX-2

### Cascada de video

| # | Proveedor | Modelo | Clave |
|---|-----------|--------|-------|
| 1 | fal.ai | LTX-2 (audio+video sincronizado) | FAL_API_KEY ✅ |
| 2 | fal.ai | LTX-Video (solo video) | FAL_API_KEY ✅ |
| 3 | fal.ai | Wan-2.1 (alternativa) | FAL_API_KEY ✅ |
| 4 | HuggingFace | Lightricks/LTX-Video | HF_TOKEN |

### Cómo generar videos
```
/video un gato surfeando una ola al atardecer 5
/video ciudad cyberpunk con lluvia y luces de neón 8
/video mujer bailando flamenco en escenario con humo 5
/video explosión de colores en cámara lenta 3
```
Duración: 3, 5, 8 o 10 segundos.

**LTX-2 características**:
- Primer modelo DiT con audio + video sincronizado
- Text-to-video e image-to-video
- 22B parámetros — calidad profesional

---

## 8. Visión sin Censura — Qwen2-VL

beehAIve analiza fotos con modelos sin censura, **antes** que GPT-4o:

1. **Qwen2-VL-72B** via Together AI (5 claves, sin censura)
2. **Qwen2.5-VL-72B** via Together AI
3. **Qwen2-VL-7B** via HuggingFace
4. GPT-4o (fallback)
5. GPT-4o-mini (fallback ligero)

Envía una foto → beehAIve describe exactamente lo que ve + genera un prompt preciso para recrearla.

---

## 9. Trading y Crypto

### Análisis de mercado
```
/precio BTC ETH SOL          — precios en tiempo real
/chart BTC 4h                — gráfico técnico
/analiza ETH                 — análisis completo: RSI, MACD, soporte/resistencia
```

### Trading autónomo
- Modo dry-run por defecto (sin dinero real hasta que lo actives)
- Gestión de riesgo: stop-loss, take-profit automáticos
- Monitoreo de 124 pares simultáneamente con BEEs

### PumpFun y wallets
```
/pumpfun <dirección>    — análisis de token en pump.fun
/wallet <dirección>     — saldo y transacciones de wallet
/alerta BTC > 100000    — configurar alerta de precio
```

---

## 10. Búsqueda Web y Research

- Búsqueda en tiempo real con DuckDuckGo (sin API key)
- Extracción y resumen de contenido de URLs
- Research profundo con múltiples BEEs en paralelo
- YouTube: transcripciones y resúmenes automáticos

```
/busca precio gas Ethereum hoy
/research arquitecturas multi-agente para trading
/yt https://youtube.com/watch?v=xxx
```

---

## 11. Voz y Multimedia

- **TTS**: BEEA responde con audio en modo voz
- **STT**: envía notas de voz y BEEA las entiende
- **Visión Qwen**: analiza fotos sin censura
- **PDFs**: extrae y analiza contenido
- **ZIPs**: descomprime y procesa archivos
- **QR**: genera códigos QR

```
/voz on         — activar respuestas de voz
/voz off        — desactivar
/qr https://...  — generar QR
```

---

## 12. Código y Construcción

- Escribe, revisa y ejecuta código en sandbox seguro
- Genera proyectos completos desde cero
- Analiza repositorios enteros con HiveMind
- Self-upgrade: propone y aplica mejoras al propio código del bot

```
/build un scraper de precios en tiempo real para 20 exchanges
/corre print("hola mundo")   — ejecuta código Python
```

---

## 13. Comandos Completos de Telegram

| Categoría | Comando | Función |
|-----------|---------|---------|
| Core | `/start` | Menú principal |
| Core | `/sistema` | Estado del sistema (BEEs, claves, uptime) |
| BEEs | `/bees <tarea>` | Lanzar BEEs en paralelo |
| BEEs | `/hivemind <objetivo>` | HiveMind completo (hasta 124 BEEs) |
| BEEs | `/hibernate <role> <tema> [tiempo]` | Poner BEE a entrenar |
| Autónomo | `/autonomo` | Estado del loop autónomo |
| Autónomo | `/mejoras` | Propuestas de mejora generadas |
| Crypto | `/precio BTC` | Precio en tiempo real |
| Crypto | `/chart ETH 1h` | Gráfico técnico |
| Crypto | `/analiza SOL` | Análisis técnico completo |
| Crypto | `/alerta BTC > 100k` | Configurar alerta de precio |
| Crypto | `/pumpfun <addr>` | Análisis pump.fun |
| Crypto | `/wallet <addr>` | Estado de wallet |
| Imágenes | `/imagen <desc>` | Generar imagen (FLUX.2 → cascada) |
| Video | `/video <desc> [s]` | Generar video con LTX-2 (audio+video) |
| Search | `/busca <query>` | Búsqueda web en tiempo real |
| Search | `/research <tema>` | Research profundo multi-BEE |
| Search | `/yt <url>` | Resumir video de YouTube |
| Código | `/build <descripción>` | Construir software completo |
| Código | `/corre <código>` | Ejecutar Python en sandbox |
| Multimedia | `/traduce <texto>` | Traducir a cualquier idioma |
| Multimedia | `/qr <url>` | Generar código QR |
| Multimedia | `/voz on/off` | Activar/desactivar respuestas de voz |
| Mantenimiento | `/healer` | Estado de la Colmena auto-reparación |
| Mantenimiento | `/reiniciar` | Reiniciar servicios del bot |

---

## 14. Estructura del Proyecto beehAIve

```
beehAIve/
├── bot.py                          — Punto de entrada principal
├── telegram_bot.py                 — Bot Telegram (2500+ líneas)
├── discord_bot.py                  — Bot Discord
├── config.py                       — Configuración global
├── personality_profile.py          — Personalidad y filtros BEEA
├── swarm/
│   ├── hivemind.py                 — Orquestador del enjambre
│   ├── agent_worker.py             — Motor de cada BEE
│   ├── bee_identity.py             — 100 identidades únicas
│   ├── bee_trainer.py              — Sistema de hibernación/entrenamiento
│   ├── bee_roles.py                — Roles especializados
│   ├── bee_tools.py                — Herramientas de las BEEs
│   └── autonomous_loop.py         — Loop autónomo 24/7 (50 BEEs)
├── colmena/
│   └── monitor.py                  — Auto-reparación inteligente
├── tools/
│   ├── llm_adapter.py              — Multi-proveedor (7 proveedores, 44 claves)
│   ├── image_providers.py          — Imágenes: BFL/FLUX.2 → cascada completa
│   ├── video_gen.py                — Video: LTX-2 → Wan-2.1 → HF
│   ├── image_gen.py                — Wrapper generación de imágenes
│   ├── free_providers.py           — 32 proveedores g4f gratuitos
│   ├── websearch.py                — Búsqueda web (DuckDuckGo/DDGS)
│   ├── tts.py                      — Text-to-Speech
│   ├── browser_tool.py             — Playwright, screenshots reales
│   ├── code_sandbox.py             — Ejecución segura de Python
│   ├── pdf_reader.py               — Análisis de PDFs
│   └── ...                         — 20+ herramientas más
├── crypto/
│   ├── wallet_manager.py           — Wallets BTC/ETH/Base/BSC/Solana
│   ├── price_feed.py               — Precios en tiempo real
│   └── analysis.py                 — RSI, MACD, Bollinger Bands
├── trading/
│   ├── trading_engine.py           — Jupiter swaps en Solana
│   ├── autonomous_trader.py        — Trader autónomo 24/7
│   └── pumpfun.py                  — Scanner de memecoins
├── memory/
│   ├── long_memory.py              — Memoria persistente
│   ├── shared_knowledge.py         — Inteligencia colectiva (pool)
│   ├── collective_knowledge.json   — Top 200 insights del enjambre
│   └── bee_skills/                 — Habilidades entrenadas
└── docs/
    ├── BEEA_GUIA_COMPLETA.md      — Este archivo
    ├── BEEA_MONETIZACION.md        — Cómo monetizar beehAIve
    └── BEEA_APIS.md                — Claves API y configuración
```
