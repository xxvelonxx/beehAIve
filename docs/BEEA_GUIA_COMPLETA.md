# beehAIve — Guía Completa de Funciones y Capacidades

> Propietario exclusivo: Álvaro (@xxvelonxx)
> Versión: 4.0 — 10 Marzo 2026

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
| Recordar algo | "Recuerda que prefiero X" |
| Ver estado del sistema | `/sistema` |
| Ver versión y estado | `/start` |

---

## 2. El Enjambre de BEEs — Capacidad real (10 Mar 2026)

### Infraestructura completa de proveedores

| Proveedor | Tokens/Claves | RPM total | Límite diario | Rol |
|-----------|--------------|-----------|---------------|-----|
| **Puter** | **5 tokens** | Sin límite publicado | Sin límite | Claude Opus 4 + Sonnet 4 + GPT-4o GRATIS |
| **Cerebras** | **15 claves** | **750 rpm** | Sin límite | Columna vertebral BEEs 24/7 |
| Together AI | 4 válidas | 60 rpm | 8.000/día | Backup + visión Qwen sin censura |
| Gemini Flash | 4 | 40 rpm | 1.400/día | Contexto largo |
| Groq | 1 | 25 rpm | 90/día | Velocidad + tool-use |
| OpenAI | 1 | 50 rpm | Sin límite | GPT-4o + DALL-E fallback |
| Anthropic | 1 | 10 rpm | Sin límite | Claude backup pago |

### Matemática del enjambre
- **750 BEEs garantizadas** — solo con Cerebras, dentro de límites oficiales
- **1000+ BEEs probables** — Cerebras (750) + Puter overflow (250)
- Puter: 5 tokens × ~50 rpm de overflow = 250 rpm extra
- Coste total: **$0/mes** (todo gratis)

### Routing inteligente por tarea
| Tarea | Proveedor usado | Modelo | Por qué |
|---|---|---|---|
| Análisis / código / razonamiento | **Puter** | Claude Sonnet 4 | El mejor modelo gratis |
| Creatividad / escritura profunda | **Puter** | Claude Opus 4 | El más potente del mercado |
| BEEs en bulk (1-750) | **Cerebras** | llama 3.3 | 750 rpm garantizados |
| BEEs overflow (751-1000) | **Puter** | GPT-4o-mini | Gratis, veloz |
| Contexto largo (docs, PDFs) | Gemini Flash | gemini-2.0-flash | 1M tokens contexto |
| Tool-use / funciones | Groq | llama3-groq-70b | Function calling nativo |

### Modos del enjambre
| Modo | BEEs activas | RPM usado | Cuándo usar |
|------|-------------|-----------|-------------|
| `idle` (DEFAULT) | 0 | 0 | Toda la cuota libre para Álvaro |
| `economico` | 5 | 5 rpm | Pruebas ligeras |
| `normal` | 25 | 25 rpm | Uso diario |
| `full` | 126 | 126 rpm | Capacidad clásica |
| `burst` | 750 | 750 rpm | Máximo Cerebras |
| `mega` | 1000 | 1000 rpm | Cerebras + Puter overflow |

### Cómo activar el enjambre

**Desde Telegram:**
```
/hivemind analiza el top 50 tokens y dame cuáles tienen mejor momentum
/hivemind 20 encuentra las mejores APIs de datos crypto gratuitas
/bees <tarea>
/beemode full     — activar modo completo (126 BEEs)
/beemode idle     — volver a modo silencioso
```

**Por lenguaje natural:**
```
"manda las bees a investigar los mejores exchanges descentralizados"
"lanza el enjambre a auditar todos los contratos de esta semana"
"que 40 bees analicen el mercado de NFTs en Solana"
```

### Comparativa de velocidad

| Tarea | 1 Modelo solo | HiveMind (126 BEEs) | Ganancia |
|-------|--------------|---------------------|---------|
| Investigar 20 exchanges | 4 min | 3 seg | **80x** |
| Auditar 50 archivos Python | 8 min | 4 seg | **120x** |
| Analizar 100 tokens | 15 min | 5 seg | **180x** |
| Research de mercado (50 fuentes) | 20 min | 4 seg | **300x** |

---

## 3. Puter — Cerebro Premium Gratuito

**Puter.com** actúa como proxy gratuito a los mejores modelos de IA del mundo.
BEEA tiene 5 tokens Puter rotando con retry automático si uno expira.

