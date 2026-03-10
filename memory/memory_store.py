import json
from pathlib import Path
from typing import Any, Dict

class MemoryStore:
    FILE = Path("memory.json")

    def __init__(self):
        if not self.FILE.exists():
            self.FILE.write_text("{}", encoding="utf-8")

    def load(self) -> Dict[str, Any]:
        return json.loads(self.FILE.read_text(encoding="utf-8"))

    def save(self, data: Dict[str, Any]) -> None:
        self.FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def set(self, key: str, value: Any) -> None:
        data = self.load()
        data[key] = value
        self.save(data)

    def get(self, key: str, default=None):
        return self.load().get(key, default)

memory_store = MemoryStore()
