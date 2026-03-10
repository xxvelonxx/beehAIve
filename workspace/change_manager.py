import difflib
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

class ChangeManager:
    def __init__(self):
        self.locks: Dict[str, str] = {}
        self.change_dir = Path("workspace/.changes")
        self.change_dir.mkdir(parents=True, exist_ok=True)

    def acquire_lock(self, file_path: str, agent_id: str):
        owner = self.locks.get(file_path)
        if owner and owner != agent_id:
            return False, owner
        self.locks[file_path] = agent_id
        return True, agent_id

    def release_lock(self, file_path: str, agent_id: str):
        owner = self.locks.get(file_path)
        if owner == agent_id:
            del self.locks[file_path]
            return True
        return False

    def backup(self, file_path: str) -> Optional[str]:
        src = Path(file_path)
        if src.exists():
            backup = src.with_suffix(src.suffix + ".bak")
            backup.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            return str(backup)
        return None

    def rollback(self, file_path: str) -> bool:
        src = Path(file_path)
        backup = src.with_suffix(src.suffix + ".bak")
        if backup.exists():
            src.write_text(backup.read_text(encoding="utf-8"), encoding="utf-8")
            return True
        return False

    def diff(self, old_text: str, new_text: str) -> str:
        return "\n".join(
            difflib.unified_diff(
                old_text.splitlines(),
                new_text.splitlines(),
                fromfile="before",
                tofile="after",
                lineterm=""
            )
        )

    def save_change_log(self, file_path: str, diff_text: str) -> str:
        stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        target = self.change_dir / f"{stamp}_{Path(file_path).name}.diff"
        target.write_text(diff_text, encoding="utf-8")
        return str(target)

change_manager = ChangeManager()
