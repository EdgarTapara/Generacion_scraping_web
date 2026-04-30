"""
Helpers específicos del sector inmobiliario.

Lo genuinamente genérico vive en `core/limpieza/`; aquí queda lo que no
tendría sentido en otros sectores: parsing del Redux state de portales
inmobiliarios (CFT codes, priceOperationTypes, postingLocation), y
extracción de campos desde descripciones de anuncios inmobiliarios
(pisos, antigüedad, medio baño, ubicación referencial).

Migrado de v1/utils.py (sin la parte de BrowserManager / logging que
subió a core).
"""

import re

from core.limpieza import parsear_numero, parsear_entero


# =====================================================================
# Redux state — parseo para portales Navent (Urbania / Adondevivir)
# =====================================================================

# CFT = Custom Feature Type en el esquema Navent. Mapeo código → columna v1.2.
_CFT_MAP = {
    "CFT100": "area_total_m2",
    "CFT101": "area_construida_m2",
    "CFT2": "dormitorios",
    "CFT3": "banos",
    "CFT7": "estacionamientos",
    "CFT5": "antiguedad_anos",
}


def mapear_main_features(main_features: dict) -> dict:
    """Traduce el dict `mainFeatures` del Redux al esquema interno.

    Input:  {"CFT100": {"value": "247"}, "CFT2": {"value": "3"}, ...}
    Output: {"area_total_m2": 247.0, "dormitorios": 3, ...}
    """
    result: dict = {}
    if not isinstance(main_features, dict):
        return result

    for cft_key, target in _CFT_MAP.items():
        entry = main_features.get(cft_key)
        if not isinstance(entry, dict):
            continue
        value = entry.get("value")
        if value is None or value == "":
            continue

        if target in ("area_total_m2", "area_construida_m2"):
            num = parsear_numero(str(value))
            if num is not None and num > 0:
                result[target] = num
        else:
            num = parsear_entero(str(value))
            if num is not None and num >= 0:
                result[target] = num
    return result


def extraer_precio_redux(price_operation_types: list, operacion: str) -> dict:
    """Extrae precio primario y secundario desde `priceOperationTypes`.

    Filtra por tipo de operación (alquiler/venta) y devuelve el dict del
    pipeline: precio + moneda + precio_secundario + moneda_secundaria.
    """
    from core.limpieza import moneda_a_iso

    result = {
        "precio": None,
        "moneda": None,
        "precio_secundario": None,
        "moneda_secundaria": None,
    }
    if not isinstance(price_operation_types, list) or not price_operation_types:
        return result

    operacion_norm = operacion.lower().strip()
    match_op = {"alquiler": "alquiler", "venta": "venta"}.get(operacion_norm)

    prices = None
    for pot in price_operation_types:
        if not isinstance(pot, dict):
            continue
        op_name = (pot.get("operationType", {}) or {}).get("name", "").lower()
        if match_op and match_op in op_name:
            prices = pot.get("prices")
            break

    if not prices and price_operation_types:
        primer = price_operation_types[0]
        if isinstance(primer, dict):
            prices = primer.get("prices")

    if not isinstance(prices, list):
        return result

    monedas_vistas = []
    for p in prices:
        if not isinstance(p, dict):
            continue
        amount = p.get("amount")
        currency = p.get("currency")
        if amount is None:
            continue
        try:
            monto = float(amount)
        except (ValueError, TypeError):
            continue
        if monto <= 0:
            continue
        iso = moneda_a_iso(str(currency)) if currency else None
        if not iso:
            continue
        monedas_vistas.append((monto, iso))

    if not monedas_vistas:
        return result

    result["precio"] = monedas_vistas[0][0]
    result["moneda"] = monedas_vistas[0][1]
    if len(monedas_vistas) > 1:
        result["precio_secundario"] = monedas_vistas[1][0]
        result["moneda_secundaria"] = monedas_vistas[1][1]
    return result


def extraer_distrito_redux(posting_location: dict, distritos_norm: set) -> dict:
    """Recorre la jerarquía `postingLocation.location` extrayendo distrito,
    zone_name (nodo más específico que no es distrito) y address_name
    (solo si visibility == "EXACT").
    """
    result = {"distrito": None, "zone_name": None, "address_name": None}
    if not isinstance(posting_location, dict):
        return result

    address = posting_location.get("address") or {}
    if isinstance(address, dict):
        visibility = str(address.get("visibility") or "").upper()
        name = address.get("name")
        if name and visibility == "EXACT":
            result["address_name"] = str(name).strip()

    nodo = posting_location.get("location")
    zone_candidata = None
    while isinstance(nodo, dict):
        nombre = nodo.get("name")
        if nombre:
            nombre_str = str(nombre).strip()
            nombre_norm = nombre_str.lower()
            es_distrito = nombre_norm in distritos_norm
            if es_distrito:
                if result["distrito"] is None:
                    result["distrito"] = nombre_str.title()
            else:
                if nombre_norm not in ("arequipa", "peru", "perú"):
                    if zone_candidata is None:
                        zone_candidata = nombre_str
        nodo = nodo.get("parent")

    if zone_candidata:
        result["zone_name"] = zone_candidata
    return result


