import json
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

from config import config
from tools.project_status import project_status_tool

app = FastAPI(title="Beeatrix Panel")


@app.get("/", response_class=HTMLResponse)
def home():
    status = project_status_tool.get_status()
    status_str = json.dumps(status, indent=2, ensure_ascii=False)
    html = f"""
    <html>
    <head>
        <title>Beeatrix Panel</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #111; color: #eee; }}
            h1 {{ color: #7ee787; }}
            pre {{ background: #222; padding: 16px; border-radius: 8px; overflow-x: auto; white-space: pre-wrap; }}
            .card {{ background: #1b1b1b; padding: 20px; border-radius: 10px; margin-bottom: 20px; }}
        </style>
    </head>
    <body>
        <h1>🐝 Beeatrix Panel</h1>
        <div class="card">
            <h2>Status</h2>
            <pre>{status_str}</pre>
        </div>
    </body>
    </html>
    """
    return html


@app.get("/status")
def status_json():
    return project_status_tool.get_status()


def run_panel():
    uvicorn.run(app, host=config.PANEL_HOST, port=config.PANEL_PORT)


if __name__ == "__main__":
    run_panel()
