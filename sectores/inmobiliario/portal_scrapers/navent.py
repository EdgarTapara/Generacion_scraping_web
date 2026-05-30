"""
Scraper para portales Navent: Urbania y Adonde Vivir (misma plataforma).

Estrategia primaria: parsear el Redux state `window.__NEXT_DATA__` con
4 métodos en cascada. Fallback DOM-only con selectores `data-qa` estables.

Migrado de v1/scraper.py (scrape_listados_navent + helpers Redux).
"""

import json
import logging
import re

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from core.browser import BrowserManager
from core.browser.selectors import buscar_texto_rapido
from core.calidad import nuevo_diagnostico_scraping
from core.snapshots import guardar_snapshot_html
from sectores.inmobiliario.config import (
    generar_url_listado, MAX_PAGINAS_SEGURIDAD, TIMEOUT_ELEMENTO,
)
from sectores.inmobiliario.modelos import DISTRITOS_NORM
from sectores.inmobiliario.utils_sector import (
    mapear_main_features,
    extraer_precio_redux,
    extraer_distrito_redux,
    parsear_features_tarjeta,
)

logger = logging.getLogger("scraping")


# =====================================================================
# Selectores de tarjetas de listado
# =====================================================================

SELECTORES_TARJETA = [
    (By.CSS_SELECTOR, '[data-qa="posting PROPERTY"]'),
    (By.XPATH, '//div[contains(@class,"postingCardLayout-module__posting-card-layout")]'),
    (By.XPATH, '//div[contains(@class,"postingCard")]'),
]


def _encontrar_tarjetas(driver):
    for by_type, selector in SELECTORES_TARJETA:
        try:
            WebDriverWait(driver, TIMEOUT_ELEMENTO).until(
                EC.presence_of_element_located((by_type, selector))
            )
            tarjetas = driver.find_elements(by_type, selector)
            if tarjetas:
                return tarjetas
        except Exception:
            continue
    return []


def _extraer_enlace_tarjeta(tarjeta, portal: str) -> str | None:
    # Método 1: atributo data-to-posting
    try:
        path = tarjeta.get_attribute("data-to-posting")
        if path:
            if portal == "urbania":
                return "https://urbania.pe" + path
            if portal == "adondevivir":
                return "https://www.adondevivir.com" + path
    except Exception:
        pass
    # Método 2: primer <a>
    try:
        elem = tarjeta.find_element(By.XPATH, ".//a")
        href = elem.get_attribute("href")
        if href:
            return href
    except Exception:
        pass
    return None


def _extraer_anunciante_dom(tarjeta) -> str | None:
    """Anunciante desde el logo del publisher (slug en src) o texto del bloque."""
    for selector in (
        '[data-qa="POSTING_CARD_PUBLISHER"]',
        '[data-qa="POSTING_CARD_PUBLISHER_DEV"]',
    ):
        try:
            img = tarjeta.find_element(By.CSS_SELECTOR, selector)
            src = img.get_attribute("src") or ""
            match = re.search(
                r'/logo_([a-z0-9\-\.]+?)_\d+\.(?:jpg|jpeg|png|webp)',
                src, re.IGNORECASE,
            )
            if match:
                slug = match.group(1)
                nombre = slug.replace("-", " ").replace(".", ".").strip()
                partes = []
                for palabra in nombre.split():
                    if "." in palabra and len(palabra) <= 10:
                        partes.append(palabra.upper())
                    else:
                        partes.append(palabra.capitalize())
                return " ".join(partes)
        except Exception:
            continue

    for selector in (
        '[class*="postingPublisher-module__posting-publisher"]',
        '[class*="postingPublisher"]',
    ):
        try:
            elem = tarjeta.find_element(By.CSS_SELECTOR, selector)
            texto = elem.text.strip()
            if texto and 3 <= len(texto) <= 100:
                return texto
        except Exception:
            continue
    return None


