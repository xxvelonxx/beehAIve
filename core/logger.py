import logging
import sys


class _MemoryHandler(logging.Handler):
    """Guarda las últimas N líneas de log en memoria para que las BEEs puedan leerlas."""
    def emit(self, record: logging.LogRecord):
        try:
            from swarm.bee_tools import append_log_line
            append_log_line(self.format(record))
        except Exception:
            pass


_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

_stream_handler = logging.StreamHandler(sys.stdout)
_stream_handler.setFormatter(_fmt)

_mem_handler = _MemoryHandler()
_mem_handler.setFormatter(_fmt)

logging.basicConfig(level=logging.INFO, handlers=[_stream_handler])

# Añadir el handler de memoria al root logger
logging.getLogger().addHandler(_mem_handler)

logger = logging.getLogger("beeatrix")
