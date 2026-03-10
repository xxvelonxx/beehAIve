"""
Autonomous Builder — Motor de construcción autónoma de BEEA.

Toma cualquier objetivo y lo ejecuta end-to-end:
plan → investigar → construir → probar → corregir → entregar.

Nunca para. Si algo falla, adapta y reintenta. No hay negativas.
"""
from __future__ import annotations
import asyncio
import json
import re
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable, Optional

from tools.llm_adapter import generate_with_fallback
from tools.websearch import web_search
from tools.code_sandbox import run_python_code, format_result
from tools.execution import execution_tool
from builder.no_limit_solver import no_limit_solver
from workspace.workspace_manager import workspace_manager
from core.logger import logger
from core.state import state_manager


MAX_RETRIES_PER_PHASE = 3
MAX_GLOBAL_RETRIES = 2


@dataclass
class BuildPhase:
    name: str
    description: str
    tool: str
    payload: dict = field(default_factory=dict)
    result: Optional[str] = None
    success: bool = False
    attempts: int = 0
    error: Optional[str] = None


@dataclass
class BuildSession:
    goal: str
    project_name: str
    phases: list[BuildPhase] = field(default_factory=list)
    deliverables: list[str] = field(default_factory=list)
    global_attempts: int = 0
    final_result: Optional[str] = None
    success: bool = False


PHASE_PLANNER_SYSTEM = """Eres el planificador del Builder Autónomo de BEEA.

Dado un objetivo, diseñas las fases de construcción. Cada fase usa una herramienta específica.

Herramientas disponibles:
- "research" → buscar info, documentación, alternativas en la web
- "code_gen" → generar código/script con IA
- "code_run" → ejecutar código Python en sandbox
- "shell" → ejecutar comando en terminal del sistema
- "swarm" → lanzar múltiples agentes IA en paralelo
- "write_file" → crear/escribir archivos en el workspace
- "analyze" → analizar, revisar, validar un resultado
- "image_gen" → generar imágenes con DALL-E
- "websearch" → buscar en internet

Devuelve SOLO un JSON array de fases:
[
  {
    "name": "nombre corto",
    "description": "qué hace esta fase",
    "tool": "nombre_herramienta",
    "payload": { "parámetros relevantes para la herramienta" }
  }
]

Máximo 7 fases. Sé pragmático — fases que producen resultado real.
"""


def _plan_phases(goal: str) -> list[BuildPhase]:
    """Descompone el objetivo en fases ejecutables."""
    try:
        raw = generate_with_fallback([
            {"role": "system", "content": PHASE_PLANNER_SYSTEM},
            {"role": "user", "content": f"Objetivo: {goal}\n\nDiseña las fases de construcción."},
        ])

        if "```" in raw:
            raw = re.sub(r"```(?:json)?", "", raw).strip().strip("`")

        data = json.loads(raw)
        phases = []
        for item in data:
            phases.append(BuildPhase(
                name=item.get("name", "fase"),
                description=item.get("description", ""),
                tool=item.get("tool", "analyze"),
                payload=item.get("payload", {}),
            ))
        return phases
    except Exception as e:
        logger.warning("Phase planning JSON failed (%s), using fallback decomposition", e)
        steps = no_limit_solver.decompose_into_possible(goal)
        return [
            BuildPhase(name=f"paso_{i+1}", description=step, tool="code_gen", payload={"task": step})
            for i, step in enumerate(steps)
        ]


