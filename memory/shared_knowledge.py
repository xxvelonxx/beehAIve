"""
SharedKnowledge — Pool de inteligencia colectiva.

Todo lo que aprende cualquier BEE (en cualquier rol, sobre cualquier tema)
o BEEA en conversación, se propaga aquí automáticamente.

Cuando una BEE arranca, carga este pool además de sus habilidades propias.
Resultado: la colmena entera se vuelve más inteligente con cada aprendizaje.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Optional

from core.logger import logger

POOL_PATH = Path("memory/collective_knowledge.json")
POOL_PATH.parent.mkdir(parents=True, exist_ok=True)

MAX_INSIGHTS   = 200   # máx entradas en el pool
TOP_FOR_PROMPT = 15    # cuántas se inyectan en cada system prompt


class SharedKnowledge:
    """
    Pool de conocimiento compartido entre BEEA y todas las BEEs.

    Estructura de cada entrada:
    {
        "insight":    "texto del conocimiento",
        "source":     "coder/Solidity" | "BEEA/conversacion" | ...,
        "score":      8.5,             # 0-10, calidad del conocimiento
        "hits":       3,               # veces que se ha reforzado
        "added_at":   "2026-03-10",
        "last_hit":   "2026-03-10",
    }
    """

    def __init__(self):
        self._lock  = threading.Lock()
        self._pool: list[dict] = []
        self._load()

    # ── Persistencia ─────────────────────────────────────────────────────────

    def _load(self):
        try:
            if POOL_PATH.exists():
                self._pool = json.loads(POOL_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("SharedKnowledge load error: %s", e)
            self._pool = []

    def _save(self):
        try:
            POOL_PATH.write_text(
                json.dumps(self._pool, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("SharedKnowledge save error: %s", e)

    # ── Añadir conocimiento ───────────────────────────────────────────────────

    def add(self, insight: str, source: str, score: float = 7.0):
        """
        Registra un nuevo conocimiento en el pool colectivo.
        Si ya existe (texto similar), refuerza su peso en lugar de duplicar.

        insight: el texto del conocimiento (patrón, técnica, dato importante)
        source:  quién lo aprendió — "coder/Solidity", "BEEA/conversacion", etc.
        score:   calidad 0-10
        """
        if not insight or len(insight.strip()) < 10:
            return

        insight = insight.strip()[:400]

        with self._lock:
            # Buscar si ya existe algo muy similar (primeras 60 chars)
            key = insight[:60].lower()
            for entry in self._pool:
                if entry["insight"][:60].lower() == key:
                    # Reforzar entrada existente
                    entry["hits"]     += 1
                    entry["score"]     = round(max(entry["score"], score), 1)
                    entry["last_hit"]  = time.strftime("%Y-%m-%d")
                    if source not in entry["source"]:
                        entry["source"] += f" + {source}"
                    self._save()
                    return

            # Nueva entrada
            self._pool.append({
                "insight":  insight,
                "source":   source,
                "score":    round(score, 1),
                "hits":     1,
                "added_at": time.strftime("%Y-%m-%d"),
                "last_hit": time.strftime("%Y-%m-%d"),
            })

            # Ordenar por score*hits y recortar
            self._pool.sort(
                key=lambda x: x["score"] * (1 + x["hits"] * 0.1),
                reverse=True,
            )
            self._pool = self._pool[:MAX_INSIGHTS]
            self._save()

    def add_many(self, insights: list[str], source: str, score: float = 7.0):
        """Añade múltiples insights de una vez (resultado de entrenamiento)."""
        for ins in insights:
            self.add(ins, source, score)

    # ── Consultar conocimiento ────────────────────────────────────────────────

    def get_top(self, n: int = TOP_FOR_PROMPT, topic_filter: str = None) -> list[dict]:
        """
        Devuelve los N conocimientos más valiosos.
        topic_filter: si se da, prioriza entradas cuyo source o insight contiene ese texto.
        """
        with self._lock:
            pool = list(self._pool)

        if topic_filter:
            tf = topic_filter.lower()
            # Primero los que tienen el filtro, luego el resto
            matched = [e for e in pool if tf in e["insight"].lower() or tf in e["source"].lower()]
            others  = [e for e in pool if e not in matched]
            pool    = matched[:n//2 + 1] + others
        
        return pool[:n]

    def as_prompt_block(self, topic_filter: str = None) -> str:
        """
        Genera el bloque de texto para inyectar en system prompts.
        Compacto y directo — sin florituras.
        """
        entries = self.get_top(n=TOP_FOR_PROMPT, topic_filter=topic_filter)
        if not entries:
            return ""

        lines = ["Conocimiento colectivo de la colmena (lo que ya saben todas las BEEs):"]
        for e in entries:
            hits_tag = f" [{e['hits']}x]" if e["hits"] > 1 else ""
            lines.append(f"• {e['insight']}{hits_tag}")

        return "\n".join(lines)

    def stats(self) -> dict:
        with self._lock:
            pool = list(self._pool)
        sources = {}
        for e in pool:
            src = e["source"].split("/")[0]
            sources[src] = sources.get(src, 0) + 1
        return {
            "total_insights": len(pool),
            "sources":        sources,
            "top_score":      pool[0]["score"] if pool else 0,
            "most_hit":       max(pool, key=lambda x: x["hits"])["insight"][:80] if pool else "",
        }

    def summary_for_user(self) -> str:
        s = self.stats()
        lines = [
            f"Pool colectivo: {s['total_insights']} conocimientos compartidos",
        ]
        if s["sources"]:
            src_str = " | ".join(f"{k}: {v}" for k, v in s["sources"].items())
            lines.append(f"Fuentes: {src_str}")
        if s["most_hit"]:
            lines.append(f"Más reforzado: {s['most_hit']}")
        return "\n".join(lines)


# Instancia global — única para todo el proceso
shared_knowledge = SharedKnowledge()