# =====================================================================
# Parsers desde descripción libre (fallback cuando Redux no trae el dato)
# =====================================================================

def parsear_features_tarjeta(texto_features: str | None) -> dict:
    """Parsea '247 m² tot. 3 dorm. 4 baños 1 estac.' de la tarjeta del listado."""
    result: dict = {}
    if not texto_features:
        return result

    texto = texto_features.lower()

    match = re.search(r'([\d,.]+)\s*m[²2]\s*tot', texto)
    if match:
        result["area_total_m2"] = parsear_numero(match.group(1))

    match = re.search(r'([\d,.]+)\s*m[²2]\s*(?:cub|const)', texto)
    if match:
        result["area_construida_m2"] = parsear_numero(match.group(1))

    match = re.search(r'(\d+)\s*(?:dorm|hab)', texto)
    if match:
        result["dormitorios"] = int(match.group(1))

    match = re.search(r'(\d+)\s*ba[ñn]', texto)
    if match:
        result["banos"] = int(match.group(1))

    match = re.search(r'(\d+)\s*(?:estac|coch)', texto)
    if match:
        result["estacionamientos"] = int(match.group(1))
    return result


def extraer_pisos_descripcion(descripcion: str | None) -> int | None:
    """Número de pisos del inmueble (prioritario) o piso donde está el depa (fallback)."""
    if not isinstance(descripcion, str) or not descripcion.strip():
        return None

    texto = descripcion.lower()

    patrones_total = [
        r'(?:casa|edificio|vivienda|inmueble|propiedad|condominio)\s+de\s+(\d+)\s+pisos?',
        r'de\s+(\d+)\s+pisos?\s+(?:y|con|\.)',
        r'consta\s+de\s+(\d+)\s+pisos?',
        r'(\d+)\s+pisos?\s+(?:con|y)',
        r'(\d+)\s+niveles?',
    ]
    for patron in patrones_total:
        match = re.search(patron, texto)
        if match:
            try:
                n = int(match.group(1))
                if 1 <= n <= 60:
                    return n
            except ValueError:
                continue

    _cardinal = {
        "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4,
        "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    }
    match = re.search(
        r'(?:casa|edificio|vivienda|inmueble|propiedad|condominio)\s+de\s+'
        r'(un|uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\s+pisos?',
        texto,
    )
    if match:
        return _cardinal.get(match.group(1))

    _ordinal = {
        "primer": 1, "primero": 1, "1er": 1, "1ro": 1,
        "segundo": 2, "2do": 2,
        "tercer": 3, "tercero": 3, "3er": 3, "3ro": 3,
        "cuarto": 4, "4to": 4,
        "quinto": 5, "5to": 5,
        "sexto": 6, "6to": 6,
        "septimo": 7, "sétimo": 7, "7mo": 7,
        "octavo": 8, "8vo": 8,
        "noveno": 9, "9no": 9,
        "decimo": 10, "décimo": 10, "10mo": 10,
    }
    for palabra, n in _ordinal.items():
        if re.search(rf'\b{palabra}\s+piso\b', texto):
            return n

    match = re.search(
        r'(?:en\s+el\s+|ubicado\s+en\s+el\s+)(\d+)(?:°|º|er|do|ro|to|mo|vo|no)?\s+piso',
        texto,
    )
    if match:
        try:
            n = int(match.group(1))
            if 1 <= n <= 60:
                return n
        except ValueError:
            pass
    return None


def extraer_medio_banos_descripcion(descripcion: str | None) -> int | None:
    """'2 medios baños', 'medio baño', '½ baño', 'baño de visitas'."""
    if not isinstance(descripcion, str) or not descripcion.strip():
        return None

    texto = descripcion.lower()

    match = re.search(r'(\d+)\s+medios?\s+ba[ñn]os?', texto)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass

    if re.search(r'\bun(?:a|o)?\s+medio\s+ba[ñn]o', texto):
        return 1
    if re.search(r'(?:medio|½|1/2)\s+ba[ñn]o', texto):
        return 1
    if re.search(r'ba[ñn]o\s+(?:de\s+)?(?:visita|social)', texto):
        return 1
    return None


def extraer_antiguedad_descripcion(descripcion: str | None) -> int | None:
    """Antigüedad en años desde la descripción. 'a estrenar' → 0."""
    if not isinstance(descripcion, str) or not descripcion.strip():
        return None

    texto = descripcion.lower()

    if re.search(r'\b(a\s+estrenar|estreno|nuevo|nueva|sin\s+estrenar)\b', texto):
        return 0

    match = re.search(r'(\d+)\s*a[ñn]os?\s+de\s+antig[üu]edad', texto)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass

    match = re.search(r'antig[üu]edad\s+de\s+(\d+)', texto)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    return None


def extraer_ubicacion_referencial_regex(descripcion: str | None) -> str | None:
    """Fallback determinístico: Av./Calle/Jr./Mz./Urb. desde la descripción."""
    if not descripcion:
        return None

    texto = descripcion[:500]

    patrones = [
        r'\b(Av\.?\s+[\wñÑáéíóúÁÉÍÓÚ\s\-]{3,60})',
        r'\b(Avenida\s+[\wñÑáéíóúÁÉÍÓÚ\s\-]{3,60})',
        r'\b(Calle\s+[\wñÑáéíóúÁÉÍÓÚ\s\-]{3,60})',
        r'\b(Ca\.\s+[\wñÑáéíóúÁÉÍÓÚ\s\-]{3,60})',
        r'\b(Jr\.?\s+[\wñÑáéíóúÁÉÍÓÚ\s\-]{3,60})',
        r'\b(Jir[óo]n\s+[\wñÑáéíóúÁÉÍÓÚ\s\-]{3,60})',
        r'\b(Pasaje\s+[\wñÑáéíóúÁÉÍÓÚ\s\-]{3,60})',
        r'\b(Pje\.?\s+[\wñÑáéíóúÁÉÍÓÚ\s\-]{3,60})',
        r'\b(Psje\.?\s+[\wñÑáéíóúÁÉÍÓÚ\s\-]{3,60})',
        r'\b(Mz\.?\s+[\w\-]{1,20}[^.,\n]{0,40})',
        r'\b(Manzana\s+[\w\-]{1,20}[^.,\n]{0,40})',
        r'\b(Urb\.?\s+[\wñÑáéíóúÁÉÍÓÚ\s\-]{3,60})',
    ]

    for patron in patrones:
        match = re.search(patron, texto, re.IGNORECASE)
        if match:
            raw = match.group(1).strip()
            raw = re.split(r'[,\n]', raw)[0].strip()
            raw = re.sub(r'\s+', ' ', raw)
            if len(raw) >= 5:
                return raw
    return None


def extraer_distrito_dom(ubicacion_raw: str | None, distritos_norm: set) -> str | None:
    """Fallback: extrae distrito desde el texto visible de la tarjeta del listado."""
    if not isinstance(ubicacion_raw, str) or not ubicacion_raw.strip():
        return None
    texto = ubicacion_raw.replace("Ver mapa", "").replace("Ubicacion", "").strip()
    partes = [p.strip() for p in texto.split(",") if p.strip()]
    for parte in reversed(partes):
        parte_norm = parte.lower().strip()
        if parte_norm in ("arequipa",):
            continue
        if parte_norm in distritos_norm:
            return parte.strip().title()
    for parte in partes:
        if parte.lower().strip() in distritos_norm:
            return parte.strip().title()
    return None


def detectar_tipo_inmueble_fallback(
    descripcion: str | None = None,
    enlace: str | None = None,
) -> str | None:
    """Detecta tipo_inmueble desde texto libre cuando Redux no lo trae."""
    textos = []
    if enlace:
        textos.append(enlace)
    if descripcion:
        textos.append(descripcion[:200])
    if not textos:
        return None

    t = " ".join(textos).lower()

    if any(x in t for x in ["departamento", "apartamento", "flat", "duplex",
                            "penthouse", "dpto", "depa"]):
        return "departamento"
    if any(x in t for x in ["casa", "chalet", "villa"]):
        return "casa"
    if any(x in t for x in ["local comercial", "local-comercial", "tienda"]):
        return "local_comercial"
    if any(x in t for x in ["terreno", "lote"]):
        return "terreno"
    if "oficina" in t:
        return "oficina"
    if any(x in t for x in ["habitacion", "habitación", "cuarto", "room"]):
        return "habitacion"
    return None
