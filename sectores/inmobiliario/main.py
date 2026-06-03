"""
Orquestador del sector inmobiliario — EJEMPLO ILUSTRATIVO sobre core/.

⚠️ No es producción (esa vive en v1-portales-web). Demuestra el pipeline
completo y vigente del framework:

    1. Scraping (Navent) → datos + diagnostico estándar (+ snapshots HTML).
    2. Limpieza → DataFrame normalizado + columnas de periodo.
    3. publicacion_id.
    4. Compuerta de calidad (core.calidad). Si degradado → degradadas/ +
       reporte de mantenimiento, y NO continúa.
    5. IA (DeepSeek) con cache, sólo corridas aptas.
    6. NSE (después de IA/ubicacion) — se omite si no hay base de referencia.
    7. Historial SQLite (ciclo de vida).
    8. Excel acumulativo (Consolidado institucional + Diagnostico).

Uso:
    python -m sectores.inmobiliario.main --portal urbania --paginas 1 --sin-ia
"""

import argparse
import logging
import os
import traceback
from datetime import datetime

import pandas as pd

from core.calidad import EstadoCalidad, evaluar_cobertura
from core.logging import configurar_logging
from core.mantenimiento_frontend import generar_reporte_mantenimiento_frontend
from core.nse import asignar_nse_dataframe, cargar_clasificador_desde_excel
from core.reportes import ExcelAcumulativo, Hoja
from core.tipo_cambio import (
    COLUMNAS_ESTIMADAS,
    aplicar_conversion_tipo_cambio,
    marcar_columnas_estimadas_excel,
)

from sectores.inmobiliario import config
from sectores.inmobiliario.scraper import scrape_portal_con_diagnostico
from sectores.inmobiliario.limpieza import pipeline_limpieza, construir_export_alberth
from sectores.inmobiliario.extractor_ia import (
    asignar_publicacion_id, procesar_con_ia, ia_disponible,
)
from sectores.inmobiliario.historial import registrar_corrida as historial_registrar

logger = logging.getLogger("scraping")

COLUMNAS_DIAGNOSTICO = [
    "fecha_publicacion", "anio", "trimestre", "mes",
    "titulo", "tipo_inmueble", "distrito", "nse",
    "zone_name", "address_name", "ubicacion",
    "precio", "moneda", "precio_secundario", "moneda_secundaria",
    "area_total_m2", "area_construida_m2",
    "dormitorios", "banos", "estacionamientos", "antiguedad_anos",
    "descripcion", "anunciante", "enlace", "precio_por_m2",
    "portal", "tipo_operacion", "fecha_extraccion",
    "estado_anuncio", "warnings",
]