### Modelos disponibles gratis via Puter
| Modelo | Quién es | Para qué |
|---|---|---|
| `claude-sonnet-4` | Claude Sonnet 4 (Anthropic) | Análisis, código, razonamiento |
| `claude-opus-4` | Claude Opus 4 — el más potente | Tareas complejas premium |
| `gpt-4o` | OpenAI flagship | Razonamiento general |
| `gpt-4o-mini` | OpenAI rápido | BEEs de volumen y overflow |
| `gemini-2.0-flash` | Google | Velocidad + multimodal |

### Funcionamiento técnico
- `POST https://api.puter.com/drivers/call` — llamada directa, sin navegador
- 5 tokens en round-robin — si uno da 401, salta automáticamente al siguiente
- Integrado en `tools/llm_adapter.py` como proveedor de máxima prioridad
- Variables: `PUTER_TOKEN`, `PUTER_TOKEN2`…`PUTER_TOKEN6`

---

## 4. Roles de BEEs disponibles

`coder`, `debugger`, `researcher`, `architect`, `reviewer`, `planner`, `data`, `strategist`, `analyst`, `optimizer`, `web_scraper`, `devops`, `security`, `key_hunter`, `api_integrator`, `quota_manager`

---

## 5. Loop Autónomo

El loop autónomo corre en background 24/7:
- **Ciclo cada 60 segundos**: detecta BEEs libres → asigna entrenamiento
- **Cada hora**: una BEE estratega analiza el bot y genera propuestas de mejora
- **Circuit breaker**: si 3 fallos seguidos → pausa 5 minutos, evita quemar cuota

### Comandos
```
/autonomo               — estado del loop
/autonomo pausa         — pausar
/autonomo resume        — reanudar
/mejoras                — propuestas generadas por BEEs
/beemode <modo>         — cambiar modo (idle/economico/normal/full/burst/mega)
/cuotas                 — estado de todas las cuotas en tiempo real
```

---

## 6. Colmena — Auto-reparación

La Colmena monitorea el sistema y actúa automáticamente:
- Detecta automáticamente el archivo que causó el error
- Lanza **3 BEEs de reparación en paralelo** con enfoques distintos
- La primera BEE que genera un fix válido gana
- Instala paquetes pip faltantes automáticamente

```
/healer         — estado de la Colmena
/healer reparar — forzar ciclo manual
```

---

## 7. Generación de Imágenes — FLUX.2 + Cascada sin Replicate

### Cascada de proveedores (orden de prioridad)

| # | Proveedor | Modelo | Clave | Estado |
|---|-----------|--------|-------|--------|
| 0 | **BFL API** | FLUX.2-dev (32B) / FLUX.2-klein / FLUX.1-Pro | BFL_API_KEY + BFL_API_KEY2 | ✅ 2 claves |
| 1 | Stable Horde | SD multi-modelo NSFW | gratis | ✅ |
| 2 | **fal.ai** | FLUX.2-dev / FLUX.2-klein / FLUX.1 | FAL_API_KEY | ✅ |
| 3 | Together AI | FLUX.2-schnell-Free / FLUX.1 | TOG_API1-5 | ✅ |
| 4 | getimg.ai | SDXL adult ON | GETIMG_API_KEY | opcional |
| 5 | Prodia | DreamShaper NSFW | PRODIA_API_KEY | opcional |
| 6 | HuggingFace | FLUX.2-klein-4B / SDXL | HF_TOKEN | opcional |
| 7 | DALL-E 3 | con auto-bypass | OPENAI_API_KEY | ✅ fallback |

**REGLA ABSOLUTA**: Sin Replicate — nunca.

### Cómo generar imágenes
```
/imagen una ciudad cyberpunk al amanecer desde un rascacielos
/imagen retrato de mujer con ojos verdes y pelo rojo, fotorrealista
"genera imagen de un toro de oro rompiendo una pared"
```

---

## 8. Generación de Video — LTX-2

```
/video un gato surfeando una ola al atardecer 5
/video ciudad cyberpunk con lluvia y luces de neón 8
```
Duración: 3, 5, 8 o 10 segundos.

---

## 9. Visión sin Censura — Cascada completa

