# AGENTS.md — instrucciones para agentes IA (Claude, Codex, etc.)

> **Audiencia**: agentes IA que vayan a construir, ampliar o mantener
> scrapers usando este framework. Si eres una persona buscando entender
> el proyecto, empezá por [`README.md`](README.md).

## Filosofía del proyecto

`bcrp-scraping` es una librería de **metodologías**, no una colección de
scrapers. Cada patrón en `core/` está aquí porque resolvió un problema
real durante el desarrollo del scraping inmobiliario v1. La meta es que
cualquier scraper nuevo (empleo, financiero, comercio, etc.) reutilice
estos patrones en vez de reinventarlos.

**Regla mental**: si vas a copiar lógica entre dos sectores, primero
pregúntate "¿debería esto vivir en `core/`?".

## Capas

```
core/                ← reutilizable, sector-agnóstico. Se cambia con cuidado.
sectores/<x>/        ← específico de cada dominio. Importa de core/.
sectores/_template/  ← scaffold para arrancar un sector nuevo.
sectores/inmobiliario/  ← ejemplo de referencia (NO producción — v1 sí lo es).
```

**Núcleo `core/` disponible** (ver docstrings de cada `__init__.py`
para la API exacta):

| Módulo | Para qué |
|---|---|
| `core.browser` | `BrowserManager` con undetected-chromedriver, monkeypatch __del__, delays aleatorios anti-bot, cierre de cookies, override `CHROME_VERSION_MAIN` |
| `core.redux` | Parser de `__NEXT_DATA__` y búsqueda recursiva por clave. Para SPAs Next.js / portales hidratados (Navent, etc.) |
| `core.limpieza` | Helpers puros: `parsear_numero`, `parsear_entero`, `moneda_a_iso`, `limpiar_precio_pe`, `limpiar_fecha_relativa` |
| `core.modelos` | `AnuncioBase` Pydantic + `EstadoAnuncio`. Cada sector hereda |
| `core.extractor_ia` | `DeepSeekExtractor` (cliente OpenAI-compatible con fallback Flash→Pro) + `CachePublicaciones` (SQLite por `publicacion_id + descripcion_hash + campo`) |
| `core.historial` | `HistorialSQLite` multi-sector con ciclo de vida (nuevo/repetido/desaparecido/dado de baja) y bitácora de corridas |
| `core.calidad` | `evaluar_cobertura(df, umbrales, señales)` → `Veredicto` con estado OK/advertencia/degradado. Compuerta pre-IA |
| `core.tipo_cambio` | BCRP DataAPI + cache SQLite + `aplicar_conversion_tipo_cambio` con columnas estimadas auditables |
| `core.nse` | Clasificador NSE por urbanización con fallback. Genérico: acepta cualquier tabla de referencia |
| `core.reportes` | `ExcelAcumulativo` (append + dedup multi-hoja) + `aplicar_formato_hojas` (header BCRP, freeze) |
| `core.logging` | `configurar_logging(carpeta_logs)` con archivo por corrida |
| `core.utils` | `normalizar_enlace`, `hash_enlace`, `descripcion_hash`, `publicacion_id`, `asignar_publicacion_id` |

## Reglas para subir un patrón a `core/`

1. **El patrón apareció en al menos 2 sectores** (YAGNI estricto).
2. Es **sector-agnóstico** — si tiene literales geográficos o de negocio,
   se exponen como parámetros con defaults.
3. Tiene **tests unitarios** sin red ni Chrome (fixtures locales).
4. No depende de otro módulo de `core/` por circularidad. La dirección
   es siempre `core/utils` → `core/<otros>` → `sectores/<x>`.

## Reglas que NO se rompen nunca

- **Nunca importar de `sectores/` desde `core/`.** La dirección es de
  un solo sentido.
- **Nunca usar Selenium o llamadas a red en tests.** Hay fixtures HTML
  y mocks para eso.
- **Nunca commitear `.env`** o claves API. `.env.example` con placeholders.
- **Nunca duplicar `normalizar_enlace`** en el código. La única
  implementación canónica vive en `core.utils.enlaces`. Si historial
  y cache IA usan formas distintas, los hits no coinciden.
- **Nunca asumir que el portal no cambió HTML.** Toda fuente de campo
  debe tener fallback en cascada (Redux → DOM → regex → None).
- **Nunca pasar datos degradados al historial SQLite.** La compuerta
  de `core.calidad` los desvía a `resultados/degradadas/`.

## Cómo construir un sector nuevo

Receta corta:

```bash
cp -r sectores/_template sectores/<mi_sector>
```

