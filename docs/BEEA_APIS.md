# BEEA — Claves API y Configuración Completa

> Última actualización: 10 Marzo 2026
> Propietario: Álvaro (@xxvelonxx)

---

## Claves actualmente configuradas (inventario real — 10 Mar 2026)

| Variable | Servicio | Tipo | Estado |
|----------|----------|------|--------|
| `PUTER_TOKEN`…`PUTER_TOKEN6` | Puter.com — Claude Opus 4 / Sonnet 4 / GPT-4o | LLM premium gratis | ✅ 5 activos |
| `CEREBRAS_API`, `CEREBRAS_API2`…`CEREBRAS_API19` | Cerebras — llama ultra-rápido | LLM bulk BEEs | ✅ 19 claves |
| `TOG_API1`…`TOG_API5` | Together AI — LLM + FLUX imágenes | LLM + imagen | ✅ 4 válidas (tgp_v1_) |
| `GEMINI_API`, `GEMINI_API2`, `GEMINI_API3`, `GEMINI_API5` | Gemini Flash 2.0 | LLM contexto largo | ✅ 4 claves |
| `GROQ_API` | Groq — Llama tool-use | LLM rápido | ✅ 1 clave |
| `OPENAI_API_KEY` | OpenAI GPT-4o + DALL-E 3 | LLM + imagen fallback | ✅ 1 clave |
| `ANTHROPIC_API_KEY` | Anthropic Claude (backup pago) | LLM backup | ✅ 1 clave |
| `FAL_KEY` / `FAL_API_KEY` | fal.ai — FLUX.2 + LTX-2 video | Imagen + video | ✅ |
| `BFL_API_KEY` + `BFL_API_KEY2` | BFL API — FLUX.2-dev 32B | Imagen premium | ✅ 2 claves |
| `DISCORD_BOT_TOKEN` | Bot Discord | Bot | ✅ |
| `GITHUB_TOKEN_ALVARO` / `GITHUB_PERSONAL_ACCESS_TOKEN` | GitHub push | Git | ✅ |
| `SESSION_SECRET` | Web panel Flask | Auth | ✅ |

---

## Capacidad total por proveedor

| Proveedor | Claves/Tokens | RPM | Diario | BEEs estables |
|-----------|--------------|-----|--------|---------------|
| **Puter** | 5 tokens | Sin límite publicado | Sin límite | **250 overflow** |
| **Cerebras** | 19 | 950 rpm | Sin límite | **950 estables** |
| Together AI | 4 | 60 rpm | 8.000 | 60 |
| Gemini Flash | 4 | 40 rpm | 1.400 | 40 |
| Groq | 1 | 25 rpm | 90 | 25 |
| OpenAI | 1 | 50 rpm | Sin límite | 50 (pago) |
| **TOTAL** | **34** | **1200+ rpm** | — | **1200+ BEEs** |

---

## Routing de LLM — Prioridad real en llm_adapter.py

```
Tarea premium (análisis/código/escritura):
  → Puter claude-sonnet-4   (gratis, el mejor)
  → Puter claude-opus-4     (gratis, el más potente)
  → OpenAI gpt-4o           (pago, fallback final)

BEEs en bulk (1-750):
  → Cerebras llama-3.3-70b  (gratis, 750 rpm garantizados)

BEEs overflow (751-1000):
  → Puter gpt-4o-mini       (gratis, veloz)

Contexto largo (docs, PDFs):
  → Gemini 2.0 Flash        (gratis, 1M tokens)

Tool-use / function calling:
  → Groq llama3-groq-70b    (gratis, nativo)
```

---

## Puter — Detalles técnicos

**Endpoint:** `POST https://api.puter.com/drivers/call`
**Body:** `{"interface": "puter-chat-completion", "test_mode": false, "driver": "claude", "method": "complete", "args": {"model": "claude-sonnet-4", "messages": [...], "auth_token": "TOKEN"}}`

**Modelos confirmados funcionando (nombres exactos):**

| Nombre exacto | Driver | Modelo real | Calidad |
|---------------|--------|-------------|---------|
| `claude-sonnet-4` | `claude` | Claude Sonnet 4 | ⭐⭐⭐⭐⭐ |
| `claude-opus-4` | `claude` | Claude Opus 4 | ⭐⭐⭐⭐⭐ |
| `gpt-4o` | `openai-completion` | GPT-4o | ⭐⭐⭐⭐ |
| `gpt-4o-mini` | `openai-completion` | GPT-4o mini | ⭐⭐⭐ |
| `gemini-2.0-flash` | `gemini` | Gemini 2.0 Flash | ⭐⭐⭐⭐ |

**NOMBRES INCORRECTOS** (dan error, no usar):
- ~~`claude-3-7-sonnet-20250219`~~ ❌
- ~~`claude-3-5-sonnet`~~ ❌
- ~~`grok-3`~~ ❌

**Retry logic:** Si un token da 401 (expirado), rota automáticamente al siguiente. 5 tokens → prácticamente imposible que fallen todos.

