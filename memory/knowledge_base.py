"""
Knowledge Base — Base de conocimiento persistente de BEEA.

Almacena todo lo que BEEA aprende por dominio.
Real, persistente, organizado. Crece con cada sesión de aprendizaje.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional
from core.logger import logger


KB_FILE = Path("knowledge_base.json")


def _load() -> dict:
    if not KB_FILE.exists():
        KB_FILE.write_text("{}", encoding="utf-8")
    try:
        return json.loads(KB_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict) -> None:
    KB_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


class KnowledgeBase:
    """
    Base de conocimiento real y persistente.
    Cada dominio tiene su propio árbol de conocimiento acumulado.
    """

    def get_domains(self) -> list[str]:
        """Lista todos los dominios aprendidos."""
        return list(_load().keys())

    def get_domain(self, domain: str) -> Optional[dict]:
        """Devuelve todo el conocimiento de un dominio."""
        return _load().get(domain.lower().strip())

    def get_expertise_level(self, domain: str) -> int:
        """0-100. Sube con cada sesión de aprendizaje."""
        d = self.get_domain(domain)
        if not d:
            return 0
        return d.get("expertise_level", 0)

    def add_learning(self, domain: str, subtopic: str, content: str, source: str = "") -> None:
        """
        Agrega un bloque de conocimiento a un dominio.
        Se llama una vez por BEE que completó su investigación.
        """
        data = _load()
        domain = domain.lower().strip()

        if domain not in data:
            data[domain] = {
                "domain": domain,
                "expertise_level": 0,
                "sessions": 0,
                "subtopics": {},
                "synthesis": "",
                "key_facts": [],
                "sources": [],
                "first_learned": time.strftime("%Y-%m-%d %H:%M"),
                "last_updated": time.strftime("%Y-%m-%d %H:%M"),
            }

        domain_data = data[domain]

        # Guardar subtópico
        domain_data["subtopics"][subtopic] = {
            "content": content[:3000],
            "source": source,
            "learned_at": time.strftime("%Y-%m-%d %H:%M"),
        }

        # Registrar fuente
        if source and source not in domain_data["sources"]:
            domain_data["sources"].append(source)

        domain_data["last_updated"] = time.strftime("%Y-%m-%d %H:%M")

        _save(data)
        logger.info("KB: Added '%s' to domain '%s'", subtopic, domain)

    def update_synthesis(self, domain: str, synthesis: str, key_facts: list[str], expertise_delta: int = 10) -> None:
        """
        Actualiza la síntesis maestra y el nivel de experiencia del dominio.
        Se llama después de que todas las BEES terminan.
        """
        data = _load()
        domain = domain.lower().strip()

        if domain not in data:
            return

        domain_data = data[domain]
        domain_data["synthesis"] = synthesis[:5000]
        domain_data["key_facts"] = key_facts[:50]
        domain_data["sessions"] = domain_data.get("sessions", 0) + 1
        current_level = domain_data.get("expertise_level", 0)
        domain_data["expertise_level"] = min(100, current_level + expertise_delta)
        domain_data["last_updated"] = time.strftime("%Y-%m-%d %H:%M")

        _save(data)
        logger.info("KB: Updated synthesis for '%s' (expertise: %d)", domain, domain_data["expertise_level"])

    def get_context_for_query(self, query: str, max_chars: int = 3000) -> str:
        """
        Dado un query, extrae el conocimiento más relevante de la KB.
        Se usa para enriquecer las respuestas de BEEA con lo que sabe.
        """
        data = _load()
        if not data:
            return ""

        query_lower = query.lower()
        relevant_chunks = []

        for domain, domain_data in data.items():
            # Match por dominio
            domain_relevance = domain in query_lower or any(
                word in query_lower for word in domain.split("_")
            )

            # Match por facts
            facts = domain_data.get("key_facts", [])
            fact_hits = [f for f in facts if any(w in f.lower() for w in query_lower.split() if len(w) > 3)]

            # Match por subtópicos
            subtopics = domain_data.get("subtopics", {})
            subtopic_hits = []
            for st_name, st_data in subtopics.items():
                if any(w in st_name.lower() or w in st_data.get("content", "").lower()
                       for w in query_lower.split() if len(w) > 3):
                    subtopic_hits.append(f"  [{st_name}]: {st_data['content'][:400]}")

            if domain_relevance or fact_hits or subtopic_hits:
                expertise = domain_data.get("expertise_level", 0)
                synthesis = domain_data.get("synthesis", "")[:600]

                chunk = f"[CONOCIMIENTO: {domain.upper()} — Nivel {expertise}/100]\n"
                if synthesis:
                    chunk += f"Síntesis: {synthesis}\n"
                if fact_hits:
                    chunk += f"Hechos clave: {'; '.join(fact_hits[:5])}\n"
                if subtopic_hits:
                    chunk += "\n".join(subtopic_hits[:3])

                relevant_chunks.append(chunk)

        if not relevant_chunks:
            return ""

        combined = "\n\n".join(relevant_chunks)
        return combined[:max_chars]

    def get_full_knowledge_summary(self) -> str:
        """Resumen de todo lo que BEEA sabe. Para /status o preguntas sobre capacidades."""
        data = _load()
        if not data:
            return "Aún no he aprendido ningún dominio específico."

        lines = ["Lo que sé hasta ahora:\n"]
        for domain, d in data.items():
            level = d.get("expertise_level", 0)
            sessions = d.get("sessions", 0)
            subtopic_count = len(d.get("subtopics", {}))
            last = d.get("last_updated", "?")
            bar = "█" * (level // 10) + "░" * (10 - level // 10)
            lines.append(
                f"• {domain.upper()}: [{bar}] {level}/100 | "
                f"{subtopic_count} subtópicos | {sessions} sesiones | Actualizado: {last}"
            )

        return "\n".join(lines)

    def forget_domain(self, domain: str) -> bool:
        """Olvida todo lo de un dominio. Para limpiar o resetear."""
        data = _load()
        domain = domain.lower().strip()
        if domain in data:
            del data[domain]
            _save(data)
            return True
        return False


knowledge_base = KnowledgeBase()