Luego seguir [`docs/agregar_nuevo_sector.md`](docs/agregar_nuevo_sector.md)
paso a paso. El template ya tiene:

- `config.py` con slots para URLs, delays, umbrales, paths.
- `modelos.py` con un `AnuncioMiSector(AnuncioBase)` listo para extender.
- `scraper.py` + `portales/portal_a.py` con el patrón Redux→DOM→regex.
- `limpieza.py` con el pipeline-shape.
- `extractor_ia.py` con cache + DeepSeek ya cableado.
- `main.py` con la orquestación de fases y CLI argparse.

Cada archivo tiene `# TODO:` con anclas concretas — no hay que descubrir
las dependencias a fuerza de `grep`.

## Convenciones de código

- **Español** para dominio (`anuncio`, `distrito`, `publicacion_id`).
- **Inglés** para tecnología (`browser`, `driver`, `batch`, `retry`).
- **Docstrings** en español, breves, orientadas al "por qué".
- **Comentarios** sólo cuando el "por qué" no es obvio desde el código.
  No comentar nombres de funciones que ya son explicitos.
- **Errors recuperables** → log WARNING + continuar.
- **Violaciones de negocio** → warning en columna `warnings`, no excepción.
- **Pre-compilar regexes** sólo si están en hot-path. Para una vez
  por corrida no vale la pena.

## Anti-bot — el problema persistente

Los portales peruanos y latam usan Cloudflare / DataDome / fingerprinting
nativo de Chromium. Por eso:

- Se usa `undetected_chromedriver`, no `selenium` puro.
- Hay un solo Chrome reutilizado por corrida (no abrir uno por anuncio).
- Hay delays aleatorios (uniform, no fijos) entre páginas.
- El monkeypatch `Chrome.__del__` evita un WinError 6 conocido en Windows.
- Si Chrome no inicia tras una actualización, override
  `CHROME_VERSION_MAIN` (env var, ya respetado por `BrowserManager`).

Si un portal mete CAPTCHA visual, hoy se atiende manualmente — no hay
solver automático.

## Cache de IA

`CachePublicaciones` indexa por `(publicacion_id, descripcion_hash, campo)`.
La normalización del texto antes de hashear vive en `core.utils.texto.descripcion_hash`
y debe usarse igual en TODO el pipeline. Si dos lugares hashean distinto,
no hay hit y se quema el token.

`publicacion_id` se arma como:
- `<sector>:<portal>:<operacion>:posting:<id_del_portal>` si existe.
- `<sector>:<portal>:<operacion>:url:<sha1_truncado_del_enlace_canonico>` si no.

El enlace canónico es el que devuelve `normalizar_enlace` — sin query,
sin fragmento, sin slash final. Ese mismo enlace es la PK lógica del
historial SQLite.

## Tipo de cambio BCRP

`aplicar_conversion_tipo_cambio` NO sobreescribe montos observados. Sólo
agrega columnas estimadas + auditoría:

```
Monto S/ estimado TC | Monto USD estimado TC | TC fecha dato | TC fecha usada |
TC compra | TC venta | TC usado | TC fuente | TC regla
```

Cuando se exporta a Excel, las columnas estimadas se pintan en fuente
roja (#C00000) usando `core.tipo_cambio.formato.marcar_columnas_estimadas_excel`
para que quien lea el Excel sepa qué es observado y qué es imputado.

## NSE

`NSEClassifier` no usa ML. Es un lookup `(distrito, urbanización)`
con fallbacks. Documentación de la decisión: ver `INFORME_NSE_METODOLOGIA.md`
de v1.

**No agregar** un clasificador ML hasta que la base histórica tenga
suficiente cobertura por categoría (hoy 87% es Alto + Medio Alto;
entrenar produciría sesgo sistemático).

## Cuándo NO usar este framework

- Scrapers de **un solo uso** (extracción ad-hoc de una página) — para
  eso basta `requests` + `bs4`.
- Sitios que **no requieren JS** (APIs públicas) — usar `requests`
  directamente y skipear el browser.
- Cuando el portal **provee API oficial** (ej. BCRPData) — consumirla
  directo. El módulo `core.tipo_cambio.bcrp` hace exactamente eso.

## Documentación viva

- [`docs/arquitectura.md`](docs/arquitectura.md) — capas y flujo.
- [`docs/convenciones.md`](docs/convenciones.md) — idioma y estilo.
- [`docs/agregar_nuevo_sector.md`](docs/agregar_nuevo_sector.md) — checklist paso a paso.
- [`docs/runbook_operacion.md`](docs/runbook_operacion.md) — troubleshooting.
