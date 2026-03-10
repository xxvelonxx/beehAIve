"""
BEEA Self-Healer — Sistema de auto-diagnóstico y auto-reparación.

Monitorea los logs en tiempo real, detecta errores, los analiza con IA,
aplica reparaciones automáticas al código y notifica a Álvaro.
"""
import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("beeatrix.healer")

WORKSPACE = Path("/home/runner/workspace")
HEALER_LOG = WORKSPACE / "memory" / "self_healer_log.json"
SEEN_ERRORS_FILE = WORKSPACE / "memory" / "healer_seen_errors.json"

ERROR_PATTERNS = [
    re.compile(r'\[ERROR\] beeatrix.*?: (.+)', re.IGNORECASE),
    re.compile(r'ERROR:root: (.+)', re.IGNORECASE),
    re.compile(r'Traceback \(most recent call last\)', re.IGNORECASE),
    re.compile(r"cannot import name '(.+?)' from '(.+?)'"),
    re.compile(r"AttributeError: '(.+?)' object has no attribute '(.+?)'"),
    re.compile(r"KeyError: '(.+?)'"),
    re.compile(r"TypeError: (.+)"),
    re.compile(r"ModuleNotFoundError: No module named '(.+?)'"),
    re.compile(r"NameError: name '(.+?)' is not defined"),
    re.compile(r"ImportError: (.+)"),
    re.compile(r"'error': '(.+?)'"),
    re.compile(r"Tool signal IMG failed: (.+)"),
    re.compile(r"Tool signal .+ error: (.+)"),
]

FILE_ERROR_PATTERNS = [
    (re.compile(r"File \"(/home/runner/workspace/[^\"]+\.py)\", line (\d+)"), "traceback"),
    (re.compile(r"Error en ([a-z_]+): "), "function_error"),
]

SAFE_TO_AUTOFIX = [
    "cannot import name",
    "has no attribute",
    "KeyError",
    "NameError",
    "'error': 'zip_path missing'",
    "Tool signal",
]

MAX_FILE_SIZE_TO_FIX = 50_000
SCAN_INTERVAL = 300
COOLDOWN_SAME_ERROR = 1800


