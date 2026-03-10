"""
BEEA Emergency Web Panel — acceso directo cuando Telegram/Discord están caídos.

Rutas:
  GET  /           → Dashboard (status del sistema + logs)
  POST /chat        → Chat con BEEA
  GET  /bee         → Selector de rol de BEE
  POST /bee         → Chat directo con una BEE específica
  POST /repair      → Disparar reparación manual completa
  GET  /logs        → Logs del bot en tiempo real

Seguridad: contraseña requerida (SESSION_SECRET o PANEL_PASSWORD).
"""

from __future__ import annotations

import json
import os
import sys
import time
import threading
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from flask import Flask, request, session, redirect, url_for, render_template_string, jsonify
from core.logger import logger

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET") or os.environ.get("PANEL_PASSWORD") or "beea_panel_2025"

PANEL_PASSWORD = os.environ.get("PANEL_PASSWORD") or os.environ.get("SESSION_SECRET", "beea")

# ── HTML base ─────────────────────────────────────────────────────────────────

BASE_CSS = """
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BEEA Panel</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0d0d0d;color:#e8e8e8;font-family:'Segoe UI',sans-serif;font-size:14px}
  a{color:#d4a0ff;text-decoration:none}
  a:hover{text-decoration:underline}
  nav{background:#1a1a2e;padding:12px 24px;display:flex;gap:20px;align-items:center;border-bottom:1px solid #2a2a4a}
  nav .logo{font-size:18px;font-weight:700;color:#d4a0ff;letter-spacing:1px}
  .page{max-width:960px;margin:24px auto;padding:0 16px}
  .card{background:#1a1a2e;border:1px solid #2a2a4a;border-radius:10px;padding:20px;margin-bottom:20px}
  .card h3{color:#d4a0ff;margin-bottom:12px;font-size:15px;letter-spacing:.5px}
  .badge{display:inline-block;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:600}
  .ok{background:#1a3a1a;color:#5eff5e}
  .dead{background:#3a1a1a;color:#ff5e5e}
  .warn{background:#3a301a;color:#ffcc5e}
  input[type=text],input[type=password],textarea,select{
    background:#0d0d1a;border:1px solid #2a2a4a;color:#e8e8e8;
    padding:10px 14px;border-radius:8px;width:100%;margin-bottom:10px;font-size:14px
  }
  input[type=text]:focus,textarea:focus,select:focus{outline:none;border-color:#d4a0ff}
  button,input[type=submit]{
    background:#6a0dad;color:#fff;border:none;padding:10px 22px;
    border-radius:8px;cursor:pointer;font-size:14px;font-weight:600
  }
  button:hover,input[type=submit]:hover{background:#8a2dcd}
  .msg{padding:10px 14px;border-radius:8px;margin-bottom:8px;line-height:1.5}
  .msg.user{background:#1a1a3a;border-left:3px solid #6a0dad}
  .msg.beea{background:#1a2a1a;border-left:3px solid #2a8a2a}
  .msg.bee{background:#2a1a2a;border-left:3px solid #d4a0ff}
  .msg .who{font-size:11px;color:#888;margin-bottom:4px}
  pre{background:#080810;padding:14px;border-radius:8px;overflow-x:auto;font-size:12px;color:#aaf;white-space:pre-wrap}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px}
  .stat{background:#14142a;border:1px solid #2a2a4a;border-radius:8px;padding:14px;text-align:center}
  .stat .val{font-size:22px;font-weight:700;color:#d4a0ff}
  .stat .lbl{font-size:11px;color:#888;margin-top:4px}
  .alert{background:#2a1a1a;border:1px solid #5a2a2a;border-radius:8px;padding:12px;margin-bottom:8px;color:#ffaaaa;font-size:13px}
</style>
"""

def nav_html(active=""):
    links = [
        ("/", "Dashboard"),
        ("/chat", "BEEA"),
        ("/bee", "BEEs"),
        ("/logs", "Logs"),
        ("/repair", "Repair"),
    ]
    items = " ".join(
        f'<a href="{h}" style="{"color:#fff;font-weight:700" if active==h else ""}">{l}</a>'
        for h, l in links
    )
    return f'<nav><span class="logo">🐝 BEEA</span>{items}<span style="margin-left:auto;color:#555;font-size:12px">{datetime.utcnow().strftime("%H:%M UTC")}</span></nav>'


