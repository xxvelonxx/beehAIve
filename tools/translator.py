LANGUAGE_MAP = {
    "inglés": "English", "english": "English",
    "español": "Spanish", "spanish": "Spanish",
    "francés": "French", "french": "French",
    "alemán": "German", "german": "German",
    "portugués": "Portuguese", "portuguese": "Portuguese",
    "italiano": "Italian", "italian": "Italian",
    "chino": "Chinese", "chinese": "Chinese",
    "japonés": "Japanese", "japanese": "Japanese",
    "árabe": "Arabic", "arabic": "Arabic",
    "ruso": "Russian", "russian": "Russian",
    "coreano": "Korean", "korean": "Korean",
}


def translate(text: str, target_language: str = "English") -> str:
    """Traduce texto al idioma destino usando OpenAI."""
    import os, openai

    lang = LANGUAGE_MAP.get(target_language.lower(), target_language)

    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"Translate the following text to {lang}. Return only the translation, nothing else."},
            {"role": "user", "content": text},
        ],
        max_tokens=1000,
    )
    return response.choices[0].message.content.strip()