class SelfHealer:
    def __init__(self):
        self._notify_fn = None
        self._running = False
        self._last_log_pos: dict = {}
        self._seen_errors: dict = {}
        self._load_seen_errors()

    def set_notify_fn(self, fn):
        self._notify_fn = fn

    def _load_seen_errors(self):
        try:
            if SEEN_ERRORS_FILE.exists():
                self._seen_errors = json.loads(SEEN_ERRORS_FILE.read_text())
        except Exception:
            self._seen_errors = {}

    def _save_seen_errors(self):
        try:
            SEEN_ERRORS_FILE.write_text(json.dumps(self._seen_errors, indent=2))
        except Exception:
            pass

    def _log_repair(self, error_summary: str, file_fixed: str, patch_summary: str, success: bool):
        try:
            log = []
            if HEALER_LOG.exists():
                log = json.loads(HEALER_LOG.read_text())
            log.append({
                "timestamp": datetime.now().isoformat(),
                "error": error_summary[:200],
                "file": file_fixed,
                "patch": patch_summary[:300],
                "success": success,
            })
            log = log[-100:]
            HEALER_LOG.write_text(json.dumps(log, indent=2))
        except Exception:
            pass

    async def _notify(self, text: str):
        if self._notify_fn:
            try:
                await self._notify_fn(f"🔧 AUTO-HEALER\n\n{text}")
            except Exception as e:
                logger.warning("Healer notify failed: %s", e)

    def _find_log_files(self) -> list:
        log_dir = Path("/tmp/logs")
        if not log_dir.exists():
            return []
        files = sorted(log_dir.glob("Start_application_*.log"), key=lambda f: f.stat().st_mtime, reverse=True)
        return [str(f) for f in files[:2]]

    def _read_new_log_lines(self, log_file: str) -> list[str]:
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                pos = self._last_log_pos.get(log_file, 0)
                f.seek(pos)
                lines = f.readlines()
                self._last_log_pos[log_file] = f.tell()
            return lines
        except Exception:
            return []

    def _extract_errors_from_lines(self, lines: list[str]) -> list[dict]:
        errors = []
        context_buffer = []
        in_traceback = False
        traceback_lines = []
        file_ref = None

        for line in lines:
            context_buffer.append(line)
            if len(context_buffer) > 30:
                context_buffer.pop(0)

            if "Traceback (most recent call last)" in line:
                in_traceback = True
                traceback_lines = [line]
                continue

            if in_traceback:
                traceback_lines.append(line)
                file_match = re.search(r'File "(/home/runner/workspace/[^"]+\.py)", line (\d+)', line)
                if file_match:
                    file_ref = {"path": file_match.group(1), "line": int(file_match.group(2))}
                if re.match(r'\w+Error:', line.strip()) or re.match(r'\w+Exception:', line.strip()):
                    error_text = line.strip()
                    errors.append({
                        "type": "traceback",
                        "text": error_text,
                        "context": "".join(traceback_lines[-15:]),
                        "file": file_ref,
                    })
                    in_traceback = False
                    traceback_lines = []
                    file_ref = None
                continue

            for pattern in ERROR_PATTERNS:
                m = pattern.search(line)
                if m and "[ERROR]" in line or "ERROR" in line:
                    err_text = m.group(0)
                    file_ref_inline = None
                    errors.append({
                        "type": "inline_error",
                        "text": err_text[:300],
                        "context": "".join(context_buffer[-10:]),
                        "file": file_ref_inline,
                    })
                    break

        return errors

    def _is_duplicate_error(self, error_key: str) -> bool:
        now = time.time()
        last_seen = self._seen_errors.get(error_key, 0)
        if now - last_seen < COOLDOWN_SAME_ERROR:
            return True
        self._seen_errors[error_key] = now
        self._save_seen_errors()
        return False

    def _is_safe_to_autofix(self, error_text: str) -> bool:
        return any(pattern in error_text for pattern in SAFE_TO_AUTOFIX)

    def _get_file_content(self, file_path: str) -> str | None:
        try:
            p = Path(file_path)
            if not p.exists() or not p.suffix == ".py":
                return None
            size = p.stat().st_size
            if size > MAX_FILE_SIZE_TO_FIX:
                content = p.read_text(encoding="utf-8", errors="replace")
                return content[:MAX_FILE_SIZE_TO_FIX]
            return p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None

    def _generate_fix(self, error: dict) -> dict | None:
        """Llama a GPT-4o para analizar el error y proponer una reparación."""
        try:
            import openai
            client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

            file_content = ""
            file_path = ""
            if error.get("file"):
                file_path = error["file"]["path"]
                file_content = self._get_file_content(file_path) or ""

            prompt = (
                f"You are a senior Python engineer analyzing a bug in a Telegram bot named BEEA.\n\n"
                f"ERROR:\n{error['text']}\n\n"
                f"CONTEXT (log lines around the error):\n{error['context']}\n\n"
            )
            if file_content:
                prompt += f"FILE WITH ERROR ({file_path}):\n```python\n{file_content}\n```\n\n"

            prompt += (
                "Task:\n"
                "1. Identify the EXACT cause of this error in 1-2 sentences.\n"
                "2. If you can fix it with a small, safe code change:\n"
                "   - Provide the EXACT old_string (the broken code) and new_string (the fix)\n"
                "   - Make the change minimal — only fix what's broken, nothing else\n"
                "   - The fix must be a simple string replacement in the file\n"
                "3. If the fix is too complex or risky, say 'NO_AUTOFIX' and explain why.\n\n"
                "Respond in this exact JSON format:\n"
                '{"can_fix": true/false, "cause": "...", "file": "full/path.py", '
                '"old_string": "exact broken code", "new_string": "fixed code", '
                '"patch_summary": "what was changed in one line"}\n\n'
                'If cannot fix, respond: {"can_fix": false, "cause": "...", "patch_summary": "needs manual fix"}'
            )

            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.1,
            )

            raw = resp.choices[0].message.content.strip()
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            return json.loads(raw)

        except Exception as e:
            logger.error("Healer generate_fix error: %s", e)
            return None

    def _apply_fix(self, fix: dict) -> bool:
        """Aplica el fix directamente al archivo."""
        try:
            file_path = fix.get("file", "")
            old_string = fix.get("old_string", "")
            new_string = fix.get("new_string", "")

            if not file_path or not old_string or old_string == new_string:
                return False

            p = Path(file_path)
            if not p.exists() or not p.suffix == ".py":
                return False

            content = p.read_text(encoding="utf-8")
            if old_string not in content:
                logger.warning("Healer: old_string not found in %s", file_path)
                return False

            new_content = content.replace(old_string, new_string, 1)
            p.write_text(new_content, encoding="utf-8")
            logger.info("Healer: applied fix to %s", file_path)
            return True

        except Exception as e:
            logger.error("Healer apply_fix error: %s", e)
            return False

    async def _process_error(self, error: dict):
        error_key = error["text"][:100]

        if self._is_duplicate_error(error_key):
            return

        logger.info("Healer: analyzing error: %s", error_key[:80])

        fix = await asyncio.get_event_loop().run_in_executor(None, self._generate_fix, error)

        if not fix:
            await self._notify(
                f"Detecté un error pero no pude analizarlo:\n\n`{error['text'][:300]}`"
            )
            return

        can_fix = fix.get("can_fix", False)
        cause = fix.get("cause", "")
        patch_summary = fix.get("patch_summary", "")
        file_fixed = fix.get("file", "")

        if can_fix and self._is_safe_to_autofix(error["text"]):
            success = self._apply_fix(fix)
            self._log_repair(error["text"], file_fixed, patch_summary, success)

            if success:
                rel_path = file_fixed.replace("/home/runner/workspace/", "")
                await self._notify(
                    f"Encontré y reparé un bug automáticamente.\n\n"
                    f"Error: {error['text'][:150]}\n\n"
                    f"Causa: {cause}\n\n"
                    f"Reparación en `{rel_path}`:\n{patch_summary}\n\n"
                    f"El fix ya está aplicado. Si quieres que reinicie el bot para que surta efecto, dímelo."
                )
            else:
                await self._notify(
                    f"Detecté un bug y sé cómo arreglarlo, pero no pude aplicar el fix automáticamente.\n\n"
                    f"Error: {error['text'][:150]}\n\n"
                    f"Causa: {cause}\n\n"
                    f"Fix propuesto en `{file_fixed.replace('/home/runner/workspace/', '')}`:\n{patch_summary}"
                )
        else:
            await self._notify(
                f"Detecté un error que requiere revisión manual:\n\n"
                f"Error: {error['text'][:200]}\n\n"
                f"Causa: {cause}\n\n"
                f"Recomendación: {patch_summary}"
            )

    async def run_scan(self):
        """Un ciclo de escaneo: lee logs nuevos y procesa errores encontrados."""
        log_files = self._find_log_files()
        all_errors = []

        for log_file in log_files:
            lines = self._read_new_log_lines(log_file)
            if lines:
                errors = self._extract_errors_from_lines(lines)
                all_errors.extend(errors)

        for error in all_errors:
            await self._process_error(error)

    async def background_loop(self):
        """Loop principal del auto-healer. Escanea cada SCAN_INTERVAL segundos."""
        self._running = True
        await asyncio.sleep(60)
        logger.info("SelfHealer: background monitor activo (scan cada %ds)", SCAN_INTERVAL)

        while self._running:
            try:
                await self.run_scan()
            except Exception as e:
                logger.error("SelfHealer scan error: %s", e)
            await asyncio.sleep(SCAN_INTERVAL)

    def stop(self):
        self._running = False

    def get_repair_history(self, limit: int = 10) -> list:
        try:
            if HEALER_LOG.exists():
                log = json.loads(HEALER_LOG.read_text())
                return log[-limit:]
        except Exception:
            pass
        return []


self_healer = SelfHealer()
