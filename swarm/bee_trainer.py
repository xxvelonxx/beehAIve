"""
BeeTrainer — Hibernación y entrenamiento intensivo de BEEs.

Una BEE entra en modo hibernación sobre un tema durante X tiempo.
Corre miles de iteraciones: intenta → auto-evalúa → extrae patrón → memoriza.
Al salir, tiene conocimiento acumulado de haber vivido el problema miles de veces.

Cuando esa BEE trabaja en real, carga su memoria de habilidad y empieza
desde el nivel más alto alcanzado, no desde cero.

Comandos:
  /hibernate <role> <tema> <duración>
  Ej: /hibernate coder optimizar contratos Solidity 2h
      /hibernate researcher mercado crypto DeFi 30m
      /hibernate analyst análisis técnico BTC 1h
"""
from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from core.logger import logger

# Directorio donde se guarda la memoria de habilidad de cada BEE
SKILLS_DIR = Path(__file__).resolve().parent.parent / "memory" / "bee_skills"
SKILLS_DIR.mkdir(parents=True, exist_ok=True)

# Velocidad: iteraciones rápidas con modelo ligero, evaluación con modelo inteligente
ITER_MAX_TOKENS   = 600   # tokens por iteración (respuesta rápida)
EVAL_MAX_TOKENS   = 300   # tokens para auto-evaluación
SAVE_EVERY        = 10    # guardar memoria cada N iteraciones
LOG_EVERY         = 25    # log de progreso cada N iteraciones


def _slug(text: str) -> str:
    """Convierte texto en nombre de archivo seguro."""
    return re.sub(r"[^a-z0-9_]", "_", text.lower().strip())[:60]


def _parse_duration(s: str) -> int:
    """
    Parsea duración a segundos.
    Acepta: '30m', '1h', '2h30m', '45', '8h', '10minutos', '1hora'.
    Devuelve segundos (mínimo 60).
    """
    s = s.lower().strip()
    total = 0
    h = re.search(r"(\d+)\s*h", s)
    m = re.search(r"(\d+)\s*m", s)
    if h:
        total += int(h.group(1)) * 3600
    if m:
        total += int(m.group(1)) * 60
    if total == 0:
        # intenta número solo → minutos
        digits = re.search(r"(\d+)", s)
        if digits:
            total = int(digits.group(1)) * 60
    return max(60, total)


