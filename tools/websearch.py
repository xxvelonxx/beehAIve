def web_search(query: str, max_results: int = 6) -> str:
    """Búsqueda real en DuckDuckGo. Sin API key."""
    results = []
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            title = r.get("title", "")
            body = r.get("body", "")[:300]
            href = r.get("href", "")
            results.append(f"**{title}**\n{body}\n{href}")
    return "\n\n".join(results) if results else "No encontré resultados."
