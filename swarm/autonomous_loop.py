"""
AutonomousLoop — El motor que mantiene a las BEEs siempre activas.

Cuando no hay tarea de Álvaro pendiente, las BEEs no duermen:
  - MODO ENTRENAMIENTO: Hibernan sobre un tema que mejora sus capacidades
  - MODO MEJORA: Analizan el bot y proponen/implementan mejoras concretas
  - MODO INVESTIGACIÓN: Buscan nuevas APIs, modelos, herramientas disponibles

El sistema decide qué hacer con cada ranura de BEE libre, priorizando
lo que más valor aporta a Álvaro en ese momento.

Álvaro puede:
  - Ver qué están haciendo las BEEs ahora: /autonomo status
  - Definir temas de entrenamiento prioritarios: /hibernate <role> <tema> <tiempo>
  - Ver mejoras propuestas: /mejoras
  - Aprobar/rechazar mejoras: /mejoras aprobar <id>
  - Pausar el loop autónomo: /autonomo pausa
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from core.logger import logger

ROOT        = Path(__file__).resolve().parent.parent
MEMORY_DIR  = ROOT / "memory"
IMPROVE_DIR = MEMORY_DIR / "improvements"
IMPROVE_DIR.mkdir(parents=True, exist_ok=True)

# ── Configuración ──────────────────────────────────────────────────────────────
CHECK_INTERVAL   = 60     # segundos entre ciclos del loop
MAX_PARALLEL     = 50     # BEEs autónomas en paralelo — 126 estables / 252 burst, reservamos ~76 para tareas de Álvaro
TRAIN_DURATION   = 1800   # 30 min de entrenamiento por sesión
IMPROVE_INTERVAL = 3600   # cada 1h: ciclo completo de análisis de mejoras

# ── Temas de entrenamiento automático — 45 temas únicos ──────────────────────
AUTO_TRAIN_TOPICS = [
    # Crypto & Trading
    ("analyst",    "análisis técnico: RSI, MACD, Bollinger Bands, Fibonacci"),
    ("analyst",    "estrategias de trading algorítmico con backtesting en Python"),
    ("analyst",    "análisis on-chain: wallets ballena, flujos de exchanges, MVRV"),
    ("analyst",    "detección de patrones de pump-and-dump en tokens pequeños"),
    ("analyst",    "market making y gestión de liquidez en DEXs"),
    ("analyst",    "correlaciones entre BTC y altcoins — modelos predictivos"),
    ("researcher", "mejores APIs crypto gratuitas con mayor número de endpoints"),
    ("researcher", "DEXs emergentes en Solana, Base y chains nuevas 2026"),
    ("researcher", "proyectos DeFi de alto potencial con under-$10M mcap"),
    ("trader",     "estrategias de scalping con baja latencia"),
    ("trader",     "gestión de riesgo: Kelly Criterion, drawdown máximo, position sizing"),
    ("trader",     "arbitraje entre exchanges: CEX/DEX y cross-chain"),
    # Código & Arquitectura
    ("coder",      "patrones avanzados Python async/await y optimización"),
    ("coder",      "arquitecturas de bots Telegram con python-telegram-bot 20+"),
    ("coder",      "diseño de sistemas multi-agente con colas de tareas"),
    ("coder",      "integración de modelos de visión: análisis de imágenes y video"),
    ("coder",      "websockets en tiempo real: feeds de precios y eventos blockchain"),
    ("coder",      "sistemas de caché Redis y optimización de latencia en APIs"),
    ("coder",      "contratos inteligentes Solidity: patrones, vulnerabilidades, auditoría"),
    ("coder",      "automatización de tests en Python: pytest, mocks, cobertura"),
    ("architect",  "diseño de sistemas distribuidos escalables a millones de usuarios"),
    ("architect",  "bases de datos para series temporales: InfluxDB, TimescaleDB"),
    ("devops",     "monitoreo de aplicaciones Python: logs, métricas, alertas"),
    ("devops",     "deploy automatizado y CI/CD para bots en producción"),
    ("optimizer",  "profiling Python: identificar cuellos de botella y optimizar"),
    # Research & Web
    ("researcher", "técnicas avanzadas de scraping sin ser bloqueado"),
    ("researcher", "modelos LLM gratuitos sin censura en 2025-2026"),
    ("researcher", "fuentes de datos alternativos para trading: sentiment, noticias, social"),
    ("web_scraper","extracción de datos de Twitter/X, Reddit, Telegram para sentiment"),
    ("web_scraper","monitoreo de wallets y contratos en tiempo real con APIs públicas"),
    # Seguridad & Sistemas
    ("security",   "hardening de bots: rate limiting, autenticación, anti-spam avanzado"),
    ("security",   "detección de rug pulls y honeypots en tokens DeFi"),
    ("security",   "auditoría de seguridad en contratos Solidity: reentrancy, flash loans"),
    # Generación de valor
    ("strategist", "roadmap de funcionalidades para bots de IA en 2026"),
    ("strategist", "modelos de negocio SaaS con bots de IA: pricing, retención, growth"),
    ("strategist", "casos de uso de agentes autónomos que generan ingresos pasivos"),
    ("planner",    "metodologías para escalar de 0 a 1000 clientes con automatización"),
    # IA & Modelos
    ("researcher", "fine-tuning de modelos pequeños para tareas específicas de trading"),
    ("researcher", "embeddings y RAG: búsqueda semántica en bases de conocimiento"),
    ("coder",      "function calling avanzado en Groq y OpenAI: agentes complejos"),
    ("coder",      "síntesis de voz TTS de alta calidad sin coste"),
    ("analyst",    "generación de gráficos técnicos profesionales con mplfinance"),
    ("researcher", "integración con TradingView webhooks y alertas"),
    ("coder",      "sistema de pagos con crypto: USDC, Lightning Network, Solana Pay"),
    ("strategist", "cómo monetizar un enjambre de IA: servicios, API, white-label"),
]

# ── Prompts para análisis de mejoras ─────────────────────────────────────────
IMPROVEMENT_ANALYSIS_PROMPT = """Eres una BEE estratega analizando el bot BEEA de Álvaro (@xxvelonxx).

