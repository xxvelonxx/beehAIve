from __future__ import annotations
from typing import Any, Dict, List, Optional

class StateManager:
    def __init__(self) -> None:
        self.current_project: Optional[str] = None
        self.system_memory: Dict[str, Any] = {}
        self.task_queue: List[Dict[str, Any]] = []
        self.active_swarm: List[Dict[str, Any]] = []
        self.last_uploaded_file: Optional[str] = None
        self.authorized_self_modify: bool = False

    def set_current_project(self, name: Optional[str]) -> None:
        self.current_project = name

    def get_system_memory(self, key: str) -> Any:
        return self.system_memory.get(key)

    def set_system_memory(self, key: str, value: Any) -> None:
        self.system_memory[key] = value

    def add_task(self, task: Dict[str, Any]) -> None:
        self.task_queue.append(task)

    def pop_task(self) -> Optional[Dict[str, Any]]:
        if self.task_queue:
            return self.task_queue.pop(0)
        return None

    def list_tasks(self) -> List[Dict[str, Any]]:
        return list(self.task_queue)

state_manager = StateManager()
