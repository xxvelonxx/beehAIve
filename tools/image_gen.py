"""
Generador de imágenes para BEEA.
Cascada automática sin Replicate — Stable Horde primero (gratis, NSFW, sin censura).
"""
import os
import logging

logger = logging.getLogger("beeatrix.imagegen")


def generate_image(prompt: str, size: str = "1024x1024", quality: str = "standard") -> dict:
    """
    Genera imagen. Cascade sin Replicate:
    Stable Horde → FAL → Together → getimg → Prodia → HuggingFace → DALL-E bypass
    """
    from tools.image_providers import generate_any
    return generate_any(prompt, size)
