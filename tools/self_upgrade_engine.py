from __future__ import annotations

import ast
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from core.logger import logger
from core.state import state_manager


@dataclass
class UpgradePlan:
    request: str
    capability_name: str
    summary: str
    files_to_create: List[str]
    files_to_modify: List[str]
    authorized: bool
    created_at: str


class SelfUpgradeEngine:
    PLAN_KEY = "self_upgrade_last_plan"

    def _infer_capability_name(self, request: str) -> str:
        text = request.lower()
        if "imagen" in text or "image" in text:
            return "image_generation"
        if "archivo" in text or "file" in text:
            return "file_processing"
        if "memoria" in text or "memory" in text:
            return "memory_store"
        if "voice" in text or "voz" in text or "audio" in text:
            return "voice_handler"
        if "schedule" in text or "cron" in text or "tarea programada" in text:
            return "scheduler"
        slug = text.strip().replace(" ", "_")[:30]
        return slug or "custom_capability"

    def build_plan(self, request: str, authorized: bool = False) -> Dict:
        from tools.llm_adapter import llm_adapter

        capability = self._infer_capability_name(request)

        prompt = (
            f"You are planning a self-upgrade for a Python Telegram bot called Beeatrix.\n"
            f"Upgrade request: {request}\n"
            f"Inferred capability name: {capability}\n\n"
            f"Briefly describe (2-3 sentences) what new files to create and what existing files "
            f"to modify. Be specific about file paths and what each file should do."
        )
        summary = llm_adapter.generate_text(prompt)

        files_to_create = [f"tools/{capability}.py"]
        files_to_modify = [
            "tools/capabilities.py",
            "conversation_mode.py",
            "orchestration/orchestrator.py",
        ]

        plan = UpgradePlan(
            request=request,
            capability_name=capability,
            summary=summary,
            files_to_create=files_to_create,
            files_to_modify=files_to_modify,
            authorized=authorized,
            created_at=datetime.utcnow().isoformat(),
        )
        state_manager.set_system_memory(self.PLAN_KEY, asdict(plan))
        logger.info("Self-upgrade plan built: %s", capability)
        return asdict(plan)

    def get_last_plan(self) -> Optional[Dict]:
        return state_manager.get_system_memory(self.PLAN_KEY)

    def apply_plan(self, repo_root: str = ".", authorized: bool = False) -> Dict:
        from tools.llm_adapter import llm_adapter

        plan = self.get_last_plan()
        if not plan:
            return {"error": "no_upgrade_plan_found"}
        if not authorized and not plan.get("authorized"):
            return {"error": "upgrade_requires_authorization"}

        root = Path(repo_root)
        written: List[str] = []
        errors: List[str] = []

        for rel_path in plan.get("files_to_create", []):
            dest = root / rel_path
            if dest.exists():
                logger.info("Skipping existing file: %s", rel_path)
                continue

            prompt = (
                f"Write a complete, production-ready Python module for the following capability.\n"
                f"Capability name: {plan['capability_name']}\n"
                f"File path: {rel_path}\n"
                f"Summary: {plan['summary']}\n"
                f"Original request: {plan['request']}\n\n"
                f"Return ONLY the Python code, no markdown fences, no explanations."
            )
            try:
                code = llm_adapter.generate_text(prompt)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(code, encoding="utf-8")
                written.append(rel_path)
                logger.info("Created: %s", rel_path)
            except Exception as e:
                errors.append(f"{rel_path}: {e}")
                logger.error("Failed to create %s: %s", rel_path, e)

        for rel_path in plan.get("files_to_modify", []):
            dest = root / rel_path
            if not dest.exists():
                continue
            existing = dest.read_text(encoding="utf-8")

            prompt = (
                f"You are upgrading a Python file for a Telegram bot called Beeatrix.\n"
                f"File: {rel_path}\n"
                f"New capability to integrate: {plan['capability_name']}\n"
                f"Summary of upgrade: {plan['summary']}\n\n"
                f"Existing file content:\n```python\n{existing[:3000]}\n```\n\n"
                f"Return the COMPLETE updated file with the new capability integrated. "
                f"Return ONLY the Python code, no markdown fences, no explanations."
            )
            try:
                new_code = llm_adapter.generate_text(prompt)
                ast.parse(new_code)
                backup = dest.with_suffix(".py.bak")
                backup.write_text(existing, encoding="utf-8")
                dest.write_text(new_code, encoding="utf-8")
                written.append(rel_path)
                logger.info("Modified: %s", rel_path)
            except SyntaxError as e:
                errors.append(f"{rel_path}: syntax error in generated code — {e}")
                logger.error("Syntax error in generated code for %s: %s", rel_path, e)
            except Exception as e:
                errors.append(f"{rel_path}: {e}")
                logger.error("Failed to modify %s: %s", rel_path, e)

        return {
            "status": "applied" if not errors else "partial",
            "capability_name": plan["capability_name"],
            "files_written": written,
            "errors": errors,
        }


self_upgrade_engine = SelfUpgradeEngine()
