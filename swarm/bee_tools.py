"""
BEE Tools — herramientas reales que cada BEE puede ejecutar.
Las BEEs no son sólo LLM. Pueden leer archivos, escribir código,
correr scripts, buscar en la web y ver logs.
"""
from __future__ import annotations

import json
import os
import subprocess
import traceback
from pathlib import Path
from typing import Any

from core.logger import logger

# Directorio raíz del proyecto
ROOT = Path(__file__).resolve().parent.parent

# ── Definición de herramientas (OpenAI function-calling format) ───────────────

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Lee el contenido de un archivo del proyecto. Usa esto para entender el código antes de modificarlo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Ruta relativa del archivo desde la raíz del proyecto"},
                    "lines": {"type": "integer", "description": "Número máximo de líneas a leer (default 200)"},
                    "offset": {"type": "integer", "description": "Línea desde donde empezar (default 1)"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Escribe o reemplaza el contenido de un archivo. Úsalo para aplicar fixes de código.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Ruta relativa del archivo"},
                    "content": {"type": "string", "description": "Contenido completo a escribir"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "patch_file",
            "description": "Reemplaza una cadena exacta dentro de un archivo. Más seguro que write_file para cambios pequeños.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_string": {"type": "string", "description": "Texto exacto a reemplazar"},
                    "new_string": {"type": "string", "description": "Texto nuevo"},
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_python",
            "description": "Ejecuta código Python y devuelve stdout/stderr. Úsalo para probar fixes o analizar datos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Código Python a ejecutar"},
                    "timeout": {"type": "integer", "description": "Timeout en segundos (default 15)"},
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Ejecuta un comando de shell seguro (solo lectura: ls, cat, grep, python -c, etc).",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout": {"type": "integer", "description": "Timeout en segundos (default 10)"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "Lista archivos en un directorio del proyecto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Directorio a listar (default '.')"},
                    "recursive": {"type": "boolean", "description": "Listar recursivamente (default false)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Busca información en internet. Úsalo para investigar errores, APIs o tecnologías.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "description": "Número de resultados (default 5)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_logs",
            "description": "Lee los logs recientes del bot para diagnosticar errores.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lines": {"type": "integer", "description": "Últimas N líneas de log (default 50)"},
                    "filter": {"type": "string", "description": "Filtrar líneas que contengan esta cadena"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reload_module",
            "description": "Recarga un módulo Python roto sin reiniciar el bot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "module_name": {"type": "string", "description": "Nombre del módulo (ej: tools.image_gen)"},
                },
                "required": ["module_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "install_package",
            "description": "Instala un paquete pip faltante.",
            "parameters": {
                "type": "object",
                "properties": {
                    "package": {"type": "string", "description": "Nombre del paquete pip"},
                },
                "required": ["package"],
            },
        },
    },
]


# ── Implementaciones reales ────────────────────────────────────────────────────

def read_file(path: str, lines: int = 200, offset: int = 1) -> str:
    try:
        p = ROOT / path
        if not p.exists():
            return f"ERROR: archivo no encontrado: {path}"
        text = p.read_text(errors="replace")
        all_lines = text.splitlines()
        start = max(0, offset - 1)
        chunk = all_lines[start: start + lines]
        result = "\n".join(f"{start + i + 1}: {l}" for i, l in enumerate(chunk))
        total = len(all_lines)
        if total > start + lines:
            result += f"\n... ({total - start - lines} líneas más)"
        return result
    except Exception as e:
        return f"ERROR leyendo {path}: {e}"


def write_file(path: str, content: str) -> str:
    try:
        p = ROOT / path
        p.parent.mkdir(parents=True, exist_ok=True)
        # Crear backup
        backup_dir = ROOT / ".backups"
        backup_dir.mkdir(exist_ok=True)
        if p.exists():
            import shutil, time
            ts = int(time.time())
            shutil.copy2(p, backup_dir / f"{p.name}.{ts}.bak")
        p.write_text(content, encoding="utf-8")
        logger.info("BEE write_file: %s (%d chars)", path, len(content))
        return f"OK: {path} escrito ({len(content)} chars)"
    except Exception as e:
        return f"ERROR escribiendo {path}: {e}"


def patch_file(path: str, old_string: str, new_string: str) -> str:
    try:
        p = ROOT / path
        if not p.exists():
            return f"ERROR: archivo no encontrado: {path}"
        original = p.read_text(encoding="utf-8")
        if old_string not in original:
            return f"ERROR: old_string no encontrado en {path}"
        count = original.count(old_string)
        if count > 1:
            return f"ERROR: old_string aparece {count} veces en {path} — sé más específico"
        # Backup
        backup_dir = ROOT / ".backups"
        backup_dir.mkdir(exist_ok=True)
        import shutil, time
        shutil.copy2(p, backup_dir / f"{p.name}.{int(time.time())}.bak")
        patched = original.replace(old_string, new_string, 1)
        p.write_text(patched, encoding="utf-8")
        logger.info("BEE patch_file: %s", path)
        return f"OK: {path} parchado"
    except Exception as e:
        return f"ERROR parchando {path}: {e}"


