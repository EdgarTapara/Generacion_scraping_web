"""
Configuración de logging estructurado con archivo por corrida.

Generaliza v1/utils.py:configurar_logging — ahora la carpeta de logs
la decide el caller (cada sector apunta a su propia `resultados/logs/`).
"""

import logging
from datetime import datetime
from pathlib import Path


def configurar_logging(
    carpeta_logs: str | Path,
    nivel: int = logging.INFO,
    nombre_logger: str = "scraping",
) -> str:
    """Configura logging a consola y a archivo.

    Crea un archivo `scraping_YYYYMMDD_HHMMSS.log` en `carpeta_logs`.
    Retorna la ruta del archivo creado.
    """
    carpeta = Path(carpeta_logs)
    carpeta.mkdir(parents=True, exist_ok=True)
    log_path = carpeta / f"scraping_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    # Limpiar handlers previos para evitar duplicación en reconfiguraciones.
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)

    logging.basicConfig(
        level=nivel,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )
    logging.getLogger(nombre_logger).info(f"Log guardado en: {log_path}")
    return str(log_path)