def _format_duration(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    if s and not h:
        parts.append(f"{s}s")
    return "".join(parts) or "0s"


class SkillMemory:
    """
    Memoria de habilidad persistente por (role, topic).
    Guarda: iteraciones, patrones exitosos, errores comunes, mejores respuestas.
    """

    def __init__(self, role: str, topic: str):
        self.role  = role
        self.topic = topic
        self._path = SKILLS_DIR / role / f"{_slug(topic)}.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        try:
            if self._path.exists():
                return json.loads(self._path.read_text())
        except Exception:
            pass
        return {
            "role":         self.role,
            "topic":        self.topic,
            "iterations":   0,
            "total_time_s": 0,
            "patterns":     [],   # patrones exitosos extraídos
            "errors":       [],   # errores comunes detectados
            "best_outputs": [],   # mejores respuestas (top 5)
            "skill_level":  0,    # 0-100
            "last_trained": None,
        }

    def save(self):
        try:
            self._path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.warning("SkillMemory save error: %s", e)

        # Propagar al pool de conocimiento colectivo — lo que aprende una lo saben todas
        try:
            from memory.shared_knowledge import shared_knowledge
            patterns = self._data.get("patterns", [])
            if patterns:
                source = f"{self._data['role']}/{self._data['topic'][:40]}"
                score  = self._data.get("skill_level", 5.0) / 10.0 * 10  # escala 0-10
                shared_knowledge.add_many(patterns[-10:], source=source, score=max(5.0, score))
        except Exception as e:
            logger.debug("SharedKnowledge propagation error: %s", e)

    def add_iteration(self, result: str, score: float, patterns: list[str],
                      errors: list[str], elapsed_s: float):
        self._data["iterations"] += 1
        self._data["total_time_s"] = self._data.get("total_time_s", 0) + elapsed_s
        self._data["last_trained"] = time.strftime("%Y-%m-%d %H:%M:%S")

        # Guardar nuevos patrones (sin duplicados, máx 50)
        for p in patterns:
            if p and p not in self._data["patterns"]:
                self._data["patterns"].append(p)
        self._data["patterns"] = self._data["patterns"][-50:]

        # Guardar errores comunes (máx 20)
        for e in errors:
            if e and e not in self._data["errors"]:
                self._data["errors"].append(e)
        self._data["errors"] = self._data["errors"][-20:]

        # Guardar mejores outputs (top 5 por score)
        if score >= 7.0 and result:
            entry = {"score": score, "result": result[:800], "iter": self._data["iterations"]}
            self._data["best_outputs"].append(entry)
            self._data["best_outputs"].sort(key=lambda x: x["score"], reverse=True)
            self._data["best_outputs"] = self._data["best_outputs"][:5]

        # Actualizar nivel de habilidad (media móvil)
        old = self._data["skill_level"]
        self._data["skill_level"] = round(min(100, old * 0.95 + score * 0.5), 1)

    @property
    def iterations(self) -> int:
        return self._data["iterations"]

    @property
    def skill_level(self) -> float:
        return self._data["skill_level"]

    def as_context(self) -> str:
        """
        Genera el bloque de contexto que se inyecta en el system prompt
        cuando la BEE trabaja en real con este tema.
        """
        d = self._data
        if d["iterations"] == 0:
            return ""

        lines = [
            f"[MEMORIA DE ENTRENAMIENTO — {d['role'].upper()} / {d['topic']}]",
            f"Iteraciones de práctica: {d['iterations']} | Nivel: {d['skill_level']:.0f}/100",
        ]
        if d["patterns"]:
            lines.append("Patrones que funcionan:")
            for p in d["patterns"][-10:]:
                lines.append(f"  • {p}")
        if d["errors"]:
            lines.append("Errores comunes a evitar:")
            for e in d["errors"][-5:]:
                lines.append(f"  ✗ {e}")
        if d["best_outputs"]:
            lines.append(f"Mejor respuesta previa (score {d['best_outputs'][0]['score']:.1f}/10):")
            lines.append(d["best_outputs"][0]["result"][:400])
        return "\n".join(lines)


def load_skill_context(role: str, topic: str) -> str:
    """
    Carga el contexto de habilidad para inyectar en el system prompt de una BEE.
    Retorna string vacío si no hay entrenamiento.
    """
    path = SKILLS_DIR / role / f"{_slug(topic)}.json"
    if not path.exists():
        # Buscar por coincidencia parcial
        role_dir = SKILLS_DIR / role
        if role_dir.exists():
            for f in role_dir.glob("*.json"):
                if _slug(topic)[:10] in f.stem:
                    path = f
                    break
    if not path.exists():
        return ""
    try:
        mem = SkillMemory(role, topic)
        return mem.as_context()
    except Exception:
        return ""


class BeeTrainer:
    """
    Motor de entrenamiento de BEEs.
    Corre iteraciones rápidas durante la duración solicitada.
    """

    def __init__(self):
        self._active_sessions: dict[str, dict] = {}
        self._lock = threading.Lock()

    def _generate_task_variant(self, role: str, topic: str, iteration: int,
                                memory: SkillMemory) -> str:
        """
        Genera una variante de tarea para esta iteración.
        Progresiva: empieza simple, se vuelve más compleja.
        """
        complexity = min(10, 1 + iteration // 20)
        patterns = memory._data.get("patterns", [])
        errors   = memory._data.get("errors", [])

        context = ""
        if patterns:
            context += f"\nPatrones conocidos: {', '.join(patterns[-3:])}"
        if errors:
            context += f"\nErrores a evitar: {', '.join(errors[-2:])}"

        return (
            f"Iteración {iteration + 1} — Nivel de complejidad: {complexity}/10\n"
            f"Tema de entrenamiento: {topic}\n"
            f"Rol: {role}\n"
            f"{context}\n\n"
            f"Genera una tarea concreta de nivel {complexity}/10 sobre este tema y resuélvela "
            f"de la mejor forma posible. Sé específico y técnico. "
            f"Al final incluye en una línea: PATRÓN: [el patrón clave aprendido en esta iteración]"
        )

    def _evaluate(self, result: str, topic: str) -> tuple[float, list[str], list[str]]:
        """
        Auto-evaluación rápida del resultado.
        Retorna (score 0-10, patrones, errores).
        """
        from tools.llm_adapter import generate_for_bees

        eval_prompt = (
            f"Evalúa este resultado sobre '{topic}' en una escala 0-10.\n"
            f"Resultado:\n{result[:600]}\n\n"
            "Responde SOLO en este formato (3 líneas):\n"
            "SCORE: [número del 0 al 10]\n"
            "PATRON: [un patrón exitoso extraído, máx 15 palabras]\n"
            "ERROR: [un error o limitación detectada, máx 15 palabras, o NINGUNO]"
        )
        try:
            raw = generate_for_bees([
                {"role": "system", "content": "Eres un evaluador técnico conciso."},
                {"role": "user",   "content": eval_prompt},
            ])
            score    = 5.0
            patterns = []
            errors   = []
            for line in raw.splitlines():
                if line.upper().startswith("SCORE:"):
                    try:
                        score = float(re.search(r"[\d.]+", line).group())
                        score = min(10.0, max(0.0, score))
                    except Exception:
                        pass
                elif line.upper().startswith("PATRON:"):
                    p = line.split(":", 1)[-1].strip()
                    if p and p.upper() != "NINGUNO":
                        patterns.append(p)
                elif line.upper().startswith("ERROR:"):
                    e = line.split(":", 1)[-1].strip()
                    if e and e.upper() != "NINGUNO":
                        errors.append(e)
            return score, patterns, errors
        except Exception:
            return 5.0, [], []

    def _extract_inline_pattern(self, result: str) -> list[str]:
        """Extrae patrones que la BEE incluyó inline en su respuesta."""
        patterns = []
        for line in result.splitlines():
            if line.upper().startswith("PATRÓN:") or line.upper().startswith("PATRON:"):
                p = line.split(":", 1)[-1].strip()
                if p:
                    patterns.append(p)
        return patterns

    def _run_session(self, role: str, topic: str, duration_s: int,
                     session_id: str, notify_fn: Optional[Callable] = None):
        """
        Loop principal de entrenamiento. Corre en un thread separado.
        """
        from swarm.agent_worker import AgentWorker

        memory   = SkillMemory(role, topic)
        start    = time.time()
        deadline = start + duration_s
        iteration = 0
        worker   = AgentWorker(agent_id=0, role=role)

        logger.info("BeeTrainer [%s] iniciando: role=%s topic='%s' duración=%s",
                    session_id, role, topic, _format_duration(duration_s))

        if notify_fn:
            notify_fn(
                f"Entrenamiento iniciado\n"
                f"Role: {role} | Tema: {topic}\n"
                f"Duración: {_format_duration(duration_s)}\n"
                f"Primeras iteraciones en curso..."
            )

        while time.time() < deadline:
            with self._lock:
                session = self._active_sessions.get(session_id)
                if session and session.get("stop"):
                    break

            iter_start = time.time()

            # 1. Generar variante de tarea
            task_prompt = self._generate_task_variant(role, topic, iteration, memory)

            # 2. BEE intenta resolver (modo rápido — sin tools para velocidad máxima)
            try:
                from tools.llm_adapter import generate_for_bees
                sys_prompt = (
                    f"Eres una BEE en modo entrenamiento intensivo. Rol: {role}. "
                    f"Estás practicando: {topic}. "
                    "Responde con la máxima calidad técnica posible. Sé específico. "
                    + memory.as_context()
                )
                result = generate_for_bees([
                    {"role": "system", "content": sys_prompt},
                    {"role": "user",   "content": task_prompt},
                ])
            except Exception as e:
                logger.warning("BeeTrainer iter %d error: %s", iteration, e)
                time.sleep(2)
                iteration += 1
                continue

            iter_elapsed = time.time() - iter_start

            # 3. Extrae patrones inline
            inline_patterns = self._extract_inline_pattern(result)

            # 4. Auto-evaluación (cada 5 iteraciones para no saturar la API)
            score     = 7.0
            patterns  = inline_patterns
            errors    = []
            if iteration % 5 == 0:
                score, eval_patterns, errors = self._evaluate(result, topic)
                patterns = inline_patterns + eval_patterns

            # 5. Guardar en memoria
            memory.add_iteration(result, score, patterns, errors, iter_elapsed)

            # 6. Guardar a disco cada N iteraciones
            if iteration % SAVE_EVERY == 0:
                memory.save()

            # 7. Log de progreso
            if iteration % LOG_EVERY == 0 and iteration > 0:
                elapsed_total = time.time() - start
                remaining     = deadline - time.time()
                iters_per_min = iteration / max(1, elapsed_total / 60)
                projected     = int(iters_per_min * remaining / 60)

                msg = (
                    f"Entrenamiento en curso — {role}/{topic}\n"
                    f"Iteraciones: {iteration} | Nivel: {memory.skill_level:.0f}/100\n"
                    f"Ritmo: {iters_per_min:.0f} iter/min\n"
                    f"Tiempo restante: {_format_duration(int(remaining))}\n"
                    f"Proyección: ~{iteration + projected} iter totales"
                )
                logger.info("BeeTrainer %s: iter=%d skill=%.1f", session_id, iteration, memory.skill_level)
                if notify_fn:
                    notify_fn(msg)

            iteration += 1

            # Pequeña pausa para no saturar la API (rate limit)
            time.sleep(0.3)

        # Fin del entrenamiento — guardar memoria final
        memory.save()
        total_time = time.time() - start
        iters_per_min = iteration / max(1, total_time / 60)

        summary = (
            f"Entrenamiento completado\n"
            f"Role: {role} | Tema: {topic}\n"
            f"Iteraciones: {iteration} | Nivel final: {memory.skill_level:.0f}/100\n"
            f"Tiempo total: {_format_duration(int(total_time))}\n"
            f"Ritmo promedio: {iters_per_min:.0f} iter/min\n"
            f"Patrones aprendidos: {len(memory._data['patterns'])}\n"
            f"Memoria guardada en: memory/bee_skills/{role}/{_slug(topic)}.json"
        )

        logger.info("BeeTrainer [%s] completado: %d iter, nivel=%.1f",
                    session_id, iteration, memory.skill_level)

        with self._lock:
            if session_id in self._active_sessions:
                self._active_sessions[session_id]["status"]     = "completed"
                self._active_sessions[session_id]["iterations"] = iteration
                self._active_sessions[session_id]["skill_level"] = memory.skill_level
                self._active_sessions[session_id]["summary"]    = summary

        if notify_fn:
            notify_fn(summary)

    def start(self, role: str, topic: str, duration_str: str,
              notify_fn: Optional[Callable] = None) -> str:
        """
        Inicia una sesión de entrenamiento en background.
        Retorna el session_id.
        """
        duration_s = _parse_duration(duration_str)
        session_id = f"{role}_{_slug(topic)}_{int(time.time())}"

        with self._lock:
            self._active_sessions[session_id] = {
                "role":        role,
                "topic":       topic,
                "duration_s":  duration_s,
                "started_at":  time.time(),
                "status":      "running",
                "iterations":  0,
                "skill_level": 0,
                "stop":        False,
            }

        thread = threading.Thread(
            target=self._run_session,
            args=(role, topic, duration_s, session_id, notify_fn),
            daemon=True,
            name=f"bee-train-{session_id[:20]}",
        )
        thread.start()
        return session_id

    def stop(self, session_id: str):
        with self._lock:
            if session_id in self._active_sessions:
                self._active_sessions[session_id]["stop"] = True

    def status(self) -> list[dict]:
        with self._lock:
            now = time.time()
            result = []
            for sid, s in self._active_sessions.items():
                elapsed = now - s["started_at"]
                remaining = max(0, s["duration_s"] - elapsed)
                result.append({
                    "session_id":  sid,
                    "role":        s["role"],
                    "topic":       s["topic"],
                    "status":      s["status"],
                    "iterations":  s["iterations"],
                    "skill_level": s["skill_level"],
                    "elapsed":     _format_duration(int(elapsed)),
                    "remaining":   _format_duration(int(remaining)),
                })
            return result

    def load_skills_for_role(self, role: str) -> list[dict]:
        """
        Carga todas las habilidades entrenadas para un role específico.
        Retorna lista de dicts con topic, patterns, skill_level, iterations.
        Ordenada por skill_level descendente.
        """
        role_dir = SKILLS_DIR / role
        if not role_dir.exists():
            return []
        skills = []
        for skill_file in role_dir.glob("*.json"):
            try:
                data = json.loads(skill_file.read_text())
                skills.append(data)
            except Exception:
                pass
        return sorted(skills, key=lambda x: x.get("skill_level", 0), reverse=True)

    def list_skills(self) -> dict[str, list[dict]]:
        """Lista todas las habilidades entrenadas guardadas."""
        result = {}
        if not SKILLS_DIR.exists():
            return result
        for role_dir in SKILLS_DIR.iterdir():
            if not role_dir.is_dir():
                continue
            skills = []
            for skill_file in role_dir.glob("*.json"):
                try:
                    data = json.loads(skill_file.read_text())
                    skills.append({
                        "topic":      data.get("topic", skill_file.stem),
                        "iterations": data.get("iterations", 0),
                        "skill_level": data.get("skill_level", 0),
                        "last_trained": data.get("last_trained", "?"),
                    })
                except Exception:
                    pass
            if skills:
                result[role_dir.name] = sorted(skills, key=lambda x: x["skill_level"], reverse=True)
        return result


# Instancia global
bee_trainer = BeeTrainer()
