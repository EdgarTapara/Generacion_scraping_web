"""Configuración del sector inmobiliario — EJEMPLO ILUSTRATIVO.

⚠️ Este sector NO es producción. La metodología que demuestra (composición
de `core/` en un pipeline completo) sí es real, pero el scraper productivo
de portales inmobiliarios vive en `../../INMOBILIARIA/v1-portales-web/` y se
mantiene aparte. Este ejemplo se reduce a UN tipo de portal (Navent:
Urbania / AdondeVivir) para ser legible y testeable sin red.

Si mejoras producción, NO esperes que este ejemplo se sincronice solo:
es una demostración congelada de cómo se arma un sector sobre `core/`.
"""

import os

from dotenv import load_dotenv

load_dotenv()

SECTOR = "inmobiliario"

# --- API DeepSeek (enriquecimiento IA, opcional) ---
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
DEEPSEEK_MODEL_2 = os.getenv("DEEPSEEK_MODEL_2", "deepseek-v4-pro")
BCRP_EJECUTOR = os.getenv("BCRP_EJECUTOR", "desconocido")

# --- Portales del ejemplo: ambos son Navent (misma estrategia) ---
PORTALES_SOPORTADOS = ["urbania", "adondevivir"]
OPERACIONES = ["alquiler", "venta"]

URLS = {
    "urbania": {
        "alquiler": "https://urbania.pe/buscar/alquiler-de-propiedades-en-arequipa?page={pagina}&sort=more_recent",
        "venta": "https://urbania.pe/buscar/venta-de-propiedades-en-arequipa?page={pagina}&sort=more_recent",
        "base": "https://urbania.pe",
    },
    "adondevivir": {
        "alquiler": {
            "pagina_1": "https://www.adondevivir.com/inmuebles-en-alquiler-en-arequipa-ordenado-por-fechaonline-descendente.html",
            "pagina_n": "https://www.adondevivir.com/inmuebles-en-alquiler-en-arequipa-ordenado-por-fechaonline-descendente-pagina-{pagina}.html",
        },
        "venta": {
            "pagina_1": "https://www.adondevivir.com/inmuebles-en-venta-en-arequipa-ordenado-por-fechaonline-descendente.html",
            "pagina_n": "https://www.adondevivir.com/inmuebles-en-venta-en-arequipa-ordenado-por-fechaonline-descendente-pagina-{pagina}.html",
        },
    },
}

# --- Parámetros de scraping ---
DEFAULT_NUM_PAGINAS = 1
MAX_PAGINAS_SEGURIDAD = 25
DELAY_LISTADO = (2.0, 4.0)
DELAY_DETALLE = (2.0, 5.0)
TIMEOUT_ELEMENTO = 8

# --- Salidas ---
CARPETA_SALIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resultados")
CARPETA_LOGS = os.path.join(CARPETA_SALIDA, "logs")
CARPETA_SNAPSHOTS_FRONTEND = os.path.join(CARPETA_SALIDA, "snapshots_frontend")
CARPETA_REPORTES_MANTENIMIENTO = os.path.join(
    CARPETA_SALIDA, "reportes_mantenimiento_frontend"
)
os.makedirs(CARPETA_SALIDA, exist_ok=True)

# --- Historial ---
RUTA_DB = os.path.join(CARPETA_SALIDA, "historial_inmobiliario.db")
UMBRAL_AUSENCIAS = 3  # corridas quincenales consecutivas

# Corridas degradadas: aisladas aquí, NUNCA tocan el historial.
CARPETA_DEGRADADAS = os.path.join(CARPETA_SALIDA, "degradadas")

# Base de referencia NSE (urbanización → NSE). NO se versiona en este
# ejemplo: si el archivo no existe, la clasificación NSE simplemente se
# omite (así corre offline). En producción apunta a la base real.
RUTA_BASE_NSE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "datos", "base_nse_arequipa.xlsx"
)

# --- Compuerta de calidad (core.calidad.evaluar_cobertura) ---
# Umbral de cobertura mínima por campo, por estrategia. Si no se alcanza,
# la corrida se marca degradada y NO toca el historial.
UMBRALES_CALIDAD = {
    "navent": {
        "enlace": 0.99,
        "precio": 0.70,
        "distrito": 0.70,
        "descripcion": 0.50,
    },
}

# Señales instrumentales: baja cobertura aquí es advertencia, no bloqueo
# (el dato puede no venir en Redux y eso no invalida la corrida).
SENALES_INSTRUMENTALES_NAVENT = ("area_total_m2", "latitud", "longitud", "anunciante")

# --- Mapa portal → funciones reales (lo usa el reporte de mantenimiento) ---
# Declarado por el sector; core no lo hardcodea.
CODIGO_POR_PORTAL = {
    "urbania": ["portal_scrapers/navent.py: scrape_listados / _extraer_redux_state"],
    "adondevivir": ["portal_scrapers/navent.py: scrape_listados / _extraer_redux_state"],
}


def generar_nombre_archivo_historico(portal: str, operacion: str) -> str:
    return f"{portal}_{operacion}_historico.xlsx"


def generar_url_listado(portal: str, operacion: str, pagina: int) -> str:
    if portal == "urbania":
        return URLS["urbania"][operacion].format(pagina=pagina)
    if portal == "adondevivir":
        urls = URLS["adondevivir"][operacion]
        return urls["pagina_1"] if pagina == 1 else urls["pagina_n"].format(pagina=pagina)
    raise ValueError(f"Portal no soportado en este ejemplo: {portal}")
