"""
Orquestador del sector inmobiliario sobre core/.

Equivalente a v1/main.py pero importando de core/ (BrowserManager,
HistorialSQLite, ExcelAcumulativo, logging).

Uso:
    python -m sectores.inmobiliario.main                      # todos los portales + operaciones
    python -m sectores.inmobiliario.main --portal urbania
    python -m sectores.inmobiliario.main --paginas 5
    python -m sectores.inmobiliario.main --sin-ia
    python -m sectores.inmobiliario.main --headless
"""

import argparse
import logging
import os
from datetime import datetime

import pandas as pd

from core.logging import configurar_logging
from core.reportes import ExcelAcumulativo, Hoja

from sectores.inmobiliario.config import (
    generar_nombre_archivo_historico, CARPETA_SALIDA, CARPETA_LOGS,
    DEFAULT_NUM_PAGINAS, RUTA_DB, UMBRAL_AUSENCIAS, PORTALES_SOPORTADOS,
)
from sectores.inmobiliario.scraper import scrape_portal
from sectores.inmobiliario.limpieza import pipeline_limpieza, construir_export_alberth
from sectores.inmobiliario.extractor_ia import (
    asignar_publicacion_id,
    procesar_con_ia,
    ia_disponible,
)
from sectores.inmobiliario.historial import registrar_corrida as historial_registrar

logger = logging.getLogger("scraping")
_NAVENT_PORTALES = {"urbania", "adondevivir"}
_NAVENT_MATCH_RATIO_MIN = 0.85


COLUMNAS_DIAGNOSTICO = [
    "fecha_publicacion", "titulo", "tipo_inmueble",
    "distrito", "zone_name", "address_name", "ubicacion",
    "precio", "moneda", "precio_secundario", "moneda_secundaria",
    "mantenimiento",
    "area_total_m2", "area_construida_m2",
    "dormitorios", "banos", "medio_banos",
    "estacionamientos", "pisos", "antiguedad_anos",
    "descripcion", "anunciante",
    "enlace", "precio_por_m2",
    "portal", "tipo_operacion", "fecha_extraccion",
    "estado_anuncio",
    "warnings",
]


def _contar_warnings(df: pd.DataFrame | None) -> int:
    """Cuenta warnings no vacíos sin asumir que la columna siempre existe."""
    if df is None or df.empty or "warnings" not in df.columns:
        return 0
    return int(df["warnings"].fillna("").astype(str).str.strip().ne("").sum())


def _porcentaje_lleno(df: pd.DataFrame, campo: str) -> float:
    if campo not in df.columns or len(df) == 0:
        return 0.0
    serie = df[campo]
    return float((serie.notna() & (serie.astype(str).str.strip() != "")).mean())


def _evaluar_calidad_scraping(
    portal: str,
    operacion: str,
    diagnostico: dict | None,
    df: pd.DataFrame,
) -> dict:
    """Bloquea corridas que no son aptas para actualizar el historico."""
    resultado = {
        "estado": "ok",
        "apta_para_historial": True,
        "motivos": [],
        "diagnostico": diagnostico or {},
    }

    if df is None or df.empty:
        resultado["estado"] = "sin_datos"
        resultado["apta_para_historial"] = False
        resultado["motivos"].append("No se obtuvieron registros limpios.")
        return resultado

    estrategia = (diagnostico or {}).get("estrategia")
    if estrategia is None and portal in _NAVENT_PORTALES:
        estrategia = "navent"

    if estrategia == "navent":
        bloqueos = []
        advertencias = []
        paginas_fallidas = (diagnostico or {}).get("redux_paginas_fallidas", 0)
        paginas_ok = (diagnostico or {}).get("redux_paginas_ok")
        ratio_match = (diagnostico or {}).get("ratio_match_redux_dom")

        if _porcentaje_lleno(df, "enlace") < 0.99:
            bloqueos.append("Mas del 1% de registros Navent sin enlace.")
        if _porcentaje_lleno(df, "precio") < 0.70:
            bloqueos.append("Menos del 70% de registros Navent tiene precio.")
        if _porcentaje_lleno(df, "distrito") < 0.70:
            bloqueos.append("Menos del 70% de registros Navent tiene distrito.")
        if _porcentaje_lleno(df, "descripcion") < 0.50:
            bloqueos.append("Menos del 50% de registros Navent tiene descripcion.")

        if paginas_ok == 0:
            advertencias.append(
                "No se pudo leer Redux/Next data en ninguna pagina Navent."
            )
        if paginas_fallidas > 0:
            advertencias.append(
                f"Hubo {paginas_fallidas} pagina(s) Navent con fallback solo DOM."
            )
        if ratio_match is not None and ratio_match < _NAVENT_MATCH_RATIO_MIN:
            advertencias.append(f"Match Redux/DOM insuficiente ({ratio_match:.1%}).")

        resultado["motivos"] = bloqueos + advertencias
        if bloqueos:
            resultado["estado"] = "degradado"
            resultado["apta_para_historial"] = False
        elif advertencias:
            resultado["estado"] = "advertencia"

    if resultado["motivos"] and not resultado["apta_para_historial"]:
        logger.error(
            "Corrida degradada en %s/%s. Se bloquea actualizacion de historico. %s",
            portal,
            operacion,
            " | ".join(resultado["motivos"]),
        )
    elif resultado["motivos"]:
        logger.warning(
            "Corrida con advertencias en %s/%s. Se permite historico. %s",
            portal,
            operacion,
            " | ".join(resultado["motivos"]),
        )

    return resultado


