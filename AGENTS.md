# AGENTS.md — instrucciones para agentes IA (Claude, Codex, etc.)

> **Audiencia**: agentes IA que vayan a construir, ampliar o mantener
> scrapers usando este framework. Si eres una persona buscando entender
> el proyecto, empezá por [`README.md`](README.md).

> **Punto de partida obligatorio (cualquier agente: Claude, Codex,
> Antigravity, Gemini…).** Ante CUALQUIER pedido de scraping del BCRP, lo
> primero es leer este archivo y `core/` antes de escribir código. No se
> arranca un scraper desde cero ni se reinventa un patrón que ya vive en
> `core/`. Esta metodología es el contrato; el código nuevo se construye
> copiando `plantilla_proyecto/` y reutilizando `core/`.

## Filosofía del proyecto

`bcrp-scraping` es una librería de **metodologías**, no una colección de
scrapers. Cada patrón en `core/` está aquí porque resolvió un problema
real durante el desarrollo del scraping inmobiliario v1. La meta es que
cualquier scraper nuevo (empleo, financiero, comercio, etc.) reutilice
estos patrones en vez de reinventarlos.

El objetivo base es que este repositorio funcione como **contrato de trabajo
para agentes IA**: Codex, Claude, Gemini, OpenAI API, Anthropic API o cualquier
otro modelo debe poder leer estas reglas y construir un sector nuevo sobre
la metodología BCRP ya validada. No optimices para "hacer que corra una vez";
optimiza para trazabilidad, memoria histórica, evidencia auditable y
reproducibilidad institucional.

**Regla mental**: si vas a copiar lógica entre dos sectores, primero
pregúntate "¿debería esto vivir en `core/`?".

## Compuerta de intake (NO se rompe — antes de escribir código)

Cuando el usuario pide scrapear un **sitio nuevo**, NO empieces a escribir
código de inmediato. Un scraper sin contexto produce datos que nadie pidió y
desperdicia trabajo. Primero completá esta compuerta en dos pasos:

**Paso 1 — Entrevista de propósito (antes de tocar el sitio).** Preguntá al
usuario y registrá las respuestas:

- **¿Para qué?** ¿Qué pregunta económica/analítica del BCRP responde este
  scraping? (ej. seguimiento de precios de alquiler, vacantes por sector).
- **¿Qué universo?** Región/segmento/operación de interés y qué dejar fuera.
- **¿Qué horizonte?** ¿Foto puntual o serie longitudinal? (define si hace
  falta historial SQLite + ciclo de vida o basta un volcado).

**Paso 2 — Exposición de hallazgos (después de inspeccionar/parsear la
página, antes de construir el pipeline).** Inspeccioná la fuente (HTML,
`__NEXT_DATA__`, JSON-LD, XHR/API, PDF) y devolvé al usuario, para que
confirme antes de codear:

- **Qué datos hay disponibles realmente** por anuncio/registro (lista de
  campos observados, no los deseados), y la fuente de cada uno.
- **Temporalidad del dato**: ¿hay fecha de publicación? ¿es absoluta o
  relativa ("hace 3 días")? El periodo analítico SIEMPRE sale de la fecha
  de publicación, nunca de la de extracción.
- **Volumen y paginación**: ¿cuántos registros, cuántas páginas?
- **Cada cuánto correr**: cadencia sugerida (diaria/quincenal/mensual) según
  cómo se actualiza la fuente y el uso analítico.
- **Estrategia de acceso**: ¿`core.http` (requests) basta o exige
  `core.browser`? ¿hay anti-bot? ¿API oficial?
- **Riesgos/lagunas**: campos ausentes, anti-bot, calidad dudosa.

Sólo después de que el usuario confirma propósito + hallazgos, se diseña el
sector siguiendo `docs/agregar_nuevo_sector.md`. Si el usuario ya dio todo
el contexto explícitamente, resumilo y confirmá en una línea — no lo saltes
en silencio.

## Capas

```
core/                ← reutilizable, sector-agnóstico. Se cambia con cuidado.
plantilla_proyecto/  ← estructura ESTÁNDAR de un scraper nuevo (se copia).
```

Este repo es **metodología pura**: `core/` (patrones reutilizables) +
`plantilla_proyecto/` (el estándar de archivos que tiene cualquier scraper).
No hay scrapers de producción adentro. Cada proyecto real (inmobiliario,
empleo, diarios/PDF…) vive en su propia carpeta/repo, copia la plantilla y
trae de `core/` SÓLO lo que importa (ver "Proyectos standalone" abajo).

