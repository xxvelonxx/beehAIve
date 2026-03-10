import subprocess

class ExecutionTool:
    def run(self, cmd: str, cwd: str = None):
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        return {
            "command": cmd,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "cwd": cwd,
        }

execution_tool = ExecutionTool()
