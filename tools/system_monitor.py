def get_system_stats() -> str:
    """Devuelve estadísticas reales del sistema: CPU, memoria, disco."""
    import psutil, os

    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    lines = [
        f"CPU: {cpu}%",
        f"Memoria: {mem.used / 1024**2:.0f} MB usados / {mem.total / 1024**2:.0f} MB total ({mem.percent}%)",
        f"Disco: {disk.used / 1024**3:.1f} GB usados / {disk.total / 1024**3:.1f} GB total ({disk.percent}%)",
        f"Procesos activos: {len(psutil.pids())}",
    ]

    try:
        net = psutil.net_io_counters()
        lines.append(f"Red: {net.bytes_sent / 1024**2:.1f} MB enviados, {net.bytes_recv / 1024**2:.1f} MB recibidos")
    except Exception:
        pass

    return "\n".join(lines)