**Núcleo `core/` disponible** (ver docstrings de cada `__init__.py`
para la API exacta):

| Módulo | Para qué |
|---|---|
| `core.http` | **HTTP-first**: `HttpClient` (`requests` + retries + throttle + `connect_timeout` para fail-fast en hosts bloqueados) y `detectar_bloqueo_anti_bot(status, texto)`. Primera opción para portales con HTML server-side / JSON / XHR. Empezar liviano; escalar a `core.browser` sólo cuando la detección anti-bot dispara |
| `core.browser` | `BrowserManager` con undetected-chromedriver, monkeypatch __del__, delays aleatorios anti-bot, cierre de cookies, override `CHROME_VERSION_MAIN`. **No es el default**: usar sólo si el portal exige navegador real (SPA dependiente de JS o bloqueo anti-bot confirmado) |
| `core.ingesta` | Ingesta documental: PDF por columnas (`leer_pdf_columnas`), **extracción de tablas** (`extraer_tablas_pdf`: lattice con bordes + stream por geometría de palabras para tablas sin bordes) y segmentación por código/sección para diarios, boletines o clasificados impresos. La geometría (`reconstruir_tabla`) es pura y testeable sin PDF |
| `core.redux` | Parser de `__NEXT_DATA__` y búsqueda recursiva por clave. Para SPAs Next.js / portales hidratados (Navent, etc.) |
| `core.limpieza` | Helpers puros: `parsear_numero`, `parsear_entero`, `moneda_a_iso`, `limpiar_precio_pe`, `limpiar_fecha_relativa`. Periodos: `derivar_periodo` y `agregar_columnas_periodo(df, "fecha_publicacion")` → columnas `anio`/`trimestre` (`YYYY-T{1..4}`)/`mes` (`YYYY-MM`) para agregación BCRP |
| `core.modelos` | `AnuncioBase` Pydantic + `EstadoAnuncio` + `RefAnuncio` (referencia ligera del listado). Cada sector hereda |
| `core.contratos` | `PortalScraper` (`Protocol`) + `ClientePreferido` (`http`/`browser`/`hybrid`). Formaliza HTTP-first en el código: cada portal declara su transporte y separa `descubrir_listado` (barato) de `extraer_detalle` (caro). Tipado estructural — no exige herencia |
| `core.extractor_ia` | `DeepSeekExtractor` (cliente OpenAI-compatible con fallback Flash→Pro) + `CachePublicaciones` (SQLite por `publicacion_id + descripcion_hash + campo`) |
| `core.historial` | `HistorialSQLite` multi-sector con ciclo de vida (nuevo/repetido/desaparecido/dado de baja) y bitácora. Seguridad: `listado_completo` (un listado parcial NO marca bajas), guarda anti-colapso (una corrida encogida no borra historial) y retiro por vejez (`dias_vejez`) para listados con tope de páginas |
| `core.calidad` | `evaluar_cobertura(df, umbrales, señales)` → `Veredicto` (OK/advertencia/degradado), compuerta pre-IA. `nuevo_diagnostico_scraping(...)` shape estándar. `detectar_duplicados(...)` — agrupa candidatos cross-source por similitud como **señal** para revisión humana (NUNCA borra) + `aplicar_resaltado_duplicados` |
| `core.snapshots` | `guardar_snapshot_html(driver, portal, op, pagina, etapa, carpeta, diagnostico)` — captura HTML renderizado y registra en `diagnostico["snapshots_html"]` |
| `core.mantenimiento_frontend` | `generar_reporte_mantenimiento_frontend(...)` — Markdown auditable con cobertura, JSON diagnóstico, snapshots, mapa portal→funciones probables. Para corridas degradadas / sin_datos / excepción |
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
   es siempre `core/utils` → `core/<otros>` → `<mi_proyecto>`.

## Reglas que NO se rompen nunca

- **Nunca importar del paquete del proyecto desde `core/`.** La dirección
  es de un solo sentido: el proyecto importa `core/`, nunca al revés.
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
- **Nunca tratar al proveedor IA como metodología.** Hoy el template usa
  DeepSeek por costo y compatibilidad OpenAI, pero el patrón real es:
  reglas determinísticas + cache + IA solo para pendientes + salida auditable.
  Si se cambia a OpenAI, Anthropic, Gemini u otro, se cambia el adaptador,
  no las reglas de negocio.
