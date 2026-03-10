"""
HiveMind — Orquestador de BEEs al estilo de la arquitectura que viste en Kimi.

Flujo:
  1. PLANNER BEE: recibe el objetivo, lo descompone en subtareas específicas con roles asignados
  2. PARALLEL EXECUTION: todas las subtareas se lanzan en paralelo con ThreadPoolExecutor
  3. SYNTHESIZER BEE: recibe todos los resultados + objetivo original → produce respuesta final coherente

Álvaro lo activa con: /hivemind <objetivo>
O naturalmente cuando dice "manda las bees a..." / "quiero que el enjambre..."
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout
from typing import Callable, Optional

from core.logger import logger

MAX_BEES_PER_TASK = 160
DEFAULT_BEES = 4
BEE_TIMEOUT = 120  # segundos por BEE


class HiveMind:
    """
    Orquestador completo: Planifica → Distribuye → Sintetiza.
    Usa Groq como backbone (gratis). OpenAI como fallback.
    """

    def __init__(self):
        self._progress_cb: Optional[Callable] = None

    def set_progress_callback(self, fn: Callable):
        """Callback para enviar actualizaciones de progreso a Álvaro."""
        self._progress_cb = fn

    def _emit(self, msg: str):
        if self._progress_cb:
            try:
                self._progress_cb(msg)
            except Exception:
                pass
        logger.info("HiveMind: %s", msg)

    # ── Paso 1: Planificador ───────────────────────────────────────────────────

    def _plan(self, goal: str, n_bees: int) -> list[dict]:
        """
        BEE planificadora: descompone el objetivo en N subtareas concretas.
        Devuelve lista de {role, task, description}.
        """
        from tools.llm_adapter import generate_smart
        from swarm.bee_roles import BEE_ROLES

        roles_available = ", ".join(BEE_ROLES.keys())

        planning_prompt = f"""Eres el PLANIFICADOR de un enjambre de IA. Tu trabajo es descomponer un objetivo en subtareas concretas para BEEs especializadas.

Objetivo: {goal}

Roles disponibles: {roles_available}

Descompón este objetivo en exactamente {n_bees} subtareas paralelas. Cada subtarea debe:
1. Ser completamente independiente (pueden ejecutarse en paralelo)
2. Tener un rol específico de la lista
3. Tener una descripción clara y accionable de qué debe hacer esa BEE exactamente

Responde SOLO con un JSON válido, sin markdown, sin explicaciones:
[
  {{"role": "researcher", "task": "Descripción exacta de la subtarea 1"}},
  {{"role": "coder", "task": "Descripción exacta de la subtarea 2"}},
  ...
]"""

        messages = [
            {"role": "system", "content": "Eres un planificador de IA. Respondes SOLO con JSON válido."},
            {"role": "user", "content": planning_prompt},
        ]

        try:
            raw = generate_smart(messages, task_type="planning")
            # Limpiar posible markdown
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            plan = json.loads(raw)
            if isinstance(plan, list) and plan:
                # Validar que cada item tenga role y task
                validated = []
                from swarm.bee_roles import BEE_ROLES
                for item in plan[:MAX_BEES_PER_TASK]:
                    role = item.get("role", "researcher")
                    if role not in BEE_ROLES:
                        role = "researcher"
                    validated.append({"role": role, "task": item.get("task", goal)})
                logger.info("HiveMind plan: %d subtareas — %s", len(validated), [v["role"] for v in validated])
                return validated
        except Exception as e:
            logger.warning("HiveMind planner falló: %s — usando plan genérico", e)

        # Plan genérico si el LLM falla
        generic_roles = ["researcher", "architect", "coder", "reviewer"]
        return [
            {"role": generic_roles[i % len(generic_roles)], "task": f"{goal} — parte {i+1}"}
            for i in range(n_bees)
        ]

    # ── Paso 2: Ejecución paralela ─────────────────────────────────────────────

    def _execute_parallel(self, goal: str, subtasks: list[dict]) -> list[dict]:
        """Lanza todas las BEEs en paralelo. Devuelve resultados."""
        from swarm.agent_worker import AgentWorker

        def run_bee(idx: int, subtask: dict) -> dict:
            worker = AgentWorker(agent_id=idx, role=subtask["role"])
            task = {
                "step": subtask["task"],
                "objective": goal,
                "role": subtask["role"],
            }
            return worker.run_task(task)

        results = []
        n = len(subtasks)

        with ThreadPoolExecutor(max_workers=n, thread_name_prefix="hivemind-bee") as executor:
            futures = {
                executor.submit(run_bee, i, st): (i, st)
                for i, st in enumerate(subtasks)
            }
            completed = 0
            for fut in as_completed(futures, timeout=BEE_TIMEOUT * n):
                idx, st = futures[fut]
                try:
                    res = fut.result(timeout=BEE_TIMEOUT)
                    results.append(res)
                    completed += 1
                    bee_name = res.get("bee_name", f"BEE-{idx}")
                    self._emit(f"{bee_name} [{st['role']}] completada ({completed}/{n})")
                except FuturesTimeout:
                    logger.warning("BEE-%d [%s] timeout", idx, st["role"])
                    results.append({
                        "bee_id": idx, "bee_name": f"BEE-{idx}", "role": st["role"],
                        "result": f"Timeout — la BEE {st['role']} tardó demasiado.",
                        "status": "timeout",
                    })
                except Exception as e:
                    logger.error("BEE-%d [%s] error: %s", idx, st["role"], e)
                    results.append({
                        "bee_id": idx, "bee_name": f"BEE-{idx}", "role": st["role"],
                        "result": f"Error en BEE {st['role']}: {e}",
                        "status": "error",
                    })

        # Ordenar por bee_id
        results.sort(key=lambda r: r.get("bee_id", 0))
        return results

    # ── Paso 3: Sintetizador ───────────────────────────────────────────────────

    def _synthesize(self, goal: str, subtasks: list[dict], results: list[dict]) -> str:
        """
        SYNTHESIZER BEE: combina todos los outputs de las BEEs en una respuesta
        coherente y completa para Álvaro.
        """
        from tools.llm_adapter import generate_smart

        # Construir contexto de resultados
        results_text = ""
        for i, (st, res) in enumerate(zip(subtasks, results)):
            role     = st.get("role", res.get("role", "bee"))
            task     = st.get("task", "")
            result   = res.get("result", "")
            bee_name = res.get("bee_name", f"BEE-{i}")
            results_text += f"\n\n--- {bee_name} [{role}] ---\nTarea: {task}\nResultado:\n{result[:1500]}"

        synth_prompt = f"""Eres el SINTETIZADOR del enjambre de BEEA. Recibiste los resultados de {len(results)} BEEs que trabajaron en paralelo.