def _extraer_datos_tarjeta(tarjeta, portal: str) -> dict | None:
    enlace = _extraer_enlace_tarjeta(tarjeta, portal)
    if not enlace:
        return None

    posting_id = None
    try:
        posting_id = tarjeta.get_attribute("data-id")
    except Exception:
        pass

    precio_raw = buscar_texto_rapido(tarjeta, By.CSS_SELECTOR, '[data-qa="POSTING_CARD_PRICE"]')
    features_raw = buscar_texto_rapido(tarjeta, By.CSS_SELECTOR, '[data-qa="POSTING_CARD_FEATURES"]')
    features = parsear_features_tarjeta(features_raw)
    descripcion = buscar_texto_rapido(tarjeta, By.CSS_SELECTOR, '[data-qa="POSTING_CARD_DESCRIPTION"]')
    mantenimiento_raw = buscar_texto_rapido(tarjeta, By.CSS_SELECTOR, '[data-qa="expensas"]')
    fecha_raw = buscar_texto_rapido(
        tarjeta, By.CSS_SELECTOR,
        '[class*="postingCard-module__posting-antiquity"]',
    )
    ubicacion_raw = buscar_texto_rapido(tarjeta, By.CSS_SELECTOR, '[data-qa="POSTING_CARD_LOCATION"]')
    anunciante_dom = _extraer_anunciante_dom(tarjeta)

    return {
        "enlace": enlace,
        "posting_id": posting_id,
        "precio_raw": precio_raw,
        "features_raw": features_raw,
        "descripcion_dom": descripcion,
        "mantenimiento_raw": mantenimiento_raw,
        "fecha_publicacion_raw": fecha_raw,
        "ubicacion_raw": ubicacion_raw,
        "anunciante_dom": anunciante_dom,
        **features,
    }


# =====================================================================
# Redux state — extracción en cascada (4 métodos)
# =====================================================================

def _indexar_postings(postings: list) -> dict[str, dict]:
    indexed = {}
    for p in postings:
        if not isinstance(p, dict):
            continue
        pid = p.get("postingId") or p.get("id")
        if pid is not None:
            indexed[str(pid)] = p
    return indexed


def _buscar_list_postings(obj, depth: int = 0):
    if depth > 15:
        return None
    if isinstance(obj, dict):
        if "listPostings" in obj:
            val = obj["listPostings"]
            if isinstance(val, list) and val:
                return val
        for v in obj.values():
            result = _buscar_list_postings(v, depth + 1)
            if result is not None:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = _buscar_list_postings(item, depth + 1)
            if result is not None:
                return result
    return None


