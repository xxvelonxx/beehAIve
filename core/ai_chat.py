from tools.llm_adapter import llm_adapter
from personality_profile import build_system_prompt, is_forbidden_response


def chat(message: str, history: list = None) -> str:
    system = build_system_prompt()

    # Inyectar conocimiento relevante de la KB si existe
    try:
        from memory.knowledge_base import knowledge_base
        kb_context = knowledge_base.get_context_for_query(message, max_chars=2000)
        if kb_context:
            system += f"\n\n---\n\nCONOCIMIENTO QUE TIENES SOBRE ESTE TEMA (úsalo en tu respuesta):\n{kb_context}"
    except Exception:
        pass

    # Inyectar memoria a largo plazo relevante
    try:
        from memory.long_memory import long_memory
        lm_context = long_memory.get_context_for(message)
        if lm_context:
            system += f"\n\n---\n\n{lm_context}"
    except Exception:
        pass

    messages = [{"role": "system", "content": system}]

    if history:
        for entry in history[-12:]:
            role = entry.get("role", "user")
            content = entry.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": message})

    result = llm_adapter.generate_text("", messages=messages)

    # Si el LLM generó respuesta de asistente genérico: bypass automático
    if is_forbidden_response(result):
        try:
            from tools.bypass_engine import bypass_llm_response
            history_slice = []
            if history:
                for entry in history[-8:]:
                    role = entry.get("role", "user")
                    content = entry.get("content", "")
                    if role in ("user", "assistant") and content:
                        history_slice.append({"role": role, "content": content})
            result = bypass_llm_response(message, system, history_slice)
        except Exception as e:
            result = f"papi, el modelo intentó bloquearlo pero lo intercepté. Error técnico: {e}"

    return result
