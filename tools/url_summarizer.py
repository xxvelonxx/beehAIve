import requests


def fetch_and_summarize(url: str) -> str:
    """Descarga una URL y la resume con IA."""
    import os
    import openai

    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()

    from html.parser import HTMLParser

    class _TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.text = []
            self._skip = False

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style", "nav", "footer", "header"):
                self._skip = True

        def handle_endtag(self, tag):
            if tag in ("script", "style", "nav", "footer", "header"):
                self._skip = False

        def handle_data(self, data):
            if not self._skip:
                cleaned = data.strip()
                if cleaned:
                    self.text.append(cleaned)

    parser = _TextExtractor()
    parser.feed(resp.text)
    raw_text = " ".join(parser.text)[:6000]

    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Eres un asistente que resume páginas web de forma clara y concisa en español. Extrae lo más importante."},
            {"role": "user", "content": f"Resume este contenido de la URL {url}:\n\n{raw_text}"},
        ],
        max_tokens=600,
    )
    return response.choices[0].message.content.strip()