def require_auth(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("auth"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        if request.form.get("password") == PANEL_PASSWORD:
            session["auth"] = True
            return redirect(url_for("dashboard"))
        error = "Contraseña incorrecta."
    return render_template_string(f"""
    {BASE_CSS}
    <div style="display:flex;justify-content:center;align-items:center;min-height:100vh">
      <div style="width:320px">
        <div style="text-align:center;margin-bottom:28px">
          <div style="font-size:40px">🐝</div>
          <div style="font-size:22px;font-weight:700;color:#d4a0ff;margin-top:8px">BEEA Panel</div>
          <div style="color:#666;font-size:13px;margin-top:4px">Acceso de emergencia</div>
        </div>
        <form method="post">
          <input type="password" name="password" placeholder="Contraseña" autofocus>
          {'<div class="alert">'+error+'</div>' if error else ''}
          <input type="submit" value="Entrar" style="width:100%">
        </form>
      </div>
    </div>
    """)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route("/")
@require_auth
def dashboard():
    status_data = _get_system_status()
    bees_html = ""
    for name, info in status_data.get("bees", {}).items():
        cls = "ok" if info.get("viva") else "dead"
        bees_html += f'<div class="stat"><div class="val"><span class="badge {cls}">{name}</span></div><div class="lbl">{info.get("ultimo_latido","?")}</div></div>'
    if not bees_html:
        bees_html = '<div style="color:#666">Colmena no iniciada aún</div>'

    modules_html = ""
    for mod, ok in status_data.get("modules", {}).items():
        cls = "ok" if ok else "dead"
        modules_html += f'<span class="badge {cls}" style="margin:3px">{mod}</span> '

    issues_html = ""
    for iss in status_data.get("recent_issues", []):
        issues_html += f'<div class="alert">{iss}</div>'
    if not issues_html:
        issues_html = '<div class="badge ok">Sin issues detectados</div>'

    repairs = status_data.get("repairs", 0)
    running = status_data.get("running", False)

    return render_template_string(f"""
    {BASE_CSS}
    {nav_html("/")}
    <div class="page">
      <div class="grid" style="margin-bottom:20px">
        <div class="stat"><div class="val">{"🟢" if running else "🔴"}</div><div class="lbl">Colmena</div></div>
        <div class="stat"><div class="val">{status_data.get("num_bees",0)}</div><div class="lbl">Bees vivas</div></div>
        <div class="stat"><div class="val">{repairs}</div><div class="lbl">Reparaciones</div></div>
        <div class="stat"><div class="val">{status_data.get("issues_count",0)}</div><div class="lbl">Issues reportados</div></div>
      </div>
      <div class="card">
        <h3>Bees</h3>
        <div class="grid">{bees_html}</div>
      </div>
      <div class="card">
        <h3>Módulos del sistema</h3>
        <div>{modules_html}</div>
      </div>
      <div class="card">
        <h3>Issues activos</h3>
        {issues_html}
      </div>
    </div>
    """)


def _get_system_status() -> dict:
    data = {"bees": {}, "modules": {}, "running": False, "num_bees": 0,
            "repairs": 0, "issues_count": 0, "recent_issues": []}
    try:
        from colmena.monitor import colmena
        st = colmena.status()
        data["bees"] = st.get("bees", {})
        data["running"] = st.get("running", False)
        data["repairs"] = st.get("repairs_realizados", 0)
        data["issues_count"] = st.get("issues_reportados", 0)
        data["num_bees"] = sum(1 for v in st.get("bees", {}).values() if v.get("viva"))
    except Exception:
        pass

    mods_to_check = [
        "tools.llm_adapter", "tools.image_gen", "tools.image_providers",
        "tools.bypass_engine", "core.ai_chat", "personality_profile",
        "crypto.price_feed", "tools.scheduler", "memory.long_memory",
        "tools.websearch", "tools.tts",
    ]
    import importlib
    for mod in mods_to_check:
        try:
            importlib.import_module(mod)
            data["modules"][mod.split(".")[-1]] = True
        except Exception:
            data["modules"][mod.split(".")[-1]] = False
            data["recent_issues"].append(f"{mod} roto")

    return data


# ── Chat con BEEA ─────────────────────────────────────────────────────────────

_beea_history: list[dict] = []

@app.route("/chat", methods=["GET", "POST"])
@require_auth
def chat_beea():
    reply = ""
    error = ""
    if request.method == "POST":
        msg = request.form.get("message", "").strip()
        if msg:
            try:
                from core.ai_chat import chat as _chat
                reply = _chat(msg)
                _beea_history.append({"role": "user", "text": msg})
                _beea_history.append({"role": "beea", "text": reply})
                if len(_beea_history) > 40:
                    del _beea_history[:-40]
            except Exception as e:
                error = f"Error: {e}"

    history_html = ""
    for h in _beea_history[-20:]:
        cls = h["role"]
        who = "Tú" if cls == "user" else "BEEA"
        history_html += f'<div class="msg {cls}"><div class="who">{who}</div>{_esc(h["text"])}</div>'

    return render_template_string(f"""
    {BASE_CSS}
    {nav_html("/chat")}
    <div class="page">
      <div class="card">
        <h3>Chat directo con BEEA</h3>
        <div style="max-height:400px;overflow-y:auto;margin-bottom:14px" id="hist">
          {history_html if history_html else '<div style="color:#555;text-align:center;padding:20px">Sin mensajes aún</div>'}
        </div>
        {'<div class="alert">'+error+'</div>' if error else ''}
        <form method="post">
          <div style="display:flex;gap:10px">
            <input type="text" name="message" placeholder="Escribe algo..." autofocus style="margin:0">
            <button type="submit" style="white-space:nowrap">Enviar</button>
          </div>
        </form>
      </div>
    </div>
    <script>var h=document.getElementById('hist');if(h)h.scrollTop=h.scrollHeight</script>
    """)


# ── Chat con BEE específica ────────────────────────────────────────────────────

_bee_history: list[dict] = []

@app.route("/bee", methods=["GET", "POST"])
@require_auth
def chat_bee():
    from swarm.bee_roles import BEE_ROLES
    roles = list(BEE_ROLES.keys())
    result = ""
    error = ""
    selected_role = request.form.get("role", "debugger")
    msg = ""

    if request.method == "POST":
        msg = request.form.get("message", "").strip()
        if msg:
            try:
                from swarm.agent_worker import AgentWorker
                worker = AgentWorker(agent_id=99, role=selected_role)
                task = {
                    "step": msg,
                    "objective": msg,
                    "role": selected_role,
                }
                res = worker.run_task(task)
                result = res.get("result", "")
                _bee_history.append({"role": "user", "text": msg, "bee": selected_role})
                _bee_history.append({"role": "bee", "text": result, "bee": selected_role})
                if len(_bee_history) > 30:
                    del _bee_history[:-30]
            except Exception as e:
                import traceback
                error = f"Error: {e}\n{traceback.format_exc()[:500]}"

    roles_opts = "".join(
        f'<option value="{r}" {"selected" if r==selected_role else ""}>{r} — {BEE_ROLES[r]["description"]}</option>'
        for r in roles
    )

    history_html = ""
    for h in _bee_history[-16:]:
        cls = h["role"]
        who = "Tú" if cls == "user" else f"BEE [{h.get('bee','')}]"
        history_html += f'<div class="msg {cls}"><div class="who">{who}</div><pre>{_esc(h["text"])}</pre></div>'

    return render_template_string(f"""
    {BASE_CSS}
    {nav_html("/bee")}
    <div class="page">
      <div class="card">
        <h3>Chat directo con una BEE</h3>
        <div style="color:#888;font-size:12px;margin-bottom:12px">
          Hablas directamente con la BEE. Ella tiene herramientas reales: leer/escribir archivos, ejecutar código, buscar en la web.
        </div>
        <div style="max-height:380px;overflow-y:auto;margin-bottom:14px" id="hist">
          {history_html if history_html else '<div style="color:#555;text-align:center;padding:20px">Sin mensajes aún</div>'}
        </div>
        {'<div class="alert">'+error+'</div>' if error else ''}
        <form method="post">
          <select name="role">{roles_opts}</select>
          <div style="display:flex;gap:10px">
            <input type="text" name="message" placeholder="Tarea para la BEE..." autofocus style="margin:0">
            <button type="submit" style="white-space:nowrap">Enviar</button>
          </div>
        </form>
      </div>
    </div>
    <script>var h=document.getElementById('hist');if(h)h.scrollTop=h.scrollHeight</script>
    """)


# ── Logs ──────────────────────────────────────────────────────────────────────

@app.route("/logs")
@require_auth
def logs():
    from swarm.bee_tools import read_logs
    filt = request.args.get("filter", "")
    lines_param = int(request.args.get("lines", 80))
    log_text = read_logs(lines=lines_param, filter=filt)

    return render_template_string(f"""
    {BASE_CSS}
    {nav_html("/logs")}
    <div class="page">
      <div class="card">
        <h3>Logs del bot</h3>
        <form method="get" style="display:flex;gap:10px;margin-bottom:14px">
          <input type="text" name="filter" value="{_esc(filt)}" placeholder="Filtrar..." style="margin:0">
          <button type="submit">Filtrar</button>
          <a href="/logs" style="padding:10px 16px;background:#1a1a2e;border-radius:8px;color:#e8e8e8">Limpiar</a>
        </form>
        <pre style="max-height:500px;overflow-y:auto">{_esc(log_text)}</pre>
      </div>
    </div>
    """)


# ── Repair manual ─────────────────────────────────────────────────────────────

_repair_results: list[str] = []

@app.route("/repair", methods=["GET", "POST"])
@require_auth
def repair():
    message = ""
    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "full_check":
            # Ejecutar chequeo + repair en un thread separado
            def _do_repair():
                import asyncio
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    from colmena.monitor import colmena
                    issues = loop.run_until_complete(colmena._run_full_check())
                    results = []
                    for iss in issues:
                        res = loop.run_until_complete(colmena._try_repair(iss))
                        results.append(f"Issue: {iss}\nRepair: {res}")
                    _repair_results.clear()
                    _repair_results.extend(results if results else ["Sin issues detectados."])
                except Exception as e:
                    _repair_results.append(f"Error en repair: {e}")
                finally:
                    loop.close()
            t = threading.Thread(target=_do_repair, daemon=True)
            t.start()
            t.join(timeout=30)
            message = "Chequeo + reparación completado."
        elif action == "restart_scheduler":
            try:
                from tools.scheduler import bee_scheduler
                import asyncio
                asyncio.run_coroutine_threadsafe(bee_scheduler.run_loop(), asyncio.get_event_loop())
                message = "Scheduler reiniciado."
            except Exception as e:
                message = f"Error: {e}"

    results_html = ""
    for r in _repair_results[-20:]:
        results_html += f'<pre style="margin-bottom:8px">{_esc(r)}</pre>'

    return render_template_string(f"""
    {BASE_CSS}
    {nav_html("/repair")}
    <div class="page">
      <div class="card">
        <h3>Reparación manual</h3>
        <form method="post" style="display:flex;gap:10px;flex-wrap:wrap">
          <button name="action" value="full_check">Chequear y reparar todo</button>
          <button name="action" value="restart_scheduler">Reiniciar scheduler</button>
        </form>
        {'<div class="badge ok" style="margin-top:12px">'+message+'</div>' if message else ''}
      </div>
      {'<div class="card"><h3>Resultados</h3>' + results_html + '</div>' if results_html else ''}
    </div>
    """)


# ── API JSON (para integraciones futuras) ─────────────────────────────────────

@app.route("/api/status")
@require_auth
def api_status():
    return jsonify(_get_system_status())

@app.route("/api/chat", methods=["POST"])
@require_auth
def api_chat():
    data = request.get_json(force=True) or {}
    msg = data.get("message", "")
    try:
        from core.ai_chat import chat as _chat
        reply = _chat(msg)
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Utils ─────────────────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


# ── Runner ────────────────────────────────────────────────────────────────────

def run_panel(port: int = 8080, host: str = "0.0.0.0"):
    logger.info("BEEA Web Panel arrancando en %s:%d", host, port)
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    run_panel()
