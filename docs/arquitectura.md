# Arquitectura — bcrp-scraping

> Documento vivo. Se completa durante S1 a medida que los módulos se consolidan.

## Fuente de verdad del diseño

Ver [`../../PLAN_PROYECTO_SCRAPING_BCRP.md`](../../PLAN_PROYECTO_SCRAPING_BCRP.md) secciones 2 y 3 para arquitectura aprobada y patrones heredados de `v1/`.

## Capas implementadas (S1 cerrado)

| Capa | Módulo | Notas |
|---|---|---|
| `core/browser/` | `BrowserManager`, `buscar_texto*` | Singleton Chrome con delays parametrizados, context manager |
| `core/logging/` | `configurar_logging(carpeta_logs)` | El caller decide la carpeta de logs por sector |
| `core/modelos/` | `AnuncioBase`, `EstadoAnuncio` | Campos comunes a cualquier anuncio web; `use_enum_values=True` |
| `core/limpieza/` | `parsear_numero`, `moneda_a_iso`, `limpiar_precio_pe`, `limpiar_fecha_relativa` | Helpers puros; fechas aceptan `referencia: datetime` para tests deterministas |
| `core/extractor_ia/` | `ExtractorIA` (ABC) + `DeepSeekExtractor` | Cliente OpenAI-compatible con fallback de modelos ante errores retryables |
| `core/historial/` | `HistorialSQLite` | Schema dinámico: el sector declara `campos_snapshot` y `campo_operacion` |
| `core/reportes/` | `ExcelAcumulativo` + `Hoja` | N hojas con claves de dedup independientes, merge sobre disco |

## Sectores

| Sector | Módulo | Notas |
|---|---|---|
| `sectores/inmobiliario/` | `main.py` CLI, `portales/{navent,properati,remax}.py` | Equivalente funcional a `v1/`. Consume `core/` para browser, historial, IA y reportes |

## Ciclo de vida del anuncio

Implementado por `core/historial/HistorialSQLite.registrar_corrida`:

| Estado | Regla |
|---|---|
| `nuevo` | Primera corrida en que aparece el enlace (canonicalizado sin query/fragment) |
| `repetido` | Ya existía; snapshot se actualiza, `ausencias_consecutivas = 0` |
| `desaparecido` | Activo en DB pero no apareció esta corrida; `ausencias_consecutivas++` |
| `dado_de_baja` | `ausencias_consecutivas ≥ umbral_ausencias` (inmobiliario: 3) |

## Flujo de una corrida (sector inmobiliario)

```
CLI → BrowserManager → scraper.scrape_portal
  → portales/{navent|properati|remax}.scrape_listados
  → pipeline_limpieza (core.limpieza + utils_sector)
  → extractor_ia.procesar_con_ia (core.DeepSeekExtractor + prompt sector + cache SQLite)
  → historial.registrar_corrida (HistorialSQLite)
  → construir_export_alberth (hoja Consolidado)
  → ExcelAcumulativo.escribir (append + dedup sobre Consolidado + Diagnostico)
```
