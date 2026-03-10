# BEEA — Claves API y Configuración Completa

> Última actualización: Marzo 2026
> Propietario: Álvaro (@xxvelonxx)

---

## Claves actualmente configuradas

| Variable | Servicio | Estado |
|----------|----------|--------|
| `DISCORD_BOT_TOKEN` | Discord | Activa |
| `OPENAI_API_KEY` | OpenAI (chat + DALL-E) | Activa |
| `TOG_API1` … `TOG_API5` | Together AI (imágenes + LLM) | Activa (5 claves) |
| `CEREBRAS_API` / `CEREBRAS_API2` / `CEREBRAS_API3` | Cerebras (LLM ultra-rápido) | Activa (3 claves) |
| `GROQ_API` | Groq (LLM rápido) | Activa |
| `ANTHROPIC_API_KEY` | Anthropic / Claude | Activa |
| `SESSION_SECRET` | Web panel (flask) | Activa |
| `GITHUB_TOKEN_ALVARO` | GitHub repo beehAIve | Activa |

---

## Claves pendientes de añadir (activarán funciones nuevas)

### FAL_KEY — fal.ai
**Para qué sirve:**
- Generar **imágenes** con FLUX.2-dev, FLUX.2-klein, FLUX.1-schnell
- Generar **videos** con LTX-2 (audio + video sincronizado)
- Modelos: `fal-ai/flux-2/dev`, `fal-ai/flux-2-klein`, `fal-ai/ltx-video-2`

**Cómo conseguirla gratis ($15 de crédito al registrarse):**
1. Ir a https://fal.ai
2. Crear cuenta (GitHub o Google)
3. Dashboard → API Keys → Create Key
4. Añadir en Replit como secreto `FAL_KEY`

**Sin esta clave:** imágenes usan Stable Horde + Together AI (funcionan bien). Videos no disponibles.

---

### BFL_API_KEY — Black Forest Labs
**Para qué sirve:**
- Generar imágenes con **FLUX.2-dev** (32B, la mayor calidad existente)
- Generar imágenes con **FLUX.2-klein** (4B, sub-segundo)
- Edición de imágenes con referencia única o múltiple
- API oficial: https://api.bfl.ai

**Cómo conseguirla:**
1. Ir a https://api.bfl.ai
2. Crear cuenta y verificar email
3. Dashboard → API Keys
4. Añadir en Replit como secreto `BFL_API_KEY`

**Sin esta clave:** imágenes usan el resto de la cascada. BFL es la prioridad #0 (máxima calidad).

---

### HF_TOKEN — HuggingFace
**Para qué sirve:**
- Acceder a modelos en HuggingFace Inference API
- **FLUX.2-klein-4B** (imagen, Apache 2.0)
- **Qwen2-VL** vision fallback
- Otros modelos serverless gratuitos

**Cómo conseguirla (100% gratis):**
1. Ir a https://huggingface.co → Sign Up
2. Settings → Access Tokens → New token (tipo: read)
3. Añadir en Replit como secreto `HF_TOKEN`

---

### GETIMG_API_KEY — getimg.ai
**Para qué sirve:** 100 imágenes/mes gratis, content adulto activado, SDXL y otros modelos

**Cómo conseguirla:** https://getimg.ai → Sign Up (plan gratuito disponible)

---

### PRODIA_API_KEY — Prodia
**Para qué sirve:** 100 imágenes/día gratis, modelos NSFW, DreamShaper, etc.

**Cómo conseguirla:** https://prodia.com → Sign Up → API → Generate Key

---

## Cascada de imágenes — estado actual

```
Con las claves actuales (TOG_API1-5 + OPENAI_API_KEY):

  Stable Horde (gratis, sin clave) → FUNCIONA
  Together AI / FLUX.1-schnell-Free → FUNCIONA
  DALL-E 3 (fallback) → FUNCIONA

Añadiendo BFL_API_KEY:
  BFL / FLUX.2-dev (32B, máxima calidad) → DISPONIBLE #0

Añadiendo FAL_KEY:
  fal.ai / FLUX.2-dev → DISPONIBLE #1
  fal.ai / FLUX.2-klein → DISPONIBLE #2
  LTX-2 video generation → DISPONIBLE
```

---

## Cascada de video — estado actual

```
Sin FAL_KEY ni HF_TOKEN:
  → No disponible (muestra instrucciones)

Con FAL_KEY:
  LTX-2 (audio+video, fal-ai/ltx-video-2) → DISPONIBLE
  LTX-Video (solo video, fal-ai/ltx-video) → DISPONIBLE
  Wan-2.1 (alternativa, fal-ai/wan-video)  → DISPONIBLE

Con HF_TOKEN:
  Lightricks/LTX-Video via HF Inference    → DISPONIBLE
```

---

## Modelos LLM — estado actual

| Proveedor | Claves | BEEs estables | BEEs burst |
|-----------|--------|---------------|------------|
| Together AI | 5 | 20 | 40 |
| Cerebras | 3 | 3 | 6 |
| Groq | 1 | 1 | 2 |
| OpenAI | 1 | 6 | 12 |
| Anthropic | 1 | 0 | 0 (backup) |
| g4f (32 proveedores libres) | 32 | 64 | 128 |
| **TOTAL** | **45** | **94** | **188** |

> Límite configurado en `autonomous_loop.py`: 160 BEEs paralelas

---

## Claves de análisis y datos

| Variable | Servicio | Estado |
|----------|----------|--------|
| `COINGECKO_API_KEY` | Precios crypto | Opcional (funciona sin ella) |
| `BIRDEYE_API_KEY` | Datos Solana/SPL tokens | Opcional |
| `SOLANA_RPC_URL` | RPC de Solana | Configurable (usa public por defecto) |

---

## Cómo añadir una nueva clave en Replit

1. Panel izquierdo → "Secrets" (🔒 candado)
2. "New Secret"
3. Key: nombre de la variable (ej: `FAL_KEY`)
4. Value: tu clave
5. "Add Secret"
6. Reiniciar el bot con `/reiniciar` o desde el panel de Replit