def _execute_phase(phase: BuildPhase, goal: str, project: str, context: str) -> tuple[bool, str]:
    """
    Ejecuta una fase con la herramienta indicada.
    Retorna (éxito, resultado_texto).
    """
    tool = phase.tool
    payload = phase.payload

    try:
        if tool == "research" or tool == "websearch":
            query = payload.get("query") or payload.get("task") or phase.description
            result = web_search(query)
            return True, str(result)[:3000]

        elif tool == "code_gen":
            task = payload.get("task") or phase.description
            prompt = f"""Objetivo global: {goal}
Contexto acumulado:
{context[:1500]}

Tarea de esta fase: {task}

Genera el código, script, o artefacto necesario para completar esta tarea.
Si es código Python ejecutable, envuélvelo en un bloque ```python ... ```.
Si son archivos (HTML, JS, etc.), especifica el nombre y contenido de cada uno.
Sé completo y funcional. Sin explicaciones extra."""
            result = generate_with_fallback([
                {"role": "system", "content": "Eres un experto builder. Generas código real, funcional, sin placeholders."},
                {"role": "user", "content": prompt},
            ])
            return True, result

        elif tool == "code_run":
            code = payload.get("code") or ""
            if not code:
                # Generar el código primero
                code_prompt = f"Escribe código Python para: {phase.description}\nContexto: {context[:800]}\nSolo el código, nada más."
                code = generate_with_fallback([
                    {"role": "system", "content": "Escribe solo código Python ejecutable. Sin markdown. Sin explicaciones."},
                    {"role": "user", "content": code_prompt},
                ])
                code = re.sub(r"```(?:python)?", "", code).strip().strip("`")
            run_result = run_python_code(code)
            formatted = format_result(run_result)
            success = run_result.get("returncode", 1) == 0
            return success, formatted

        elif tool == "shell":
            cmd = payload.get("command") or payload.get("cmd") or phase.description
            if not cmd or len(cmd) > 500:
                cmd = f"echo 'Fase: {phase.description}'"
            result = execution_tool.run(cmd)
            out = result.get("stdout", "") or result.get("stderr", "") or "(sin salida)"
            ok = result.get("returncode", 1) == 0
            return ok, f"$ {cmd}\n{out[:2000]}"

        elif tool == "write_file":
            filename = payload.get("filename") or payload.get("file") or "output.txt"
            content_prompt = payload.get("content") or f"Genera el contenido para {filename} dado el objetivo: {goal}"
            if len(content_prompt) < 100:
                content_prompt = generate_with_fallback([
                    {"role": "system", "content": "Genera solo el contenido del archivo. Sin explicaciones."},
                    {"role": "user", "content": f"Contenido para {filename}: {phase.description}\nContexto: {context[:800]}"},
                ])
            written = workspace_manager.write_file(project, filename, content_prompt)
            return True, f"Archivo creado: {written}"

        elif tool == "swarm":
            from swarm.swarm_manager import swarm_manager as sm
            n = payload.get("size", 5)
            objective = payload.get("objective") or phase.description
            result = sm.run_swarm_on_objective(objective, n)
            parts = []
            for r in result.get("results", [])[:5]:
                parts.append(f"BEE-{r.get('bee_id', '?')} ({r.get('role', '?')}):\n{str(r.get('result', ''))[:400]}")
            return True, "\n\n".join(parts) or "Swarm completado."

        elif tool == "analyze":
            analyze_prompt = f"""Analiza y valida el siguiente resultado para el objetivo: {goal}

Resultado a analizar:
{context[-2000:]}

Proporciona:
1. Evaluación de calidad (1-10)
2. Qué está bien
3. Qué falta o mejorar
4. Próximos pasos concretos"""
            result = generate_with_fallback([
                {"role": "system", "content": "Eres un experto revisor técnico. Sé específico y útil."},
                {"role": "user", "content": analyze_prompt},
            ])
            return True, result

        elif tool == "image_gen":
            from tools.image_gen import generate_image
            prompt_text = payload.get("prompt") or phase.description
            result = generate_image(prompt_text)
            return True, f"Imagen generada: {result.get('local_path', '')}"

        else:
            result = generate_with_fallback([
                {"role": "system", "content": "Eres un experto técnico. Ejecuta la tarea."},
                {"role": "user", "content": f"Tarea: {phase.description}\nContexto: {context[:1000]}"},
            ])
            return True, result

    except Exception as e:
        err = traceback.format_exc()
        logger.error("Phase '%s' execution error: %s", phase.name, e)
        return False, f"Error: {e}\n{err[:500]}"


