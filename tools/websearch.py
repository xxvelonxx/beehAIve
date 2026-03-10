from __future__ import annotations


def web_search(query: str, max_results: int = 6) -> str:
    """Búsqueda real en DuckDuckGo con headers ghost si está activo."""
    from tools import ghost_mode
    results = []
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS

    ghost_mode.jitter(0.2, 0.8)
    with DDGS(headers=ghost_mode.get_headers() if ghost_mode.is_active() else None) as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            title = r.get("title", "")
            body = r.get("body", "")[:300]
            href = r.get("href", "")
            results.append(f"**{title}**\n{body}\n{href}")
    ghost_mode.rotate_if_needed()
    return "\n\n".join(results) if results else "No encontré resultados."
