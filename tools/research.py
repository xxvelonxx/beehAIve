import urllib.request
import urllib.parse
import json


class ResearchTool:
    def search(self, query: str) -> dict:
        try:
            url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(query.replace(" ", "_"))
            with urllib.request.urlopen(url, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "query": query,
                    "title": data.get("title", ""),
                    "summary": data.get("extract", "")[:600],
                    "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
                }
        except Exception:
            return {
                "query": query,
                "summary": f"No se encontró información automática para: {query}. Intenta especificar más.",
            }

    def fetch_url(self, url: str) -> dict:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Beeatrix/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode("utf-8", errors="ignore")[:3000]
                return {
                    "url": url,
                    "status": resp.status,
                    "content_preview": content,
                }
        except Exception as e:
            return {"url": url, "error": str(e)}


research_tool = ResearchTool()
