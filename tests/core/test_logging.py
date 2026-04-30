"""Tests de core/logging/."""

import logging
from pathlib import Path

from core.logging import configurar_logging


def test_configurar_logging_crea_archivo(tmp_path):
    log_path = configurar_logging(carpeta_logs=tmp_path)
    assert Path(log_path).exists()
    assert Path(log_path).parent == tmp_path
    assert Path(log_path).name.startswith("scraping_")
    assert Path(log_path).suffix == ".log"


def test_configurar_logging_escribe_mensaje(tmp_path):
    log_path = configurar_logging(carpeta_logs=tmp_path)
    logging.getLogger("scraping").info("mensaje-prueba-123")
    # Flush de handlers
    for h in logging.getLogger().handlers:
        h.flush()
    contenido = Path(log_path).read_text(encoding="utf-8")
    assert "mensaje-prueba-123" in contenido
