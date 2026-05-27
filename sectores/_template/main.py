"""Orquestador principal del sector <SECTOR>.

Pipeline estándar (v1-validado):
    1. Scraping → (datos_crudos, diagnostico) con snapshots HTML por etapa.
    2. Limpieza → DataFrame normalizado.
    3. Compuerta de calidad → Veredicto OK / advertencia / degradado.
        - Si degradado/sin_datos/excepcion: exportar a `degradadas/` Y
          generar reporte Markdown para la IA de mantenimiento. NO continuar.
    4. Enriquecimiento IA (sólo corridas aptas) con cache SQLite.
    5. Historial SQLite → ciclo de vida (nuevo/repetido/desaparecido/baja).
    6. Excel acumulativo (Consolidado + Diagnostico).
    7. Formato visual + columnas estimadas en rojo (si aplica TC).

Uso:
    python -m sectores.<mi_sector>.main --portal portal_a --paginas 5 --sin-ia
"""

from __future__ import annotations

import argparse
import logging
import traceback
from datetime import datetime

from core.calidad import (
    EstadoCalidad,
    evaluar_cobertura,
    nuevo_diagnostico_scraping,
)
from core.historial import HistorialSQLite
from core.logging import configurar_logging
from core.mantenimiento_frontend import generar_reporte_mantenimiento_frontend
from core.reportes import ExcelAcumulativo, Hoja

logger = logging.getLogger("scraping")


def ejecutar_scraping(
    portal: str,
    operacion: str | None,
    num_paginas: int,
    usar_ia: bool = True,
    headless: bool = False,
) -> dict:
    """Una corrida = un (portal, operación). Devuelve resumen."""
    from sectores._template import config  # TODO: reemplazar al copiar
    from sectores._template.scraper import scrape_portal_con_diagnostico  # noqa: F401
    # from sectores._template.limpieza import pipeline_limpieza
    # from sectores._template.extractor_ia import procesar_con_ia

    diagnostico: dict = {}
    df = None
    excepcion_texto: str | None = None

    try:
        datos, diagnostico = scrape_portal_con_diagnostico(
            portal, operacion, num_paginas, headless=headless
        )
        # df = pipeline_limpieza(datos, portal, operacion)

        # veredicto = evaluar_cobertura(
        #     df,
        #     umbrales=config.UMBRALES_CALIDAD.get(diagnostico.get("estrategia")),
        # )
        # veredicto.loggear(f"{portal}/{operacion}")
        #
        # if not veredicto.apta_para_historial:
        #     ruta_degradada = _exportar_corrida_degradada(df, portal, operacion, veredicto)
        #     generar_reporte_mantenimiento_frontend(
        #         portal=portal,
        #         operacion=operacion,
        #         estado=veredicto.estado.value,
        #         carpeta_reportes=config.CARPETA_REPORTES_MANTENIMIENTO,
        #         motivos=list(veredicto.motivos),
        #         diagnostico=diagnostico,
        #         df=df,
        #         ruta_degradada=ruta_degradada,
        #         codigo_por_portal=config.CODIGO_POR_PORTAL,
        #     )
        #     return {"estado": veredicto.estado.value, "anuncios": len(df)}
        #
        # if usar_ia:
        #     df = procesar_con_ia(df, config.SECTOR, config.RUTA_DB, ...)
        #
        # historial = HistorialSQLite(
        #     ruta_db=config.RUTA_DB, sector=config.SECTOR,
        #     campos_snapshot=[("titulo", "TEXT"), ("precio", "REAL"), ...],
        #     umbral_ausencias=config.UMBRAL_AUSENCIAS,
        #     campo_operacion="tipo_operacion" if config.OPERACIONES else None,
        # )
        # df, stats = historial.registrar_corrida(df, portal, operacion,
        #                                         estado_calidad=veredicto.estado.value)
        #
        # exporter = ExcelAcumulativo(
        #     ruta_archivo=str(config.CARPETA_SALIDA / config.NOMBRE_ARCHIVO_CONSOLIDADO),
        #     hojas=[Hoja("Consolidado", ["enlace"]),
        #            Hoja("Diagnostico", ["enlace", "fecha_extraccion"])],
        # )
        # exporter.escribir({"Consolidado": df, "Diagnostico": df})
        raise NotImplementedError
    except Exception:
        excepcion_texto = traceback.format_exc()
        logger.exception("Excepcion en %s/%s", portal, operacion)
        generar_reporte_mantenimiento_frontend(
            portal=portal,
            operacion=operacion,
            estado="excepcion",
            carpeta_reportes=config.CARPETA_REPORTES_MANTENIMIENTO,
            motivos=[f"Excepcion durante la corrida: {excepcion_texto.splitlines()[-1][:200]}"],
            diagnostico=diagnostico,
            df=df,
            excepcion=excepcion_texto,
            codigo_por_portal=getattr(config, "CODIGO_POR_PORTAL", None),
        )
        return {"estado": "excepcion", "anuncios": 0}


def main() -> None:
    from sectores._template import config  # TODO: reemplazar al copiar

    configurar_logging(config.CARPETA_LOGS)

    parser = argparse.ArgumentParser(description=f"Scraping {config.SECTOR} BCRP")
    parser.add_argument(
        "--portal", choices=config.PORTALES_SOPORTADOS + ["todos"], default="todos"
    )
    parser.add_argument("--paginas", type=int, default=config.DEFAULT_NUM_PAGINAS)
    parser.add_argument("--sin-ia", action="store_true")
    parser.add_argument("--headless", action="store_true")
    if config.OPERACIONES:
        parser.add_argument(
            "--operacion", choices=config.OPERACIONES + ["todas"], default="todas"
        )
    args = parser.parse_args()

    portales = config.PORTALES_SOPORTADOS if args.portal == "todos" else [args.portal]
    operaciones = (
        config.OPERACIONES if (config.OPERACIONES and args.operacion == "todas")
        else ([args.operacion] if config.OPERACIONES else [None])
    )

    logger.info("=" * 60)
    logger.info("SCRAPING %s — %s", config.SECTOR, datetime.now())
    logger.info("=" * 60)

    for portal in portales:
        for operacion in operaciones:
            ejecutar_scraping(
                portal, operacion, args.paginas,
                usar_ia=not args.sin_ia, headless=args.headless,
            )


if __name__ == "__main__":
    main()
