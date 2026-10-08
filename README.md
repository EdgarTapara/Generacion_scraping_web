# bcrp-scraping

Librería de **metodologías** de scraping reutilizables.

> **No es una colección de scrapers.** Es el núcleo de patrones y
> herramientas que cada scraper nuevo (empleo, financiero, comercio…)
> reutiliza en vez de reinventar. Si vienes a construir un scraper nuevo
> con un agente IA, leé primero [`AGENTS.md`](AGENTS.md).

La brújula correcta es esta: el proyecto busca convertir el aprendizaje de
inmobiliaria, empleo, diarios/PDF y APIs BCRP en una metodología reutilizable
para agentes IA. El código importa, pero el contrato principal está en
`AGENTS.md`, `core/`, `plantilla_proyecto/` y las guías de `docs/`.

> Este repo es **metodología pura**: no contiene scrapers de producción. Es
> `core/` (patrones reutilizables) + `plantilla_proyecto/` (la estructura
> estándar de archivos). Cada scraper real vive en su propia carpeta/repo.

## Filosofía en 3 líneas

1. **Lo que es reusable entre proyectos vive en `core/`**: anti-bot,
   cookies, ingesta documental (PDF por columnas y por tablas), parser Redux,
   historial SQLite, cache IA, tipo de cambio BCRP, NSE, control de calidad,
   formato auditable Excel, compuerta de poda.
2. **Lo específico de cada scraper vive en su propio paquete** (`<mi_proyecto>/`,
   estandarizado por `plantilla_proyecto/`) y consume `core/`.
3. **Para construir un scraper nuevo** se copia `plantilla_proyecto/` y se
   sigue [`docs/agregar_nuevo_sector.md`](docs/agregar_nuevo_sector.md).

## Estructura

```
bcrp-scraping/
├── AGENTS.md              ← instrucciones para agentes IA (contrato)
├── README.md              ← (este archivo)
├── guia.html              ← guía visual autocontenida del proyecto
├── pyproject.toml
├── core/                  ← núcleo reutilizable (metodología)
│   ├── utils/             normalizar_enlace, hashes, publicacion_id
│   ├── http/              HTTP-first: HttpClient + detección anti-bot
│   ├── ingesta/           PDF por columnas + tablas + segmentacion documental
│   ├── redux/             parser __NEXT_DATA__ + búsqueda recursiva
│   ├── browser/           BrowserManager (undetected-chromedriver, anti-bot)
│   ├── limpieza/          parsear_numero, moneda_a_iso, limpiar_precio_pe, fechas_es
│   ├── modelos/           AnuncioBase Pydantic + EstadoAnuncio + RefAnuncio
│   ├── contratos.py       PortalScraper (Protocol) + ClientePreferido
│   ├── extractor_ia/      DeepSeekExtractor + CachePublicaciones SQLite
│   ├── historial/         HistorialSQLite multi-sector con ciclo de vida
│   ├── calidad/           Compuerta pre-IA + duplicados (señal)
│   ├── mantenimiento_frontend/  reporte auditable + clasificación de fallo
│   ├── snapshots/         captura HTML por etapa
│   ├── tipo_cambio/       BCRP DataAPI + cache + conversión auditable
│   ├── nse/               Clasificador NSE por lookup (sin ML)
│   ├── reportes/          Excel acumulativo + formato visual
│   ├── poda.py            compuerta: módulos sin importadores
│   └── logging/           Logging por corrida
├── plantilla_proyecto/    ← estructura ESTÁNDAR de un scraper nuevo (se copia)
├── docs/
│   ├── arquitectura.md    capas, módulos, flujo
│   ├── convenciones.md    idioma, estilo, errores
│   ├── agregar_nuevo_sector.md   checklist paso a paso
│   ├── distribucion_proyecto_nuevo.md  generación selectiva + poda
│   ├── fuentes_documentales.md   metodología PDF/diarios
│   └── runbook_operacion.md      troubleshooting
└── tests/
    └── core/              tests del núcleo (sin red ni Chrome)
```

## Metodologías que aporta cada módulo de `core/`

Nota: para fuentes documentales/PDF, `core.ingesta` aporta lectura por columnas,
extracción de tablas y segmentación por código/sección. Ver `docs/fuentes_documentales.md`.

