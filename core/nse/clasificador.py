"""Clasificador NSE por lookup de urbanización / lugar.

API mínima:

    config = NSEConfig()  # defaults Arequipa
    clf = NSEClassifier.from_excel("BASE_DE_UBICACIONES.xlsx", config)
    match = clf.clasificar(ubicacion="Av. Cayma 200", distrito="Cayma")
    # match.nse == "Medio Alto", match.metodo == "urbanizacion_distrito"

Cargado genérico desde Pandas:

    df_ref = pd.DataFrame([
        {"distrito": "Cayma", "lugar": "Urb. Quinta Samay", "nse": "Medio Alto"},
        ...
    ])
    clf = NSEClassifier.from_dataframe(df_ref, config)
"""

from __future__ import annotations

import logging
import os
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Iterable

import pandas as pd

logger = logging.getLogger("scraping")

# Etiquetas NSE canónicas del INEI / clasificación BCRP.
NSE_CANONICOS = ("Alto", "Medio Alto", "Medio", "Medio Bajo", "Bajo")

_ETIQUETAS_NSE_DEFAULT = {
    "alto": "Alto",
    "allto": "Alto",
    "medio alto": "Medio Alto",
    "media alto": "Medio Alto",
    "medio": "Medio",
    "medio bajo": "Medio Bajo",
    "bajo": "Bajo",
}

# Defaults para Arequipa metropolitana (33 distritos + alias frecuentes).
# Si el sector trabaja en Lima u otra región, pasa los suyos en NSEConfig.
_DISTRITOS_ALIAS_DEFAULT = {
    "cercado": "arequipa",
    "cercado de arequipa": "arequipa",
    "j l b y rivero": "jose luis bustamante y rivero",
    "jlb y rivero": "jose luis bustamante y rivero",
    "jlbyr": "jose luis bustamante y rivero",
    "jose luis bustamante y rivero": "jose luis bustamante y rivero",
    "jacobo hunter": "hunter",
}

_DISTRITOS_TEXTO_DEFAULT = (
    "alto selva alegre", "arequipa", "cayma", "cerro colorado", "characato",
    "chiguata", "hunter", "jacobo hunter", "jose luis bustamante y rivero",
    "la joya", "mariano melgar", "miraflores", "mollebaya", "paucarpata",
    "pocsi", "polobaya", "quequena", "sabandia", "sachaca",
    "san juan de siguas", "san juan de tarucani", "santa isabel de siguas",
    "santa rita de siguas", "socabaya", "tiabaya", "uchumayo", "vitor",
    "yanahuara", "yarabamba", "yura",
)

_PREFIJOS_URBANOS_DEFAULT = (
    "urb", "urbanizacion", "residencial", "quinta", "villa", "condominio",
    "asoc", "asociacion", "coop", "cooperativa", "pueblo tradicional",
    "pueblo joven",
)

_PALABRAS_DESCARTE_SEGMENTO = {
    "arequipa", "venta", "alquiler",
    "departamento", "departamentos", "casa", "casas",
    "terreno", "terrenos", "habitacion", "habitaciones",
    "inmueble", "inmuebles",
}

_INICIO_VIA = re.compile(
    r"^(av|avenida|calle|jr|jiron|pasaje|psje|prolongacion|ovalo|plaza|parque|via)\b"
)
_VIA_DENTRO_SEGMENTO = re.compile(
    r"\b(av|avenida|calle|jr|jiron|pasaje|psje|prolongacion|ovalo|plaza|parque|via)\.?\b"
)


@dataclass(frozen=True)
class NSEMatch:
    nse: str | None
    metodo: str | None       # 'urbanizacion_distrito' | 'urbanizacion_global' | 'urbanizacion_texto'
    match: str | None        # texto normalizado matcheado
    confianza: float | None  # proporción del modo en el cluster


@dataclass(frozen=True)
class NSEConfig:
    """Parámetros de normalización geográfica. Los defaults son Arequipa."""

    etiquetas_nse: dict[str, str] = field(
        default_factory=lambda: dict(_ETIQUETAS_NSE_DEFAULT)
    )
    distritos_alias: dict[str, str] = field(
        default_factory=lambda: dict(_DISTRITOS_ALIAS_DEFAULT)
    )
    distritos_texto: tuple[str, ...] = _DISTRITOS_TEXTO_DEFAULT
    prefijos_urbanos: tuple[str, ...] = _PREFIJOS_URBANOS_DEFAULT
    min_registros_urbanizacion: int = 2
    columna_distrito: str = "distrito"
    columna_lugar: str = "lugar"
    columna_nse: str = "nse"  # también acepta "clasificacion"/"clasificación"


