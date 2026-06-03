# sectores/inmobiliario — EJEMPLO ILUSTRATIVO

> ⚠️ **No es producción y NO se sincroniza solo.** Es una demostración
> congelada de cómo un sector compone `core/` en un pipeline completo. El
> scraper inmobiliario productivo del BCRP vive en
> `../../INMOBILIARIA/v1-portales-web/` y se mantiene aparte.

## Por qué existe (y por qué es mínimo)

Una IA agente (o una persona) que va a construir un sector nuevo necesita
ver **un caso end-to-end real** que ya consume `core/`. Este ejemplo se
reduce **a propósito a UN tipo de portal (Navent: Urbania / AdondeVivir)**
para ser legible y testeable sin red. No intenta cubrir todos los portales
ni competir con producción.

Históricamente este directorio era una copia casi completa de una versión
vieja de v1 — quedó desfasada respecto al propio framework (le faltaban
snapshots, diagnóstico y mantenimiento). Se redujo a este ejemplo mínimo
para que **demuestre la metodología vigente**, no una versión antigua.

## Qué demuestra (pipeline vigente del framework)

1. `scraper.py` — fachada delgada que rutea a `portal_scrapers/navent.py`.
2. `portal_scrapers/navent.py` — Redux → DOM en cascada, construye el
   `diagnostico` estándar (`core.calidad`) y captura snapshots HTML
   (`core.snapshots`) por página.
3. `limpieza.py` — helpers de `core.limpieza` + columnas de periodo
   (`agregar_columnas_periodo`, `derivar_periodo`).
4. `main.py` — compuerta de calidad **real** (`core.calidad.evaluar_cobertura`,
   no un gate casero), aislamiento de degradadas + reporte de mantenimiento
   con clasificación de fallo (`core.mantenimiento_frontend`,
   `SUPERFICIE_POR_CATEGORIA`), IA con cache, NSE (`core.nse`), tipo de cambio
   BCRP (`core.tipo_cambio`: columnas estimadas auditables pintadas en rojo) e
   historial (`core.historial`) + Excel acumulativo (`core.reportes`).

## Reglas de este directorio

- **No replicar mejoras de producción aquí.** Si un patrón nuevo vale la
  pena, sube a `core/`. Este sigue siendo una vitrina, no un fork de v1.
- **No correrlo como producción.** Paths, base NSE y `.env` reales no
  están aquí; producción es v1-portales-web.
- La **base NSE** (`datos/base_nse_arequipa.xlsx`) NO se versiona: si no
  existe, la clasificación NSE se omite y el ejemplo corre igual.

## Para construir un sector nuevo

Ver [`../../docs/agregar_nuevo_sector.md`](../../docs/agregar_nuevo_sector.md)
y el scaffold en [`../_template/`](../_template/).
