import subprocess
import tempfile
import os


def run_python_code(code: str, timeout: int = 15) -> dict:
    """
    Ejecuta código Python en un subproceso aislado y devuelve stdout/stderr.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        path = f.name

    try:
        result = subprocess.run(
            ["python3", path],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        return {
            "stdout": result.stdout[:3000],
            "stderr": result.stderr[:1000],
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": f"Timeout: el código tardó más de {timeout}s", "returncode": -1}
    finally:
        os.unlink(path)


def format_result(result: dict) -> str:
    out = result.get("stdout", "").strip()
    err = result.get("stderr", "").strip()
    rc = result.get("returncode", 0)

    parts = []
    if out:
        parts.append(f"```\n{out}\n```")
    if err:
        parts.append(f"Error:\n```\n{err}\n```")
    if not out and not err:
        parts.append("(Sin salida)")
    parts.append(f"Código de salida: {rc}")
    return "\n".join(parts)
