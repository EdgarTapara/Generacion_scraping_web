"""Configuración del sector inmobiliario. Migrado de v1/config.py con pequeños ajustes:

  - Los delays se pasan a BrowserManager vía constructor (no a un util global).
  - La carpeta de logs deriva de CARPETA_SALIDA (antes vivía al lado de utils.py).
"""

import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# --- API DeepSeek ---
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
DEEPSEEK_MODEL_2 = os.getenv("DEEPSEEK_MODEL_2", "deepseek-v4-pro")

# --- Ejecutor (se persiste como metadato en cada anuncio) ---
BCRP_EJECUTOR = os.getenv("BCRP_EJECUTOR", "desconocido")

# --- URLs por portal y operación (idénticas a v1) ---
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
    "properati": {
        "alquiler": {
            "pagina_1": "https://www.properati.com.pe/s/arequipa/alquiler/?sort=published_on_desc",
            "pagina_n": "https://www.properati.com.pe/s/arequipa/alquiler/{pagina}/?sort=published_on_desc",
        },
        "venta": {
            "pagina_1": "https://www.properati.com.pe/s/arequipa/venta/?sort=published_on_desc",
            "pagina_n": "https://www.properati.com.pe/s/arequipa/venta/{pagina}/?sort=published_on_desc",
        },
        "base": "https://www.properati.com.pe",
    },
    "remax": {
        "alquiler": (
            "https://www.remax.pe/web/search/all/propertys/list/"
            "?coordinates__exclude=&range__exclude=2.0"
            "&ubication_name__exclude=Arequipa%2C+Arequipa"
            "&code__in=&type__in=&contract__type=rent"
            "&contract__price_money__exclude=S%2F."
            "&contract__price__range=&antiquity__range=&floors__range="
            "&bedrooms__range=&bathrooms__range=&medium_bathrooms__range="
            "&parking_lots__range=&departament__in=4&province__in=35"
        ),
        "venta": (
            "https://www.remax.pe/web/search/all/propertys/list/"
            "?coordinates__exclude=&range__exclude=2.0"
            "&ubication_name__exclude=Arequipa%2C+Arequipa"
            "&code__in=&type__in=&contract__type=sale"
            "&contract__price_money__exclude=S%2F."
            "&contract__price__range=&antiquity__range=&floors__range="
            "&bedrooms__range=&bathrooms__range=&medium_bathrooms__range="
            "&parking_lots__range=&departament__in=4&province__in=35"
        ),
        "base": "https://www.remax.pe",
    },
}

PORTALES_SOPORTADOS = ["urbania", "adondevivir", "properati", "remax"]

# --- Parámetros de scraping ---
DEFAULT_NUM_PAGINAS = 1
MAX_PAGINAS_SEGURIDAD = 25
DELAY_LISTADO = (2.0, 4.0)
DELAY_DETALLE = (2.0, 5.0)
TIMEOUT_ELEMENTO = 8

# --- Salidas ---
CARPETA_SALIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resultados")
CARPETA_LOGS = os.path.join(CARPETA_SALIDA, "logs")
os.makedirs(CARPETA_SALIDA, exist_ok=True)

# --- Historial ---
RUTA_DB = os.path.join(CARPETA_SALIDA, "historial_inmobiliario.db")
UMBRAL_AUSENCIAS = 3  # corridas quincenales consecutivas


def generar_nombre_archivo_historico(portal: str, operacion: str) -> str:
    return f"{portal}_{operacion}_historico.xlsx"


def generar_nombre_archivo(portal: str, operacion: str) -> str:
    """Backup con fecha en el nombre (legacy, raro)."""
    fecha = datetime.now().strftime("%d-%m-%Y")
    return f"{portal}_{operacion}_extraccion_{fecha}.xlsx"


def generar_url_listado(portal: str, operacion: str, pagina: int) -> str:
    if portal == "urbania":
        return URLS["urbania"][operacion].format(pagina=pagina)
    if portal == "adondevivir":
        urls = URLS["adondevivir"][operacion]
        return urls["pagina_1"] if pagina == 1 else urls["pagina_n"].format(pagina=pagina)
    if portal == "properati":
        urls = URLS["properati"][operacion]
        return urls["pagina_1"] if pagina == 1 else urls["pagina_n"].format(pagina=pagina)
    if portal == "remax":
        base = URLS["remax"][operacion]
        return base if pagina == 1 else f"{base}&page={pagina}"
    raise ValueError(f"Portal no soportado: {portal}")
