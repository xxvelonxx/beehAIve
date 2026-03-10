from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any

from tools.zip_analyzer import zip_analyzer


class FileProcessor:
    SUPPORTED_TEXT = {'.txt', '.md', '.py', '.json', '.yaml', '.yml', '.csv', '.html', '.css', '.js', '.ts', '.toml'}

    def process(self, path_str: str) -> Dict[str, Any]:
        path = Path(path_str)
        if not path.exists():
            return {"error": "file_not_found", "path": str(path)}

        if path.is_dir():
            files = [str(p.relative_to(path)) for p in path.rglob('*') if p.is_file()][:200]
            return {
                "path": str(path),
                "type": "directory",
                "file_count": len(files),
                "files": files,
            }

        suffix = path.suffix.lower()
        if suffix == '.zip':
            analysis = zip_analyzer.analyze(str(path))
            return {
                "path": str(path),
                "type": "zip",
                "analysis": analysis,
            }

        if suffix in self.SUPPORTED_TEXT:
            text = path.read_text(encoding='utf-8', errors='ignore')
            result = {
                "path": str(path),
                "type": "text",
                "extension": suffix,
                "size": path.stat().st_size,
                "preview": text[:4000],
                "line_count": len(text.splitlines()),
            }
            if suffix == '.json':
                try:
                    data = json.loads(text)
                    result["json_keys"] = list(data.keys())[:50] if isinstance(data, dict) else []
                except Exception:
                    result["json_keys"] = []
            return result

        return {
            "path": str(path),
            "type": "binary_or_unsupported",
            "extension": suffix,
            "size": path.stat().st_size,
            "note": "File exists but no parser is implemented for this type yet.",
        }


file_processor = FileProcessor()
