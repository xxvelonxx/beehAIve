import re


def get_video_id(url: str) -> str:
    patterns = [
        r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:embed/)([A-Za-z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    raise ValueError(f"No pude extraer el ID del video de: {url}")


def get_transcript(url: str, lang: str = "es") -> str:
    """Obtiene la transcripción de un video de YouTube."""
    from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound

    video_id = get_video_id(url)
    api = YouTubeTranscriptApi()

    try:
        transcript = api.fetch(video_id, languages=[lang, "en", "es"])
    except NoTranscriptFound:
        transcript = api.fetch(video_id)

    text = " ".join(entry.text for entry in transcript)
    return text[:8000]


def summarize_transcript(url: str) -> str:
    """Descarga y resume la transcripción de un video de YouTube."""
    import os, openai

    transcript = get_transcript(url)

    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Resume esta transcripción de YouTube en español. Sé conciso y claro. Incluye los puntos más importantes."},
            {"role": "user", "content": transcript},
        ],
        max_tokens=700,
    )
    return response.choices[0].message.content.strip()
