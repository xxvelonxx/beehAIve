"""
BEEA Img2Img — Imagen a imagen.
Toma una foto de referencia y genera una nueva basada en ella.
Usa Stable Horde (gratis, NSFW) para img2img real.
"""
import base64
import logging
import os
import time
import tempfile
import requests

logger = logging.getLogger("beeatrix.img2img")


def _img_to_b64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _b64_to_img(b64_str: str) -> bytes:
    return base64.b64decode(b64_str)


def img2img_stable_horde(
    init_image_b64: str,
    prompt: str,
    denoising_strength: float = 0.65,
    width: int = 512,
    height: int = 512,
) -> dict:
    """
    Imagen a imagen con Stable Horde.
    init_image_b64: imagen base en base64
    prompt: descripción de lo que quieres cambiar/mantener
    denoising_strength: 0.0 = igual a la original, 1.0 = completamente nueva
    """
    api_key = os.environ.get("STABLE_HORDE_KEY", "0000000000")

    job_resp = requests.post(
        "https://stablehorde.net/api/v2/generate/async",
        headers={
            "apikey": api_key,
            "Content-Type": "application/json",
            "Client-Agent": "BEEA:1.0:beea-img2img",
        },
        json={
            "prompt": prompt,
            "params": {
                "sampler_name": "k_euler_a",
                "cfg_scale": 7.5,
                "denoising_strength": denoising_strength,
                "height": min(height, 1024),
                "width": min(width, 1024),
                "steps": 25,
                "n": 1,
            },
            "source_image": init_image_b64,
            "source_processing": "img2img",
            "nsfw": True,
            "censor_nsfw": False,
            "trusted_workers": False,
            "slow_workers": True,
            "models": ["Deliberate", "Realistic Vision", "Anything Diffusion"],
            "r2": True,
        },
        timeout=30,
    )

    if job_resp.status_code not in (200, 201, 202):
        raise RuntimeError(f"Stable Horde img2img {job_resp.status_code}: {job_resp.text[:200]}")

    job_id = job_resp.json().get("id")
    if not job_id:
        raise RuntimeError("Stable Horde img2img: sin job ID")

    logger.info("Stable Horde img2img job %s enviado...", job_id)

    for attempt in range(72):
        time.sleep(5)
        status_resp = requests.get(
            f"https://stablehorde.net/api/v2/generate/check/{job_id}",
            headers={"apikey": api_key},
            timeout=15,
        )
        status = status_resp.json()

        if status.get("done"):
            break
        if status.get("faulted"):
            raise RuntimeError("Stable Horde img2img: job fallido")

        logger.info("img2img esperando... ETA: %ss (intento %d/72)", status.get("wait_time", "?"), attempt + 1)

    result_resp = requests.get(
        f"https://stablehorde.net/api/v2/generate/status/{job_id}",
        headers={"apikey": api_key},
        timeout=30,
    )
    result = result_resp.json()
    generations = result.get("generations", [])

    if not generations:
        raise RuntimeError("Stable Horde img2img: sin generaciones")

    gen = generations[0]
    img_b64 = gen.get("img", "")
    if not img_b64:
        raise RuntimeError("Stable Horde img2img: imagen vacía")

    img_bytes = _b64_to_img(img_b64)
    with tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as tmp:
        tmp.write(img_bytes)
        local_path = tmp.name

    logger.info("img2img completado con modelo: %s", gen.get("model", "?"))
    return {
        "local_path": local_path,
        "url": None,
        "provider": f"StableHorde_img2img/{gen.get('model','?')}",
        "model": gen.get("model", "?"),
    }


def img2img_from_file(image_path: str, prompt: str, strength: float = 0.65) -> dict:
    """Wrapper conveniente: acepta path de archivo."""
    b64 = _img_to_b64(image_path)
    from PIL import Image
    with Image.open(image_path) as img:
        w, h = img.size
    w = min(w, 1024)
    h = min(h, 1024)
    w = (w // 64) * 64
    h = (h // 64) * 64
    w = max(w, 512)
    h = max(h, 512)
    return img2img_stable_horde(b64, prompt, strength, w, h)


def img2img_from_b64(img_b64: str, prompt: str, strength: float = 0.65) -> dict:
    """Wrapper: acepta base64 directamente."""
    return img2img_stable_horde(img_b64, prompt, strength, 512, 512)
