"""
Proveedores de imágenes para BEEA.
Cada proveedor se activa automáticamente si tiene su API key configurada.

REGLA ABSOLUTA: Sin Replicate.

Prioridad de uso:
  0. BFL API/FLUX.2     — BFL_API_KEY           (FLUX.2-dev/klein, mejor calidad, sin censura)
  1. FAL.ai/FLUX.2      — FAL_KEY               (FLUX.2 + FLUX.2-klein, rápido)
  2. Stable Horde       — sin API key           (gratis, NSFW sin censura)
  3. Together AI        — TOG_API1/TOGETHER_API_KEY  (FLUX.1-schnell-Free gratis)
  4. getimg.ai          — GETIMG_API_KEY        (100 imgs/mes gratis, adult ON)
  5. Prodia             — PRODIA_API_KEY        (100 imgs/día gratis, sin filtros)
  6. HuggingFace        — HF_TOKEN              (FLUX.2-klein-4B o SDXL sin censura)
  7. DALL-E 3           — OPENAI_API_KEY        (fallback, con auto-bypass de prompts)
"""

import os
import io
import time
import base64
import tempfile
import requests
import logging

logger = logging.getLogger("beeatrix.imgproviders")

TIMEOUT = 120


def _save_bytes(data: bytes, suffix: str = ".png") -> str:
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        return tmp.name


# ── 0. BFL API — FLUX.2 (Black Forest Labs, api.bfl.ai) ──────────────────────