- **Nunca omitir las columnas de periodo si el sector tiene fecha.** El
  BCRP agrega por trimestre. Llamar `agregar_columnas_periodo(df,
  "fecha_publicacion")` en la limpieza y declarar `anio/trimestre/mes`
  en `campos_snapshot` para que existan también en SQL.
- **Nunca mutar ausencias/bajas con reruns o fuentes degradadas.** Para
  PDFs, diarios o ediciones periódicas usar `id_fuente` en
  `HistorialSQLite.registrar_corrida(...)`. Un rerun no debe inflar
  ediciones ni dar de baja avisos por accidente.
- **El alcance del ciclo de vida es el EJE DE CONSULTA, nunca un campo del
  dato.** `campo_operacion` debe ser lo que pediste en la corrida (región
  consultada, tipo de operación, rubro), no lo que el portal declara dentro
  del anuncio. Si una corrida de `AREQUIPA` pudiera marcar ausencias de
  `TACNA`, el alcance está mal definido. Separá "región consultada" de
  "región observada" cuando difieran (lección de empleo: `region_consulta`
  ≠ `region` del aviso).
- **Un listado parcial NO marca ausencias ni bajas.** Si el scraper llegó a
  un tope de páginas con indicios de más resultados, pasá
  `listado_completo=False` a `registrar_corrida(...)` y registrá
  `diagnostico["listado_completo"]=False`. Un universo truncado no prueba que
  un aviso desapareció. Para esos portales, el retiro se hace por vejez
  (`dias_vejez`), no por ausencia.
- **La deduplicación por similitud NUNCA borra automáticamente.** El historial
  deduplica por `enlace` canónico exacto (automático). La similitud entre
  fuentes (`core.calidad.detectar_duplicados`) sólo SEÑALA candidatos para
  que un humano decida. Pintar/agrupar, sí; eliminar filas por similitud sin
  revisión, jamás.
- **`scraper.py` del proyecto es fachada delgada.** Sólo rutea al
  módulo correspondiente en `portal_scrapers/<portal>.py`. Cualquier
  lógica de parseo va en el módulo del portal, NO en la fachada. Los
  tests parchean el módulo real, no la fachada.
- **Toda corrida fallida deja evidencia.** Si una corrida queda
  degradada, sin_datos o lanza excepción, el sector DEBE llamar a
  `generar_reporte_mantenimiento_frontend(...)` y los `portal_scrapers`
  DEBEN haber llamado `guardar_snapshot_html(...)` en cada página.
  Sin evidencia, una IA auditora no puede reparar el portal.
- **Nunca dejar copias muertas de `core/` en un proyecto.** Si construís un
  proyecto standalone (fuera de este repo) que adopta metodología, copiá
  SÓLO los módulos que el proyecto realmente importa, anotá su procedencia
  en un manifiesto y corré la compuerta de poda antes de cerrar. Un módulo
  con 0 importadores se borra. Ver "Proyectos standalone" abajo.
- **HTTP-first.** No abras un navegador "por las dudas". Empezá con
  `core.http` (requests). Escalá a `core.browser` sólo si el portal es una
  SPA que depende de JS o si `detectar_bloqueo_anti_bot` confirma un
  desafío. Un Chrome por anuncio es el antipatrón más caro del proyecto.

## Cómo construir un proyecto nuevo

Receta corta — copiá la plantilla estándar y renombrala:

```bash
cp -r plantilla_proyecto <mi_proyecto>
```

Luego seguir [`docs/agregar_nuevo_sector.md`](docs/agregar_nuevo_sector.md)
paso a paso. La plantilla ya tiene (imports internos **relativos**, así que
renombrar el paquete no rompe nada):

- `config.py` con slots para URLs, delays, umbrales, paths.
- `modelos.py` con un `AnuncioMiProyecto(AnuncioBase)` listo para extender.
- `scraper.py` + `portal_scrapers/portal_a.py` con el patrón Redux→DOM→regex.
- `limpieza.py` con el pipeline-shape.
- `extractor_ia.py` con cache + DeepSeek ya cableado.
- `main.py` con la orquestación de fases y CLI argparse.

Cada archivo tiene `# TODO:` con anclas concretas — no hay que descubrir
las dependencias a fuerza de `grep`. La plantilla es un **scaffold guiado**:
no es producción hasta que el agente complete los TODOs, defina umbrales,
agregue fixtures y corra tests. Ese conjunto de archivos es **el estándar**:
todo scraper nuevo se ve igual, sin importar el sector.

## Proyectos standalone: cómo consumir la metodología sin copias muertas

