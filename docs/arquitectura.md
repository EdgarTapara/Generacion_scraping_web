# Arquitectura — bcrp-scraping

> Documento vivo. Actualizar cuando se mueva un patrón a `core/` o se
> agregue un módulo nuevo.

## Fuente de verdad del diseño

- [`AGENTS.md`](../AGENTS.md) — instrucciones para agentes IA, filosofía y reglas.
- [`PLAN_PROYECTO_SCRAPING_BCRP.md`](../../PLAN_PROYECTO_SCRAPING_BCRP.md) — roadmap y decisiones de fondo (Sprint 0).
- `v1/` (carpeta hermana) — implementación productiva del scraper
  inmobiliario, validada en informe interno. Es la referencia técnica de
  cada patrón que termina en `core/`.

## Capas

```
┌─────────────────────────────────────────────────────────┐
│  sectores/<x>/                                           │
│   - config / modelos / scraper / portales / limpieza     │
│   - extractor_ia (sector-specific prompt + cache cableado)│
│   - main (CLI orquestador)                                │
└─────────────────────────────────────────────────────────┘
                       ▲
                       │ depende
                       │
┌─────────────────────────────────────────────────────────┐
│  core/                                                   │
│   - utils, redux, browser, limpieza, modelos            │
│   - extractor_ia, historial, calidad                    │
│   - tipo_cambio, nse, reportes, logging                  │
└─────────────────────────────────────────────────────────┘
```

**Regla**: `core/` nunca importa de `sectores/`. La dirección es de un
solo sentido.

## Módulos `core/` y para qué sirven

| Módulo | Responsabilidad | API destacada |
|---|---|---|
| `core.utils` | Normalización canónica (enlaces, texto, hashing) y generación de `publicacion_id` cross-sector | `normalizar_enlace`, `descripcion_hash`, `publicacion_id`, `asignar_publicacion_id` |
| `core.redux` | Extracción de `__NEXT_DATA__` y búsqueda recursiva genérica | `extraer_next_data`, `buscar_clave_recursivo`, `extraer_redux_state` |
| `core.browser` | Singleton Chrome con undetected-chromedriver, anti-bot patches | `BrowserManager`, `buscar_texto`, `buscar_texto_rapido` |
| `core.limpieza` | Helpers puros de parsing genéricos | `parsear_numero`, `parsear_entero`, `moneda_a_iso`, `limpiar_precio_pe`, `limpiar_fecha_relativa` |
| `core.modelos` | Schema base de cualquier anuncio web | `AnuncioBase`, `EstadoAnuncio` |
| `core.extractor_ia` | Cliente DeepSeek + interfaz extensible + cache SQLite | `ExtractorIA`, `DeepSeekExtractor`, `CachePublicaciones` |
| `core.historial` | SQLite acumulativo con ciclo de vida (nuevo→repetido→desaparecido→baja) | `HistorialSQLite` |
| `core.calidad` | Compuerta pre-IA con umbrales + señales + diagnóstico estándar | `evaluar_cobertura`, `Veredicto`, `EstadoCalidad`, `nuevo_diagnostico_scraping` |
| `core.snapshots` | Captura de HTML renderizado por etapa para auditoría | `guardar_snapshot_html` |
| `core.mantenimiento_frontend` | Generador de reporte Markdown para handoff con IA auditora | `generar_reporte_mantenimiento_frontend` |
| `core.tipo_cambio` | BCRP DataAPI + cache + conversión auditable | `descargar_tipo_cambio_bcrp`, `aplicar_conversion_tipo_cambio`, `marcar_columnas_estimadas_excel` |
| `core.nse` | Clasificación por urbanización (lookup, sin ML) | `NSEClassifier`, `NSEConfig`, `asignar_nse_dataframe` |
| `core.reportes` | Excel acumulativo multi-hoja + formato visual | `ExcelAcumulativo`, `Hoja`, `aplicar_formato_hojas` |
| `core.logging` | Logging estructurado con archivo por corrida | `configurar_logging(carpeta_logs)` |

## Ciclo de vida del anuncio

Implementado por `core.historial.HistorialSQLite.registrar_corrida`:

| Estado | Regla |
|---|---|
| `nuevo` | Primera corrida en que aparece el `clave_registro` (sector + portal + operación + enlace canónico) |
| `repetido` | Existe en DB; snapshot se actualiza, `ausencias_consecutivas = 0` |
| `desaparecido` | Activo en DB pero no apareció esta corrida; `ausencias_consecutivas += 1` |
| `dado de baja` | `ausencias_consecutivas ≥ umbral_ausencias` (default inmobiliario: 3) |

La identidad del anuncio NO es el enlace bruto, es el enlace
**canonicalizado** (sin query, sin fragmento, sin slash final) — usar
siempre `core.utils.normalizar_enlace`.

## Flujo de una corrida

```
CLI → BrowserManager
   → scraper.scrape_portal_con_diagnostico
       → portales/<portal>.py (Redux → DOM → regex en cascada)
   → limpieza.pipeline_limpieza (helpers de core.limpieza)
   → core.calidad.evaluar_cobertura
       │ veredicto.estado == DEGRADADO → degradadas/ (no continúa)
       │ veredicto.estado == OK | ADVERTENCIA → continúa
       ▼
   → extractor_ia.procesar_con_ia
       (CachePublicaciones lookup → fallback regex → DeepSeek si falta)
   → historial.registrar_corrida
       (nuevo / repetido / desaparecido / baja)
   → ExcelAcumulativo.escribir (Consolidado + Diagnostico, dedup por hoja)
   → [opcional] aplicar_conversion_tipo_cambio
   → [opcional] aplicar_formato_hojas + marcar_columnas_estimadas_excel
```

## Fuente de verdad por sistema

- **SQLite** (`resultados/historial_<sector>.db`) es la **fuente de verdad
  longitudinal**. Todo el historial canónico vive ahí.
- **Excel** (`consolidado_<sector>.xlsx`) es una vista cómoda. Si se
  corrompe, se puede regenerar desde SQLite + Diagnostico de corridas
  anteriores.
- **Cache de IA** (`ia_respuestas` en el mismo SQLite por defecto) es un
  optimización: si se borra, simplemente se reprocesa con DeepSeek.

## Auditoría visual del Excel

Columnas en **rojo (#C00000)** = valor imputado (no observado).
Hoy se usa para columnas estimadas por TC (`Monto S/ estimado TC`, ...).
Si un sector imputa otros campos (ej. salario_promedio_por_rango),
seguir la misma convención visual.

## Decisiones explícitas (no son bugs)

- **No paralelizar** el browser entre portales. Riesgo anti-bot > ganancia.
- **No usar ML para NSE** mientras la base esté desbalanceada (87% Alto+
  Medio Alto). Lookup auditable es suficiente.
- **No invertir** en geocodificación de direcciones ruidosas mientras
  las coordenadas Redux estén en 0%.
- **No usar el TC para sustituir** montos observados. Sólo se agregan
  columnas estimadas + auditoría.