def _exportar_degradada(df, portal, operacion) -> str | None:
    """Aisla una corrida degradada en degradadas/ (nunca toca el historial)."""
    if df is None or df.empty:
        return None
    os.makedirs(config.CARPETA_DEGRADADAS, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta = os.path.join(config.CARPETA_DEGRADADAS, f"{portal}_{operacion}_{ts}.xlsx")
    df.to_excel(ruta, index=False)
    logger.warning("Corrida degradada aislada en %s", ruta)
    return ruta


def _marcar_estimados_tc(ruta_archivo: str, hoja: str = "Consolidado") -> None:
    """Pinta en rojo las celdas que el tipo de cambio rellenó como estimadas.

    Relee la hoja YA escrita (post append+dedup acumulativo) para que las
    marcas correspondan a las filas reales del archivo, no al orden de la
    corrida actual. Idempotente: si una columna estimada no existe, se ignora.
    """
    try:
        hoja_df = pd.read_excel(ruta_archivo, sheet_name=hoja)
    except Exception as e:  # archivo recién creado o sin la hoja: no es fatal
        logger.warning("No se pudo releer '%s' para marcar TC: %s", hoja, e)
        return
    presentes = [c for c in COLUMNAS_ESTIMADAS if c in hoja_df.columns]
    if not presentes:
        return
    marcas: dict[int, set[str]] = {}
    for idx, fila in hoja_df.iterrows():
        marcadas = {c for c in presentes if pd.notna(fila.get(c))}
        if marcadas:
            marcas[int(idx)] = marcadas
    if marcas:
        marcar_columnas_estimadas_excel(ruta_archivo, {hoja: marcas})


def ejecutar_scraping(
    portal: str, operacion: str, num_paginas: int,
    usar_ia: bool = True, headless: bool = False, usar_tc: bool = True,
) -> tuple[pd.DataFrame | None, dict | None]:
    diagnostico: dict = {}
    df = None
    try:
        # Fase 1-2: Scraping con diagnostico + snapshots.
        datos_crudos, diagnostico = scrape_portal_con_diagnostico(
            portal, operacion, num_paginas, headless=headless
        )

        # Fase 3: Limpieza (incluye columnas de periodo).
        logger.info("FASE 3: Limpieza y normalizacion...")
        df = pipeline_limpieza(datos_crudos, portal, operacion)

        # Fase 4: publicacion_id + compuerta de calidad (core.calidad).
        if df is not None and not df.empty:
            df = asignar_publicacion_id(df)
        ratio = diagnostico.get("ratio_match_redux_dom")
        veredicto = evaluar_cobertura(
            df,
            umbrales=config.UMBRALES_CALIDAD.get("navent"),
            senales_instrumentales=[
                ("Redux falló en alguna página (fallback DOM).",
                 diagnostico.get("redux_paginas_fallidas", 0) > 0),
                ("Match Redux/DOM bajo (<85%).",
                 ratio is not None and ratio < 0.85),
            ],
        )
        veredicto.loggear(f"{portal}/{operacion}")

        if not veredicto.apta_para_historial:
            ruta_deg = _exportar_degradada(df, portal, operacion)
            generar_reporte_mantenimiento_frontend(
                portal=portal, operacion=operacion,
                estado=veredicto.estado.value,
                carpeta_reportes=config.CARPETA_REPORTES_MANTENIMIENTO,
                motivos=list(veredicto.motivos),
                diagnostico=diagnostico, df=df, ruta_degradada=ruta_deg,
                codigo_por_portal=config.CODIGO_POR_PORTAL,
                superficie_por_categoria=config.SUPERFICIE_POR_CATEGORIA,
            )
            return df, None

        # Fase 5: IA (sólo corridas aptas).
        if usar_ia and ia_disponible():
            logger.info("FASE 5: Enriquecimiento con DeepSeek...")
            df = procesar_con_ia(df, ruta_cache=config.RUTA_DB)
        elif usar_ia:
            logger.info("FASE 5: IA no disponible. Continuando sin IA.")

        # Fase 6: NSE (después de IA/ubicacion). Se omite si no hay base.
        clasificador = cargar_clasificador_desde_excel(config.RUTA_BASE_NSE)
        if clasificador is not None:
            logger.info("FASE 6: Clasificacion NSE por urbanizacion...")
            df = asignar_nse_dataframe(df, clasificador)

        # Fase 7: Historial SQLite.
        logger.info("FASE 7: Registrando en historial SQLite...")
        df, stats = historial_registrar(
            df, portal, operacion, config.RUTA_DB, config.UMBRAL_AUSENCIAS,
            estado_calidad=veredicto.estado.value,
        )
        logger.info(
            "  Nuevos: %s | Repetidos: %s | Desaparecidos: %s | Bajas: %s",
            stats["nuevos"], stats["repetidos"],
            stats["desaparecidos"], stats["dados_de_baja"],
        )

        # Fase 8: Excel acumulativo (Consolidado institucional + Diagnostico).
        ruta_archivo = os.path.join(
            config.CARPETA_SALIDA,
            config.generar_nombre_archivo_historico(portal, operacion),
        )
        cols_diag = [c for c in COLUMNAS_DIAGNOSTICO if c in df.columns]
        df_consolidado = construir_export_alberth(df)

        # Fase 8a: Tipo de cambio BCRP. Conversión analítica auditable: agrega
        # columnas estimadas SIN tocar los montos observados. Degrada silencioso
        # si no hay red ni cache (las columnas quedan vacías).
        if usar_tc and not df_consolidado.empty:
            logger.info("FASE 8a: Tipo de cambio BCRP (conversion analitica)...")
            df_consolidado = aplicar_conversion_tipo_cambio(
                df_consolidado, ruta_cache=config.RUTA_DB, modo=config.TC_MODO,
            )

        exporter = ExcelAcumulativo(
            ruta_archivo=ruta_archivo,
            hojas=[
                Hoja("Consolidado", ["Enlace", "Fecha de revisión"]),
                Hoja("Diagnostico", ["enlace", "fecha_extraccion"]),
            ],
        )
        exporter.escribir({
            "Consolidado": df_consolidado,
            "Diagnostico": df[cols_diag],
        })

        # Auditoría visual: las celdas estimadas por TC van en rojo.
        if usar_tc:
            _marcar_estimados_tc(ruta_archivo, "Consolidado")
        return df, stats

    except Exception:
        tb = traceback.format_exc()
        logger.exception("Excepcion en %s/%s", portal, operacion)
        generar_reporte_mantenimiento_frontend(
            portal=portal, operacion=operacion, estado="excepcion",
            carpeta_reportes=config.CARPETA_REPORTES_MANTENIMIENTO,
            motivos=[f"Excepcion: {tb.splitlines()[-1][:200]}"],
            diagnostico=diagnostico or {}, df=df, excepcion=tb,
            codigo_por_portal=config.CODIGO_POR_PORTAL,
            superficie_por_categoria=config.SUPERFICIE_POR_CATEGORIA,
        )
        return df, None


def main(argv: list[str] | None = None):
    configurar_logging(carpeta_logs=config.CARPETA_LOGS)

    parser = argparse.ArgumentParser(
        description="Scraping inmobiliario BCRP — ejemplo sobre core/"
    )
    parser.add_argument(
        "--portal", choices=config.PORTALES_SOPORTADOS + ["todos"], default="todos",
    )
    parser.add_argument(
        "--operacion", choices=config.OPERACIONES + ["todas"], default="todas",
    )
    parser.add_argument("--paginas", type=int, default=config.DEFAULT_NUM_PAGINAS)
    parser.add_argument("--sin-ia", action="store_true")
    parser.add_argument("--sin-tc", action="store_true",
                        help="No aplicar conversión de tipo de cambio BCRP.")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args(argv)

    portales = (
        list(config.PORTALES_SOPORTADOS) if args.portal == "todos" else [args.portal]
    )
    operaciones = (
        list(config.OPERACIONES) if args.operacion == "todas" else [args.operacion]
    )
    usar_ia = not args.sin_ia

    logger.info("=" * 60)
    logger.info("SCRAPING INMOBILIARIO BCRP (EJEMPLO) — %s", datetime.now())
    logger.info("Portales: %s | Operaciones: %s | Páginas: %s | IA: %s",
                ", ".join(portales), ", ".join(operaciones), args.paginas,
                "sí" if usar_ia else "no")
    logger.info("=" * 60)

    total = 0
    for portal in portales:
        for operacion in operaciones:
            df, _ = ejecutar_scraping(
                portal, operacion, args.paginas,
                usar_ia=usar_ia, headless=args.headless,
                usar_tc=not args.sin_tc,
            )
            if df is not None:
                total += len(df)
    logger.info("Total anuncios procesados: %s", total)
    logger.info("Salidas en: %s", config.CARPETA_SALIDA)


if __name__ == "__main__":
    main()
