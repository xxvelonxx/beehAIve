"""
Learning Engine — Motor de aprendizaje real de BEEA.

Despliega BEES en paralelo para investigar un tema desde múltiples ángulos.
Todo real: búsquedas web reales, síntesis LLM real, almacenamiento persistente real.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Awaitable, Optional

from tools.websearch import web_search
from tools.llm_adapter import generate_with_fallback
from memory.knowledge_base import knowledge_base
from core.logger import logger


# ── Generadores de subtópicos ──────────────────────────────────────────────────

def _generate_subtopics(domain: str, n: int = 10) -> list[str]:
    """
    Genera N subtópicos reales para aprender sobre un dominio.
    Usa LLM para hacerlo inteligente y específico.
    """
    prompt = f"""Dominio a aprender: {domain}

Genera exactamente {n} subtópicos específicos y distintos para investigar en profundidad sobre "{domain}".
Cubre fundamentos, técnicas avanzadas, aplicaciones prácticas, errores comunes, y herramientas.

Devuelve SOLO una lista numerada, un subtópico por línea. Sin explicaciones.
Ejemplo formato:
1. Fundamentos de X
2. Estrategias avanzadas de Y
...
"""
    try:
        raw = generate_with_fallback([
            {"role": "system", "content": "Eres un experto en educación. Generas planes de estudio detallados."},
            {"role": "user", "content": prompt},
        ])
        subtopics = []
        for line in raw.splitlines():
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-")):
                clean = line.lstrip("0123456789.-) ").strip()
                if clean and len(clean) > 3:
                    subtopics.append(clean)
        if len(subtopics) < 3:
            subtopics = [f"{domain} fundamentos", f"{domain} estrategias", f"{domain} herramientas",
                         f"{domain} errores comunes", f"{domain} casos reales"]
        return subtopics[:n]
    except Exception as e:
        logger.error("_generate_subtopics error: %s", e)
        return [f"{domain} conceptos básicos", f"{domain} técnicas avanzadas", f"{domain} práctica real"]


def _bee_research_subtopic(domain: str, subtopic: str, bee_id: int) -> dict:
    """
    Una BEE investiga UN subtópico específico.
    Hace búsqueda web real y sintetiza el resultado con LLM.
    Retorna: {"subtopic": str, "content": str, "sources": list, "bee_id": int}
    """
    logger.info("BEE-%d investigando: %s > %s", bee_id, domain, subtopic)

    # 1. Búsqueda web real
    query = f"{domain} {subtopic}"
    try:
        raw_results = web_search(query, max_results=5)
    except Exception as e:
        raw_results = f"Búsqueda web falló: {e}"

    # 2. Síntesis con LLM
    synthesis_prompt = f"""Eres una BEE experta investigadora. Estás aprendiendo sobre "{domain}".
Tu subtópico específico: "{subtopic}"

Resultados de búsqueda web:
{raw_results[:2500]}

Sintetiza lo más importante en un bloque de conocimiento denso y útil.
Incluye:
- Conceptos clave
- Datos concretos y cifras si los hay
- Técnicas o métodos específicos
- Insights no obvios

Escribe en español. Sé densa en información. Máximo 600 palabras."""

    try:
        synthesis = generate_with_fallback([
            {"role": "system", "content": f"Eres una BEE especialista en {domain}. Sintetizas conocimiento de forma densa y precisa."},
            {"role": "user", "content": synthesis_prompt},
        ])
    except Exception as e:
        synthesis = f"Síntesis: {raw_results[:500]}"

    # Guardar inmediatamente en KB
    knowledge_base.add_learning(
        domain=domain,
        subtopic=subtopic,
        content=synthesis,
        source=f"web_search:{query}",
    )

    return {
        "bee_id": bee_id,
        "subtopic": subtopic,
        "content": synthesis,
        "raw_search": raw_results[:500],
    }


def _synthesize_domain(domain: str, bee_results: list[dict]) -> tuple[str, list[str]]:
    """
    Después de que todas las BEES terminan, sintetiza todo en conocimiento maestro.
    Retorna (synthesis_text, key_facts_list).
    """
    all_content = []
    for r in bee_results:
        all_content.append(f"[{r['subtopic']}]\n{r['content'][:800]}")

    combined = "\n\n".join(all_content)

    master_prompt = f"""Acabas de recibir investigación exhaustiva de {len(bee_results)} BEES sobre "{domain}".

Resultados de todas las BEES:
{combined[:6000]}

Ahora eres la síntesis maestra. Crea:

1. SÍNTESIS_MAESTRA: Un párrafo denso de 300-500 palabras que capture la esencia completa de lo que se aprendió sobre {domain}.

2. HECHOS_CLAVE: Lista de exactamente 15 hechos clave, datos concretos, o insights más importantes. Un hecho por línea, empezando con "•".

Formato EXACTO:
SÍNTESIS_MAESTRA:
[texto]