Un proyecto real vive en su propia carpeta/repo y **no puede importar `core/`
por path**. El riesgo es copiar `core/` entero y terminar con módulos que
nadie usa, ensuciando el árbol y confundiendo a quien revisa archivo por
archivo (problema real observado en empleo: se copió `comun/modelos` y otros
sin importadores).

**Generación selectiva + poda (obligatorio):**

- **Generá sólo lo que el proyecto importa.** No copies `core/` completo.
  Si el proyecto sólo hace HTTP y limpieza, su paquete compartido (p. ej.
  `<proyecto>/comun/`) tiene HTTP + limpieza + lo transversal mínimo
  (historial, calidad, reportes). Nada más "por si acaso".
- **Anotá la procedencia en un manifiesto.** Un archivo
  `comun/PROCEDENCIA.md` con una fila por módulo adoptado:
  `módulo | origen en bcrp-scraping | fecha copiada | adaptaciones`. Esto
  hace **visible la desincronización** (que es manual y por diseño) y
  permite re-sincronizar un módulo puntual sin adivinar de dónde salió.
- **Corré la compuerta de poda antes de cerrar.** Todo módulo del paquete
  compartido con **0 importadores** se borra. Herramienta reusable en `core/`:
  `python -m core.poda <ruta_paquete>` (lista módulos sin importadores). No
  cierres una tarea con código muerto adentro.

Detalle completo y ejemplos en
[`docs/distribucion_proyecto_nuevo.md`](docs/distribucion_proyecto_nuevo.md).

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

## HTTP-first y escalado a navegador

Lección del sector empleo (3 de 4 portales sin Selenium): **el navegador es
la excepción, no el default**. Abrir Chrome es caro, frágil y casi nunca
necesario. El orden correcto al atacar un portal:

1. **¿Hay API oficial / JSON / XHR?** Consumir directo con `core.http`.
2. **¿HTML server-side?** `core.http` + parser (BeautifulSoup / regex /
   JSON-LD embebido `<script type="application/ld+json">`).
3. **¿SPA que hidrata con JS (Next.js, etc.)?** Muchas veces el estado ya
   viene en `__NEXT_DATA__` y se lee con `core.redux` SIN navegador. Probá
   eso antes de Selenium.
4. **Sólo si lo anterior no alcanza** (render 100% client-side sin blob, o
   anti-bot confirmado) → `core.browser` (undetected-chromedriver).

`HttpClient` trae un `connect_timeout` corto: un host bloqueado por firewall
cae en segundos en vez de colgar `read_timeout × retries` (caso real SERVIR).

**Escalado informado, no preventivo.** El scraper empieza liviano y, ante un
desafío, `core.http.detectar_bloqueo_anti_bot(status, texto)` marca el
momento exacto. Guardalo en `diagnostico["anti_bot"]`: el reporte de
mantenimiento lo clasifica como `ANTI_BOT` y recomienda portar la operación
a `core.browser`. Así el código nuevo no arrastra Selenium "por si acaso".

**Declaralo en el contrato.** Cada portal implementa `core.contratos.PortalScraper`
y fija `cliente_preferido` (`"http"` / `"browser"` / `"hybrid"`). Eso documenta
la decisión de transporte en el código, no sólo en prosa, y separa
`descubrir_listado` (barato, devuelve `RefAnuncio`) de `extraer_detalle` (caro)
para pagar el detalle SÓLO de las refs nuevas.

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

La secuencia correcta es:

1. Resolver con parser determinístico o API oficial.
2. Aplicar cache.
3. Enviar a IA solo filas/campos pendientes.
4. Guardar respuesta nueva con fuente/modelo.
5. Nunca permitir que una respuesta IA sin validación contamine SQLite.

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

## Revisión humana y capa limpia (dos capas que no se pisan)

Cuando un sector necesita curación humana (deduplicar entre fuentes, corregir
campos), separá SIEMPRE la captura cruda de la salida revisada. El scraper
nunca escribe sobre lo limpio:

- **Capa cruda**: la tabla `anuncios` del historial. Es lo que el scraper
  escribe y nunca se edita a mano.
- **Capa revisada**: tablas adicionales en la MISMA base (no SQLite mensuales
  sueltos): un **ledger de decisiones** (qué hizo el humano: mantener /
  fusionar / eliminar_duplicado / corregir, con observación y revisor) y una
  tabla **materializada limpia** por periodo de revisión.

