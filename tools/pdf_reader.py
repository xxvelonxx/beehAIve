def read_pdf(path: str) -> str:
    """Extrae texto de un PDF."""
    from pypdf import PdfReader

    reader = PdfReader(path)
    pages = []
    for page in reader.pages[:20]:
        text = page.extract_text()
        if text:
            pages.append(text.strip())

    return "\n\n".join(pages)[:8000]


def analyze_pdf(path: str) -> str:
    """Lee y analiza un PDF con IA."""
    import os, openai

    text = read_pdf(path)
    if not text.strip():
        return "El PDF no tiene texto extraíble (puede ser una imagen escaneada)."

    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Analiza este documento PDF. Resume su contenido, identifica los puntos clave y cualquier dato importante. Usa español."},
            {"role": "user", "content": text},
        ],
        max_tokens=800,
    )
    return response.choices[0].message.content.strip()
