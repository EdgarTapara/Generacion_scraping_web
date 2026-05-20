"""Orquestador principal del sector <SECTOR>.

Pipeline estándar (v1-validado):
    1. Scraping → datos_crudos + diagnostico
    2. Limpieza → DataFrame normalizado
    3. Compuerta de calidad (core.calidad) → veredicto OK / advertencia / degradado
        - Si degradado: exportar a carpeta `degradadas/` y salir.
    4. Enriquecimiento IA (sólo corridas aptas)
    5. Historial SQLite → marca nuevos/repetidos/desaparecidos/bajas
    6. Exportar al consolidado acumulativo (Excel con Consolidado + Diag)
    7. Pulir formato visual del Excel + marcar columnas estimadas en rojo

Uso:
    python -m sectores.<mi_sector>.main --portal portal_a --paginas 5 --sin-ia
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime

from core.calidad import EstadoCalidad, evaluar_cobertura
from core.historial import HistorialSQLite
from core.logging import configurar_logging
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
    # TODO: implementar. Estructura recomendada:
    #
    # from sectores.<mi_sector> import config
    # from sectores.<mi_sector>.scraper import scrape_portal_con_diagnostico
    # from sectores.<mi_sector>.limpieza import pipeline_limpieza
    # from sectores.<mi_sector>.extractor_ia import procesar_con_ia
    #
    # datos, diag = scrape_portal_con_diagnostico(portal, operacion, num_paginas, headless)
    # df = pipeline_limpieza(datos, portal, operacion)
    #
    # veredicto = evaluar_cobertura(
    #     df,
    #     umbrales=config.UMBRALES_CALIDAD.get(diag.get("estrategia")),
    # )
    # veredicto.loggear(f"{portal}/{operacion}")
    # if not veredicto.apta_para_historial:
    #     # exportar a degradadas/ y salir
    #     ...
    #     return {"estado": veredicto.estado.value, "anuncios": len(df)}
    #
    # if usar_ia:
    #     df = procesar_con_ia(df, config.SECTOR, config.RUTA_DB,
    #                          api_key=config.DEEPSEEK_API_KEY,
    #                          modelo_primario=config.DEEPSEEK_MODEL,
    #                          modelo_secundario=config.DEEPSEEK_MODEL_2)
    #
    # historial = HistorialSQLite(
    #     ruta_db=config.RUTA_DB,
    #     sector=config.SECTOR,
    #     campos_snapshot=[("titulo", "TEXT"), ("precio", "REAL"), ...],
    #     umbral_ausencias=config.UMBRAL_AUSENCIAS,
    #     campo_operacion="tipo_operacion" if config.OPERACIONES else None,
    # )
    # df, stats = historial.registrar_corrida(df, portal, operacion,
    #                                          estado_calidad=veredicto.estado.value)
    #
    # exporter = ExcelAcumulativo(
    #     ruta_archivo=str(config.CARPETA_SALIDA / config.NOMBRE_ARCHIVO_CONSOLIDADO),
    #     hojas=[Hoja("Consolidado", ["enlace"]),
    #            Hoja("Diagnostico", ["enlace", "fecha_extraccion"])],
    # )
    # exporter.escribir({"Consolidado": df, "Diagnostico": df})
    raise NotImplementedError


def main() -> None:
    from sectores._template import config  # noqa: F401 — reemplazar al copiar

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
            try:
                ejecutar_scraping(portal, operacion, args.paginas,
                                  usar_ia=not args.sin_ia, headless=args.headless)
            except Exception as exc:
                logger.error("Error en %s/%s: %s", portal, operacion, exc)


if __name__ == "__main__":
    main()