# ---------------------------------------------------------------------------
# Normalización
# ---------------------------------------------------------------------------

def _normalizar_texto(valor: object) -> str:
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    texto = str(valor).strip().lower()
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[\r\n\t]+", " ", texto)
    texto = re.sub(r"[^\w\s./,;|-]", " ", texto)
    texto = re.sub(r"\b(en|de|del|la|el|los|las)\s+(venta|alquiler)\b", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip(" .,;|-/")
    return texto


def _normalizar_etiqueta(valor: object, etiquetas: dict[str, str]) -> str | None:
    texto = _normalizar_texto(valor)
    if not texto:
        return None
    texto = re.sub(r"\s+", " ", texto)
    return etiquetas.get(texto)


def _normalizar_distrito(valor: object, alias: dict[str, str]) -> str:
    texto = _normalizar_texto(valor)
    texto = re.sub(r"\s+", " ", texto)
    return alias.get(texto, texto)


def _limpiar_segmento_urbano(
    segmento: str, distritos_texto: tuple[str, ...]
) -> str:
    texto = _normalizar_texto(segmento)
    partes_via = _VIA_DENTRO_SEGMENTO.split(texto, maxsplit=1)
    if partes_via and partes_via[0].strip():
        texto = partes_via[0]
    texto = re.sub(r"\b(en|de|del|la|el|los|las)\b", " ", texto)
    texto = re.sub(
        r"\b(urb|urbanizacion|residencial|condominio|asoc|asociacion|coop|cooperativa)\b\.?",
        " ", texto,
    )
    texto = re.sub(r"\s+", " ", texto).strip(" .-/")
    for distrito in distritos_texto:
        if texto == distrito:
            return texto
        if texto.endswith(f" {distrito}"):
            texto = texto[: -len(distrito)].strip(" .-/")
            break
    palabras = texto.split()
    if len(palabras) % 2 == 0:
        mitad = len(palabras) // 2
        if palabras[:mitad] == palabras[mitad:]:
            texto = " ".join(palabras[:mitad])
    return texto


def _es_candidato_urbano(
    segmento: str, distritos_texto: tuple[str, ...]
) -> bool:
    if not segmento or len(segmento) < 4:
        return False
    if segmento in distritos_texto:
        return False
    if segmento in _PALABRAS_DESCARTE_SEGMENTO:
        return False
    if _INICIO_VIA.search(segmento):
        return False
    palabras = segmento.split()
    if len(palabras) > 6:
        return False
    if all(p in _PALABRAS_DESCARTE_SEGMENTO for p in palabras):
        return False
    return True


def extraer_candidatos_urbanizacion(
    *textos: object,
    config: NSEConfig | None = None,
) -> list[str]:
    """Devuelve candidatos de urbanización extraídos de los textos dados."""
    cfg = config or NSEConfig()
    candidatos: list[str] = []
    vistos: set[str] = set()

    patron_prefijo = (
        r"\b(" + "|".join(re.escape(p) for p in cfg.prefijos_urbanos)
        + r")\.?\s+([a-z0-9\s.-]{3,60})"
    )

    distritos_ord = tuple(sorted(cfg.distritos_texto, key=len, reverse=True))

    for valor in textos:
        texto = _normalizar_texto(valor)
        if not texto:
            continue
        for parte in re.split(r"[,;|·]+", texto):
            parte = parte.strip()
            if not parte:
                continue
            m = re.search(patron_prefijo, parte)
            if m:
                candidato = _limpiar_segmento_urbano(
                    f"{m.group(1)} {m.group(2)}", distritos_ord
                )
            else:
                candidato = _limpiar_segmento_urbano(parte, distritos_ord)
            if _es_candidato_urbano(candidato, distritos_ord) and candidato not in vistos:
                candidatos.append(candidato)
                vistos.add(candidato)
    return candidatos


# ---------------------------------------------------------------------------
# Lectura de la base de referencia
# ---------------------------------------------------------------------------

def _columna_por_nombre(df: pd.DataFrame, candidatos: Iterable[str]) -> str | None:
    objetivos = {_normalizar_texto(c) for c in candidatos}
    for col in df.columns:
        if _normalizar_texto(col) in objetivos:
            return col
    return None


def _leer_base_referencia(ruta: str, config: NSEConfig) -> pd.DataFrame:
    df = pd.read_excel(ruta)

    candidatos_distrito = [config.columna_distrito, "distrito"]
    candidatos_lugar = [config.columna_lugar, "lugar"]
    candidatos_nse = [config.columna_nse, "clasificacion", "clasificación", "nse"]

    col_distrito = _columna_por_nombre(df, candidatos_distrito)
    col_lugar = _columna_por_nombre(df, candidatos_lugar)
    col_nse = _columna_por_nombre(df, candidatos_nse)

    # Cabecera puede estar desplazada N filas (Excel humano-editado).
    if not all((col_distrito, col_lugar, col_nse)):
        for idx, row in df.head(10).iterrows():
            valores = [_normalizar_texto(v) for v in row.tolist()]
            if "distrito" in valores and "lugar" in valores and (
                "clasificacion" in valores or "nse" in valores
            ):
                df = df.iloc[idx + 1:].copy()
                df.columns = row.tolist()
                col_distrito = _columna_por_nombre(df, candidatos_distrito)
                col_lugar = _columna_por_nombre(df, candidatos_lugar)
                col_nse = _columna_por_nombre(df, candidatos_nse)
                break

    if not all((col_distrito, col_lugar, col_nse)):
        raise ValueError(
            "La base NSE no tiene columnas reconocibles. Esperadas: "
            f"distrito={candidatos_distrito} lugar={candidatos_lugar} nse={candidatos_nse}"
        )

    out = df[[col_distrito, col_lugar, col_nse]].copy()
    out.columns = ["distrito", "lugar", "nse"]
    out["distrito_norm"] = out["distrito"].map(
        lambda v: _normalizar_distrito(v, config.distritos_alias)
    )
    out["lugar_norm"] = out["lugar"].map(_normalizar_texto)
    out["nse"] = out["nse"].map(lambda v: _normalizar_etiqueta(v, config.etiquetas_nse))
    out = out.dropna(subset=["nse"])
    out = out[(out["distrito_norm"] != "") & (out["lugar_norm"] != "")]
    return out


def _modo_con_confianza(valores: Iterable[str]) -> tuple[str, float, int]:
    conteo = Counter(valores)
    n_total = sum(conteo.values())
    nse, n = conteo.most_common(1)[0]
    return nse, (n / n_total) if n_total else 0.0, n_total


# ---------------------------------------------------------------------------
# Clasificador
# ---------------------------------------------------------------------------

class NSEClassifier:
    """Clasificador construido a partir de una tabla de referencia.

    Indexes precomputados:
        urbano_por_distrito: (distrito_norm, candidato_norm) -> (nse, confianza, n)
        urbano_global:       candidato_norm -> (nse, confianza, n)
    """

    def __init__(
        self,
        urbano_por_distrito: dict[tuple[str, str], tuple[str, float, int]],
        urbano_global: dict[str, tuple[str, float, int]],
        config: NSEConfig,
    ):
        self.urbano_por_distrito = urbano_por_distrito
        self.urbano_global = urbano_global
        self.config = config
        self._urbanos_ordenados = sorted(urbano_global, key=len, reverse=True)

    # ----- Constructores -----

    @classmethod
    def from_dataframe(
        cls,
        df_referencia: pd.DataFrame,
        config: NSEConfig | None = None,
    ) -> NSEClassifier:
        cfg = config or NSEConfig()
        urbano_por_dist: dict[tuple[str, str], list[str]] = defaultdict(list)
        urbano_global: dict[str, list[str]] = defaultdict(list)

        for _, row in df_referencia.iterrows():
            nse = row.get("nse")
            distrito_norm = row.get("distrito_norm") or _normalizar_distrito(
                row.get("distrito"), cfg.distritos_alias
            )
            if not nse or not distrito_norm:
                continue
            candidatos = extraer_candidatos_urbanizacion(row.get("lugar"), config=cfg)
            for candidato in candidatos:
                urbano_por_dist[(distrito_norm, candidato)].append(nse)
                urbano_global[candidato].append(nse)

        return cls(
            urbano_por_distrito={
                k: _modo_con_confianza(v)
                for k, v in urbano_por_dist.items()
                if len(v) >= cfg.min_registros_urbanizacion
            },
            urbano_global={
                k: _modo_con_confianza(v)
                for k, v in urbano_global.items()
                if len(v) >= cfg.min_registros_urbanizacion
            },
            config=cfg,
        )

    @classmethod
    def from_excel(
        cls,
        ruta: str,
        config: NSEConfig | None = None,
    ) -> NSEClassifier:
        cfg = config or NSEConfig()
        return cls.from_dataframe(_leer_base_referencia(ruta, cfg), cfg)

    # ----- API de clasificación -----

    def clasificar(
        self,
        ubicacion: object = None,
        distrito: object = None,
        zone_name: object = None,
        address_name: object = None,
    ) -> NSEMatch:
        cfg = self.config
        distrito_norm = _normalizar_distrito(distrito, cfg.distritos_alias)
        textos = [ubicacion, zone_name, address_name]
        candidatos = extraer_candidatos_urbanizacion(*textos, config=cfg)
        texto_completo = _normalizar_texto(
            " ".join(str(t) for t in textos if t is not None)
        )

        # 1. (distrito + candidato exacto) — mayor confianza
        for candidato in candidatos:
            dato = self.urbano_por_distrito.get((distrito_norm, candidato))
            if dato:
                return NSEMatch(dato[0], "urbanizacion_distrito", candidato, round(dato[1], 4))

        # 2. candidato global (sin filtrar por distrito)
        for candidato in candidatos:
            dato = self.urbano_global.get(candidato)
            if dato:
                return NSEMatch(dato[0], "urbanizacion_global", candidato, round(dato[1], 4))

        # 3. fallback: buscar urbanización conocida dentro del texto libre
        if texto_completo:
            for urbano in self._urbanos_ordenados:
                if len(urbano) < 8 and " " not in urbano:
                    continue
                if re.search(rf"\b{re.escape(urbano)}\b", texto_completo):
                    dato = (
                        self.urbano_por_distrito.get((distrito_norm, urbano))
                        or self.urbano_global.get(urbano)
                    )
                    if dato:
                        return NSEMatch(dato[0], "urbanizacion_texto", urbano, round(dato[1], 4))

        return NSEMatch(None, None, None, None)


# ---------------------------------------------------------------------------
# Conveniencia: aplicar a DataFrame
# ---------------------------------------------------------------------------

def asignar_nse_dataframe(
    df: pd.DataFrame,
    clasificador: NSEClassifier,
    columnas_origen: tuple[str, str, str, str] = (
        "ubicacion", "distrito", "zone_name", "address_name",
    ),
) -> pd.DataFrame:
    """Agrega columnas nse / nse_metodo / nse_match / nse_confianza al DF."""
    if df is None or df.empty:
        return df

    out = df.copy()
    for col in ("nse", "nse_metodo", "nse_match", "nse_confianza"):
        if col not in out.columns:
            out[col] = None

    col_ubic, col_dist, col_zone, col_addr = columnas_origen
    for idx, row in out.iterrows():
        match = clasificador.clasificar(
            ubicacion=row.get(col_ubic),
            distrito=row.get(col_dist),
            zone_name=row.get(col_zone),
            address_name=row.get(col_addr),
        )
        out.at[idx, "nse"] = match.nse
        out.at[idx, "nse_metodo"] = match.metodo
        out.at[idx, "nse_match"] = match.match
        out.at[idx, "nse_confianza"] = match.confianza

    total = len(out)
    asignados = int(out["nse"].notna().sum())
    logger.info(
        "NSE asignado: %s/%s (%s%%)",
        asignados, total, asignados * 100 // total if total else 0,
    )
    return out


def cargar_clasificador_desde_excel(
    ruta: str,
    config: NSEConfig | None = None,
) -> NSEClassifier | None:
    """Helper para sectores: devuelve None si la base no existe o falla."""
    if not ruta or not os.path.exists(ruta):
        logger.warning("Base NSE no encontrada: %s. Se omite clasificación.", ruta)
        return None
    try:
        return NSEClassifier.from_excel(ruta, config or NSEConfig())
    except Exception as exc:
        logger.warning("No se pudo cargar base NSE %s: %s", ruta, exc)
        return None