| Módulo | Patrón clave que captura |
|---|---|
| `core.http` | **HTTP-first** (aprendizaje de empleo: 3/4 portales sin Selenium): `HttpClient` (`requests` + retries + throttle + `connect_timeout` fail-fast en hosts bloqueados) y `detectar_bloqueo_anti_bot(status, texto)`. Es la primera opción; el navegador es la excepción. |
| `core.browser` | Una sola instancia de Chrome con `undetected_chromedriver`, monkeypatch para `WinError 6` en Windows, override `CHROME_VERSION_MAIN`, delays aleatorios por tipo de página, cierre best-effort de cookies. **Sólo si el portal lo exige.** |
| `core.ingesta` | Ingesta documental para PDFs/diarios: lectura por columnas + **extracción de tablas** (lattice con bordes y stream por geometría de palabras para tablas sin bordes) + segmentación por código/sección antes del parser. |
| `core.redux` | Parser de `__NEXT_DATA__` + búsqueda recursiva por clave. Permite que cualquier scraper de un SPA Next.js (Navent, etc.) priorice el blob JSON hidratado sobre el DOM. |
| `core.utils` | `normalizar_enlace` (única implementación canónica del proyecto), `descripcion_hash` (normaliza ruido antes de hashear), `publicacion_id` (identificador estable cross-corridas). |
| `core.modelos` · `core.contratos` | `AnuncioBase` + `RefAnuncio` (referencia ligera de listado) + el `Protocol` `PortalScraper` con `ClientePreferido` (`http`/`browser`/`hybrid`): cada portal declara su transporte y separa `descubrir_listado` (barato) de `extraer_detalle` (caro). |
| `core.extractor_ia` | Cliente DeepSeek con fallback Flash→Pro ante 429/503/timeout, y `CachePublicaciones` SQLite indexada por `(publicacion_id, descripcion_hash, campo)` — no se quema un token cuando el portal reedita un anuncio sin cambiar contenido. |
| `core.historial` | SQLite acumulativo multi-sector con ciclo de vida (nuevo / repetido / desaparecido / baja). **Seguridad de bajas (de empleo):** un listado parcial (`listado_completo=False`) NO marca ausencias; guarda anti-colapso (una corrida encogida no borra historial); retiro por vejez (`dias_vejez`) para portales siempre parciales. |
| `core.calidad` | Compuerta pre-IA con umbrales + señales: una corrida con cobertura insuficiente NO actualiza el historial (va a `degradadas/`). Además `detectar_duplicados` agrupa candidatos cross-source por similitud como **señal** para revisión humana — nunca borra. |
| `core.mantenimiento_frontend` · `core.snapshots` | Evidencia auditable cuando un portal cambia su HTML: reporte Markdown con `clasificar_fallo` (categoría + superficie exacta a tocar) + snapshots HTML por etapa. Una IA auditora repara sin reproducir la corrida. |
| `core.tipo_cambio` | BCRP DataAPI con cache SQLite. Aplica conversión USD↔PEN auditable: agrega columnas `Monto S/ estimado TC`, `TC fecha usada`, `TC compra/venta`, `TC fuente`, `TC regla`. NO sobrescribe montos observados. |
| `core.nse` | Clasificación por lookup `(distrito, urbanización) → NSE`. Sin ML por sesgo del dataset (87% Alto+Medio Alto). Auditable: cada match expone método y confianza. |
| `core.reportes` | `ExcelAcumulativo` multi-hoja con dedup por hoja (claves independientes), preservación de hojas no tocadas, y `aplicar_formato_hojas` para pulido visual BCRP. |
| `core.poda` | Compuerta de higiene: detecta módulos `.py` sin importadores en un paquete copiado (evita arrastrar código muerto al adoptar metodología en un proyecto standalone). |

## Decisiones de diseño que NO son negociables

- **HTTP-first.** El navegador es la excepción, no el default. Orden:
  API/JSON/XHR → HTML server-side → `__NEXT_DATA__` sin navegador → y sólo
  si nada alcanza, Chrome. (Lección de empleo: 3/4 portales sin Selenium.)
- **Lecturas son cascada**: Redux → DOM → regex → None. Nunca asumir
  una sola fuente.
- **`normalizar_enlace` es única.** Historial SQLite y cache IA deben
  comparar la misma forma canónica.
