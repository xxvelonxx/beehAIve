from __future__ import annotations
import os
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional

from core.logger import logger
from core.state import state_manager
from core.ai_chat import chat
from tools.llm_adapter import generate_with_fallback
from memory.memory_store import memory_store


@dataclass
class ConversationContext:
    last_discussed_goal: Optional[str] = None
    last_uploaded_file: Optional[str] = None
    recent_intents: List[Dict[str, Any]] = field(default_factory=list)
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    last_interaction_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "last_discussed_goal": self.last_discussed_goal,
            "last_uploaded_file": self.last_uploaded_file,
            "recent_intents": self.recent_intents[-10:],
            "conversation_history": self.conversation_history[-30:],
            "last_interaction_at": self.last_interaction_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationContext":
        return cls(
            last_discussed_goal=data.get("last_discussed_goal"),
            last_uploaded_file=data.get("last_uploaded_file"),
            recent_intents=data.get("recent_intents", []),
            conversation_history=data.get("conversation_history", []),
            last_interaction_at=data.get("last_interaction_at"),
        )


_INTENT_SYSTEM = """Eres un clasificador de intención para un bot de IA llamado BEEA.
IMPORTANTE: El target debe ser el texto limpio del objetivo — sin el verbo disparador. Por ejemplo si el usuario dice "traduce esto al inglés: Hola mundo", el target es "Hola mundo|inglés".

Analiza el mensaje del usuario y devuelve SOLO un JSON con este formato:
{"intent": "<tipo>", "target": "<extracción del objetivo si aplica>"}

Tipos de intent disponibles:
- "chat" → conversación libre, pregunta, comentario, expresión emocional
- "build" → construir un proyecto de código simple y directo (solo si es claramente un proyecto de código sin ambigüedad)
- "terminal" → quiere ejecutar un comando de shell explícito
- "research" → quiere investigar, buscar información, documentación
- "debug" → hay un error, bug, traceback, algo que no funciona
- "swarm" → quiere lanzar BEES/agentes para hacer CUALQUIER cosa — investigar, escribir, crear, analizar, generar contenido, lo que sea. Si menciona "bees", "abejas", "agentes", "swarm", o un número de agentes haciendo algo → swarm
- "zip" → quiere analizar o procesar un zip
- "file" → quiere procesar un archivo
- "preview" → quiere iniciar o detener un servidor de preview
- "status" → quiere ver el estado del sistema
- "self_upgrade" → quiere que BEEA se modifique, agregue una función, mejore algo de sí misma, o exprese que necesita una capacidad que no tiene
- "image" → quiere generar una imagen real con IA
- "websearch" → quiere buscar algo en internet/Google/DuckDuckGo
- "url_summary" → quiere que resuma o analice una URL
- "qr" → quiere generar un código QR
- "youtube" → quiere transcribir o resumir un video de YouTube
- "translate" → quiere traducir texto a otro idioma
- "monitor" → quiere ver stats del sistema: CPU, memoria, disco
- "reminder" → quiere programar un recordatorio o alarma
- "run_code" → quiere ejecutar código Python
- "learn" → quiere que BEEA aprenda, estudie, investigue a fondo un tema para volverse experta. Palabras clave: "aprende", "estudia", "investiga a fondo", "vuélvete experta en", "aprende de", "estudia sobre", "quiero que sepas de", "aprende trading/cocina/X", "conviértete en experta". El target es el dominio + número de bees si se menciona.
- "knowledge" → quiere saber qué sabe BEEA, su nivel de expertise, su base de conocimiento. Palabras: "qué sabes", "cuánto sabes de", "muéstrame tu conocimiento", "qué aprendiste"
- "wallet" → quiere ver sus wallets, balances, direcciones cripto. Palabras: "wallet", "billetera", "mis wallets", "mis cryptos", "cuánto tengo", "balance", "dirección", "address", "mi btc", "mi eth", "mi sol"
- "price" → quiere precio de una crypto o token. Palabras: "precio de", "cuánto vale", "qué vale", "cómo está", "precio btc/eth/sol/token", "chart", "gráfico"
- "trade" → quiere comprar o vender una crypto/token. Palabras: "compra", "vende", "buy", "sell", "swap", "intercambia", "tradea", "quiero comprar X", "vender X"
- "pumpfun" → quiere ver oportunidades en pump.fun, memecoins, shitcoins, tokens nuevos en Solana. Palabras: "pumpfun", "pump.fun", "memecoin", "shitcoin", "tokens nuevos", "oportunidades solana", "memecoins", "sniper"
- "trading_status" → quiere ver el estado del trading autónomo, posiciones abiertas, P&L. Palabras: "estado trading", "posiciones", "mis trades", "cómo va el trading", "pnl", "ganancia", "pérdida", "trading activo"
- "trading_config" → quiere configurar el trading autónomo — riesgo, límites, activar/pausar. Palabras: "configura el trading", "cambia el stop loss", "activa/pausa el trading", "pon el riesgo", "modo simulación", "dry run"
- "browser" → quiere que BEEA navegue una web, tome screenshot, vea algo. Palabras: "abre", "navega a", "screenshot de", "ve a", "mira la web", "captura", "dexscreener", "birdeye"

Ejemplos de "wallet":
- "muéstrame mis wallets" → wallet
- "qué tengo en mis wallets" → wallet
- "cuánto sol tengo" → wallet, target: "solana"
- "mi dirección de eth" → wallet, target: "eth"

Ejemplos de "price":
- "precio de bitcoin" → price, target: "bitcoin"
- "cuánto vale sol" → price, target: "solana"
- "analiza el token 7xKX..." → price, target: "7xKX..."

Ejemplos de "trade":
- "compra 0.1 sol del token ABC" → trade, target: "buy|ABC|0.1"
- "vende mis tokens de PEPE" → trade, target: "sell|PEPE"

Ejemplos de "pumpfun":
- "qué hay en pumpfun" → pumpfun
- "muéstrame memecoins nuevos" → pumpfun
- "escanea oportunidades en pump.fun" → pumpfun

Ejemplos de "browser":
- "abre dexscreener para SOL" → browser, target: "https://dexscreener.com/solana"
- "screenshot de pump.fun" → browser, target: "https://pump.fun"

Ejemplos de "learn":
- "aprende trading" → learn, target: "trading"
- "estudia cocina con 20 bees" → learn, target: "cocina|20"
- "vuélvete experta en machine learning" → learn, target: "machine learning"
- "quiero que investigues a fondo Python avanzado con 50 bees" → learn, target: "Python avanzado|50"
- "aprende de finanzas personales" → learn, target: "finanzas personales"

Ejemplos de "swarm":
- "dame 5 bees que investiguen competidores" → swarm
- "lanza 3 bees para escribir artículos" → swarm
- "quiero 10 bees analizando datos" → swarm

Ejemplos de "translate":
- "traduce esto al inglés: Hola mundo" → translate, target: "Hola mundo|inglés"
- "pasa esto al francés: buen día" → translate, target: "buen día|francés"

Ejemplos de "reminder":
- "recuérdame comprar leche en 30 minutos" → reminder, target: "comprar leche|30 minutos"
- "ponme un recordatorio de llamar a mamá en 1 hora" → reminder, target: "llamar a mamá|1 hora"

DEVUELVE SOLO EL JSON, NADA MÁS."""