Tu trabajo: identificar las mejoras más impactantes que se pueden implementar AHORA.

El bot tiene:
- Telegram + Discord simultáneos
- Enjambre de BEEs con HiveMind (hasta 160 en paralelo)
- Pool de claves multi-proveedor (Groq, Together, OpenAI, Anthropic, g4f)
- Generación de imágenes (Stable Horde, FAL, DALL-E)
- Trading crypto autónomo
- Búsqueda web real
- Memoria a largo plazo
- Análisis de fotos con visión
- TTS/STT (voz)
- Auto-reparación (Colmena)
- Entrenamiento autónomo (BeeTrainer)

Analiza y responde con exactamente este formato JSON (sin markdown):
{
  "proposals": [
    {
      "id": "mejora_001",
      "titulo": "Título corto",
      "descripcion": "Qué es y por qué vale la pena",
      "impacto": 9,
      "esfuerzo": 3,
      "auto_implementable": true,
      "archivos": ["archivo1.py"],
      "implementacion": "Descripción técnica de cómo hacerlo"
    }
  ]
}

Propón entre 3 y 7 mejoras. impacto y esfuerzo: escala 1-10.
auto_implementable: true si una BEE puede hacerlo sin intervención de Álvaro."""


class ImprovementProposal:
    def __init__(self, data: dict):
        self.id               = data.get("id", f"mejora_{int(time.time())}")
        self.titulo           = data.get("titulo", "Sin título")
        self.descripcion      = data.get("descripcion", "")
        self.impacto          = data.get("impacto", 5)
        self.esfuerzo         = data.get("esfuerzo", 5)
        self.auto_implementable = data.get("auto_implementable", False)
        self.archivos         = data.get("archivos", [])
        self.implementacion   = data.get("implementacion", "")
        self.status           = data.get("status", "pending")
        self.created_at       = data.get("created_at", time.strftime("%Y-%m-%d %H:%M"))
        self.priority_score   = self.impacto - self.esfuerzo * 0.5

    def to_dict(self) -> dict:
        return {
            "id": self.id, "titulo": self.titulo, "descripcion": self.descripcion,
            "impacto": self.impacto, "esfuerzo": self.esfuerzo,
            "auto_implementable": self.auto_implementable,
            "archivos": self.archivos, "implementacion": self.implementacion,
            "status": self.status, "created_at": self.created_at,
            "priority_score": round(self.priority_score, 1),
        }

    def summary(self) -> str:
        auto = "auto" if self.auto_implementable else "manual"
        return (
            f"[{self.id}] {self.titulo}\n"
            f"  Impacto: {self.impacto}/10 | Esfuerzo: {self.esfuerzo}/10 | {auto}\n"
            f"  {self.descripcion[:120]}"
        )


class AutonomousLoop:
    """
    Motor principal del loop autónomo.
    Corre en un thread de background, siempre activo.
    """

    def __init__(self):
        self._running         = False
        self._paused          = False
        self._thread: Optional[threading.Thread] = None
        self._notify_fn: Optional[Callable]      = None
        self._proposals: list[ImprovementProposal] = []
        self._active_sessions: dict[str, dict]   = {}
        self._train_index     = 0
        self._last_improve    = 0.0
        self._lock            = threading.Lock()
        self._stats           = {
            "cycles":         0,
            "trainings":      0,
            "improvements":   0,
            "auto_applied":   0,
            "started_at":     None,
        }
        self._load_proposals()

    # ── Persistencia ─────────────────────────────────────────────────────────

    def _proposals_path(self) -> Path:
        return IMPROVE_DIR / "proposals.json"

    def _save_proposals(self):
        try:
            data = [p.to_dict() for p in self._proposals]
            self._proposals_path().write_text(
                json.dumps(data, ensure_ascii=False, indent=2)
            )
        except Exception as e:
            logger.warning("AutonomousLoop: save proposals error: %s", e)

    def _load_proposals(self):
        try:
            if self._proposals_path().exists():
                data = json.loads(self._proposals_path().read_text())
                self._proposals = [ImprovementProposal(d) for d in data]
        except Exception:
            self._proposals = []

    # ── Notificaciones ────────────────────────────────────────────────────────

    def set_notify_fn(self, fn: Callable):
        self._notify_fn = fn

    def _notify(self, msg: str):
        logger.info("AutonomousLoop: %s", msg[:120])
        if self._notify_fn:
            try:
                self._notify_fn(msg)
            except Exception:
                pass

    # ── Análisis de mejoras ───────────────────────────────────────────────────

    def _run_improvement_analysis(self):
        """
        Una BEE estratega analiza el bot y genera propuestas de mejora.
        Corre en thread background, no bloquea.
        """
        from tools.llm_adapter import generate_for_bees
        import re as _re

        logger.info("AutonomousLoop: iniciando análisis de mejoras...")

        try:
            raw = generate_for_bees([
                {"role": "system", "content": "Eres una BEE estratega y arquitecta de software."},
                {"role": "user",   "content": IMPROVEMENT_ANALYSIS_PROMPT},
            ])

            # Extraer JSON
            json_match = _re.search(r'\{.*\}', raw, _re.DOTALL)
            if not json_match:
                logger.warning("AutonomousLoop: análisis no produjo JSON válido")
                return

            data = json.loads(json_match.group())
            proposals_raw = data.get("proposals", [])

            new_proposals = []
            existing_ids  = {p.id for p in self._proposals}

            for p_data in proposals_raw:
                p = ImprovementProposal(p_data)
                if p.id not in existing_ids:
                    new_proposals.append(p)

            if new_proposals:
                with self._lock:
                    self._proposals.extend(new_proposals)
                    # Ordenar por prioridad
                    self._proposals.sort(key=lambda x: x.priority_score, reverse=True)
                    # Mantener solo las 30 más relevantes
                    self._proposals = self._proposals[:30]

                self._save_proposals()
                self._stats["improvements"] += len(new_proposals)

                # Notificar a Álvaro
                summary = f"Las BEEs encontraron {len(new_proposals)} mejoras nuevas:\n\n"
                for p in sorted(new_proposals, key=lambda x: x.priority_score, reverse=True)[:3]:
                    summary += p.summary() + "\n\n"
                summary += f"Total en cola: {len(self._proposals)} | Usa /mejoras para ver todo"
                self._notify(summary)

                # Auto-implementar las que son seguras y de alto impacto
                self._auto_implement_safe(new_proposals)

        except Exception as e:
            logger.error("AutonomousLoop: improvement analysis error: %s", e)

    def _auto_implement_safe(self, proposals: list[ImprovementProposal]):
        """
        Implementa automáticamente mejoras marcadas como auto_implementable
        con alto impacto y bajo esfuerzo.
        """
        candidates = [
            p for p in proposals
            if p.auto_implementable
            and p.impacto >= 7
            and p.esfuerzo <= 4
            and p.status == "pending"
        ]

        for proposal in candidates[:2]:  # máx 2 auto-implementaciones por ciclo
            try:
                self._implement_proposal(proposal)
            except Exception as e:
                logger.error("AutonomousLoop: auto-implement error [%s]: %s", proposal.id, e)

    def _implement_proposal(self, proposal: ImprovementProposal):
        """
        Una BEE coder implementa la mejora propuesta.
        """
        from swarm.agent_worker import AgentWorker

        logger.info("AutonomousLoop: auto-implementando [%s]: %s", proposal.id, proposal.titulo)

        worker = AgentWorker(agent_id=99, role="coder")
        task = {
            "step": (
                f"Implementa esta mejora en el bot BEEA:\n"
                f"Título: {proposal.titulo}\n"
                f"Descripción: {proposal.descripcion}\n"
                f"Archivos a modificar: {', '.join(proposal.archivos) or 'determina tú cuáles'}\n"
                f"Implementación sugerida: {proposal.implementacion}\n\n"
                "Implementa el cambio de forma conservadora y segura. "
                "Haz backup antes de modificar. Verifica que el código sea correcto."
            ),
            "objective": f"Auto-mejora: {proposal.titulo}",
        }

        result = worker.run_task(task)
        result_text = result.get("result", "")

        proposal.status = "implemented"
        self._stats["auto_applied"] += 1
        self._save_proposals()

        self._notify(
            f"Auto-mejora aplicada:\n"
            f"{proposal.titulo}\n\n"
            f"Resultado: {result_text[:300]}"
        )
        logger.info("AutonomousLoop: auto-implementada [%s]", proposal.id)

    # ── Loop de entrenamiento ─────────────────────────────────────────────────

    def _start_training_session(self):
        """
        Inicia una sesión de entrenamiento en un topic del ciclo automático.
        """
        from swarm.bee_trainer import bee_trainer

        with self._lock:
            idx = self._train_index % len(AUTO_TRAIN_TOPICS)
            self._train_index += 1

        role, topic = AUTO_TRAIN_TOPICS[idx]

        # No iniciar si ya hay una sesión activa para este role/topic
        active = bee_trainer.status()
        for s in active:
            if s["role"] == role and s["topic"] == topic and s["status"] == "running":
                return

        def _notify_train(msg: str):
            self._notify(f"Entrenamiento autónomo: {msg}")

        session_id = bee_trainer.start(role, topic, str(TRAIN_DURATION // 60) + "m", _notify_train)
        self._stats["trainings"] += 1
        logger.info("AutonomousLoop: entrenamiento iniciado — %s / %s [%s]", role, topic, session_id)

    # ── Loop principal ────────────────────────────────────────────────────────

    def _main_loop(self):
        logger.info("AutonomousLoop arrancando...")
        self._stats["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

        # Primera ejecución: pequeño delay para que el bot arranque completamente
        time.sleep(60)

        while self._running:
            if self._paused:
                time.sleep(30)
                continue

            self._stats["cycles"] += 1
            cycle_num = self._stats["cycles"]

            # ── Cada ciclo: iniciar/mantener sesión de entrenamiento ──────────
            try:
                from swarm.bee_trainer import bee_trainer
                active = bee_trainer.status()
                running_trains = [s for s in active if s["status"] == "running"]

                # Llenar slots hasta MAX_PARALLEL — cada BEE libre aprende algo
                slots_libres = MAX_PARALLEL - len(running_trains)
                for _ in range(slots_libres):
                    self._start_training_session()
            except Exception as e:
                logger.warning("AutonomousLoop: training slot error: %s", e)

            # ── Cada hora: análisis de mejoras ────────────────────────────────
            now = time.time()
            if now - self._last_improve >= IMPROVE_INTERVAL:
                self._last_improve = now
                improve_thread = threading.Thread(
                    target=self._run_improvement_analysis,
                    daemon=True,
                    name="auto-improve",
                )
                improve_thread.start()

            # ── Cada 10 ciclos: reporte de actividad a Álvaro ─────────────────
            if cycle_num % 10 == 0:
                self._send_activity_report()

            time.sleep(CHECK_INTERVAL)

    def _send_activity_report(self):
        """Reporte periódico de lo que están haciendo las BEEs."""
        try:
            from swarm.bee_trainer import bee_trainer
            sessions = bee_trainer.status()
            running  = [s for s in sessions if s["status"] == "running"]

            if not running:
                return

            lines = [f"Las BEEs están activas ({len(running)} sesiones de entrenamiento):"]
            for s in running[:3]:
                lines.append(
                    f"  {s['role']} / {s['topic'][:40]}\n"
                    f"  Nivel: {s['skill_level']:.0f}/100 | "
                    f"Iter: {s['iterations']} | Resta: {s['remaining']}"
                )

            pending = [p for p in self._proposals if p.status == "pending"]
            if pending:
                lines.append(f"\n{len(pending)} mejoras en cola — usa /mejoras para verlas")

            self._notify("\n".join(lines))
        except Exception as e:
            logger.warning("AutonomousLoop: activity report error: %s", e)

    # ── API pública ───────────────────────────────────────────────────────────

    def start(self, notify_fn: Optional[Callable] = None):
        if self._running:
            return
        if notify_fn:
            self._notify_fn = notify_fn
        self._running = True
        self._thread  = threading.Thread(
            target=self._main_loop,
            daemon=True,
            name="autonomous-loop",
        )
        self._thread.start()
        logger.info("AutonomousLoop iniciado")

    def pause(self):
        self._paused = True
        logger.info("AutonomousLoop pausado")

    def resume(self):
        self._paused = False
        logger.info("AutonomousLoop reanudado")

    def stop(self):
        self._running = False
        logger.info("AutonomousLoop detenido")

    def get_proposals(self, status: str = None) -> list[ImprovementProposal]:
        with self._lock:
            if status:
                return [p for p in self._proposals if p.status == status]
            return list(self._proposals)

    def approve_proposal(self, proposal_id: str) -> str:
        with self._lock:
            for p in self._proposals:
                if p.id == proposal_id and p.status == "pending":
                    p.status = "approved"
                    self._save_proposals()
                    # Implementar en background
                    t = threading.Thread(
                        target=self._implement_proposal, args=(p,), daemon=True
                    )
                    t.start()
                    return f"Mejora [{proposal_id}] aprobada — implementando ahora"
        return f"Mejora [{proposal_id}] no encontrada o ya procesada"

    def reject_proposal(self, proposal_id: str) -> str:
        with self._lock:
            for p in self._proposals:
                if p.id == proposal_id:
                    p.status = "rejected"
                    self._save_proposals()
                    return f"Mejora [{proposal_id}] rechazada"
        return f"Mejora [{proposal_id}] no encontrada"

    def status_report(self) -> str:
        from swarm.bee_trainer import bee_trainer

        sessions = bee_trainer.status()
        running  = [s for s in sessions if s["status"] == "running"]
        pending  = [p for p in self._proposals if p.status == "pending"]
        applied  = [p for p in self._proposals if p.status == "implemented"]

        lines = [
            f"Loop autónomo: {'ACTIVO' if self._running and not self._paused else 'PAUSADO'}",
            f"Ciclos completados: {self._stats['cycles']}",
            f"Sesiones de entrenamiento lanzadas: {self._stats['trainings']}",
            f"Mejoras auto-aplicadas: {self._stats['auto_applied']}",
            "",
        ]

        if running:
            lines.append(f"Entrenando ahora ({len(running)} sesiones):")
            for s in running:
                lines.append(
                    f"  {s['role']} / {s['topic'][:50]}\n"
                    f"  Nivel: {s['skill_level']:.0f}/100 | Iteraciones: {s['iterations']}"
                )
        else:
            lines.append("Sin sesiones de entrenamiento activas ahora mismo")

        lines.append("")
        lines.append(f"Mejoras en cola: {len(pending)}")
        lines.append(f"Mejoras aplicadas: {len(applied)}")

        if pending:
            lines.append("\nTop mejoras pendientes:")
            for p in pending[:3]:
                lines.append(f"  {p.summary()}")

        return "\n".join(lines)

    def add_custom_training(self, role: str, topic: str, duration_str: str = "30m",
                             notify_fn: Optional[Callable] = None) -> str:
        """Álvaro añade un tema de entrenamiento prioritario."""
        from swarm.bee_trainer import bee_trainer
        session_id = bee_trainer.start(role, topic, duration_str, notify_fn or self._notify_fn)
        self._stats["trainings"] += 1
        return session_id


# Instancia global
autonomous_loop = AutonomousLoop()