HECHOS_CLAVE:
• hecho 1
• hecho 2
..."""

    try:
        raw = generate_with_fallback([
            {"role": "system", "content": f"Eres BEEA, la IA maestra. Sintetizas el conocimiento colectivo de tu enjambre de BEES sobre {domain}."},
            {"role": "user", "content": master_prompt},
        ])

        synthesis = ""
        key_facts = []

        if "SÍNTESIS_MAESTRA:" in raw:
            parts = raw.split("HECHOS_CLAVE:")
            synthesis_part = parts[0].replace("SÍNTESIS_MAESTRA:", "").strip()
            synthesis = synthesis_part

            if len(parts) > 1:
                facts_text = parts[1]
                for line in facts_text.splitlines():
                    line = line.strip().lstrip("•-* ").strip()
                    if line and len(line) > 10:
                        key_facts.append(line)
        else:
            synthesis = raw[:1500]
            key_facts = [line.strip() for line in raw.splitlines() if len(line.strip()) > 20][:15]

        return synthesis, key_facts[:15]

    except Exception as e:
        logger.error("_synthesize_domain error: %s", e)
        return f"Aprendizaje completado sobre {domain}.", []


# ── Motor principal ────────────────────────────────────────────────────────────

class LearningEngine:
    """
    Motor de aprendizaje real.
    Despliega BEES en paralelo para aprender cualquier tema.
    """

    async def learn(
        self,
        domain: str,
        num_bees: int = 10,
        progress_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> dict:
        """
        Aprende un dominio completo desplegando N BEES en paralelo.
        
        Args:
            domain: El tema a aprender (e.g., "trading", "cocina", "machine learning")
            num_bees: Número de BEES a desplegar (1-50). Más = más profundidad.
            progress_callback: Función async para enviar updates al usuario.
            
        Returns:
            dict con expertise_level, key_facts, synthesis, subtopics_covered
        """
        async def _emit(msg: str):
            if progress_callback:
                try:
                    await progress_callback(msg)
                except Exception:
                    pass

        num_bees = max(1, min(50, num_bees))

        await _emit(f"Iniciando sesión de aprendizaje: {domain.upper()}\n"
                    f"Desplegando {num_bees} BEES investigadoras...")

        # 1. Generar subtópicos
        await _emit(f"Generando plan de estudio para '{domain}'...")
        subtopics = await asyncio.to_thread(_generate_subtopics, domain, num_bees)
        await _emit(
            f"Plan de estudio: {len(subtopics)} subtópicos\n" +
            "\n".join(f"  BEE-{i+1}: {st}" for i, st in enumerate(subtopics))
        )

        # 2. Lanzar BEES en paralelo (ThreadPoolExecutor = real paralelismo)
        await _emit(f"Lanzando {len(subtopics)} BEES en paralelo. Investigando simultáneamente...")

        bee_results = []
        completed = 0

        loop = asyncio.get_event_loop()

        with ThreadPoolExecutor(max_workers=min(len(subtopics), 20)) as executor:
            futures = {
                executor.submit(_bee_research_subtopic, domain, st, i + 1): (i + 1, st)
                for i, st in enumerate(subtopics)
            }

            for future in as_completed(futures):
                bee_id, subtopic = futures[future]
                try:
                    result = future.result(timeout=90)
                    bee_results.append(result)
                    completed += 1
                    preview = result["content"][:150].replace("\n", " ")
                    await _emit(f"BEE-{bee_id} completó '{subtopic}':\n{preview}...")
                except Exception as e:
                    logger.error("BEE-%d failed: %s", bee_id, e)
                    await _emit(f"BEE-{bee_id} tuvo un error en '{subtopic}' — continuando con las demás")
                    bee_results.append({
                        "bee_id": bee_id,
                        "subtopic": subtopic,
                        "content": f"Investigación parcial sobre {subtopic}",
                        "raw_search": "",
                    })
                    completed += 1

        await _emit(f"Todas las BEES completaron. {completed}/{len(subtopics)} exitosas.\n"
                    f"Sintetizando conocimiento maestro...")

        # 3. Síntesis maestra
        synthesis, key_facts = await asyncio.to_thread(_synthesize_domain, domain, bee_results)

        # Calcular expertise ganado (más BEES = más expertise)
        expertise_delta = min(40, 5 + len(bee_results) * 2)
        knowledge_base.update_synthesis(domain, synthesis, key_facts, expertise_delta)

        new_level = knowledge_base.get_expertise_level(domain)

        # 4. Resultado final
        facts_text = "\n".join(f"• {f}" for f in key_facts[:10])
        await _emit(
            f"Aprendizaje completado: {domain.upper()}\n\n"
            f"Nivel de expertise: {new_level}/100\n"
            f"Subtópicos cubiertos: {len(bee_results)}\n\n"
            f"Síntesis:\n{synthesis[:600]}\n\n"
            f"Hechos clave:\n{facts_text}"
        )

        return {
            "domain": domain,
            "expertise_level": new_level,
            "subtopics_covered": len(bee_results),
            "key_facts": key_facts,
            "synthesis": synthesis,
            "bees_used": len(subtopics),
        }


learning_engine = LearningEngine()