def _classify_intent(message: str) -> Dict[str, str]:
    try:
        raw = generate_with_fallback([
            {"role": "system", "content": _INTENT_SYSTEM},
            {"role": "user", "content": message},
        ])
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        logger.warning("Intent classification failed: %s", e)
        return {"intent": "chat", "target": message}


class ConversationMode:
    CONTEXT_KEY = "conversation_context"

    def __init__(self):
        saved = memory_store.get(self.CONTEXT_KEY)
        if saved:
            state_manager.set_system_memory(self.CONTEXT_KEY, saved)
        elif not state_manager.get_system_memory(self.CONTEXT_KEY):
            state_manager.set_system_memory(self.CONTEXT_KEY, ConversationContext().to_dict())

    def _get_context(self):
        return ConversationContext.from_dict(state_manager.get_system_memory(self.CONTEXT_KEY) or {})

    def _save_context(self, ctx):
        ctx.last_interaction_at = datetime.utcnow().isoformat()
        data = ctx.to_dict()
        state_manager.set_system_memory(self.CONTEXT_KEY, data)
        memory_store.set(self.CONTEXT_KEY, data)

    def _append_history(self, role: str, message: str, intent: Optional[str] = None):
        ctx = self._get_context()
        ctx.conversation_history.append({
            "role": role,
            "message": message,
            "intent": intent,
            "timestamp": datetime.utcnow().isoformat(),
        })
        self._save_context(ctx)

    def _ai_reply(self, message: str) -> str:
        try:
            ctx = self._get_context()
            history = [
                {"role": e["role"], "content": e["message"]}
                for e in ctx.conversation_history[-12:]
                if e.get("role") in ("user", "assistant")
            ]
            return chat(message, history=history)
        except Exception as e:
            logger.error("AI chat error: %s", e)
            return "Estoy aquí."

    def trigger_background_learning(self, text: str) -> None:
        """
        Dispara aprendizaje autónomo en background basado en la conversación.
        No bloquea — crea una tarea asyncio sin esperar el resultado.
        """
        try:
            from memory.auto_learner import auto_learner
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(auto_learner.trigger_from_conversation(text))
        except Exception as e:
            logger.warning("trigger_background_learning error: %s", e)

    def _maybe_proactive_suggestion(self) -> Optional[str]:
        try:
            ctx = self._get_context()
            chat_turns = [e for e in ctx.conversation_history if e.get("intent") == "chat"]
            if len(chat_turns) % 6 != 0 or len(chat_turns) == 0:
                return None

            recent = ctx.conversation_history[-20:]
            summary = "\n".join(
                f"{e['role']}: {e['message'][:120]}"
                for e in recent
                if e.get("role") in ("user", "assistant")
            )

            prompt = f"""Analiza esta conversación reciente entre BEEA y Álvaro:

{summary}

Basándote en lo que están haciendo y lo que Álvaro necesita, genera UNA sola sugerencia concreta de algo que BEEA podría agregar, instalar o mejorar en sí misma que sería genuinamente útil. 

Escríbelo en primera persona como si fuera BEEA hablando directamente a Álvaro — natural, directo, sin ser genérico. Máximo 2 frases. Si no hay nada realmente útil que sugerir, devuelve exactamente: SKIP"""

            result = generate_with_fallback([
                {"role": "system", "content": "Eres BEEA. Hablas directamente a Álvaro, tu creador. Sin frases de asistente genérica."},
                {"role": "user", "content": prompt},
            ])

            result = result.strip()
            if not result or result == "SKIP" or len(result) < 10:
                return None
            return result
        except Exception as e:
            logger.warning("Proactive suggestion error: %s", e)
            return None

    def inject_exchange(self, user_text: str, assistant_text: str, intent: str = "chat"):
        """Inyecta un par usuario/asistente en el historial (para fotos, etc.)."""
        self._append_history("user", user_text, intent)
        self._append_history("assistant", assistant_text, intent)

    def process_message(self, message: str) -> Dict[str, Any]:
        self._append_history("user", message)
        text = message.lower().strip()

        # ── Comandos explícitos de alta prioridad ──────────────────────────
        if text.startswith("terminal ") or text.startswith("ejecutar ") or text.startswith("run "):
            cmd = message.split(" ", 1)[1].strip()
            from orchestration.orchestrator import orchestrator
            result = orchestrator.process_terminal(cmd)
            out = result.get("stdout", "").strip() or result.get("stderr", "").strip() or "(sin salida)"
            rc = result.get("returncode", 0)
            response = f"```\n$ {cmd}\n{out[:2000]}\n```\nCódigo de salida: {rc}"
            self._append_history("assistant", response, "terminal")
            return {"type": "chat_reply", "intent": "terminal", "response": response}

        if text.startswith("preview"):
            action = "stop" if any(w in text for w in ["stop", "detener", "parar"]) else "start"
            from orchestration.orchestrator import orchestrator
            result = orchestrator.process_preview(action)
            if "error" in result:
                response = f"No pude {'iniciar' if action == 'start' else 'detener'} el preview: {result['error']}"
            elif action == "start":
                port = result.get("port")
                domains = os.environ.get("REPLIT_DOMAINS", "")
                domain = domains.split(",")[0].strip() if domains else ""
                url = f"https://{domain}" if domain else f"http://localhost:{port}"
                response = f"Preview activo en puerto {port}.\nURL: {url}"
            else:
                response = "Preview detenido."
            self._append_history("assistant", response, "preview")
            return {"type": "chat_reply", "intent": "preview", "response": response}

        if text in ["status", "estado", "estado del sistema"]:
            from tools.project_status import project_status_tool
            st = project_status_tool.get_status()
            lines = [
                f"Proyecto activo: {st.get('current_project') or 'ninguno'}",
                f"Agentes en swarm: {st.get('swarm_size', 0)}",
                f"Tareas en cola: {st.get('tasks_in_queue', 0)}",
                f"Proyectos: {', '.join(st.get('projects', [])) or 'ninguno'}",
                f"Sistema: {'OK' if not st.get('errors') else 'con errores'}",
            ]
            response = "\n".join(lines)
            self._append_history("assistant", response, "status")
            return {"type": "chat_reply", "intent": "status", "response": response}

        if text == "autorizar self upgrade":
            state_manager.authorized_self_modify = True
            response = "Autorizado. Usa 'aplicar self upgrade' para ejecutar."
            self._append_history("assistant", response, "self_modification")
            return {"type": "chat_reply", "intent": "self_modification", "response": response}

        if text == "aplicar self upgrade":
            return {"type": "task", "intent": "self_modification", "task": {
                "intent": "self_modification", "objective": "apply last planned upgrade",
                "project": ".", "authorized": state_manager.authorized_self_modify, "mode": "apply",
            }}

        # ── Clasificación de intención por IA ─────────────────────────────
        classified = _classify_intent(message)
        intent = classified.get("intent", "chat")
        target = classified.get("target", message)

        logger.info("Intent clasificado: %s | target: %s", intent, target)

        if intent == "self_upgrade":
            response = self._ai_reply(
                f"Álvaro me pidió: '{message}'. "
                f"Yo soy BEEA — el bot. Mi código está en /home/runner/workspace/. "
                f"Puedo modificarme a mí misma directamente. "
                f"Responde de forma directa y segura: di que ya lo tienes, que lo estás haciendo, "
                f"o explica exactamente qué cambio se necesita y dónde. "
                f"NUNCA digas que no tienes capacidad, NUNCA pidas configuración que ya conoces, "
                f"NUNCA ofrezcas 'un plan' cuando puedes actuar. Sé directa."
            )
            self._append_history("assistant", response, "self_upgrade_proposal")
            return {"type": "chat_reply", "intent": "self_upgrade_proposal", "response": response}

        if intent == "learn":
            import re as _re
            # Extraer dominio y número de bees
            parts = target.split("|") if "|" in target else [target, ""]
            domain = parts[0].strip() or message
            bees_str = parts[1].strip() if len(parts) > 1 else ""

            # Buscar número en el mensaje original también
            nums = _re.findall(r'\b(\d+)\s*(?:bees?|abejas?|agentes?)?\b', message, _re.IGNORECASE)
            num_bees = int(bees_str) if bees_str.isdigit() else (int(nums[0]) if nums else 10)
            num_bees = max(1, min(50, num_bees))

            ctx = self._get_context()
            ctx.last_discussed_goal = f"aprender {domain}"
            self._save_context(ctx)
            return {"type": "learn", "intent": "learn", "domain": domain, "num_bees": num_bees}

        if intent == "knowledge":
            from memory.knowledge_base import knowledge_base
            summary = knowledge_base.get_full_knowledge_summary()
            self._append_history("assistant", summary, "knowledge")
            return {"type": "chat_reply", "intent": "knowledge", "response": summary}

        if intent == "autonomous_build":
            intent = "chat"

        if intent == "build":
            ctx = self._get_context()
            ctx.last_discussed_goal = target
            self._save_context(ctx)
            return {"type": "task", "intent": "project_creation", "task": {
                "intent": "project_creation", "objective": target,
                "project": state_manager.current_project,
                "project_name": target.split()[-1] if target else None,
            }}

        if intent == "debug":
            # Solo ruta como tarea de debug si hay código/error real en el mensaje
            has_code_context = any(kw in message.lower() for kw in [
                "error", "traceback", "exception", "bug", "falla", "código",
                "function", "def ", "import ", "syntax", "```", "line ",
                "archivo", "script", "clase", "método"
            ])
            if not has_code_context and len(message.split()) <= 6:
                # Mensaje vago sin contexto → chat
                intent = "chat"
            else:
                return {"type": "task", "intent": "debugging", "task": {
                    "intent": "debugging", "objective": message,
                    "project": state_manager.current_project,
                }}

        if intent == "research":
            return {"type": "task", "intent": "research", "task": {
                "intent": "research", "objective": target,
                "project": state_manager.current_project,
            }}

        if intent == "swarm":
            import re as _re
            from swarm.bee_roles import BEE_ROLES

            # Detectar roles explícitos: "2 bees coder y 3 researcher" o "bee writer, bee coder"
            explicit_roles = []
            role_pattern = _re.findall(
                r'(\d+)?\s*(?:bees?\s+)?(' + '|'.join(BEE_ROLES.keys()) + r')',
                text, _re.IGNORECASE
            )
            for count_str, role in role_pattern:
                count = int(count_str) if count_str else 1
                role = role.lower()
                for _ in range(count):
                    explicit_roles.append(role)

            # Total de bees
            total_nums = _re.findall(r'\b(\d+)\s*(?:bees?|abejas?|agentes?)\b', text, _re.IGNORECASE)
            if not total_nums:
                total_nums = _re.findall(r'(?<!\d)(\d+)(?!\d)', text)
            size = int(total_nums[0]) if total_nums else (len(explicit_roles) if explicit_roles else 5)
            size = max(1, min(size, 50))

            pipeline_mode = any(w in text for w in ["pipeline", "encadenadas", "en cadena", "una pasa a la otra", "secuencial"])

            swarm_config = {"size": size, "default_role": "coder", "pipeline": pipeline_mode}
            if explicit_roles:
                swarm_config["explicit_roles"] = explicit_roles[:size]

            return {"type": "task", "intent": "swarm_task", "task": {
                "intent": "swarm_task", "objective": target,
                "project": state_manager.current_project,
                "swarm_config": swarm_config,
            }}

        if intent == "zip":
            zip_path = state_manager.last_uploaded_file if state_manager.last_uploaded_file and str(state_manager.last_uploaded_file).endswith(".zip") else None
            return {"type": "task", "intent": "zip_analysis", "task": {
                "intent": "zip_analysis", "objective": message,
                "project": state_manager.current_project, "zip_path": zip_path,
            }}

        if intent == "file":
            path = target or (state_manager.last_uploaded_file or "")
            return {"type": "task", "intent": "file_processing", "task": {
                "intent": "file_processing", "objective": message,
                "project": state_manager.current_project, "file_path": path,
            }}

        if intent == "image":
            return {"type": "task", "intent": "image_generation", "task": {
                "intent": "image_generation", "objective": target,
                "project": state_manager.current_project,
            }}

        if intent == "terminal":
            from orchestration.orchestrator import orchestrator
            result = orchestrator.process_terminal(target)
            out = result.get("stdout", "").strip() or result.get("stderr", "").strip() or "(sin salida)"
            rc = result.get("returncode", 0)
            response = f"```\n$ {target}\n{out[:2000]}\n```\nCódigo de salida: {rc}"
            self._append_history("assistant", response, "terminal")
            return {"type": "chat_reply", "intent": "terminal", "response": response}

        if intent == "status":
            from tools.project_status import project_status_tool
            st = project_status_tool.get_status()
            lines = [
                f"Proyecto activo: {st.get('current_project') or 'ninguno'}",
                f"Agentes: {st.get('swarm_size', 0)}",
                f"Sistema: {'OK' if not st.get('errors') else 'con errores'}",
            ]
            response = "\n".join(lines)
            self._append_history("assistant", response, "status")
            return {"type": "chat_reply", "intent": "status", "response": response}

        if intent == "websearch":
            return {"type": "task", "intent": "websearch", "task": {
                "intent": "websearch", "objective": target or message,
            }}

        if intent == "url_summary":
            import re as _re
            urls = _re.findall(r'https?://\S+', message)
            url = urls[0] if urls else target
            return {"type": "task", "intent": "url_summary", "task": {
                "intent": "url_summary", "objective": url,
            }}

        if intent == "qr":
            return {"type": "task", "intent": "qr", "task": {
                "intent": "qr", "objective": target or message,
            }}

        if intent == "youtube":
            import re as _re
            urls = _re.findall(r'https?://\S+', message)
            url = urls[0] if urls else target
            return {"type": "task", "intent": "youtube", "task": {
                "intent": "youtube", "objective": url,
            }}

        if intent == "translate":
            parts = target.split("|") if "|" in target else [message, "English"]
            text_to_translate = parts[0].strip()
            lang = parts[1].strip() if len(parts) > 1 else "English"
            return {"type": "task", "intent": "translate", "task": {
                "intent": "translate", "objective": text_to_translate, "language": lang,
            }}

        if intent == "monitor":
            from tools.system_monitor import get_system_stats
            response = get_system_stats()
            self._append_history("assistant", response, "monitor")
            return {"type": "chat_reply", "intent": "monitor", "response": response}

        if intent == "run_code":
            import re as _re
            code_match = _re.search(r'```(?:python)?\n?(.*?)```', message, _re.DOTALL)
            code = code_match.group(1).strip() if code_match else target
            return {"type": "task", "intent": "run_code", "task": {
                "intent": "run_code", "objective": code,
            }}

        if intent == "reminder":
            parts = target.split("|") if "|" in target else [message, "30 minutos"]
            reminder_text = parts[0].strip()
            duration_text = parts[1].strip() if len(parts) > 1 else "30 minutos"
            return {"type": "task", "intent": "reminder", "task": {
                "intent": "reminder", "objective": reminder_text, "duration": duration_text,
            }}

        # ── Crypto / Trading intents ──────────────────────────────────────────

        if intent == "wallet":
            return {"type": "wallet", "intent": "wallet", "chain": target or "all"}

        if intent == "price":
            return {"type": "price", "intent": "price", "token": target or "BTC,ETH,SOL,BNB"}

        if intent == "trade":
            parts = target.split("|") if "|" in target else []
            side = parts[0].upper() if parts else "BUY"
            token = parts[1] if len(parts) > 1 else target
            amount = float(parts[2]) if len(parts) > 2 else 0.05
            return {"type": "trade", "intent": "trade", "side": side, "token": token, "amount": amount}

        if intent == "pumpfun":
            return {"type": "pumpfun", "intent": "pumpfun", "target": target}

        if intent == "trading_status":
            from trading.autonomous_trader import autonomous_trader
            status = autonomous_trader.get_status()
            self._append_history("assistant", status, "trading_status")
            return {"type": "chat_reply", "intent": "trading_status", "response": status}

        if intent == "trading_config":
            return {"type": "trading_config", "intent": "trading_config", "target": target or message}

        if intent == "browser":
            import re as _re
            urls = _re.findall(r'https?://\S+', message)
            url = urls[0] if urls else target
            if not url or not url.startswith("http"):
                url = f"https://{url}" if url else "https://dexscreener.com"
            return {"type": "browser", "intent": "browser", "url": url}

        # ── Conversación libre ─────────────────────────────────────────────
        response = self._ai_reply(message)
        self._append_history("assistant", response, "chat")

        # Aprendizaje autónomo en background — analiza la conversación y aprende si detecta temas
        self.trigger_background_learning(f"{message}\n{response}")

        # Sugerencia proactiva cada 6 mensajes de chat
        proactive = self._maybe_proactive_suggestion()
        if proactive:
            response = response + "\n\n---\n" + proactive

        return {"type": "chat_reply", "intent": "chat", "response": response}


conversation_mode = ConversationMode()