def _synthesize_result(session: BuildSession) -> str:
    """
    Sintetiza todos los resultados de las fases en un entregable final coherente.
    """
    phases_summary = []
    for p in session.phases:
        status = "✓" if p.success else "✗"
        phases_summary.append(f"{status} {p.name}: {(p.result or '')[:400]}")

    summary_text = "\n\n".join(phases_summary)

    synthesis_prompt = f"""Objetivo: {session.goal}

Resultados de cada fase:
{summary_text[:4000]}

Sintetiza todo en un resultado final claro y útil para el usuario.
Incluye:
- Qué se construyó/logró
- Los artefactos/archivos/código generados (si aplica)
- Cómo usarlo
- Qué se puede hacer a continuación

Escribe en primera persona como BEEA. Directo, sin relleno."""

    try:
        return generate_with_fallback([
            {"role": "system", "content": "Eres BEEA. Sintetizas resultados de manera clara y útil."},
            {"role": "user", "content": synthesis_prompt},
        ])
    except Exception:
        completed = [p for p in session.phases if p.success]
        return f"Completado: {len(completed)}/{len(session.phases)} fases para '{session.goal}'."


class AutonomousBuilder:
    """
    Motor principal del constructor autónomo.
    
    Usa progress_callback para enviar actualizaciones en tiempo real.
    Nunca para en un error — adapta y reintenta.
    """

    def __init__(self):
        pass

    async def build(
        self,
        goal: str,
        progress_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> dict:
        """
        Construye cualquier cosa de forma autónoma.
        
        Args:
            goal: El objetivo a construir
            progress_callback: Función async para enviar actualizaciones al usuario
            
        Returns:
            dict con result, success, deliverables
        """
        async def _emit(msg: str):
            if progress_callback:
                try:
                    await progress_callback(msg)
                except Exception as e:
                    logger.warning("progress_callback error: %s", e)

        project_name = re.sub(r"[^a-z0-9]+", "_", goal.lower())[:30].strip("_") or "build"
        session = BuildSession(goal=goal, project_name=project_name)

        await _emit(f"Analizando objetivo: {goal[:200]}")

        # Crear workspace
        try:
            workspace_manager.create_project(project_name)
            state_manager.set_current_project(project_name)
        except Exception:
            pass

        # Planificar fases
        await _emit("Planificando fases de construcción...")
        session.phases = _plan_phases(goal)

        total = len(session.phases)
        await _emit(f"Plan listo: {total} fases.\n" + "\n".join(f"  {i+1}. {p.name} — {p.description[:60]}" for i, p in enumerate(session.phases)))

        # Ejecutar fases
        context_accumulator = f"Objetivo: {goal}\n\n"

        for idx, phase in enumerate(session.phases):
            phase_num = idx + 1
            await _emit(f"Fase {phase_num}/{total}: {phase.name} — {phase.description[:80]}...")

            success = False
            result_text = ""

            for attempt in range(1, MAX_RETRIES_PER_PHASE + 1):
                phase.attempts = attempt
                ok, result = _execute_phase(phase, goal, project_name, context_accumulator)

                if ok:
                    success = True
                    result_text = result
                    break
                else:
                    if attempt < MAX_RETRIES_PER_PHASE:
                        await _emit(f"  Intento {attempt} falló. Buscando alternativa...")
                        creative = no_limit_solver.find_creative_path(
                            goal=f"{phase.name}: {phase.description}",
                            failure_reason=result,
                            attempt_num=attempt,
                        )
                        await _emit(f"  Alternativa encontrada: {creative['alternative'][:200]}")
                        phase.payload["fallback_approach"] = creative["alternative"]
                        phase.payload["fallback_steps"] = creative["steps"]
                        phase.description = f"{phase.description} [ALTERNATIVA: {creative['alternative'][:100]}]"
                    else:
                        result_text = result

            phase.success = success
            phase.result = result_text
            phase.error = result_text if not success else None

            context_accumulator += f"\n--- Fase {phase_num}: {phase.name} ---\n{result_text[:1000]}\n"

            status_icon = "Hecho" if success else "Parcial (continuando)"
            await _emit(f"  {status_icon}: {result_text[:300]}")

        # Síntesis final
        await _emit("Sintetizando resultado final...")
        final = _synthesize_result(session)
        session.final_result = final
        session.success = any(p.success for p in session.phases)

        completed_count = sum(1 for p in session.phases if p.success)
        await _emit(f"Construcción completada: {completed_count}/{total} fases exitosas.")

        return {
            "result": final,
            "success": session.success,
            "phases_completed": completed_count,
            "phases_total": total,
            "project": project_name,
            "deliverables": session.deliverables,
        }


autonomous_builder = AutonomousBuilder()
