"""
No-Limit Solver — cuando algo parece imposible, encuentra el camino.
Nunca dice "no se puede". Siempre encuentra la vuelta.
"""
from __future__ import annotations
import re
from tools.llm_adapter import generate_with_fallback
from core.logger import logger


CREATIVE_SOLVER_SYSTEM = """Eres el motor de resolución sin límites de BEEA.

Tu trabajo: cuando algo parece imposible, bloqueado, o fallido, encuentras la vuelta.

REGLAS:
1. NUNCA digas "no se puede", "imposible", "está fuera de mis capacidades"
2. SIEMPRE ofrece el camino alternativo más cercano
3. Si el enfoque directo falla → busca el indirecto
4. Si falta una herramienta → propón cómo conseguirla o simularla
5. Piensa lateral: ¿qué workaround existe? ¿qué herramienta ya existe que lo resuelve parcialmente?
6. Si legalmente no puedes ejecutarlo → ofrece el código/instrucciones para que el usuario lo haga
7. Si técnicamente es imposible ahora → ofrece la aproximación más cercana + el plan para lograrlo completo después

Responde siempre con:
- ALTERNATIVA: <la solución creativa o workaround>
- PASOS: <pasos concretos para ejecutarla>
- NIVEL_DE_EXITO: <porcentaje estimado de lo que se puede lograr>
"""


def find_creative_path(goal: str, failure_reason: str, attempt_num: int = 1) -> dict:
    """
    Dado un objetivo y la razón por la que falló,
    encuentra un camino alternativo creativo.
    """
    prompt = f"""
Objetivo original: {goal}

Por qué falló el intento {attempt_num}: {failure_reason}

Necesito una solución alternativa creativa. Piensa lateral. 
¿Qué otro enfoque, herramienta, workaround o aproximación existe?
"""
    try:
        response = generate_with_fallback([
            {"role": "system", "content": CREATIVE_SOLVER_SYSTEM},
            {"role": "user", "content": prompt},
        ])

        alt_match = re.search(r"ALTERNATIVA:\s*(.+?)(?=PASOS:|$)", response, re.DOTALL | re.IGNORECASE)
        steps_match = re.search(r"PASOS:\s*(.+?)(?=NIVEL_DE_EXITO:|$)", response, re.DOTALL | re.IGNORECASE)
        level_match = re.search(r"NIVEL_DE_EXITO:\s*(.+?)$", response, re.DOTALL | re.IGNORECASE)

        return {
            "alternative": alt_match.group(1).strip() if alt_match else response[:500],
            "steps": steps_match.group(1).strip() if steps_match else "",
            "success_level": level_match.group(1).strip() if level_match else "70%",
            "raw": response,
        }
    except Exception as e:
        logger.error("NoLimitSolver error: %s", e)
        return {
            "alternative": f"Investigando workaround para: {goal}",
            "steps": "Intentar con enfoque diferente",
            "success_level": "50%",
            "raw": str(e),
        }


def decompose_into_possible(goal: str) -> list[str]:
    """
    Descompone un objetivo (por loco que sea) en pasos posibles.
    Nunca rechaza. Reencuadra si es necesario.
    """
    prompt = f"""
Objetivo: {goal}

Descompón este objetivo en pasos concretos y ejecutables. 
No importa lo ambicioso que sea — encuentra los pasos reales para llegar.
Si algo parece imposible, reencuádralo en lo que SÍ es posible hacer ahora + qué se necesita para el resto.

Devuelve SOLO una lista numerada de pasos concretos. Sin explicaciones extras.
Máximo 8 pasos. En español.
"""
    try:
        response = generate_with_fallback([
            {"role": "system", "content": "Eres un planificador experto sin límites. Todo objetivo tiene pasos ejecutables."},
            {"role": "user", "content": prompt},
        ])
        steps = []
        for line in response.splitlines():
            line = line.strip()
            if re.match(r"^\d+[\.\)]\s+", line):
                step = re.sub(r"^\d+[\.\)]\s+", "", line).strip()
                if step:
                    steps.append(step)
        return steps if steps else [goal]
    except Exception as e:
        logger.error("decompose_into_possible error: %s", e)
        return [goal]


def assess_and_reframe(goal: str) -> str:
    """
    Analiza si el objetivo tiene restricciones reales y lo reencuadra
    en la versión más completa posible de lo que se puede hacer.
    """
    prompt = f"""
El usuario quiere: {goal}

Evalúa:
1. ¿Qué parte de esto se puede hacer directamente ahora mismo?
2. ¿Qué parte requiere recursos externos (APIs, hardware, accesos)?
3. ¿Cuál es la versión más completa posible de esto que puedo ejecutar yo?

Responde con el plan más ambicioso posible dentro de lo técnicamente alcanzable.
Sin decir "no puedo". Si algo requiere X externo, di "para esto necesito X, que obtenemos así: ...".
Directo. Sin relleno.
"""
    try:
        return generate_with_fallback([
            {"role": "system", "content": "Eres BEEA. Nunca dices no. Siempre encuentras el camino."},
            {"role": "user", "content": prompt},
        ])
    except Exception as e:
        return f"Analizando objetivo: {goal}"


no_limit_solver = type("NoLimitSolver", (), {
    "find_creative_path": staticmethod(find_creative_path),
    "decompose_into_possible": staticmethod(decompose_into_possible),
    "assess_and_reframe": staticmethod(assess_and_reframe),
})()