**Variables:** `PUTER_TOKEN`, `PUTER_TOKEN2`, `PUTER_TOKEN3`, `PUTER_TOKEN4`, `PUTER_TOKEN5` (y opcionalmente `PUTER_TOKEN6`)

---

## Cerebras — Detalles técnicos

- API compatible con OpenAI (`/v1/chat/completions`)
- Endpoint: `https://api.cerebras.ai/v1`
- Modelo principal: `llama-3.3-70b` (inferencia ~1000 tokens/seg)
- **50 RPM por clave × 19 claves = 950 RPM garantizados**
- Sin límite diario — ideal para BEEs 24/7
- Variables aceptadas (todas): `CEREBRAS_API`, `CEREBRAS_API2`…`CEREBRAS_API19`, `CEREBRA_API5`…`CEREBRA_API14`

---

## Together AI — Solo keys válidas

**IMPORTANTE:** Solo funcionan las keys con prefijo `tgp_v1_`.
Las keys antiguas `key_XXXX` están expiradas — el sistema las ignora automáticamente.

Modelos usados:
- LLM: `meta-llama/Llama-3.3-70B-Instruct-Turbo`
- Visión: `Qwen/Qwen2-VL-72B-Instruct` (sin censura)
- Imagen: `black-forest-labs/FLUX.1-schnell-Free`

---

## Endpoints Web Panel (web_panel/app.py)

| Ruta | Auth | Función |
|------|------|---------|
| `GET /ping` | Público | Keep-alive para UptimeRobot |
| `GET /health` | Público | Alias de /ping |
| `GET /` | Password | Dashboard |
| `GET /chat` | Password | Chat con BEEA |
| `GET /bee` | Password | Chat con BEE directa |
| `GET /logs` | Password | Logs en tiempo real |
| `GET /repair` | Password | Forzar reparación |
| `GET /api/status` | Password | Estado JSON |

**URL de ping para UptimeRobot:**
`https://2ca5a0be-f9cc-4883-be17-6d27b53f94fe-00-lzusp9kyl6y0.kirk.replit.dev/ping`

**Respuesta esperada de /ping:**
`{"status": "alive", "bot": "BEEA", "ts": 1234567890}`

---

## Cascada de imágenes — estado actual (orden real del código)

```
Con FAL_KEY (primero — fal.ai prueba 4 modelos en cascada):
  fal.ai / FLUX.2-dev         → DISPONIBLE #1 ✅
  fal.ai / FLUX.2-klein       → DISPONIBLE #2 ✅
  fal.ai / FLUX.1-schnell     → DISPONIBLE #3 ✅
  fal.ai / FLUX.1-dev         → DISPONIBLE #4 ✅

Con BFL_API_KEY (segundo — máxima calidad):
  BFL / FLUX.2-dev 32B        → DISPONIBLE #5 ✅

Con TOG_API1-5 (tgp_v1_):
  Together / FLUX.1-schnell   → DISPONIBLE #6 ✅

Opcionales (sin configurar):
  getimg.ai (GETIMG_API_KEY)  → opcional
  Prodia (PRODIA_API_KEY)     → opcional
  HuggingFace (HF_TOKEN)      → opcional

Stable Horde (sin clave, siempre disponible — ÚLTIMO):
  SD multi-modelo NSFW        → DISPONIBLE ✅

Fallback final:
  DALL-E 3 (OPENAI_API_KEY)   → DISPONIBLE ✅
```

---

## Cascada de video — estado actual

```
Con FAL_API_KEY:
  LTX-2 (audio+video, fal-ai/ltx-video-2)  → DISPONIBLE ✅
  LTX-Video (solo video, fal-ai/ltx-video)  → DISPONIBLE ✅
  Wan-2.1 (fal-ai/wan-video)               → DISPONIBLE ✅

Sin FAL_API_KEY:
  → No disponible (muestra instrucciones)
```

---

## Claves opcionales para más capacidad

### HF_TOKEN — HuggingFace (gratis)
1. https://huggingface.co → Sign Up
2. Settings → Access Tokens → New token (tipo: read)
3. Añadir como secreto `HF_TOKEN`

### GETIMG_API_KEY — getimg.ai
100 imágenes/mes gratis, adult content ON, SDXL.
https://getimg.ai → Sign Up

### PRODIA_API_KEY — Prodia
100 imágenes/día gratis, DreamShaper NSFW.
https://prodia.com → API → Generate Key

### COINGECKO_API_KEY — CoinGecko
Precios crypto más rápidos. Funciona sin ella (usa API pública).

---

## Cómo añadir una nueva clave en Replit

1. Panel izquierdo → "Secrets" (🔒 candado)
2. "New Secret"
3. Key: nombre de la variable (ej: `PUTER_TOKEN6`)
4. Value: tu clave/token
5. "Add Secret"
6. Reiniciar el bot desde Replit → Workflows → Restart

El sistema hace auto-discovery de todas las variables — no hay que tocar el código.
