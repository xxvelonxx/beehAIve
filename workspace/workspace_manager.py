from pathlib import Path
from workspace.change_manager import change_manager

class WorkspaceManager:
    ROOT = Path("workspace")

    def __init__(self):
        self.ROOT.mkdir(parents=True, exist_ok=True)

    def project_path(self, name: str) -> Path:
        return self.ROOT / name

    def create_project(self, name: str) -> str:
        base = self.project_path(name)
        (base / "src").mkdir(parents=True, exist_ok=True)
        (base / "docs").mkdir(parents=True, exist_ok=True)
        (base / "tests").mkdir(parents=True, exist_ok=True)
        (base / "web").mkdir(parents=True, exist_ok=True)
        (base / "imports").mkdir(parents=True, exist_ok=True)
        return str(base)

    def list_projects(self):
        return [p.name for p in self.ROOT.iterdir() if p.is_dir() and not p.name.startswith(".") and not p.name.startswith("__") ]

    def read_file(self, project: str, relative_path: str) -> str:
        return (self.project_path(project) / relative_path).read_text(encoding="utf-8")

    def write_file(self, project: str, relative_path: str, content: str, agent_id: str = "system") -> str:
        path = self.project_path(project) / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)

        ok, owner = change_manager.acquire_lock(str(path), agent_id)
        if not ok:
            raise RuntimeError(f"File locked by {owner}")

        old = ""
        if path.exists():
            old = path.read_text(encoding="utf-8")
            change_manager.backup(str(path))

        path.write_text(content, encoding="utf-8")
        diff_text = change_manager.diff(old, content)
        change_manager.save_change_log(str(path), diff_text)
        change_manager.release_lock(str(path), agent_id)
        return str(path)

    def append_file(self, project: str, relative_path: str, content: str, agent_id: str = "system") -> str:
        path = self.project_path(project) / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)

        ok, owner = change_manager.acquire_lock(str(path), agent_id)
        if not ok:
            raise RuntimeError(f"File locked by {owner}")

        old = path.read_text(encoding="utf-8") if path.exists() else ""
        if path.exists():
            change_manager.backup(str(path))

        new = old + content
        path.write_text(new, encoding="utf-8")
        diff_text = change_manager.diff(old, new)
        change_manager.save_change_log(str(path), diff_text)
        change_manager.release_lock(str(path), agent_id)
        return str(path)

    def write_many_files(self, project: str, files: dict, agent_prefix: str = "builder") -> list:
        written = []
        for idx, (relative_path, content) in enumerate(files.items()):
            written.append(self.write_file(project, relative_path, content, agent_id=f"{agent_prefix}_{idx}"))
        return written

    def list_project_files(self, project: str) -> list:
        root = self.project_path(project)
        if not root.exists():
            return []
        return [str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()]

    def import_files_into_project(self, project: str, extracted_root: str, target_prefix: str = "imports") -> list:
        extracted = Path(extracted_root)
        if not extracted.exists():
            return []
        written = []
        for file_path in extracted.rglob("*"):
            if file_path.is_file():
                rel = file_path.relative_to(extracted)
                target_rel = str(Path(target_prefix) / rel)
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                written.append(self.write_file(project, target_rel, content, agent_id="zip_import"))
        return written

workspace_manager = WorkspaceManager()
