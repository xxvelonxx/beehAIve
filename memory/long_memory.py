"""
BEEA Long Memory — Memoria persistente a largo plazo.
Almacena hechos importantes, preferencias y contexto en un vector store simple.
Sin ChromaDB ni dependencias pesadas — usa embeddings de OpenAI + cosine similarity.
"""
import json
import logging
import math
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("beeatrix.longmemory")

MEMORY_FILE = Path("memory/long_term.json")
MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)

MAX_MEMORIES = 500
TOP_K = 5


def _cosine(a: list, b: list) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _embed(text: str) -> list:
    """Crea embedding simple usando OpenAI text-embedding-3-small."""
    import openai
    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
    resp = client.embeddings.create(
        model="text-embedding-3-small",
        input=text[:2000],
    )
    return resp.data[0].embedding


def _load() -> list:
    if not MEMORY_FILE.exists():
        return []
    try:
        return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(memories: list):
    MEMORY_FILE.write_text(
        json.dumps(memories, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


class LongMemory:
    def remember(self, content: str, category: str = "general", importance: int = 5) -> dict:
        """
        Guarda un hecho o preferencia en la memoria a largo plazo.
        importance: 1-10 (10 = crítico)
        """
        try:
            embedding = _embed(content)
        except Exception as e:
            logger.warning("Embedding error, guardando sin vector: %s", e)
            embedding = []

        entry = {
            "id": f"mem_{int(time.time() * 1000)}",
            "content": content,
            "category": category,
            "importance": importance,
            "embedding": embedding,
            "created_at": datetime.now().isoformat(),
            "accessed": 0,
        }

        memories = _load()
        memories.append(entry)

        if len(memories) > MAX_MEMORIES:
            memories.sort(key=lambda m: m.get("importance", 1) * 10 + m.get("accessed", 0))
            memories = memories[-MAX_MEMORIES:]

        _save(memories)
        logger.info("LongMemory: guardado — '%s...' [%s]", content[:60], category)

        # Compartir con todas las BEEs si es conocimiento relevante (importance >= 6)
        if importance >= 6 and category not in ("conversacion", "preferencia_alvaro"):
            try:
                from memory.shared_knowledge import shared_knowledge
                shared_knowledge.add(content, source=f"BEEA/{category}", score=float(importance))
            except Exception:
                pass

        return entry

    def recall(self, query: str, top_k: int = TOP_K) -> list:
        """
        Busca los recuerdos más relevantes para la consulta.
        Devuelve lista de {content, category, similarity, created_at}.
        """
        memories = _load()
        if not memories:
            return []

        try:
            query_emb = _embed(query)
        except Exception as e:
            logger.warning("Recall embedding error: %s", e)
            return memories[-top_k:]

        scored = []
        for mem in memories:
            emb = mem.get("embedding", [])
            if emb:
                sim = _cosine(query_emb, emb)
            else:
                sim = 0.3
            scored.append((sim, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]

        results = []
        for sim, mem in top:
            results.append({
                "content": mem["content"],
                "category": mem.get("category", "general"),
                "similarity": round(sim, 3),
                "created_at": mem.get("created_at", ""),
                "importance": mem.get("importance", 5),
            })
            mem["accessed"] = mem.get("accessed", 0) + 1

        updated_mems = [m for _, m in scored] + [m for m in memories if m not in [x[1] for x in scored]]
        _save(updated_mems[:MAX_MEMORIES])

        return results

    def remember_preference(self, pref: str):
        """Guarda una preferencia de Álvaro con importancia alta."""
        self.remember(pref, category="preferencia_alvaro", importance=8)

    def remember_fact(self, fact: str):
        """Guarda un hecho general."""
        self.remember(fact, category="hecho", importance=5)

    def remember_conversation(self, summary: str):
        """Guarda un resumen de conversación importante."""
        self.remember(summary, category="conversacion", importance=4)

    def get_context_for(self, message: str) -> str:
        """
        Devuelve contexto relevante de la memoria para inyectar en el prompt.
        Formato listo para usar en system prompt.
        """
        results = self.recall(message, top_k=3)
        if not results:
            return ""

        lines = ["[Recuerdos relevantes de conversaciones pasadas:]"]
        for r in results:
            lines.append(f"- ({r['category']}) {r['content']}")
        return "\n".join(lines)

    def list_recent(self, n: int = 10) -> list:
        memories = _load()
        memories.sort(key=lambda m: m.get("created_at", ""), reverse=True)
        return memories[:n]

    def forget(self, memory_id: str) -> bool:
        memories = _load()
        original = len(memories)
        memories = [m for m in memories if m.get("id") != memory_id]
        _save(memories)
        return len(memories) < original

    def forget_all(self):
        _save([])
        logger.info("LongMemory: memoria borrada")

    def stats(self) -> dict:
        memories = _load()
        categories = {}
        for m in memories:
            cat = m.get("category", "general")
            categories[cat] = categories.get(cat, 0) + 1
        return {
            "total": len(memories),
            "max": MAX_MEMORIES,
            "categories": categories,
        }


long_memory = LongMemory()