def _extraer_redux_state(driver) -> dict[str, dict]:
    # Método 0: execute_script
    try:
        next_data = driver.execute_script("return window.__NEXT_DATA__")
        if next_data and isinstance(next_data, dict):
            postings = _buscar_list_postings(next_data)
            if postings:
                indexed = _indexar_postings(postings)
                if indexed:
                    logger.debug(f"Redux via window.__NEXT_DATA__: {len(indexed)} postings")
                    return indexed
    except Exception as e:
        logger.debug(f"execute_script __NEXT_DATA__ no disponible: {e}")

    try:
        html = driver.page_source
    except Exception as e:
        logger.debug(f"No se pudo leer page_source: {e}")
        return {}
    if not html:
        return {}

    # Método 1: tag __NEXT_DATA__
    m = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE,
    )
    if m:
        try:
            next_data = json.loads(m.group(1))
            postings = _buscar_list_postings(next_data)
            if postings:
                indexed = _indexar_postings(postings)
                if indexed:
                    return indexed
        except Exception:
            pass

    # Método 2: otros <script type="application/json">
    for m in re.finditer(
        r'<script[^>]+type=["\']application/json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = json.loads(m.group(1))
            postings = _buscar_list_postings(data)
            if postings:
                indexed = _indexar_postings(postings)
                if indexed:
                    return indexed
        except Exception:
            continue

    # Método 3: bracket balancing
    if '"listPostings"' not in html:
        logger.warning("listPostings no encontrado en ningun script ni en el HTML.")
        return {}

    marker = '"listPostings"'
    start = 0
    while True:
        pos = html.find(marker, start)
        if pos == -1:
            break
        start = pos + 1

        i = pos + len(marker)
        while i < len(html) and html[i] in (" ", "\t", "\n", "\r", ":"):
            i += 1
        if i >= len(html) or html[i] != "[":
            continue

        depth = 0
        in_str = False
        esc = False
        j = i
        while j < len(html):
            ch = html[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
                    if depth == 0:
                        break
            j += 1

        if depth != 0:
            continue

        try:
            postings = json.loads(html[i:j + 1])
            if isinstance(postings, list) and postings:
                indexed = _indexar_postings(postings)
                if indexed:
                    return indexed
        except json.JSONDecodeError:
            continue

    logger.warning("Redux state: listPostings encontrado pero no parseable.")
    return {}


# =====================================================================
# Normalización y fusión Redux + DOM
# =====================================================================

_REAL_ESTATE_MAP = {
    "departamento": "departamento", "departamentos": "departamento",
    "apartamento": "departamento", "apartamentos": "departamento",
    "casa": "casa", "casas": "casa", "chalet": "casa",
    "local": "local_comercial", "locales": "local_comercial",
    "local comercial": "local_comercial", "locales comerciales": "local_comercial",
    "tienda": "local_comercial",
    "oficina": "oficina", "oficinas": "oficina",
    "terreno": "terreno", "terrenos": "terreno",
    "lote": "terreno", "lotes": "terreno",
    "habitacion": "habitacion", "habitaciones": "habitacion", "cuarto": "habitacion",
}


def _normalizar_tipo_inmueble(nombre: str | None) -> str | None:
    if not nombre:
        return None
    clave = str(nombre).strip().lower()
    if clave in _REAL_ESTATE_MAP:
        return _REAL_ESTATE_MAP[clave]
    for k, v in _REAL_ESTATE_MAP.items():
        if k in clave:
            return v
    return None


def fusionar_con_redux(dato_dom: dict, posting: dict, operacion: str) -> dict:
    """Completa el dict extraido del DOM con los datos del Redux state."""
    if not posting:
        return dato_dom

    price_ops = posting.get("priceOperationTypes")
    if price_ops:
        precios = extraer_precio_redux(price_ops, operacion)
        if precios.get("precio") is not None:
            dato_dom.update(precios)

    expenses = posting.get("expenses")
    if isinstance(expenses, dict):
        amount = expenses.get("amount")
        if amount is not None:
            try:
                dato_dom["mantenimiento"] = float(amount)
            except (ValueError, TypeError):
                pass

    main = posting.get("mainFeatures")
    if main:
        for k, v in mapear_main_features(main).items():
            dato_dom[k] = v

    publisher = posting.get("publisher")
    if isinstance(publisher, dict):
        name = publisher.get("name")
        if name:
            dato_dom["anunciante"] = str(name).strip()

    real_estate = posting.get("realEstateType")
    if isinstance(real_estate, dict):
        tipo = _normalizar_tipo_inmueble(real_estate.get("name"))
        if tipo:
            dato_dom["tipo_inmueble"] = tipo

    posting_location = posting.get("postingLocation")
    if posting_location:
        ubic = extraer_distrito_redux(posting_location, DISTRITOS_NORM)
        if ubic.get("distrito"):
            dato_dom["distrito"] = ubic["distrito"]
        if ubic.get("address_name"):
            dato_dom["address_name"] = ubic["address_name"]
        if ubic.get("zone_name"):
            dato_dom["zone_name"] = ubic["zone_name"]

    desc_norm = posting.get("descriptionNormalized") or posting.get("description")
    if desc_norm:
        dato_dom["descripcion"] = str(desc_norm).strip()
    elif dato_dom.get("descripcion_dom"):
        dato_dom["descripcion"] = dato_dom["descripcion_dom"]

    titulo_orig = posting.get("title")
    if titulo_orig:
        dato_dom["titulo_original"] = str(titulo_orig).strip()

    return dato_dom


# =====================================================================
# Función pública
# =====================================================================

def scrape_listados(
    browser: BrowserManager,
    portal: str,
    operacion: str,
    num_paginas: int,
    diagnostico: dict | None = None,
    carpeta_snapshots: str | None = None,
) -> list[dict]:
    """Recorre páginas de listado Navent y extrae datos fusionando Redux+DOM.

    Patrón actual del framework:
      - Construye/actualiza un `diagnostico` estándar (core.calidad) in-place.
      - Captura un snapshot HTML por página (core.snapshots) para que la IA
        de mantenimiento pueda reparar el portal si el frontend cambia.
    """
    if diagnostico is None:
        diagnostico = nuevo_diagnostico_scraping(portal, operacion, "navent")

    resultados = []
    total_matcheados = 0
    total_con_posting = 0
    pagina = 1

    while pagina <= num_paginas and pagina <= MAX_PAGINAS_SEGURIDAD:
        url = generar_url_listado(portal, operacion, pagina)
        logger.info(f"  Pagina {pagina}: {url[:80]}...")

        driver = browser.navegar(url, tipo="listado")
        diagnostico["paginas_visitadas"] += 1
        # Snapshot por página (best-effort, nunca lanza).
        if carpeta_snapshots:
            guardar_snapshot_html(
                driver, portal, operacion, pagina, "listado",
                carpeta_snapshots, diagnostico,
            )

        tarjetas = _encontrar_tarjetas(driver)

        if not tarjetas:
            try:
                logger.warning(
                    f"  [{portal.upper()}] Sin tarjetas en pagina {pagina} | "
                    f"titulo='{driver.title}' | url={driver.current_url[:80]} | "
                    f"html={len(driver.page_source)} chars"
                )
            except Exception:
                pass
            logger.info(f"  No se encontraron anuncios en pagina {pagina}. Fin.")
            break

        diagnostico["paginas_con_tarjetas"] += 1
        diagnostico["tarjetas_totales"] += len(tarjetas)
        logger.info(f"  Encontrados {len(tarjetas)} anuncios")

        redux = _extraer_redux_state(driver)
        if redux:
            diagnostico["redux_paginas_ok"] += 1
            logger.info(f"  Redux state parseado: {len(redux)} postings")
        else:
            diagnostico["redux_paginas_fallidas"] += 1
            logger.warning("  Redux state no disponible; usando solo DOM como fallback.")

        datos_pagina = []
        matcheados = 0
        for tarjeta in tarjetas:
            dato = _extraer_datos_tarjeta(tarjeta, portal)
            if not dato:
                continue
            pid = dato.get("posting_id")
            posting = redux.get(str(pid)) if pid else None
            if posting:
                matcheados += 1
                dato = fusionar_con_redux(dato, posting, operacion)
            else:
                if not dato.get("descripcion") and dato.get("descripcion_dom"):
                    dato["descripcion"] = dato["descripcion_dom"]
            datos_pagina.append(dato)

        if redux:
            total_matcheados += matcheados
            total_con_posting += len(datos_pagina)
            logger.info(
                f"  Fusion Redux+DOM: {matcheados}/{len(datos_pagina)} postings matcheados"
            )

        resultados.extend(datos_pagina)
        pagina += 1

    diagnostico["postings_matcheados"] = total_matcheados
    if total_con_posting:
        diagnostico["ratio_match_redux_dom"] = total_matcheados / total_con_posting
    logger.info(f"  Total anuncios extraidos: {len(resultados)}")
    return resultados
