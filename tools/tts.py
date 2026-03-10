import os
import tempfile
from pathlib import Path


def text_to_speech(text: str, voice: str = "nova") -> str:
    """
    Convierte texto a audio usando OpenAI TTS.
    Devuelve la ruta al archivo .ogg generado.
    Voces disponibles: alloy, echo, fable, onyx, nova, shimmer
    """
    import openai

    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    text = text[:4096]

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name

    with client.audio.speech.with_streaming_response.create(
        model="tts-1",
        voice=voice,
        input=text,
        response_format="opus",
    ) as response:
        response.stream_to_file(tmp_path)

    return tmp_path


VOICE_MODE_FILE = Path("memory/voice_mode.txt")


def is_voice_mode() -> bool:
    return VOICE_MODE_FILE.exists() and VOICE_MODE_FILE.read_text().strip() == "on"


def set_voice_mode(enabled: bool) -> None:
    VOICE_MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
    VOICE_MODE_FILE.write_text("on" if enabled else "off")
