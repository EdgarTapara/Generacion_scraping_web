"""
Scraper para RE/MAX Perú — HTML con clases propias (__propiedadgen,
__casventap, __casadat, __icofeat).

Toda la información proviene de la tarjeta de listado; puede haber
Cloudflare en la primera carga (primera vez en no-headless).
"""

import logging
import re

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from core.browser import BrowserManager
from core.limpieza import parsear_numero, parsear_entero

from sectores.inmobiliario.config import (
    generar_url_listado, MAX_PAGINAS_SEGURIDAD, TIMEOUT_ELEMENTO,
)

logger = logging.getLogger("scraping")


_TIPO_MAP = {
    "departamento": "departamento", "depa": "departamento", "flat": "departamento",
    "casa": "casa", "chalet": "casa",
    "terreno": "terreno", "lote": "terreno",
    "oficina": "oficina",
    "local": "local_comercial", "tienda": "local_comercial",
    "habitacion": "habitacion", "habitación": "habitacion",
}


def _parsear_tipo_desde_badge(badge_texto: str | None) -> str | None:
    if not badge_texto:
        return None
    t = badge_texto.lower()
    for clave, canonico in _TIPO_MAP.items():
        if clave in t:
            return canonico
    return None


def _parsear_distrito(casadat_loc: str | None) -> str | None:
    """'Arequipa, Arequipa, Paucarpata' → 'Paucarpata'."""
    if not casadat_loc:
        return None
    partes = [p.strip() for p in casadat_loc.split(",") if p.strip()]
    if not partes:
        return None
    return partes[-1]


def _parsear_features(features_txt_list: list[str]) -> dict:
    result: dict = {}
    for txt in features_txt_list:
        if not txt or ":" not in txt:
            continue
        etiqueta, _, valor = txt.partition(":")
        etiqueta = etiqueta.strip().lower()
        valor = valor.strip()
        if "terreno" in etiqueta:
            num = parsear_numero(valor)
            if num is not None and num > 0:
                result["area_total_m2"] = num
        elif "construida" in etiqueta:
            num = parsear_numero(valor)
            if num is not None and num > 0:
                result["area_construida_m2"] = num
        elif "ocupada" in etiqueta:
            if "area_construida_m2" not in result:
                num = parsear_numero(valor)
                if num is not None and num > 0:
                    result["area_construida_m2"] = num
        elif "pisos" in etiqueta:
            n = parsear_entero(valor)
            if n is not None and n > 0:
                result["pisos"] = n
        elif "habitaciones" in etiqueta or "dormitorios" in etiqueta:
            n = parsear_entero(valor)
            if n is not None:
                result["dormitorios"] = n
        elif "baño" in etiqueta or "bano" in etiqueta:
            n = parsear_entero(valor)
            if n is not None:
                result["banos"] = n
        elif "cochera" in etiqueta or "estacionamient" in etiqueta:
            n = parsear_entero(valor)
            if n is not None:
                result["estacionamientos"] = n
    return result


def _parsear_precio(li_items: list[str]) -> dict:
    """Lista [soles, '-', dolares] → dict de precios del pipeline."""
    result = {
        "precio": None, "moneda": None,
        "precio_secundario": None, "moneda_secundaria": None,
    }
    encontrados = []
    for raw in li_items:
        if not raw:
            continue
        t = raw.strip().upper().replace(" ", "")
        if t in ("-", "", "N/A"):
            continue
        moneda = None
        if t.startswith("USD"):
            moneda = "USD"
        elif t.startswith("S/.") or t.startswith("S/"):
            moneda = "PEN"
        # Anclar a dígito inicial para no capturar el '.' de "S/."
        numeros = re.findall(r"\d[\d.,]*", t)
        if not numeros:
            continue
        limpio = numeros[0].replace(",", "")
        try:
            monto = float(limpio)
        except ValueError:
            continue
        if monto <= 0:
            continue
        encontrados.append((monto, moneda or "PEN"))

    if encontrados:
        result["precio"] = encontrados[0][0]
        result["moneda"] = encontrados[0][1]
    if len(encontrados) > 1:
        result["precio_secundario"] = encontrados[1][0]
        result["moneda_secundaria"] = encontrados[1][1]
    return result