- **Compuerta de calidad antes de IA.** No se queman tokens sobre datos
  rotos; degradadas van a carpeta aparte.
- **Un listado parcial NO marca ausencias ni bajas.** Un universo truncado
  no prueba que un aviso desapareció; el retiro se hace por vejez.
- **La deduplicación por similitud NUNCA borra sola.** El dedup exacto por
  enlace es automático; la similitud cross-source sólo SEÑALA para revisión humana.
- **El alcance del ciclo de vida es el eje de consulta**, nunca un campo
  declarado dentro del dato (lección de empleo: `region_consulta` ≠ `region`).
- **Conversiones de TC son auditables, no destructivas.** Columnas en
  rojo (#C00000) declaran lo imputado.
- **NSE es lookup, no ML.** Mientras la base esté desbalanceada.
- **`core/` jamás importa del paquete del proyecto.** Dirección de
  dependencia estricta de un solo sentido.

## Arrancar un scraper nuevo

```bash
cp -r plantilla_proyecto mi_proyecto
# editar mi_proyecto/config.py, modelos.py, portal_scrapers/...
python -m mi_proyecto.main --portal portal_a --paginas 5 --sin-ia
```

Los proyectos productivos (inmobiliario, empleo, diarios/PDF) viven en sus
propias carpetas y traen de `core/` sólo lo que importan — ver
[`docs/distribucion_proyecto_nuevo.md`](docs/distribucion_proyecto_nuevo.md).

## Tests

```bash
PYTHONPATH='.codex-pydeps;.' python -m pytest tests -q
```

Resultado auditado el 2026-06-09: `114 passed` + `ruff check` limpio. Sin
llamadas a red ni Chrome real — todo con fixtures/mocks. Si no usas
`.codex-pydeps`, instala el paquete con extras de desarrollo antes de correr tests.

## Setup

```bash
pip install -e .
cp .env.example .env  # editar con las API keys
```

Requisitos:
- Python ≥ 3.11
- Chrome instalado (para `undetected-chromedriver`)
- `.env` con `DEEPSEEK_API_KEY` (opcional; corre sin IA con cobertura reducida)

## Roadmap

- **Sprint 1** ✓ Núcleo `core/` + sector inmobiliario de referencia.
- **Sprint 2 (extracción metodológica de v1)** ✓ `core.utils`, `core.redux`,
  `core.extractor_ia.cache`, `core.calidad`, `core.tipo_cambio`, `core.nse`,
  formato auditable, `AGENTS.md` + scaffold + checklist + fuentes documentales.
- **Sprint 3 (extracción metodológica de empleo)** ✓ El sector empleo, como
  segundo consumidor real, disparó patrones que subieron a `core/`: **HTTP-first**
  (`core.http`), **contrato de portal** (`core.contratos`), **seguridad de bajas**
  en el historial (listado parcial / anti-colapso / vejez), **clasificación de fallo**
  (`core.mantenimiento_frontend`) y **duplicados-señal** (`core.calidad`).
- **v0.1 (reestructuración, 2026-06-08)** ✓ Metodología pura: se elimina el
  alojamiento de scrapers, `plantilla_proyecto/` queda como estructura estándar,
  `core.poda`, extracción de **tablas PDF** (`core.ingesta`), `guia.html` y skill
  del repo para activar el contrato en cualquier agente.
- **Próximo** Primer consumidor productivo importando/copiando `core/` end-to-end
  (dogfooding) y endurecimiento de `core.ingesta` con PDFs reales de tablas complejas.

## Para agentes IA

Ver [`AGENTS.md`](AGENTS.md). En particular:
- Convención de capas (`core/` ↔ `<mi_proyecto>/`).
- Cuándo subir un patrón a `core/`.
- Cómo construir un scraper nuevo copiando `plantilla_proyecto/`.
- Cómo adaptar fuentes PDF/diarios con `docs/fuentes_documentales.md`.
- Anti-patrones (importar del proyecto en core, llamar a red en tests, etc.).

El repo incluye una **skill** (`.claude/skills/bcrp-scraping/`) que activa este
contrato automáticamente en Claude Code ante cualquier tarea de scraping. Otros
agentes (Codex, Antigravity, Gemini) leen el mismo contrato desde `AGENTS.md`.
