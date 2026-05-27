"""Configuración central del sector <SECTOR>.

Todo parámetro ajustable de scraping (URLs, delays, paths) vive aquí,
nunca dentro de los portales. Así se ajusta sin tocar lógica.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False

load_dotenv()


def _env_int(nombre: str, default: int) -> int:
    valor = os.getenv(nombre, "").strip()
    if not valor:
        return default
    try:
        return int(valor)
    except ValueError:
        return default


def _env_float(nombre: str, default: float) -> float:
    valor = os.getenv(nombre, "").strip()
    if not valor:
        return default
    try:
        return float(valor)
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# Identidad del sector
# ---------------------------------------------------------------------------

SECTOR = "<MI_SECTOR>"  # TODO: 'empleo' | 'financiero' | ...

# ---------------------------------------------------------------------------
# Portales y operaciones
# ---------------------------------------------------------------------------

PORTALES_SOPORTADOS = ["<portal_a>", "<portal_b>"]  # TODO

# Si el sector divide por operación (alquiler/venta, full-time/part-time, etc.)
# declararlas aquí. Si no existe, dejar la lista vacía y usar None.
OPERACIONES = ["<op_1>", "<op_2>"]  # TODO o []

# URLs parametrizadas por portal y operación.
URLS: dict[str, dict] = {
    # TODO: completar
    # "portal_a": {
    #     "op_1": "https://...?page={pagina}",
    #     "base": "https://portal_a.example",
    # },
}


def generar_url_listado(portal: str, operacion: str | None, pagina: int) -> str:
    """Adaptador: devuelve URL del listado según portal/operación/página."""
    # TODO: implementar — patrón típico:
    #   plantilla = URLS[portal][operacion]
    #   if isinstance(plantilla, dict):  # paginación con URL distinta para pág. 1
    #       return plantilla["pagina_1"] if pagina == 1 else plantilla["pagina_n"].format(pagina=pagina)
    #   return plantilla.format(pagina=pagina)
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Parámetros de scraping
# ---------------------------------------------------------------------------

DEFAULT_NUM_PAGINAS = _env_int("NUM_PAGINAS", 1)
MAX_PAGINAS_SEGURIDAD = _env_int("MAX_PAGINAS_SEGURIDAD", 25)
DELAY_LISTADO = (
    _env_float("DELAY_MIN_LISTADO", 2.0),
    _env_float("DELAY_MAX_LISTADO", 4.0),
)
DELAY_DETALLE = (
    _env_float("DELAY_MIN_DETALLE", 2.0),
    _env_float("DELAY_MAX_DETALLE", 5.0),
)
TIMEOUT_ELEMENTO = _env_int("TIMEOUT_ELEMENTO", 8)


# ---------------------------------------------------------------------------
# Umbrales de calidad (compuerta pre-IA)
# Reglas: enlace ≥ 99% siempre. Otros campos dependen del sector.
# Ajustar los nombres para que coincidan con los campos del modelo.
# ---------------------------------------------------------------------------

UMBRALES_CALIDAD: dict[str, dict[str, float]] = {
    # "portal_a": {"enlace": 0.99, "precio": 0.70},
    # TODO
}


# ---------------------------------------------------------------------------
# DeepSeek IA (opcional)
# ---------------------------------------------------------------------------

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
DEEPSEEK_MODEL_2 = os.getenv("DEEPSEEK_MODEL_2", "deepseek-v4-pro")


# ---------------------------------------------------------------------------
# Tipo de cambio (si el sector tiene precios/salarios)
# ---------------------------------------------------------------------------

BCRP_TC_MODO = os.getenv("BCRP_TC_MODO", "venta").strip().lower()


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

CARPETA_SECTOR = Path(__file__).resolve().parent
CARPETA_SALIDA = CARPETA_SECTOR / "resultados"
CARPETA_DEGRADADOS = CARPETA_SALIDA / "degradadas"
CARPETA_LOGS = CARPETA_SALIDA / "logs"
# Evidencia para mantenimiento dinámico: si una corrida falla, estos
# directorios contienen lo que la IA auditora necesita ver.
CARPETA_SNAPSHOTS_FRONTEND = CARPETA_SALIDA / "snapshots_frontend"
CARPETA_REPORTES_MANTENIMIENTO = CARPETA_SALIDA / "reportes_mantenimiento_frontend"

for carpeta in (
    CARPETA_SALIDA, CARPETA_DEGRADADOS, CARPETA_LOGS,
    CARPETA_SNAPSHOTS_FRONTEND, CARPETA_REPORTES_MANTENIMIENTO,
):
    carpeta.mkdir(parents=True, exist_ok=True)


# Mapa portal → archivos/funciones donde un humano o IA debe buscar la
# causa cuando el portal cambia su frontend. El reporte de mantenimiento
# lo usa para guiar la auditoría. Sólo lo conoce el sector.
CODIGO_POR_PORTAL: dict[str, list[str]] = {
    # "portal_a": [
    #     "portal_scrapers/portal_a.py: scrape_listados_portal_a",
    #     "portal_scrapers/portal_a.py: _extraer_datos_tarjeta",
    # ],
    # TODO
}

RUTA_DB = str(CARPETA_SALIDA / f"historial_{SECTOR}.db")
NOMBRE_ARCHIVO_CONSOLIDADO = f"consolidado_{SECTOR}.xlsx"
UMBRAL_AUSENCIAS = _env_int("UMBRAL_AUSENCIAS", 3)