def _extraer_tarjeta(card) -> dict | None:
    try:
        enlace_el = card.find_element(By.CSS_SELECTOR, "div.__imagen a")
        href = enlace_el.get_attribute("href") or ""
        if href and not href.startswith("http"):
            href = "https://www.remax.pe" + href
        enlace = href
    except Exception:
        enlace = None
    if not enlace:
        return None

    titulo = None
    cod_anun = None
    try:
        spans = card.find_elements(By.CSS_SELECTOR, "div.__tipov span.base-badge")
        if spans:
            titulo = spans[0].text.strip() if spans[0].text else None
            if len(spans) > 1:
                cod_anun = spans[1].text.strip() or None
    except Exception:
        pass

    tipo_inmueble = _parsear_tipo_desde_badge(titulo)

    li_items = []
    try:
        lis = card.find_elements(By.CSS_SELECTOR, "div.__casventap ul li")
        li_items = [li.text.strip() for li in lis]
    except Exception:
        pass
    precio_data = _parsear_precio(li_items)
    precio_raw = " / ".join([x for x in li_items if x and x != "-"]) or None

    distrito = None
    anunciante = None
    try:
        h5s = card.find_elements(By.CSS_SELECTOR, "div.__casadat h5")
        if h5s:
            distrito = _parsear_distrito(h5s[0].text)
        if len(h5s) > 1:
            lineas = [x.strip() for x in h5s[1].text.splitlines() if x.strip()]
            if lineas:
                anunciante = lineas[0]
    except Exception:
        pass

    features_txt = []
    try:
        items = card.find_elements(By.CSS_SELECTOR, "div.__icofeat p")
        features_txt = [i.text.strip() for i in items if i.text]
    except Exception:
        pass
    feats = _parsear_features(features_txt)

    return {
        "enlace": enlace,
        "posting_id": cod_anun,
        "titulo_original": titulo,
        "tipo_inmueble": tipo_inmueble,
        "distrito": distrito,
        "ubicacion_raw": None,
        "precio_raw": precio_raw,
        "precio": precio_data["precio"],
        "moneda": precio_data["moneda"],
        "precio_secundario": precio_data["precio_secundario"],
        "moneda_secundaria": precio_data["moneda_secundaria"],
        "mantenimiento_raw": None,
        "mantenimiento": None,
        "fecha_publicacion_raw": None,
        "fecha_publicacion": None,
        "descripcion": None,
        "descripcion_dom": None,
        "anunciante": anunciante,
        "area_total_m2": feats.get("area_total_m2"),
        "area_construida_m2": feats.get("area_construida_m2"),
        "dormitorios": feats.get("dormitorios"),
        "banos": feats.get("banos"),
        "estacionamientos": feats.get("estacionamientos"),
        "pisos": feats.get("pisos"),
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
        url = generar_url_listado("remax", operacion, pagina)
        logger.info(f"  Pagina {pagina}: {url[:80]}...")

        driver = browser.navegar(url, tipo="listado")
        try:
            WebDriverWait(driver, TIMEOUT_ELEMENTO).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.__propiedadgen'))
            )
        except Exception:
            logger.info(f"  No se encontraron anuncios en pagina {pagina}. Fin.")
            break

        cards = driver.find_elements(By.CSS_SELECTOR, 'div.__propiedadgen')
        if not cards:
            logger.info(f"  Sin anuncios en pagina {pagina}. Fin.")
            break

        logger.info(f"  Encontrados {len(cards)} anuncios")
        for c in cards:
            dato = _extraer_tarjeta(c)
            if dato:
                resultados.append(dato)
        pagina += 1

    logger.info(f"  Total anuncios extraidos (REMAX): {len(resultados)}")
    return resultados
