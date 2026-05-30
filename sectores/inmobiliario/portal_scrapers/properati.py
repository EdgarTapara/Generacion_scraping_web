"""
Scraper para Properati — HTML tradicional con selectores `data-test`.

Toda la información proviene de la tarjeta `<article class="snippet">`.
Sin fetch de página de detalle ni Redux.
"""

import logging
import re
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from core.browser import BrowserManager
from core.browser.selectors import buscar_texto_rapido
from core.limpieza import parsear_numero, parsear_entero

from sectores.inmobiliario.config import (
    generar_url_listado, MAX_PAGINAS_SEGURIDAD, TIMEOUT_ELEMENTO,
)

logger = logging.getLogger("scraping")


_TIPO_MAP = {
    "apartamento": "departamento", "apartamentos": "departamento",
    "departamento": "departamento", "departamentos": "departamento",
    "casa": "casa", "casas": "casa",
    "terreno": "terreno", "terrenos": "terreno", "lote": "terreno",
    "oficina": "oficina", "oficinas": "oficina",
    "local": "local_comercial", "locales": "local_comercial",
    "local comercial": "local_comercial",
    "habitacion": "habitacion", "habitación": "habitacion", "cuarto": "habitacion",
}


def _parsear_titulo(titulo: str) -> tuple[str | None, str | None]:
    """'Apartamento en Alquiler en Cayma' → ('departamento', 'Cayma')."""
    if not titulo:
        return (None, None)
    partes = [p.strip() for p in titulo.split(" en ")]
    tipo = _TIPO_MAP.get(partes[0].lower().strip()) if partes else None
    distrito = partes[-1].strip() if len(partes) >= 3 else None
    return (tipo, distrito)


def _parsear_precio(texto: str) -> dict:
    """'USD1,100' o 'S/.1,400' → dict de precio."""
    if not texto:
        return {"precio": None, "moneda": None}
    limpio = texto.strip().upper().replace(" ", "")
    moneda = None
    if limpio.startswith("USD") or limpio.startswith("US$") or limpio.startswith("$"):
        moneda = "USD"
    elif limpio.startswith("S/.") or limpio.startswith("S/"):
        moneda = "PEN"
    numeros = re.findall(r"[\d,]+", limpio)
    if not numeros:
        return {"precio": None, "moneda": moneda}
    try:
        monto = float(numeros[0].replace(",", ""))
        if monto <= 0:
            return {"precio": None, "moneda": moneda}
        return {"precio": monto, "moneda": moneda or "PEN"}
    except ValueError:
        return {"precio": None, "moneda": moneda}


def _extraer_fecha_publicada(texto: str | None) -> str | None:
    if not texto:
        return None
    t = texto.strip()
    if t.lower().startswith("publicado"):
        t = t[len("Publicado"):].strip()
    return t if t else None


