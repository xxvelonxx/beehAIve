"""
video_gen.py — Generación de video con LTX-2 y otros modelos.

Cascada de proveedores (orden de prioridad):
  1. LTX-2 via fal.ai    — mejor calidad, audio + video sincronizado (FAL_KEY)
  2. LTX-Video via fal.ai — versión anterior, también buena (FAL_KEY)
  3. LTX-2 via HF        — con HF_TOKEN
  4. Minimax Video-01    — alternativa de alta calidad (via fal.ai o HF)
  5. Wan-2.1             — open source de alta calidad (via fal.ai)

Modos soportados:
  - text-to-video: descripción → video
  - image-to-video: imagen + descripción → video animado

Uso:
  from tools.video_gen import generate_video
  result = generate_video("a cat surfing a wave", duration=5)
  # result = {"url": "...", "path": "...", "provider": "...", "duration": 5}
"""
from __future__ import annotations

import os
import time
import tempfile
import logging
import requests
from pathlib import Path

logger = logging.getLogger("beeatrix.videogen")

VIDEO_DIR = Path("memory/generated_videos")
VIDEO_DIR.mkdir(parents=True, exist_ok=True)


def _fal_generate(model_id: str, payload: dict, fal_key: str) -> dict:
    """
    Llama a fal.ai API (síncrono con polling).
    model_id: "fal-ai/ltx-video-2" / "fal-ai/ltx-video" / "fal-ai/minimax-video-01" etc.
    """
    headers = {
        "Authorization": f"Key {fal_key}",
        "Content-Type": "application/json",
    }

    # Enviar a la queue
    submit_url = f"https://queue.fal.run/{model_id}"
    resp = requests.post(submit_url, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    request_id = data.get("request_id")
    if not request_id:
        raise RuntimeError(f"fal.ai no devolvió request_id: {data}")

    status_url = f"https://queue.fal.run/{model_id}/requests/{request_id}/status"
    result_url = f"https://queue.fal.run/{model_id}/requests/{request_id}"

    # Polling hasta completar (timeout 3 minutos)
    deadline = time.time() + 180
    while time.time() < deadline:
        status_resp = requests.get(status_url, headers=headers, timeout=15)
        status_data = status_resp.json()
        status = status_data.get("status", "")

        if status == "COMPLETED":
            result_resp = requests.get(result_url, headers=headers, timeout=30)
            return result_resp.json()

        if status in ("FAILED", "CANCELLED"):
            raise RuntimeError(f"fal.ai job {status}: {status_data}")

        logger.debug("fal.ai status: %s — esperando...", status)
        time.sleep(4)

    raise TimeoutError("fal.ai video generation timeout (3 min)")


def _download_video(url: str, prefix: str = "video") -> str:
    """Descarga el video generado y devuelve el path local."""
    ext = ".mp4"
    if ".webm" in url:
        ext = ".webm"

    fname = VIDEO_DIR / f"{prefix}_{int(time.time())}{ext}"
    resp = requests.get(url, timeout=120, stream=True)
    resp.raise_for_status()

    with open(fname, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    return str(fname)


def generate_video(
    prompt: str,
    duration: int = 5,
    image_url: str | None = None,
    image_b64: str | None = None,
    width: int = 848,
    height: int = 480,
    fps: int = 24,
) -> dict:
    """
    Genera un video a partir de un prompt de texto.
    Opcionalmente acepta una imagen de referencia para image-to-video.

    Devuelve:
      {"url": str, "path": str, "provider": str, "duration": int, "error": str | None}
    """
    fal_key = (
        os.environ.get("FAL_KEY") or os.environ.get("FAL_API_KEY")
        or os.environ.get("FAL_TOKEN") or ""
    )
    hf_token = (
        os.environ.get("HF_TOKEN")
        or os.environ.get("HF_API_KEY")
        or os.environ.get("HUGGINGFACE_API_KEY")
        or ""
    )

    errors = []

    # ── 1. LTX-2 via fal.ai (audio+video, mejor calidad) ─────────────────────
    if fal_key:
        for model_id in ("fal-ai/ltx-video-2", "fal-ai/ltx-video"):
            try:
                payload: dict = {
                    "prompt": prompt,
                    "duration": f"{duration}_seconds" if duration in (3, 5, 8, 10) else "5_seconds",
                    "resolution": "720p" if width >= 1280 else "480p",
                    "aspect_ratio": f"{width}:{height}",
                }
                if image_url:
                    payload["image_url"] = image_url
                elif image_b64:
                    payload["image_url"] = f"data:image/jpeg;base64,{image_b64}"

                logger.info("Generando video con %s...", model_id)
                result = _fal_generate(model_id, payload, fal_key)

                video_data = result.get("video") or result.get("videos", [{}])[0]
                url = video_data.get("url", "") if isinstance(video_data, dict) else str(video_data)

                if url:
                    path = _download_video(url, prefix="ltx2")
                    logger.info("Video LTX-2 generado: %s", path)
                    return {
                        "url": url, "path": path,
                        "provider": f"LTX-2/{model_id}",
                        "duration": duration, "error": None,
                    }
            except Exception as e:
                errors.append(f"fal.ai/{model_id}: {e}")
                logger.warning("fal.ai %s error: %s", model_id, e)

        # Wan-2.1 como fallback en fal.ai
        try:
            payload = {
                "prompt": prompt,
                "num_frames": fps * duration,
                "fps": fps,
            }
            result = _fal_generate("fal-ai/wan-video/text-to-video/turbo", payload, fal_key)
            video_data = result.get("video") or {}
            url = video_data.get("url", "") if isinstance(video_data, dict) else str(video_data)
            if url:
                path = _download_video(url, prefix="wan")
                return {
                    "url": url, "path": path,
                    "provider": "Wan-2.1/fal.ai",
                    "duration": duration, "error": None,
                }
        except Exception as e:
            errors.append(f"fal.ai/wan: {e}")

    # ── 2. LTX-Video via HuggingFace Inference API ────────────────────────────
    if hf_token:
        hf_models = [
            "Lightricks/LTX-Video",
            "stabilityai/stable-video-diffusion-img2vid-xt",
        ]
        for hf_model in hf_models:
            try:
                headers = {"Authorization": f"Bearer {hf_token}"}
                payload = {"inputs": prompt, "parameters": {"num_frames": fps * duration}}
                resp = requests.post(
                    f"https://api-inference.huggingface.co/models/{hf_model}",
                    headers=headers,
                    json=payload,
                    timeout=120,
                )
                if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("video"):
                    fname = VIDEO_DIR / f"hf_video_{int(time.time())}.mp4"
                    fname.write_bytes(resp.content)
                    logger.info("Video HF generado: %s", fname)
                    return {
                        "url": "", "path": str(fname),
                        "provider": f"HF/{hf_model}",
                        "duration": duration, "error": None,
                    }
                else:
                    errors.append(f"HF/{hf_model}: status {resp.status_code}")
            except Exception as e:
                errors.append(f"HF/{hf_model}: {e}")
                logger.warning("HF video %s error: %s", hf_model, e)

    # ── Sin proveedores disponibles ───────────────────────────────────────────
    error_summary = " | ".join(errors[:3]) if errors else "No hay FAL_KEY ni HF_TOKEN configurados"
    logger.warning("video_gen: todos los proveedores fallaron — %s", error_summary)
    return {
        "url": "", "path": "",
        "provider": "none",
        "duration": duration,
        "error": error_summary,
        "setup_needed": not bool(fal_key),
        "message": (
            "Para generar videos necesito una clave de fal.ai (FAL_KEY).\n"
            "Regístrate gratis en https://fal.ai y añade tu clave como secreto FAL_KEY."
            if not fal_key else error_summary
        ),
    }


def generate_video_from_image(
    img_b64: str,
    prompt: str = "animate this image naturally",
    duration: int = 5,
) -> dict:
    """Anima una imagen estática convirtiéndola en video (image-to-video)."""
    return generate_video(prompt=prompt, duration=duration, image_b64=img_b64)
