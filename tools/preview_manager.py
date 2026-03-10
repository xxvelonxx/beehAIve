from __future__ import annotations

import socket
import subprocess
from typing import Dict

from core.logger import logger

_BASE_PORT = 8090
_MAX_PORT = 8200


def _find_free_port(start: int = _BASE_PORT, end: int = _MAX_PORT) -> int:
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found between {start} and {end}")


class PreviewManager:
    def __init__(self):
        self._processes: Dict[str, subprocess.Popen] = {}
        self._ports: Dict[str, int] = {}

    def start_static_preview(self, root: str, port: int = 0) -> dict:
        if root in self._processes:
            proc = self._processes[root]
            if proc.poll() is None:
                return {
                    "message": f"Preview ya activo",
                    "root": root,
                    "port": self._ports.get(root),
                    "pid": proc.pid,
                }
            else:
                del self._processes[root]
                del self._ports[root]

        try:
            actual_port = port if port and port != 8080 else _find_free_port()
        except RuntimeError as e:
            return {"error": str(e)}

        try:
            proc = subprocess.Popen(
                ["python", "-m", "http.server", str(actual_port)],
                cwd=root,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._processes[root] = proc
            self._ports[root] = actual_port
            logger.info("Preview started: root=%s port=%s pid=%s", root, actual_port, proc.pid)
            return {
                "message": f"Preview iniciado en puerto {actual_port}",
                "root": root,
                "port": actual_port,
                "pid": proc.pid,
                "url": f"http://localhost:{actual_port}",
            }
        except Exception as e:
            return {"error": f"No se pudo iniciar preview: {e}"}

    def stop_preview(self, root: str) -> dict:
        proc = self._processes.pop(root, None)
        self._ports.pop(root, None)
        if proc:
            proc.terminate()
            logger.info("Preview stopped: root=%s", root)
            return {"message": "Preview detenido", "root": root}
        return {"message": "No había preview activo para ese proyecto", "root": root}

    def list_previews(self) -> list:
        return [
            {"root": root, "port": self._ports.get(root), "pid": proc.pid}
            for root, proc in self._processes.items()
            if proc.poll() is None
        ]


preview_manager = PreviewManager()
