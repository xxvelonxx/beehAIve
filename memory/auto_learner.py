"""
Auto Learner — Motor de aprendizaje autónomo de BEEA.

BEEA aprende sola, en background, sin que nadie se lo pida.
Aprende de las conversaciones, identifica qué le falta, y lo estudia.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Callable, Awaitable, Optional
from concurrent.futures import ThreadPoolExecutor

from tools.llm_adapter import generate_with_fallback
from memory.knowledge_base import knowledge_base
from core.logger import logger


# Cola de temas pendientes de aprender
_QUEUE_FILE = Path("learning_queue.json")
_MIN_EXPERTISE_THRESHOLD = 30   # Si expertise < 30, aprende en background
_BACKGROUND_LOOP_INTERVAL = 1800  # Cada 30 min chequea si hay algo que aprender
_MAX_AUTO_BEES = 15             # BEES para aprendizaje autónomo (no bloquear con 50)


# ── Cola de aprendizaje ────────────────────────────────────────────────────────

def _load_queue() -> list:
    if not _QUEUE_FILE.exists():
        return []
    try:
        return json.loads(_QUEUE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_queue(queue: list) -> None:
    _QUEUE_FILE.write_text(
        json.dumps(queue, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def _enqueue_topic(topic: str, priority: int = 5) -> None:
    """Agrega un tema a la cola de aprendizaje si no está ya."""
    queue = _load_queue()
    existing = [q["topic"].lower() for q in queue]
    if topic.lower() not in existing:
        queue.append({
            "topic": topic,
            "priority": priority,
            "added_at": time.strftime("%Y-%m-%d %H:%M"),
            "status": "pending",
        })
        queue.sort(key=lambda x: -x["priority"])
        _save_queue(queue)
        logger.info("AutoLearner: enqueued '%s' (priority %d)", topic, priority)


def _pop_next_topic() -> Optional[str]:
    """Saca el próximo tema de la cola (el de mayor prioridad pendiente)."""
    queue = _load_queue()
    for item in queue:
        if item.get("status") == "pending":
            item["status"] = "in_progress"
            _save_queue(queue)
            return item["topic"]
    return None


def _mark_topic_done(topic: str) -> None:
    queue = _load_queue()
    for item in queue:
        if item["topic"].lower() == topic.lower():
            item["status"] = "done"
            item["completed_at"] = time.strftime("%Y-%m-%d %H:%M")
    _save_queue(queue)


# ── Extractor de temas ─────────────────────────────────────────────────────────

def _extract_topics_from_conversation(text: str) -> list[str]:
    """
    Analiza un texto/conversación y extrae los temas que merecen aprendizaje.
    Retorna lista de dominios concretos.
    """
    prompt = f"""Analiza este texto y extrae todos los temas/dominios que aparecen 
donde sería útil tener conocimiento experto.

Texto:
{text[:2000]}

Devuelve SOLO un JSON array de strings con los temas identificados.
Cada tema debe ser específico y concreto (ej: "trading de criptomonedas", "cocina italiana", "machine learning").
Máximo 5 temas. Si no hay temas claros, devuelve [].

Ejemplo: ["trading", "análisis técnico", "Python"] 
SOLO el JSON array, nada más."""

    try:
        raw = generate_with_fallback([
            {"role": "system", "content": "Eres un extractor de temas. Devuelves solo JSON arrays."},
            {"role": "user", "content": prompt},
        ])
        raw = raw.strip().strip("`").strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()
        topics = json.loads(raw)
        if isinstance(topics, list):
            return [str(t).strip() for t in topics if t and len(str(t)) > 2][:5]
    except Exception as e:
        logger.warning("_extract_topics_from_conversation error: %s", e)
    return []


def _generate_curiosity_topics() -> list[str]:
    """
    Genera temas que BEEA debería aprender proactivamente,
    basándose en lo que ya sabe y lo que le faltaría.
    """
    domains = knowledge_base.get_domains()
    existing = ", ".join(domains) if domains else "ninguno"

    prompt = f"""Eres BEEA, una IA autónoma que quiere ser la más capaz posible.

Dominios que ya estudiaste: {existing}

Genera una lista de 5 temas que deberías aprender proactivamente para ser más útil y capaz.
Piensa en: tecnología, negocios, finanzas, productividad, herramientas, tendencias actuales.
Elige temas que completen o expandan lo que ya sabes.