def _parsear_fecha_absoluta(texto: str | None) -> str | None:
    """'25 feb. 2026' → '2026-02-25'."""
    if not texto:
        return None
    meses = {
        "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
        "jul": 7, "ago": 8, "set": 9, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
    }
    m = re.search(r"(\d{1,2})\s+([a-z]{3,4})\.?\s+(\d{4})", texto.lower())
    if not m:
        return None
    dia = int(m.group(1))
    mes = meses.get(m.group(2)[:3])
    anio = int(m.group(3))
    if not mes:
        return None
    try:
        return datetime(anio, mes, dia).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _extraer_tarjeta(art) -> dict | None:
    try:
        enlace = art.get_attribute("data-url")
    except Exception:
        enlace = None
    if not enlace:
        try:
            enlace = art.find_element(By.CSS_SELECTOR, "a.title").get_attribute("href")
        except Exception:
            enlace = None
    if not enlace:
        return None

    posting_id = None
    try:
        posting_id = art.get_attribute("data-idanuncio")
    except Exception:
        pass

    titulo_txt = buscar_texto_rapido(art, By.CSS_SELECTOR, 'a.title[data-test="snippet__title"]')
    precio_raw = buscar_texto_rapido(art, By.CSS_SELECTOR, 'div.price[data-test="snippet__price"]')
    location_raw = buscar_texto_rapido(art, By.CSS_SELECTOR, 'div.location[data-test="snippet__location"]')
    agency = buscar_texto_rapido(art, By.CSS_SELECTOR, 'span.agency__name[data-test="agency-name"]')
    fecha_raw = buscar_texto_rapido(art, By.CSS_SELECTOR, 'div.published-date[data-test="published-date"]')

    dorm_txt = buscar_texto_rapido(art, By.CSS_SELECTOR, 'span.properties__bedrooms[data-test="bedrooms-value"]')
    banos_txt = buscar_texto_rapido(art, By.CSS_SELECTOR, 'span.properties__bathrooms[data-test="full-bathrooms-value"]')
    area_txt = buscar_texto_rapido(art, By.CSS_SELECTOR, 'span.properties__area[data-test="area-value"]')
    cochera_txt = buscar_texto_rapido(art, By.CSS_SELECTOR, 'span[data-test="principal-amenity-value"]')

    dormitorios = parsear_entero(dorm_txt) if dorm_txt else None
    banos = parsear_entero(banos_txt) if banos_txt else None
    area = parsear_numero(area_txt) if area_txt else None
    estacionamientos = 1 if (cochera_txt and "cochera" in cochera_txt.lower()) else None

    tipo_inmueble, distrito_titulo = _parsear_titulo(titulo_txt or "")
    distrito = distrito_titulo or None
    if not distrito and location_raw:
        distrito = location_raw.split(",")[0].strip() or None

    precio_data = _parsear_precio(precio_raw or "")
    fecha_limpia = _extraer_fecha_publicada(fecha_raw)
    fecha_iso = _parsear_fecha_absoluta(fecha_limpia)

    return {
        "enlace": enlace,
        "posting_id": posting_id,
        "titulo_original": titulo_txt,
        "tipo_inmueble": tipo_inmueble,
        "distrito": distrito,
        "ubicacion_raw": location_raw,
        "precio_raw": precio_raw,
        "precio": precio_data["precio"],
        "moneda": precio_data["moneda"],
        "precio_secundario": None,
        "moneda_secundaria": None,
        "mantenimiento_raw": None,
        "mantenimiento": None,
        "fecha_publicacion_raw": fecha_limpia,
        "fecha_publicacion": fecha_iso,
        "descripcion": None,
        "descripcion_dom": None,
        "anunciante": agency,
        "area_total_m2": area,
        "area_construida_m2": None,
        "dormitorios": dormitorios,
        "banos": banos,
        "estacionamientos": estacionamientos,
        "antiguedad_anos": None,
        "zone_name": None,
        "address_name": None,
    }


def scrape_listados(
    browser: BrowserManager, operacion: str, num_paginas: int,
) -> list[dict]:
    resultados = []
    pagina = 1

    while pagina <= num_paginas and pagina <= MAX_PAGINAS_SEGURIDAD:
        url = generar_url_listado("properati", operacion, pagina)
        logger.info(f"  Pagina {pagina}: {url[:80]}...")

        driver = browser.navegar(url, tipo="listado")
        try:
            WebDriverWait(driver, TIMEOUT_ELEMENTO).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, 'article.snippet[data-url]')
                )
            )
        except Exception:
            logger.info(f"  No se encontraron anuncios en pagina {pagina}. Fin.")
            break

        articulos = driver.find_elements(By.CSS_SELECTOR, 'article.snippet[data-url]')
        if not articulos:
            logger.info(f"  Sin anuncios en pagina {pagina}. Fin.")
            break

        logger.info(f"  Encontrados {len(articulos)} anuncios")
        for art in articulos:
            dato = _extraer_tarjeta(art)
            if dato:
                resultados.append(dato)
        pagina += 1

    logger.info(f"  Total anuncios extraidos (Properati): {len(resultados)}")
    return resultados