Flujo: (1) generar un Excel `_pre` del periodo con las columnas de control
(`dup_grupo`, `dup_score`, `decision_revision`, `corregir_*`) y las filas
candidatas a duplicado resaltadas; (2) el técnico marca decisiones; (3) se
importan al ledger y se materializa la salida limpia. Reglas:

- El **color es sólo ayuda visual**; la verdad revisable son las columnas
  (`dup_grupo`, `dup_score`, `decision_revision`), no el resaltado.
- El **periodo de revisión es operativo** (sale de captura/`ultima_vez_visto`)
  y NO reemplaza al periodo analítico (que sale de `fecha_publicacion`).
- El técnico **no borra filas libremente**: marca una acción. El borrado real
  lo decide la materialización a partir del ledger, que queda auditable.

Esto es metodología, no código de `core/` todavía: las tablas y columnas
concretas dependen del sector. `core.calidad.detectar_duplicados` aporta la
señal; el resto (Excel `_pre`, ledger, materialización) lo orquesta el sector.

## Cuándo NO usar este framework

- Scrapers de **un solo uso** (extracción ad-hoc de una página) — para
  eso basta `requests` + `bs4`.
- Sitios que **no requieren JS** (APIs públicas) — usar `requests`
  directamente y skipear el browser.
- Cuando el portal **provee API oficial** (ej. BCRPData) — consumirla
  directo. El módulo `core.tipo_cambio.bcrp` hace exactamente eso.
- Cuando la fuente es documental/PDF y no web: seguir
  [`docs/fuentes_documentales.md`](docs/fuentes_documentales.md). No forzar
  Selenium ni parser HTML sobre un diario impreso.

## Mantenimiento dinámico ante cambios de frontend

El framework no auto-repara cuando un portal cambia su HTML. Lo que
sí hace es producir, en cada corrida fallida, un **paquete auditable**
que cualquier agente IA (Claude, Codex, Antigravity) puede consumir
sin reproducir la condición:

* `resultados/snapshots_frontend/` — HTML renderizado de cada página
  visitada, con timestamp + portal + operación + página + etapa en
  el nombre. Se captura en cada llamada a `guardar_snapshot_html` que
  hagan los `portal_scrapers`.
* `resultados/reportes_mantenimiento_frontend/` — un Markdown por
  corrida fallida con: motivos, cobertura, diagnóstico JSON, lista
  de snapshots, mapa portal→funciones probables, e instrucciones
  específicas para la IA auditora.
* `resultados/degradadas/` — Excel separado con la corrida que NO
  entró al historial.

El reporte abre con una **clasificación automática del fallo**
(`core.mantenimiento_frontend.clasificar_fallo`): categoría
(`RED_O_PORTAL_CAIDO` / `ANTI_BOT` / `FRONTEND_LISTADO` / `DETALLE` /
`COBERTURA_BAJA` / `EXCEPCION`), si es o no bug de código, y la superficie
EXACTA a tocar. Esto evita que la IA auditora revise todo el proyecto: si la
categoría es `RED_O_PORTAL_CAIDO`, **no es código — se detiene y avisa**.

### Protocolo para una IA auditora que recibe un reporte

1. Leer la **clasificación automática** primero. Si dice "no es bug de
   código" (red/portal caído), detenerse y reportar al técnico.
2. Abrir SÓLO los archivos de "Tocar SOLO estos archivos/funciones" del
   reporte (la superficie de la categoría), más los snapshots HTML.
3. Abrir los snapshots HTML referenciados — comparar con fixtures
   antiguos si existen.
4. Identificar causa real: cambio de frontend / Redux / anti-bot /
   parser local / regresión en limpieza.
5. **Reparar SÓLO la superficie afectada** — el módulo del portal en
   `portal_scrapers/<portal>.py`. No mover módulos transversales.
6. Agregar fixture local + test que cubra el caso reparado.
7. Correr tests del sector. Si pasan, corrida acotada de validación.
8. Verificar que el historial SQLite NO recibió datos contaminados.

## Documentación viva

- [`docs/arquitectura.md`](docs/arquitectura.md) — capas y flujo.
- [`docs/convenciones.md`](docs/convenciones.md) — idioma y estilo.
- [`docs/agregar_nuevo_sector.md`](docs/agregar_nuevo_sector.md) — checklist paso a paso.
- [`docs/fuentes_documentales.md`](docs/fuentes_documentales.md) — metodología PDF/diarios.
- [`docs/runbook_operacion.md`](docs/runbook_operacion.md) — troubleshooting.