def generate_bfl(prompt: str, width: int = 1024, height: int = 1024) -> dict:
    """
    FLUX.2 via BFL API oficial (api.bfl.ai).
    Modelos probados en orden: flux-2-dev → flux-2-klein → flux-pro-1.1-ultra
    Auth: X-Key header
    Requiere: BFL_API_KEY o BFL_KEY
    """
    key = (os.environ.get("BFL_API_KEY") or os.environ.get("BFL_KEY")
           or os.environ.get("BFL_API_KEY2") or "")
    if not key:
        raise RuntimeError("No BFL_API_KEY")

    headers = {
        "X-Key": key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    bfl_models = [
        ("flux-2-dev",   {"prompt": prompt, "width": width, "height": height,
                          "steps": 28, "guidance": 3.5, "output_format": "png",
                          "prompt_upsampling": False}),
        ("flux-2-klein", {"prompt": prompt, "width": width, "height": height,
                          "steps": 4, "guidance": 3.5, "output_format": "png",
                          "prompt_upsampling": False}),
        ("flux-pro-1.1", {"prompt": prompt, "width": width, "height": height,
                          "steps": 25, "guidance": 3.0, "output_format": "png",
                          "prompt_upsampling": False}),
    ]

    for model_name, payload in bfl_models:
        try:
            resp = requests.post(
                f"https://api.bfl.ai/v1/{model_name}",
                headers=headers, json=payload, timeout=30,
            )
            if resp.status_code == 404:
                continue
            if resp.status_code not in (200, 202):
                raise RuntimeError(f"BFL/{model_name} {resp.status_code}: {resp.text[:200]}")

            job_id = resp.json().get("id")
            if not job_id:
                raise RuntimeError(f"BFL/{model_name}: no job ID")

            deadline = time.time() + 90
            while time.time() < deadline:
                poll = requests.get(
                    "https://api.bfl.ai/v1/get_result",
                    params={"id": job_id}, headers=headers, timeout=15,
                )
                pr = poll.json()
                status = pr.get("status", "")

                if status in ("Ready", "succeeded", "Succeeded"):
                    img_url = (pr.get("result") or {}).get("sample") or pr.get("url", "")
                    if not img_url:
                        raise RuntimeError(f"BFL/{model_name}: no image URL in result")
                    img_data = requests.get(img_url, timeout=60).content
                    local_path = _save_bytes(img_data)
                    logger.info("FLUX.2 BFL (%s) OK", model_name)
                    return {"url": img_url, "local_path": local_path,
                            "revised_prompt": prompt, "provider": f"BFL/FLUX.2/{model_name}"}

                if status in ("Error", "Failed", "failed", "error"):
                    raise RuntimeError(f"BFL/{model_name} job failed: {pr}")

                time.sleep(3)

            raise TimeoutError(f"BFL/{model_name} timeout 90s")

        except (RuntimeError, TimeoutError):
            raise
        except Exception as e:
            logger.debug("BFL/%s: %s — trying next", model_name, e)

    raise RuntimeError("BFL: ningún modelo FLUX.2 disponible")


# ── 1. FAL.ai (FLUX.2 → FLUX.1 — rápido, sin restricciones) ─────────────────

def generate_fal(prompt: str, width: int = 1024, height: int = 1024) -> dict:
    key = (os.environ.get("FAL_KEY") or os.environ.get("FAL_API_KEY")
           or os.environ.get("FAL_TOKEN") or "")
    if not key:
        raise RuntimeError("No FAL_KEY / FAL_API_KEY")

    headers = {
        "Authorization": f"Key {key}",
        "Content-Type": "application/json",
    }

    fal_models = [
        ("fal-ai/flux-2/dev",    {"prompt": prompt, "image_size": {"width": width, "height": height},
                                  "num_images": 1, "output_format": "png"}),
        ("fal-ai/flux-2-klein",  {"prompt": prompt, "image_size": {"width": width, "height": height},
                                  "num_images": 1, "output_format": "png",
                                  "num_inference_steps": 4}),
        ("fal-ai/flux/schnell",  {"prompt": prompt, "image_size": {"width": width, "height": height},
                                  "num_images": 1, "output_format": "png",
                                  "num_inference_steps": 4}),
        ("fal-ai/flux/dev",      {"prompt": prompt, "image_size": {"width": width, "height": height},
                                  "num_images": 1, "output_format": "png"}),
    ]

    for model_id, payload in fal_models:
        try:
            resp = requests.post(
                f"https://fal.run/{model_id}",
                headers=headers, json=payload, timeout=TIMEOUT,
            )
            if resp.status_code == 404:
                continue
            if resp.status_code not in (200, 202):
                raise RuntimeError(f"FAL/{model_id} {resp.status_code}: {resp.text[:200]}")

            data = resp.json()
            images = data.get("images", [])
            if not images:
                raise RuntimeError(f"FAL/{model_id}: sin imagen")

            image_url = images[0].get("url") if isinstance(images[0], dict) else images[0]
            img_data = requests.get(image_url, timeout=60).content
            local_path = _save_bytes(img_data)
            label = "FLUX.2" if "flux-2" in model_id else "FLUX.1"
            logger.info("FAL.ai %s OK (%s)", label, model_id)
            return {"url": image_url, "local_path": local_path,
                    "revised_prompt": prompt, "provider": f"FAL.ai/{label}/{model_id.split('/')[-1]}"}

        except RuntimeError:
            raise
        except Exception as e:
            logger.debug("FAL/%s: %s — trying next", model_id, e)

    raise RuntimeError("FAL.ai: ningún modelo FLUX disponible")


# ── 2. Together AI (FLUX.1-schnell-Free — gratis sin restricciones) ──────────

def generate_together(prompt: str, width: int = 1024, height: int = 1024) -> dict:
    key = (os.environ.get("TOGETHER_API_KEY") or os.environ.get("TOG_API1")
           or os.environ.get("TOG_API2") or os.environ.get("TOG_API3")
           or os.environ.get("TOG_API4") or os.environ.get("TOG_API5") or "")
    if not key:
        raise RuntimeError("No TOGETHER_API_KEY/TOG_APIx")

    together_models = [
        "black-forest-labs/FLUX.2-schnell-Free",
        "black-forest-labs/FLUX.1-schnell-Free",
        "black-forest-labs/FLUX.1-dev",
    ]

    for model in together_models:
        try:
            resp = requests.post(
                "https://api.together.xyz/v1/images/generations",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "prompt": prompt,
                    "width": width,
                    "height": height,
                    "steps": 4,
                    "n": 1,
                    "response_format": "url",
                },
                timeout=TIMEOUT,
            )
            if resp.status_code == 400 and "not found" in resp.text.lower():
                continue
            if resp.status_code != 200:
                raise RuntimeError(f"Together/{model} {resp.status_code}: {resp.text[:200]}")

            items = resp.json().get("data", [])
            if not items:
                raise RuntimeError(f"Together/{model}: sin imagen")

            image_url = items[0].get("url")
            img_data = requests.get(image_url, timeout=60).content
            local_path = _save_bytes(img_data)
            label = "FLUX.2" if "FLUX.2" in model else "FLUX.1"
            logger.info("Together AI %s OK (%s)", label, model)
            return {"url": image_url, "local_path": local_path,
                    "revised_prompt": prompt, "provider": f"Together AI/{label}"}

        except RuntimeError:
            raise
        except Exception as e:
            logger.debug("Together/%s: %s — trying next", model, e)

    raise RuntimeError("Together AI: ningún modelo FLUX disponible")