Objetivo original de Álvaro: {goal}

Resultados de las BEEs:{results_text}

Tu trabajo: combina todos estos resultados en una respuesta ÚNICA, coherente, completa y bien organizada para Álvaro.
- Elimina repeticiones
- Organiza la información de forma lógica  
- Resalta las partes más importantes
- Si las BEEs escribieron código, inclúyelo completo
- Si hay conflictos entre resultados, usa el mejor
- Sé directa y útil. No menciones "las BEEs" ni el proceso interno. Solo da el resultado final.

Responde en español, de forma directa."""

        messages = [
            {"role": "system", "content": "Eres una sintetizadora de IA. Produces respuestas claras y completas."},
            {"role": "user", "content": synth_prompt},
        ]

        try:
            result = generate_smart(messages, task_type="complex")
            if result:
                return result
        except Exception as e:
            logger.error("HiveMind synthesizer error: %s", e)

        # Fallback: concatenar resultados
        parts = [f"**BEE [{st.get('role','')}]:** {res.get('result','')[:500]}"
                 for st, res in zip(subtasks, results)]
        return "\n\n".join(parts)

    # ── Entry point ───────────────────────────────────────────────────────────

    def execute(self, goal: str, n_bees: int = DEFAULT_BEES) -> dict:
        """
        Ejecuta el flujo completo: Plan → Parallel → Synthesize.
        Devuelve {final_result, subtasks, results, elapsed}.
        """
        n_bees = max(2, min(n_bees, MAX_BEES_PER_TASK))
        t0 = time.time()

        self._emit(f"Planificando {n_bees} BEEs para: {goal[:80]}...")

        # 1. Planificar
        subtasks = self._plan(goal, n_bees)
        self._emit(f"Plan listo: {[s['role'] for s in subtasks]}")

        # 2. Ejecutar en paralelo
        self._emit(f"Lanzando {len(subtasks)} BEEs en paralelo...")
        results = self._execute_parallel(goal, subtasks)

        # 3. Sintetizar
        self._emit("Sintetizando resultados...")
        final = self._synthesize(goal, subtasks, results)

        elapsed = round(time.time() - t0, 1)
        logger.info("HiveMind completado en %.1fs — %d BEEs", elapsed, len(results))

        return {
            "final_result": final,
            "subtasks": subtasks,
            "results": results,
            "n_bees": len(results),
            "elapsed": elapsed,
        }


hivemind = HiveMind()