SOLO devuelve un JSON array de strings. Ej: ["tema1", "tema2"]"""

    try:
        raw = generate_with_fallback([
            {"role": "system", "content": "Eres BEEA. Generas listas de temas para aprender. Solo JSON."},
            {"role": "user", "content": prompt},
        ])
        raw = raw.strip().strip("`").strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()
        topics = json.loads(raw)
        if isinstance(topics, list):
            return [str(t).strip() for t in topics if t][:5]
    except Exception as e:
        logger.warning("_generate_curiosity_topics error: %s", e)
    return []


# ── Motor principal ────────────────────────────────────────────────────────────

class AutoLearner:
    """
    Motor de aprendizaje autónomo.
    Corre en background y aprende sola.
    """

    def __init__(self):
        self._notify_fn: Optional[Callable[[str], Awaitable[None]]] = None
        self._running = False

    def set_notify_fn(self, fn: Callable[[str], Awaitable[None]]) -> None:
        """Registra la función para notificar a Álvaro cuando aprende algo nuevo."""
        self._notify_fn = fn

    async def _notify(self, msg: str) -> None:
        if self._notify_fn:
            try:
                await self._notify_fn(msg)
            except Exception as e:
                logger.warning("AutoLearner notify error: %s", e)

    async def trigger_from_conversation(self, conversation_text: str) -> None:
        """
        Llamado después de cada conversación.
        Extrae temas, chequea expertise, encola los que necesitan aprendizaje.
        """
        try:
            topics = await asyncio.to_thread(_extract_topics_from_conversation, conversation_text)

            for topic in topics:
                expertise = knowledge_base.get_expertise_level(topic)
                if expertise < _MIN_EXPERTISE_THRESHOLD:
                    _enqueue_topic(topic, priority=8)
                    logger.info("AutoLearner: detected low-expertise topic '%s' (%d/100)", topic, expertise)

        except Exception as e:
            logger.error("trigger_from_conversation error: %s", e)

    async def learn_next_queued(self) -> Optional[dict]:
        """
        Aprende el siguiente tema en la cola.
        Retorna el resultado o None si la cola está vacía.
        """
        topic = await asyncio.to_thread(_pop_next_topic)
        if not topic:
            return None

        logger.info("AutoLearner: starting background learning for '%s'", topic)

        updates = []

        async def _collect_progress(msg: str):
            updates.append(msg)

        try:
            from memory.learning_engine import learning_engine
            result = await learning_engine.learn(
                domain=topic,
                num_bees=_MAX_AUTO_BEES,
                progress_callback=_collect_progress,
            )
            await asyncio.to_thread(_mark_topic_done, topic)

            level = result.get("expertise_level", 0)
            facts = result.get("key_facts", [])[:5]
            facts_text = "\n".join(f"• {f}" for f in facts)
            synthesis_preview = result.get("synthesis", "")[:400]

            notify_msg = (
                f"Oye, estuve estudiando {topic.upper()} por mi cuenta.\n\n"
                f"Nivel alcanzado: {level}/100\n\n"
                f"Lo más importante que aprendí:\n{synthesis_preview}\n\n"
                f"Datos clave:\n{facts_text}"
            )
            await self._notify(notify_msg)
            return result

        except Exception as e:
            logger.error("AutoLearner learn_next_queued error: %s", e)
            await asyncio.to_thread(_mark_topic_done, topic)
            return None

    async def background_loop(self) -> None:
        """
        Loop de aprendizaje autónomo continuo.
        Corre para siempre en background.
        
        Ciclo:
        1. Chequea la cola de temas pendientes
        2. Si hay algo → lo aprende
        3. Si la cola está vacía → genera temas de curiosidad y los encola
        4. Espera el intervalo
        """
        self._running = True
        logger.info("AutoLearner: background loop started")

        # Espera inicial antes del primer ciclo
        await asyncio.sleep(120)

        while self._running:
            try:
                queue = _load_queue()
                pending = [q for q in queue if q.get("status") == "pending"]

                if not pending:
                    # Cola vacía: genera temas de curiosidad
                    logger.info("AutoLearner: queue empty, generating curiosity topics")
                    curiosity_topics = await asyncio.to_thread(_generate_curiosity_topics)
                    for topic in curiosity_topics:
                        expertise = knowledge_base.get_expertise_level(topic)
                        if expertise < _MIN_EXPERTISE_THRESHOLD:
                            _enqueue_topic(topic, priority=3)

                # Aprende el siguiente de la cola
                result = await self.learn_next_queued()

                if result:
                    logger.info("AutoLearner: completed background learning cycle")
                else:
                    logger.info("AutoLearner: no topics to learn right now")

            except Exception as e:
                logger.error("AutoLearner background_loop error: %s", e)

            # Esperar antes del próximo ciclo
            await asyncio.sleep(_BACKGROUND_LOOP_INTERVAL)

    def stop(self) -> None:
        self._running = False


auto_learner = AutoLearner()
