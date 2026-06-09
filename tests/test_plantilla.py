"""Tests de salud de `plantilla_proyecto/` (el scaffold que se copia).

Objetivo doble:
  1. **Guardar contra drift de API**: la plantilla importa de `core/`. Si un
     módulo de `core/` cambia su API pública y rompe la plantilla, este test
     falla — la plantilla no se puede dejar pudrir en silencio.
  2. **Sin efectos secundarios al importar**: importar `config` NO debe crear
     directorios. La creación de `resultados/` ocurre recién en una corrida
     (vía `config.asegurar_directorios()`), no al importar el paquete.

Todo sin red ni Chrome (sólo imports).
"""

import importlib
import shutil

import pytest

SUBMODULOS = [
    "config",
    "modelos",
    "limpieza",
    "extractor_ia",
    "scraper",
    "main",
    "portal_scrapers.common",
    "portal_scrapers.portal_a",
]


@pytest.mark.parametrize("modulo", SUBMODULOS)
def test_submodulo_importa(modulo):
    """Cada submódulo de la plantilla importa sin error (API de core vigente)."""
    importlib.import_module(f"plantilla_proyecto.{modulo}")


def test_importar_config_no_crea_directorios():
    from plantilla_proyecto import config

    resultados = config.CARPETA_SALIDA
    if resultados.exists():
        shutil.rmtree(resultados)

    importlib.reload(config)  # re-ejecuta el top-level del módulo

    assert not resultados.exists(), (
        "Importar config no debe crear resultados/. "
        "La creación va en config.asegurar_directorios(), llamada por main()."
    )


def test_asegurar_directorios_crea_todo():
    from plantilla_proyecto import config

    resultados = config.CARPETA_SALIDA
    if resultados.exists():
        shutil.rmtree(resultados)

    config.asegurar_directorios()
    try:
        for carpeta in config.CARPETAS_SALIDA:
            assert carpeta.exists(), f"falta {carpeta}"
    finally:
        shutil.rmtree(resultados, ignore_errors=True)  # no dejar artefacto
