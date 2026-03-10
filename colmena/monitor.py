"""
BEEA Colmena Monitor — Sistema de vigilancia distribuida con auto-reparación real.

Las bees no solo detectan problemas. Los ARREGLAN:
  - Leen el archivo roto
  - Le piden al LLM que diagnostique y genere un fix
  - Escriben el fix al disco
  - Recargan el módulo
  - Reportan el resultado

Arquitectura:
  - N bees corren en paralelo como asyncio.Task
  - Cada bee registra su heartbeat cada ciclo
  - Cada bee lee los heartbeats de TODAS las demás
  - Si una bee no actualizó en DEAD_THRESHOLD segundos → está muerta → la resucitan
  - Cada bee corre el chequeo completo del sistema
  - Issues deduplicados con cooldown de 5 minutos
"""

import asyncio
import importlib
import importlib.util
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("beeatrix.colmena")

DEAD_THRESHOLD = 90
SCAN_INTERVAL_BASE = 60
MAX_BEES = 3
REPORT_COOLDOWN = 300
ROOT = Path(__file__).resolve().parent.parent


class ColmenaMonitor:

    def __init__(self):
        self._bees: dict[int, asyncio.Task] = {}
        self._heartbeats: dict[int, float] = {}
        self._reported: dict[str, float] = {}
        self._notify_fn: Optional[Callable] = None
        self._running = False
        self._num_bees = MAX_BEES
        self._repair_history: list[dict] = []

    def set_notify(self, fn: Callable):
        self._notify_fn = fn

    async def _notify(self, message: str, issue_key: str = None):
        now = time.time()
        if issue_key:
            last = self._reported.get(issue_key, 0)
            if now - last < REPORT_COOLDOWN:
                return
            self._reported[issue_key] = now

        logger.warning("Colmena alerta: %s", message[:120])
        if self._notify_fn:
            try:
                await self._notify_fn(f"🐝 Colmena: {message}")
            except Exception as e:
                logger.error("Error enviando notificación colmena: %s", e)

    # ── Chequeos del sistema ───────────────────────────────────────────────────

    async def _check_image_pipeline(self) -> list[str]:
        issues = []
        for mod in ("tools.image_providers", "tools.image_gen", "tools.bypass_engine", "tools.unblock_bee"):
            try:
                importlib.import_module(mod)
            except Exception as e:
                issues.append(f"{mod} importación rota: {e}")
        return issues

    async def _check_llm(self) -> list[str]:
        issues = []
        try:
            from tools.llm_adapter import llm_adapter
            if not llm_adapter:
                issues.append("llm_adapter: None")
        except Exception as e:
            issues.append(f"tools.llm_adapter importación rota: {e}")
        try:
            from core.ai_chat import chat
        except Exception as e:
            issues.append(f"core.ai_chat importación rota: {e}")
        try:
            from personality_profile import build_system_prompt
            sp = build_system_prompt()
            if len(sp) < 1000:
                issues.append(f"system_prompt muy corto: {len(sp)} chars")
        except Exception as e:
            issues.append(f"personality_profile rota: {e}")
        return issues

    async def _check_crypto(self) -> list[str]:
        issues = []
        for mod in ("crypto.price_feed", "crypto.wallet_manager", "crypto.analysis"):
            try:
                importlib.import_module(mod)
            except Exception as e:
                issues.append(f"{mod} rota: {e}")
        return issues

    async def _check_scheduler(self) -> list[str]:
        issues = []
        try:
            from tools.scheduler import bee_scheduler
            if not bee_scheduler._running:
                issues.append("scheduler: loop no está corriendo")
        except Exception as e:
            issues.append(f"tools.scheduler importación rota: {e}")
        tasks_file = ROOT / "memory" / "scheduled_tasks.json"
        if tasks_file.exists():
            try:
                import json
                json.loads(tasks_file.read_text())
            except Exception as e:
                issues.append(f"scheduled_tasks.json corrupto: {e}")
        return issues

    async def _check_memory(self) -> list[str]:
        issues = []
        try:
            from memory.long_memory import long_memory
            stats = long_memory.stats()
            if stats.get("total", 0) > 480:
                issues.append(f"long_memory casi llena: {stats['total']}/500 — considera limpiar")
        except Exception as e:
            issues.append(f"memory.long_memory rota: {e}")
        return issues

    async def _check_network(self) -> list[str]:
        issues = []
        for mod in ("tools.websearch", "tools.url_summarizer", "tools.code_sandbox"):
            try:
                importlib.import_module(mod)
            except Exception as e:
                issues.append(f"{mod} rota: {e}")
        return issues

    async def _check_tts(self) -> list[str]:
        issues = []
        try:
            from tools.tts import text_to_speech
        except Exception as e:
            issues.append(f"tools.tts rota: {e}")
        return issues

    async def _check_all_modules(self) -> list[str]:
        """
        Escanea TODOS los archivos .py del proyecto buscando errores de importación.
        No necesita lista hardcoded — lo descubre solo.
        """
        import subprocess, sys
        issues = []
        skip_dirs = {"__pycache__", ".git", ".pythonlibs", "node_modules", "attached_assets"}

        py_files = []
        for path in ROOT.rglob("*.py"):
            if any(d in path.parts for d in skip_dirs):
                continue
            # Convertir a nombre de módulo
            try:
                rel = path.relative_to(ROOT)
                parts = list(rel.parts)
                if parts[-1] == "__init__.py":
                    parts = parts[:-1]
                else:
                    parts[-1] = parts[-1][:-3]  # quitar .py
                mod = ".".join(parts)
                py_files.append((mod, str(rel)))
            except Exception:
                continue

        for mod, rel_path in py_files:
            try:
                spec = importlib.util.spec_from_file_location(mod, ROOT / rel_path)
                if spec is None:
                    continue
                # Solo verificar sintaxis con compile, no ejecutar
                source = (ROOT / rel_path).read_text(encoding="utf-8", errors="ignore")
                compile(source, rel_path, "exec")
            except SyntaxError as e:
                issues.append(f"SyntaxError en {rel_path} línea {e.lineno}: {e.msg}")
            except Exception:
                pass

        return issues

    async def _scan_logs_for_errors(self) -> list[str]:
        """
        Lee los logs recientes buscando ERROR/CRITICAL/Traceback.
        Extrae el contexto del error para que las BEEs puedan reparar sin guía.
        """
        issues = []
        try:
            from swarm.bee_tools import _LOG_LINES
            recent = list(_LOG_LINES)[-200:]  # últimas 200 líneas de log
        except Exception:
            return issues

        error_blocks: list[str] = []
        current_block = []
        in_traceback = False

        for line in recent:
            if "Traceback" in line or "[ERROR]" in line or "[CRITICAL]" in line:
                in_traceback = True
                current_block = [line]
            elif in_traceback:
                current_block.append(line)
                if len(current_block) >= 8:
                    error_blocks.append("\n".join(current_block))
                    current_block = []
                    in_traceback = False
            else:
                if current_block:
                    error_blocks.append("\n".join(current_block))
                    current_block = []
                    in_traceback = False

        # Deduplicar por las primeras 60 chars
        seen = set()
        for block in error_blocks[-10:]:  # máx 10 errores recientes
            key = block[:60]
            if key not in seen:
                seen.add(key)
                issues.append(f"LOG_ERROR: {block[:400]}")

        return issues

    async def _run_full_check(self) -> list[str]:
        all_issues = []
        checks = [
            self._check_image_pipeline(),
            self._check_llm(),
            self._check_crypto(),
            self._check_scheduler(),
            self._check_memory(),
            self._check_network(),
            self._check_tts(),
            self._check_all_modules(),   # ← auto-descubre TODOS los archivos rotos
            self._scan_logs_for_errors(), # ← lee logs en tiempo real
        ]
        results = await asyncio.gather(*checks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                all_issues.extend(r)
            elif isinstance(r, Exception):
                all_issues.append(f"Check falló: {r}")
        return all_issues

    # ── Auto-reparación real ───────────────────────────────────────────────────

    def _extract_file_from_error(self, issue: str) -> list[str]:
        """
        Extrae todos los archivos Python relevantes mencionados en el error.
        Trabaja con SyntaxError, Traceback, ImportError, etc. — sin guía manual.
        """
        candidates = []

        # Archivos en tracebacks: "File \"path/to/file.py\", line N"
        for m in re.finditer(r'File ["\']([^"\']+\.py)["\']', issue):
            p = m.group(1)
            if ROOT.name in p or not p.startswith("/"):
                rel = p.split(ROOT.name + "/")[-1] if ROOT.name in p else p
                candidates.append(rel)

        # SyntaxError: "SyntaxError en path/file.py"
        for m in re.finditer(r'(?:SyntaxError|error) en ([^\s:]+\.py)', issue):
            candidates.append(m.group(1))

        # ModuleNotFoundError: módulo local
        m = re.search(r"no module named '([^']+)'", issue.lower())
        if m:
            mod = m.group(1).split(".")[0]
            local_modules = {
                "crypto", "tools", "memory", "colmena", "core", "swarm",
                "conversation_mode", "personality_profile", "orchestration",
                "workspace", "discord_bot", "telegram_bot",
            }
            if mod in local_modules:
                candidates.append(mod.replace(".", "/") + ".py")

        # Filtrar: solo archivos que existen en el proyecto
        existing = []
        for c in candidates:
            full = ROOT / c
            if full.exists():
                existing.append(c)

        # Deduplicar preservando orden
        return list(dict.fromkeys(existing))

    async def _try_repair(self, issue: str) -> str:
        """
        Auto-reparación completamente autónoma:
        1. Extrae el/los archivos rotos del error (sin input manual)
        2. Si es paquete externo → pip install
        3. Si es archivo local → lanza 3 BEEs de reparación en paralelo
        4. Primera BEE que genere un fix exitoso gana
        """
        low = issue.lower()
        from swarm.bee_tools import execute_tool

        # ── Fix rápido: paquete pip externo ──────────────────────────────────
        m_pkg = re.search(r"no module named '([^']+)'", low)
        if m_pkg:
            pkg = m_pkg.group(1).split(".")[0]
            local_modules = {
                "crypto", "tools", "memory", "colmena", "core", "swarm",
                "conversation_mode", "personality_profile", "orchestration",
                "workspace", "discord_bot", "telegram_bot",
            }
            if pkg not in local_modules:
                logger.info("Colmena auto-repair: pip install %s", pkg)
                result = execute_tool("install_package", {"package": pkg})
                return f"pip install {pkg}: {result}"

        # ── Fix rápido: scheduler muerto ─────────────────────────────────────
        if "scheduler" in low and "no está corriendo" in low:
            try:
                from tools.scheduler import bee_scheduler
                if not bee_scheduler._running:
                    asyncio.create_task(bee_scheduler.run_loop())
                    return "scheduler reiniciado"
            except Exception as e:
                return f"repair scheduler falló: {e}"

        # ── Auto-descubrir archivos rotos ─────────────────────────────────────
        broken_files = self._extract_file_from_error(issue)

        if not broken_files:
            # No encontró archivo → no_action
            return "no_action"

        # ── Reparación multi-BEE en paralelo ─────────────────────────────────
        # Lanza 3 BEEs simultáneas sobre el mismo error (distintos enfoques)
        # La primera que produce un fix válido gana
        results = []
        loop = asyncio.get_event_loop()

        async def repair_bee(bee_num: int, file_path: str) -> str:
            return await loop.run_in_executor(
                None,
                lambda: self._sync_llm_repair(issue, file_path, approach=bee_num),
            )

        tasks = []
        for i, fp in enumerate(broken_files[:3]):
            for approach in range(min(3, 3 - i)):
                tasks.append(repair_bee(approach, fp))

        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        successes = [r for r in task_results if isinstance(r, str) and "error" not in r.lower()[:30]]

        if successes:
            return successes[0]
        return f"repair intentado en {broken_files} — sin fix exitoso"

    def _sync_llm_repair(self, issue: str, file_path: str, approach: int = 0) -> str:
        """
        Reparación síncrona — corre en thread pool.
        approach 0: fix mínimo conservador
        approach 1: reescritura completa
        approach 2: análisis profundo + fix
        """
        from swarm.bee_tools import execute_tool
        from tools.llm_adapter import generate_for_bees

        full_path = ROOT / file_path
        if not full_path.exists():
            return f"archivo no encontrado: {file_path}"

        try:
            file_content = full_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            return f"no pude leer {file_path}: {e}"

        approaches = [
            "Genera el fix MÍNIMO necesario para resolver el error. Preserva el código existente.",
            "Reescribe el archivo completo corregido, limpio y funcional.",
            "Analiza el error en profundidad y genera el fix más robusto posible.",
        ]
        instruction = approaches[approach % len(approaches)]

        prompt = (
            f"Archivo: {file_path}\n"
            f"Error detectado:\n{issue[:600]}\n\n"
            f"Contenido actual ({len(file_content)} chars):\n{file_content[:3000]}\n\n"
            f"{instruction}\n\n"
            "Responde SOLO con:\n"
            "- PATCH|<old_string>|<new_string>  (si es un fix pequeño)\n"
            "- O el archivo completo corregido (si hay que reescribir)\n"
            "Sin explicaciones, sin markdown, sin bloques de código."
        )

        try:
            fix_text = generate_for_bees([
                {"role": "system", "content": "Eres un debugger Python experto. Corriges errores sin palabrería."},
                {"role": "user",   "content": prompt},
            ])
        except Exception as e:
            return f"LLM repair error: {e}"

        if not fix_text or len(fix_text) < 10:
            return "LLM no generó fix"

        # Aplicar el fix
        if fix_text.strip().startswith("PATCH|"):
            parts = fix_text.strip().split("|", 2)
            if len(parts) == 3:
                result = execute_tool("patch_file", {
                    "path": file_path, "old_string": parts[1], "new_string": parts[2],
                })
            else:
                return "PATCH malformado"
        else:
            result = execute_tool("write_file", {"path": file_path, "content": fix_text})

        # Verificar que el fix compiló correctamente
        try:
            new_content = full_path.read_text(encoding="utf-8", errors="ignore")
            compile(new_content, file_path, "exec")
            verify = "sintaxis OK"
        except SyntaxError as e:
            verify = f"aún tiene SyntaxError: {e}"

        record = {
            "ts": datetime.utcnow().isoformat(),
            "issue": issue[:200],
            "file": file_path,
            "approach": approach,
            "write": str(result)[:100],
            "verify": verify,
        }
        self._repair_history.append(record)
        if len(self._repair_history) > 50:
            self._repair_history = self._repair_history[-50:]

        logger.info("Colmena repair [approach %d]: %s → %s | %s", approach, file_path, result, verify)

        if "aún tiene" in verify:
            return f"fix parcial en {file_path}: {verify}"
        return f"fix aplicado en {file_path}: {verify}"

    async def _llm_repair(self, issue: str, module_name: str) -> str:
        """
        Usa el LLM para diagnosticar y reparar un módulo roto.
        Lee el archivo, pide diagnóstico y fix, aplica el patch.
        """
        from swarm.bee_tools import execute_tool
        import openai, os as _os

        api_key = _os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            return "sin OPENAI_API_KEY para LLM repair"

        # Convertir nombre de módulo a ruta de archivo
        file_path = module_name.replace(".", "/") + ".py"
        full_path = ROOT / file_path
        if not full_path.exists():
            return f"archivo no encontrado: {file_path}"

        # Leer el archivo roto
        file_content = execute_tool("read_file", {"path": file_path, "lines": 300})

        # Pedir al LLM que diagnostique y genere un fix
        try:
            client = openai.OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Eres un debugger experto de Python. Se te da un archivo roto y el error. "
                            "Devuelve SOLO el archivo completo corregido, sin explicaciones, sin markdown. "
                            "Si el fix es pequeño, puedes devolver: PATCH|<old_string>|<new_string> "
                            "donde old_string y new_string son las cadenas exactas a reemplazar."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Archivo: {file_path}\n"
                            f"Error: {issue}\n\n"
                            f"Contenido actual:\n{file_content}\n\n"
                            "Genera el fix."
                        ),
                    },
                ],
                max_tokens=3000,
                temperature=0,
            )
        except Exception as e:
            return f"LLM repair error: {e}"

        fix_text = resp.choices[0].message.content.strip()

        # Aplicar el fix
        if fix_text.startswith("PATCH|"):
            parts = fix_text.split("|", 2)
            if len(parts) == 3:
                result = execute_tool("patch_file", {
                    "path": file_path,
                    "old_string": parts[1],
                    "new_string": parts[2],
                })
            else:
                result = "PATCH malformado"
        elif len(fix_text) > 50:
            result = execute_tool("write_file", {"path": file_path, "content": fix_text})
        else:
            return f"LLM no pudo generar fix: {fix_text[:200]}"

        # Recargar módulo
        reload_result = execute_tool("reload_module", {"module_name": module_name})

        record = {
            "ts": datetime.utcnow().isoformat(),
            "issue": issue[:200],
            "module": module_name,
            "write": result,
            "reload": reload_result,
        }
        self._repair_history.append(record)
        if len(self._repair_history) > 50:
            self._repair_history = self._repair_history[-50:]

        logger.info("Colmena LLM repair: %s → %s | %s", module_name, result, reload_result)
        return f"LLM fix aplicado en {file_path}: {result} | reload: {reload_result}"

    # ── Ciclo de vida ──────────────────────────────────────────────────────────

    async def _bee_loop(self, bee_id: int):
        offset = bee_id * (SCAN_INTERVAL_BASE // MAX_BEES)
        await asyncio.sleep(offset)

        while self._running:
            cycle_start = time.time()
            self._heartbeats[bee_id] = cycle_start

            # 1. Vigilar a las otras bees
            for other_id, last_beat in list(self._heartbeats.items()):
                if other_id == bee_id:
                    continue
                if time.time() - last_beat > DEAD_THRESHOLD:
                    logger.warning("Bee-%d detectó que Bee-%d está muerta — resucitando", bee_id, other_id)
                    await self._notify(
                        f"Bee-{other_id} dejó de responder. Bee-{bee_id} la está resucitando.",
                        issue_key=f"dead_bee_{other_id}",
                    )
                    self._heartbeats[other_id] = time.time()
                    self._launch_bee(other_id)

            # 2. Chequeo completo
            try:
                issues = await self._run_full_check()
            except Exception as e:
                logger.error("Bee-%d: error en full_check: %s", bee_id, e)
                issues = [f"Error en chequeo: {e}"]

            # 3. Reportar y reparar
            for issue in issues:
                issue_key = issue[:80]
                await self._notify(f"[Bee-{bee_id}] {issue}", issue_key=issue_key)
                try:
                    repair_result = await self._try_repair(issue)
                    if repair_result and repair_result != "no_action":
                        await self._notify(
                            f"[Bee-{bee_id}] Reparado: {repair_result[:200]}",
                            issue_key=f"repaired_{issue_key}",
                        )
                except Exception as repair_err:
                    logger.error("Bee-%d: repair falló '%s': %s", bee_id, issue[:60], repair_err)

            elapsed = time.time() - cycle_start
            await asyncio.sleep(max(5, SCAN_INTERVAL_BASE - elapsed))

    def _launch_bee(self, bee_id: int):
        old = self._bees.get(bee_id)
        if old and not old.done():
            old.cancel()
        task = asyncio.create_task(
            self._bee_loop_safe(bee_id),
            name=f"colmena-bee-{bee_id}",
        )
        self._bees[bee_id] = task
        self._heartbeats[bee_id] = time.time()
        logger.info("Colmena: Bee-%d lanzada", bee_id)

    async def _bee_loop_safe(self, bee_id: int):
        while self._running:
            try:
                await self._bee_loop(bee_id)
            except asyncio.CancelledError:
                logger.info("Bee-%d cancelada correctamente", bee_id)
                return
            except Exception as e:
                logger.error("Bee-%d crash: %s — resucitando en 15s", bee_id, e)
                self._heartbeats[bee_id] = 0
                await asyncio.sleep(15)

    async def start(self, num_bees: int = MAX_BEES, notify_fn: Callable = None):
        if self._running:
            return
        self._running = True
        if notify_fn:
            self._notify_fn = notify_fn
        self._num_bees = num_bees
        for i in range(num_bees):
            self._launch_bee(i)
        logger.info("Colmena iniciada con %d bees — auto-reparación activa", num_bees)

    async def stop(self):
        self._running = False
        for task in self._bees.values():
            task.cancel()
        self._bees.clear()
        logger.info("Colmena detenida")

    def status(self) -> dict:
        now = time.time()
        bees_status = {}
        for bee_id, last_beat in self._heartbeats.items():
            age = now - last_beat
            bees_status[f"Bee-{bee_id}"] = {
                "viva": age < DEAD_THRESHOLD,
                "ultimo_latido": f"hace {int(age)}s",
                "task_done": self._bees[bee_id].done() if bee_id in self._bees else True,
            }
        return {
            "bees": bees_status,
            "issues_reportados": len(self._reported),
            "repairs_realizados": len(self._repair_history),
            "running": self._running,
            "ultimo_repair": self._repair_history[-1] if self._repair_history else None,
        }


colmena = ColmenaMonitor()
