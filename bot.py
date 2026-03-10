import os
import subprocess
import threading

from conversation_mode import conversation_mode
from orchestration.orchestrator import orchestrator
from workspace.workspace_manager import workspace_manager
from tools.project_status import project_status_tool
from core.logger import logger
from core.state import state_manager
from config import config


def _start_web_panel():
    """Arranca el panel web de emergencia en un thread daemon."""
    try:
        from web_panel.app import run_panel
        port = int(os.environ.get("PANEL_PORT", 8080))
        t = threading.Thread(target=run_panel, args=(port,), daemon=True, name="web-panel")
        t.start()
        logger.info("Web panel iniciado en puerto %d", port)
    except Exception as e:
        logger.warning("Web panel no pudo iniciar: %s", e)


def run_cli():
    print("Beeatrix ULTIMATE / La Colmena iniciada")
    print("Ejemplos:")
    print("  hola")
    print("  crear proyecto demo")
    print("  construir bot telegram")
    print("  construir backend fastapi")
    print("  crear swarm 20")
    print("  crear swarm 50")
    print("  como usar swarm")
    print("  plan self upgrade añadir imagenes")
    print("  autorizar self upgrade")
    print("  aplicar self upgrade")
    print("  terminal ls")
    print("  preview start")
    print("  preview stop")
    print("  panel start")
    print("  research fastapi auth")
    print("  fetch https://example.com")
    print("  image prompt landing inmobiliaria")
    print("  generar imagen landing inmobiliaria")
    print("  video plan demo app")
    print("  analizar zip ruta/al/archivo.zip")
    print("  procesar archivo ruta/al/archivo.txt")

    while True:
        msg = input("> ").strip()
        if not msg:
            continue

        try:
            lower = msg.lower()

            if msg.startswith("crear proyecto "):
                name = msg.split("crear proyecto ", 1)[1].strip()
                workspace_manager.create_project(name)
                state_manager.set_current_project(name)
                print(f"Proyecto {name} creado.")
                continue

            if lower == "proyectos":
                print(workspace_manager.list_projects())
                continue

            if lower.startswith("procesar archivo ") or lower.startswith("procesa archivo "):
                path = msg.split(" ", 2)[2].strip()
                task = {
                    "intent": "file_processing",
                    "objective": f"Process file {path}",
                    "project": state_manager.current_project,
                    "file_path": path,
                }
                state_manager.last_uploaded_file = path
                orchestrator.initialize()
                print(orchestrator.process_task(task))
                continue

            if lower.startswith("analizar zip "):
                zip_path = msg.split("analizar zip ", 1)[1].strip()
                task = {
                    "intent": "zip_analysis",
                    "objective": f"Analyze ZIP {zip_path}",
                    "project": state_manager.current_project,
                    "zip_path": zip_path,
                }
                state_manager.last_uploaded_file = zip_path
                orchestrator.initialize()
                print(orchestrator.process_task(task))
                continue

            if lower.startswith("terminal "):
                command = msg.split("terminal ", 1)[1]
                print(orchestrator.process_terminal(command))
                continue

            if lower == "preview start":
                print(orchestrator.process_preview("start"))
                continue

            if lower == "preview stop":
                print(orchestrator.process_preview("stop"))
                continue

            if lower == "panel start":
                subprocess.Popen("python tools/panel_app.py", shell=True)
                print(f"Panel iniciando en http://{config.PANEL_HOST}:{config.PANEL_PORT}")
                continue

            if lower.startswith("research "):
                query = msg.split("research ", 1)[1]
                print(orchestrator.process_research(query))
                continue

            if lower.startswith("fetch "):
                url = msg.split("fetch ", 1)[1]
                print(orchestrator.process_fetch(url))
                continue

            if lower.startswith("image prompt "):
                objective = msg.split("image prompt ", 1)[1]
                print(orchestrator.process_media(objective))
                continue

            if lower.startswith("video plan "):
                objective = msg.split("video plan ", 1)[1]
                print(orchestrator.process_media(objective))
                continue

            result = conversation_mode.process_message(msg)

            if result["type"] == "chat_reply":
                print(result["response"])
                continue

            if result["type"] == "direct_answer":
                print(result["response"])
                if result["intent"] in ["status_request", "capability_help"]:
                    print(project_status_tool.get_status())
                continue

            if result["type"] == "task":
                orchestrator.initialize()
                output = orchestrator.process_task(result["task"])
                print(output)
                continue

        except Exception as e:
            logger.exception("Bot error")
            print("Error:", e)


def run_telegram():
    from telegram_bot import run
    run()


async def run_both():
    import asyncio
    from telegram_bot import run as run_tg
    from discord_bot import run_discord

    discord_token = os.environ.get("DISCORD_BOT_TOKEN")

    if discord_token:
        loop = asyncio.get_event_loop()
        tg_task = loop.run_in_executor(None, run_tg)
        discord_task = asyncio.create_task(run_discord())
        await asyncio.gather(discord_task, return_exceptions=True)
    else:
        run_tg()


def _start_autonomous_loop():
    """
    Arranca el motor autónomo en background.
    BEEs siempre activas: entrenamiento, análisis de mejoras, investigación.
    """
    try:
        from swarm.autonomous_loop import autonomous_loop
        autonomous_loop.start()
        logger.info("AutonomousLoop iniciado en background")
    except Exception as e:
        logger.warning("AutonomousLoop no pudo iniciar: %s", e)


if __name__ == "__main__":
    _start_web_panel()
    _start_autonomous_loop()
    mode = os.environ.get("BOT_MODE", "telegram")
    if mode == "cli":
        run_cli()
    elif mode == "both":
        import asyncio
        asyncio.run(run_both())
    else:
        run_telegram()