def ejecutar_scraping(
    portal: str, operacion: str, num_paginas: int,
    usar_ia: bool = True, headless: bool = False,
) -> tuple[pd.DataFrame | None, dict | None]:
    # Fase 1-2: Scraping
    datos_crudos = scrape_portal(portal, operacion, num_paginas, headless=headless)
    if not datos_crudos:
        logger.warning(f"No se obtuvieron datos de {portal}/{operacion}")
        return None, None

    # Fase 3: Limpieza determinista
    logger.info("FASE 3: Limpieza y normalizacion...")
    df = pipeline_limpieza(datos_crudos, portal, operacion)
    if df.empty:
        return None, None
    df = asignar_publicacion_id(df)

    # Fase 4: Control de calidad antes de IA e historial.
    calidad = _evaluar_calidad_scraping(portal, operacion, None, df)
    if not calidad["apta_para_historial"]:
        return df, None

    # Fase 5: IA
    if usar_ia and ia_disponible():
        logger.info("FASE 5: Enriquecimiento con Gemini API...")
        df = procesar_con_ia(df)
    elif usar_ia:
        logger.info("FASE 5: IA no disponible. Continuando sin IA.")

    # Fase 6: Historial
    logger.info("FASE 6: Registrando en historial SQLite...")
    df, stats_historial = historial_registrar(
        df,
        portal,
        operacion,
        RUTA_DB,
        UMBRAL_AUSENCIAS,
        estado_calidad=calidad["estado"],
    )
    logger.info(
        f"  Nuevos: {stats_historial['nuevos']} | "
        f"Repetidos: {stats_historial['repetidos']} | "
        f"Desaparecidos: {stats_historial['desaparecidos']} | "
        f"Dados de baja: {stats_historial['dados_de_baja']}"
    )

    # Fase 7: Excel acumulativo (hojas Consolidado + Diagnostico)
    nombre_archivo = generar_nombre_archivo_historico(portal, operacion)
    ruta_archivo = os.path.join(CARPETA_SALIDA, nombre_archivo)

    df_consolidado = construir_export_alberth(df)
    cols_diag = [c for c in COLUMNAS_DIAGNOSTICO if c in df.columns]
    df_diagnostico = df[cols_diag]

    exporter = ExcelAcumulativo(
        ruta_archivo=ruta_archivo,
        hojas=[
            Hoja("Consolidado", ["Enlace", "Fecha de revisión"]),
            Hoja("Diagnostico", ["enlace", "fecha_extraccion"]),
        ],
    )
    exporter.escribir({
        "Consolidado": df_consolidado,
        "Diagnostico": df_diagnostico,
    })

    return df, stats_historial


def main(argv: list[str] | None = None):
    configurar_logging(carpeta_logs=CARPETA_LOGS)

    parser = argparse.ArgumentParser(
        description="Scraping inmobiliario BCRP — sobre core/"
    )
    parser.add_argument(
        "--portal",
        choices=PORTALES_SOPORTADOS + ["todos"],
        default="todos",
    )
    parser.add_argument(
        "--operacion",
        choices=["alquiler", "venta", "todas"],
        default="todas",
    )
    parser.add_argument("--paginas", type=int, default=DEFAULT_NUM_PAGINAS)
    parser.add_argument("--sin-ia", action="store_true")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args(argv)

    portales = list(PORTALES_SOPORTADOS) if args.portal == "todos" else [args.portal]
    operaciones = ["alquiler", "venta"] if args.operacion == "todas" else [args.operacion]
    usar_ia = not args.sin_ia

    logger.info("=" * 60)
    logger.info("SCRAPING INMOBILIARIO BCRP — core/")
    logger.info(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Portales: {', '.join(portales)}")
    logger.info(f"Operaciones: {', '.join(operaciones)}")
    logger.info(f"Paginas por portal/operacion: {args.paginas}")
    logger.info(f"IA (Gemini): {'SI' if usar_ia else 'NO'}")
    logger.info(f"Headless: {'SI' if args.headless else 'NO'}")
    logger.info("=" * 60)

    resumen = []
    for portal in portales:
        for operacion in operaciones:
            try:
                df, stats = ejecutar_scraping(
                    portal=portal, operacion=operacion,
                    num_paginas=args.paginas, usar_ia=usar_ia, headless=args.headless,
                )
                if df is not None:
                    n_warnings = _contar_warnings(df)
                    stats = stats or {"nuevos": 0, "repetidos": 0}
                    resumen.append({
                        "portal": portal, "operacion": operacion,
                        "anuncios": len(df), "warnings": n_warnings,
                        "nuevos": stats["nuevos"], "repetidos": stats["repetidos"],
                        "archivo": generar_nombre_archivo_historico(portal, operacion),
                    })
                else:
                    resumen.append({
                        "portal": portal, "operacion": operacion,
                        "anuncios": 0, "warnings": 0,
                        "nuevos": 0, "repetidos": 0, "archivo": "-",
                    })
            except Exception as e:
                logger.exception(f"Error en {portal}/{operacion}: {e}")
                resumen.append({
                    "portal": portal, "operacion": operacion,
                    "anuncios": f"ERROR: {e}", "warnings": "-",
                    "nuevos": "-", "repetidos": "-", "archivo": "-",
                })

    print("\n" + "=" * 60)
    print("RESUMEN FINAL")
    print("=" * 60)
    total = 0
    for r in resumen:
        a = r["anuncios"]
        print(
            f"  {r['portal']:15s} {r['operacion']:10s} | {a:>4} anuncios | "
            f"{r['nuevos']:>4} nuevos | {r['repetidos']:>4} repetidos | "
            f"{r['warnings']:>3} warnings | {r['archivo']}"
        )
        if isinstance(a, int):
            total += a
    print(f"\n  Total: {total} anuncios")
    print(f"  Archivos guardados en: {CARPETA_SALIDA}")
    print("=" * 60)


if __name__ == "__main__":
    main()