| # | Proveedor | Modelo | Censura |
|---|-----------|--------|---------|
| 1 | **Together AI** | Qwen2-VL-72B-Instruct-Turbo | Mínima |
| 2 | **Together AI** | Qwen2.5-VL-72B-Instruct | Mínima |
| 3 | **Groq** | llama-3.2-90b-vision-preview | Baja |
| 4 | HuggingFace | Qwen2-VL-7B + Llama-3.2-11B-Vision | Baja |
| 5 | GPT-4o | — | Alta (fallback) |
| 6 | GPT-4o-mini | — | Alta (último recurso) |

---

## 10. Trading y Crypto

### Análisis de mercado
```
/precio BTC ETH SOL          — precios en tiempo real
/chart BTC 4h                — gráfico técnico
/analiza ETH                 — análisis completo: RSI, MACD, soporte/resistencia
```

### Wallets generadas (memory/beea_wallets.json)
| Red | Dirección |
|-----|-----------|
| ETH | `0x76ACfBb578f14cB6108107663C8FF22BE515edd0` |
| Base | `0x5Ad62254c428e5CF97F07D5F181f660C77b74c4e` |
| BSC | `0xb99F37abE395B525F9651Fc9BA449699b4472Cac` |
| Solana | `ApsczVHC9eEgvYh2WBww5V2aBxaMSFAMyLM1ouG78bwR` |
| BTC | `15M8kdCRkMq3wyo2iXNzVogK3XxGDxDdtm` |

---

## 11. Keep-Alive 24/7 — UptimeRobot

El bot expone dos endpoints públicos (sin contraseña):
- `GET /ping` → `{"status": "alive", "bot": "BEEA", "ts": timestamp}`
- `GET /health` → `{"status": "ok"}`

UptimeRobot pinga `/ping` cada 5 minutos → Replit nunca duerme el proceso → bot activo 24/7 gratis.

---

## 12. Comandos Completos de Telegram (27 registrados)

| Categoría | Comando | Función |
|-----------|---------|---------|
| Core | `/start` | Menú principal |
| Core | `/sistema` | Estado del sistema |
| Core | `/ayuda` | Lista de comandos |
| BEEs | `/bees <tarea>` | Lanzar BEEs en paralelo |
| BEEs | `/hivemind <objetivo>` | HiveMind completo |
| BEEs | `/beemode <modo>` | Cambiar modo enjambre |
| BEEs | `/cuotas` | Estado de cuotas en tiempo real |
| BEEs | `/keys` | Inventario de claves API |
| Autónomo | `/autonomo` | Estado del loop |
| Autónomo | `/mejoras` | Propuestas de mejora |
| Crypto | `/precio BTC` | Precio en tiempo real |
| Crypto | `/chart ETH 1h` | Gráfico técnico |
| Crypto | `/analiza SOL` | Análisis técnico |
| Crypto | `/alerta BTC > 100k` | Alerta de precio |
| Crypto | `/pumpfun <addr>` | Análisis pump.fun |
| Crypto | `/wallet <addr>` | Estado de wallet |
| Imágenes | `/imagen <desc>` | Generar imagen FLUX.2 |
| Video | `/video <desc> [s]` | Generar video LTX-2 |
| Search | `/busca <query>` | Búsqueda web |
| Search | `/yt <url>` | Resumir YouTube |
| Código | `/build <desc>` | Construir software |
| Código | `/corre <código>` | Ejecutar Python |
| Multimedia | `/traduce <texto>` | Traducir |
| Multimedia | `/qr <url>` | Generar QR |
| Multimedia | `/voz on/off` | Respuestas de voz |
| Mantenimiento | `/healer` | Estado auto-reparación |
| Mantenimiento | `/reiniciar` | Reiniciar servicios |

---

## 13. Cómo reiniciar el bot si no responde

1. En Replit → pestaña Workflows → "Start application" → botón restart
2. Esperar que los logs muestren: `Polling active — 27 commands registered`
3. Si no aparece → hay un error más abajo en los logs

---

## 14. Estado actual — Producción

| Aspecto | Estado |
|---------|--------|
| Bot activo 24/7 | ✅ UptimeRobot keep-alive |
| Claude Opus 4 / Sonnet 4 gratis | ✅ 5 tokens Puter |
| 750 BEEs garantizadas | ✅ 15 claves Cerebras |
| 1000 BEEs probables | ✅ Puter overflow |
| Imágenes FLUX.2 | ✅ BFL 2 claves + FAL |
| Video LTX-2 | ✅ FAL |
| Crypto y wallets | ✅ activo |
| Coste mensual | **$0/mes** |