# ── 3. getimg.ai (100 imgs/mes gratis, adult content ON) ─────────────────────

def generate_getimg(prompt: str, width: int = 1024, height: int = 1024) -> dict:
    key = os.environ.get("GETIMG_API_KEY", "")
    if not key:
        raise RuntimeError("No GETIMG_API_KEY")

    resp = requests.post(
        "https://api.getimg.ai/v1/stable-diffusion-xl/text-to-image",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "stable-diffusion-xl-base-1.0",
            "prompt": prompt,
            "negative_prompt": "blurry, bad quality, watermark, text",
            "width": width,
            "height": height,
            "steps": 30,
            "guidance": 7.5,
            "output_format": "png",
            "response_format": "b64",
        },
        timeout=TIMEOUT,
    )

    if resp.status_code != 200:
        raise RuntimeError(f"getimg.ai {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    b64 = data.get("image", "")
    if not b64:
        raise RuntimeError("getimg.ai: sin imagen en respuesta")

    img_data = base64.b64decode(b64)
    local_path = _save_bytes(img_data)

    return {"url": None, "local_path": local_path, "revised_prompt": prompt, "provider": "getimg.ai/SDXL"}


# ── 4. Prodia (100 imgs/día gratis, modelos NSFW disponibles) ────────────────

def generate_prodia(prompt: str, width: int = 1024, height: int = 1024) -> dict:
    key = os.environ.get("PRODIA_API_KEY", "")
    if not key:
        raise RuntimeError("No PRODIA_API_KEY")

    # Crear el job
    resp = requests.post(
        "https://api.prodia.com/v1/job",
        headers={
            "X-Prodia-Key": key,
            "Content-Type": "application/json",
        },
        json={
            "model": "dreamshaper_8.safetensors [9d40847d]",
            "prompt": prompt,
            "negative_prompt": "blurry, bad quality, watermark",
            "steps": 25,
            "cfg_scale": 7,
            "width": min(width, 1024),
            "height": min(height, 1024),
            "sampler": "DPM++ 2M Karras",
        },
        timeout=30,
    )

    if resp.status_code != 200:
        raise RuntimeError(f"Prodia job {resp.status_code}: {resp.text[:200]}")

    job_id = resp.json().get("job")
    if not job_id:
        raise RuntimeError("Prodia: no job ID")

    # Polling hasta que el job termine
    for _ in range(40):
        time.sleep(3)
        status_resp = requests.get(
            f"https://api.prodia.com/v1/job/{job_id}",
            headers={"X-Prodia-Key": key},
            timeout=15,
        )
        status_data = status_resp.json()
        status = status_data.get("status")

        if status == "succeeded":
            image_url = status_data.get("imageUrl")
            img_data = requests.get(image_url, timeout=60).content
            local_path = _save_bytes(img_data)
            return {"url": image_url, "local_path": local_path, "revised_prompt": prompt, "provider": "Prodia/DreamShaper"}

        elif status == "failed":
            raise RuntimeError(f"Prodia job failed: {status_data}")

    raise RuntimeError("Prodia: timeout esperando el job")


# ── 5. HuggingFace Inference API (FLUX.2-klein-4B → SDXL — gratis) ──────────

def generate_huggingface(prompt: str, width: int = 1024, height: int = 1024) -> dict:
    key = (os.environ.get("HF_TOKEN") or os.environ.get("HF_API_KEY")
           or os.environ.get("HUGGINGFACE_API_KEY", ""))
    if not key:
        raise RuntimeError("No HF_TOKEN")

    hf_models = [
        ("black-forest-labs/FLUX.2-klein-4B",      {"inputs": prompt, "parameters": {"width": min(width,1024), "height": min(height,1024), "num_inference_steps": 4}}),
        ("black-forest-labs/FLUX.1-schnell",        {"inputs": prompt, "parameters": {"width": min(width,1024), "height": min(height,1024), "num_inference_steps": 4}}),
        ("stabilityai/stable-diffusion-xl-base-1.0",{"inputs": prompt, "parameters": {"width": min(width,1024), "height": min(height,1024), "num_inference_steps": 30, "guidance_scale": 7.5}}),
    ]

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    for model, payload in hf_models:
        try:
            resp = requests.post(
                f"https://api-inference.huggingface.co/models/{model}",
                headers=headers, json=payload, timeout=TIMEOUT,
            )
            if resp.status_code == 503:
                continue
            if resp.status_code != 200:
                logger.debug("HF/%s: %s", model, resp.status_code)
                continue
            content_type = resp.headers.get("content-type", "")
            if "image" in content_type or "octet-stream" in content_type:
                local_path = _save_bytes(resp.content)
                label = "FLUX.2-klein" if "FLUX.2" in model else ("FLUX.1" if "FLUX.1" in model else "SDXL")
                logger.info("HuggingFace %s OK", label)
                return {"url": None, "local_path": local_path,
                        "revised_prompt": prompt, "provider": f"HuggingFace/{label}"}
        except Exception as e:
            logger.debug("HF/%s: %s", model, e)

    raise RuntimeError("HuggingFace: todos los modelos fallaron o cargando")


# ── Stable Horde (gratis, sin API key, NSFW activado) ────────────────────────

def generate_stable_horde(prompt: str, width: int = 512, height: int = 512) -> dict:
    """Stable Horde — gratis, anónimo, NSFW sin censura. No requiere API key."""
    from tools.unblock_bee import _try_stable_horde
    return _try_stable_horde(prompt, width, height)


# ── Función principal: prueba todos los disponibles en orden ─────────────────

def _has_together_key() -> bool:
    return bool(
        os.environ.get("TOGETHER_API_KEY") or os.environ.get("TOG_API1")
        or os.environ.get("TOG_API2") or os.environ.get("TOG_API3")
        or os.environ.get("TOG_API4") or os.environ.get("TOG_API5")
    )


PROVIDER_CHAIN = [
    ("BFL/FLUX.2",   generate_bfl,           "BFL_API_KEY"),
    ("Stable Horde", generate_stable_horde,  None),
    ("FAL.ai/FLUX.2",generate_fal,           "FAL_KEY"),
    ("Together AI",  generate_together,      "TOGETHER_API_KEY"),
    ("getimg.ai",    generate_getimg,        "GETIMG_API_KEY"),
    ("Prodia",       generate_prodia,        "PRODIA_API_KEY"),
    ("HuggingFace",  generate_huggingface,  "HF_TOKEN"),
]


def _check_key(env_key) -> bool:
    """Verifica si un proveedor tiene clave disponible, incluyendo variantes."""
    if env_key is None:
        return True
    if os.environ.get(env_key):
        return True
    if env_key == "HF_TOKEN":
        return bool(os.environ.get("HF_API_KEY") or os.environ.get("HUGGINGFACE_API_KEY"))
    if env_key == "TOGETHER_API_KEY":
        return _has_together_key()
    if env_key == "BFL_API_KEY":
        return bool(os.environ.get("BFL_API_KEY") or os.environ.get("BFL_KEY")
                    or os.environ.get("BFL_API_KEY2"))
    return False


def get_available_providers() -> list:
    available = []
    for name, fn, env_key in PROVIDER_CHAIN:
        if _check_key(env_key):
            available.append(name)
    if not any("Stable" in n for n in available):
        available.insert(0, "Stable Horde")
    if os.environ.get("OPENAI_API_KEY"):
        available.append("DALL-E 3")
    return available


def generate_any(prompt: str, size: str = "1024x1024") -> dict:
    """
    Intenta todos los proveedores disponibles en orden de prioridad.
    Sin Replicate. BFL/FLUX.2 primero (si hay BFL_API_KEY), Stable Horde siempre disponible.
    """
    parts = size.split("x")
    w = int(parts[0]) if len(parts) == 2 else 512
    h = int(parts[1]) if len(parts) == 2 else 512

    errors = []

    for name, fn, env_key in PROVIDER_CHAIN:
        if not _check_key(env_key):
            continue
        try:
            logger.info("Intentando proveedor: %s", name)
            result = fn(prompt, w, h)
            logger.info("Imagen generada con: %s", name)
            return result
        except Exception as e:
            errors.append(f"{name}: {e}")
            logger.warning("%s falló: %s", name, e)

    # 7. DALL-E con bypass automático
    if os.environ.get("OPENAI_API_KEY"):
        try:
            from tools.bypass_engine import bypass_image_generation
            return bypass_image_generation(prompt, size)
        except Exception as e:
            errors.append(f"DALL-E bypass: {e}")

    raise RuntimeError(
        f"Sin proveedores disponibles o todos fallaron. "
        f"Errores: {' | '.join(errors[-3:])}"
    )