def run_python(code: str, timeout: int = 15) -> str:
    try:
        result = subprocess.run(
            ["python", "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(ROOT),
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        if out and err:
            return f"STDOUT:\n{out}\nSTDERR:\n{err}"
        return out or err or "(sin output)"
    except subprocess.TimeoutExpired:
        return f"ERROR: timeout ({timeout}s)"
    except Exception as e:
        return f"ERROR: {e}"


_SAFE_SHELL_PREFIXES = ("ls", "cat ", "grep ", "find ", "echo ", "python -c", "python3 -c",
                         "head ", "tail ", "wc ", "pwd", "env | grep", "pip show", "pip list")

def run_shell(command: str, timeout: int = 10) -> str:
    low = command.strip().lower()
    if not any(low.startswith(p) for p in _SAFE_SHELL_PREFIXES):
        return f"BLOCKED: solo se permiten comandos de lectura (ls, cat, grep, find, python -c, pip show)"
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(ROOT),
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        if out and err:
            return f"{out}\n{err}"
        return out or err or "(sin output)"
    except subprocess.TimeoutExpired:
        return f"ERROR: timeout ({timeout}s)"
    except Exception as e:
        return f"ERROR: {e}"


def list_files(directory: str = ".", recursive: bool = False) -> str:
    try:
        p = ROOT / directory
        if not p.exists():
            return f"ERROR: directorio no encontrado: {directory}"
        if recursive:
            items = []
            for f in sorted(p.rglob("*")):
                if ".git" in f.parts or "__pycache__" in f.parts or ".backups" in f.parts:
                    continue
                rel = f.relative_to(ROOT)
                items.append(str(rel))
            return "\n".join(items[:200])
        else:
            items = sorted(p.iterdir())
            return "\n".join(
                f"{'[DIR] ' if i.is_dir() else '      '}{i.name}" for i in items
                if i.name not in ("__pycache__", ".git", ".backups")
            )
    except Exception as e:
        return f"ERROR: {e}"


def web_search(query: str, max_results: int = 5) -> str:
    try:
        from tools.websearch import web_search as _ws
        return _ws(query, max_results=max_results)
    except Exception as e:
        return f"ERROR buscando '{query}': {e}"


# Almacén de logs en memoria
_LOG_LINES: list[str] = []
MAX_LOG_LINES = 500

def append_log_line(line: str):
    _LOG_LINES.append(line)
    if len(_LOG_LINES) > MAX_LOG_LINES:
        del _LOG_LINES[:-MAX_LOG_LINES]

def read_logs(lines: int = 50, filter: str = "") -> str:
    data = _LOG_LINES[-lines:] if not filter else [l for l in _LOG_LINES if filter.lower() in l.lower()][-lines:]
    return "\n".join(data) if data else "(sin logs disponibles aún)"


def reload_module(module_name: str) -> str:
    import importlib, sys
    try:
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])
            return f"OK: {module_name} recargado"
        else:
            importlib.import_module(module_name)
            return f"OK: {module_name} importado"
    except Exception as e:
        return f"ERROR recargando {module_name}: {e}"


def install_package(package: str) -> str:
    # No instalar módulos locales del proyecto
    local = {"crypto", "tools", "memory", "colmena", "core", "swarm",
             "conversation_mode", "personality_profile", "telegram_bot", "discord_bot"}
    if package.split(".")[0] in local:
        return f"BLOCKED: '{package}' es un módulo local del proyecto, no se instala con pip"
    try:
        result = subprocess.run(
            ["pip", "install", package, "-q"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            logger.info("BEE install_package: %s OK", package)
            return f"OK: {package} instalado"
        return f"ERROR: {result.stderr.strip()[:300]}"
    except Exception as e:
        return f"ERROR: {e}"


# ── Dispatcher ────────────────────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, Any] = {
    "read_file": read_file,
    "write_file": write_file,
    "patch_file": patch_file,
    "run_python": run_python,
    "run_shell": run_shell,
    "list_files": list_files,
    "web_search": web_search,
    "read_logs": read_logs,
    "reload_module": reload_module,
    "install_package": install_package,
}


def execute_tool(name: str, args: dict) -> str:
    fn = TOOL_REGISTRY.get(name)
    if not fn:
        return f"ERROR: herramienta desconocida '{name}'"
    try:
        logger.info("BEE tool call: %s(%s)", name, str(args)[:120])
        result = fn(**args)
        return str(result)[:3000]
    except Exception as e:
        tb = traceback.format_exc()
        logger.error("BEE tool %s error: %s", name, e)
        return f"ERROR en {name}: {e}\n{tb[:500]}"
