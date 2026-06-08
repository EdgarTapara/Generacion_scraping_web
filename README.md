# bcrp-scraping

Librería de **metodologías** de scraping reutilizables del Departamento
de Estudios Económicos — BCRP Arequipa.

> **No es una colección de scrapers.** Es el núcleo de patrones y
> herramientas que cada scraper nuevo (empleo, financiero, comercio…)
> reutiliza en vez de reinventar. Si vienes a construir un sector nuevo
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

Nota: para fuentes documentales/PDF, `core.ingesta` aporta lectura por columnas
y segmentacion por codigo/seccion. Ver `docs/fuentes_documentales.md`.

| Módulo | Patrón clave que captura |
|---|---|
| `core.browser` | Una sola instancia de Chrome con `undetected_chromedriver`, monkeypatch para `WinError 6` en Windows, override `CHROME_VERSION_MAIN`, delays aleatorios por tipo de página, cierre best-effort de cookies. |
| `core.ingesta` | Ingesta documental para PDFs/diarios: ordena bloques por columnas y segmenta avisos por codigo/seccion antes del parser del sector. |
| `core.redux` | Parser de `__NEXT_DATA__` + búsqueda recursiva por clave. Permite que cualquier scraper de un SPA Next.js (Navent, etc.) priorice el blob JSON hidratado sobre el DOM. |
| `core.utils` | `normalizar_enlace` (única implementación canónica del proyecto), `descripcion_hash` (normaliza ruido antes de hashear), `publicacion_id` (identificador estable cross-corridas). |
| `core.extractor_ia` | Cliente DeepSeek con fallback Flash→Pro ante 429/503/timeout, y `CachePublicaciones` SQLite indexada por `(publicacion_id, descripcion_hash, campo)` — no se quema un token cuando el portal reedita un anuncio sin cambiar contenido. |
| `core.historial` | SQLite acumulativo multi-sector. Detecta nuevos / repetidos / desaparecidos / bajas con `ausencias_consecutivas`. Identidad por `sector + portal + operacion + enlace_canonico`. |
| `core.calidad` | Compuerta pre-IA con umbrales por campo + señales instrumentales. Una corrida con cobertura insuficiente NO actualiza el historial — se desvía a `degradadas/` para revisión. |
| `core.tipo_cambio` | BCRP DataAPI con cache SQLite. Aplica conversión USD↔PEN auditable: agrega columnas `Monto S/ estimado TC`, `TC fecha usada`, `TC compra/venta`, `TC fuente`, `TC regla`. NO sobrescribe montos observados. |
| `core.nse` | Clasificación por lookup `(distrito, urbanización) → NSE`. Sin ML por sesgo del dataset (87% Alto+Medio Alto). Auditable: cada match expone método y confianza. |
| `core.reportes` | `ExcelAcumulativo` multi-hoja con dedup por hoja (claves independientes), preservación de hojas no tocadas, y `aplicar_formato_hojas` para pulido visual BCRP. |

## Decisiones de diseño que NO son negociables

- **Lecturas son cascada**: Redux → DOM → regex → None. Nunca asumir
  una sola fuente.
- **`normalizar_enlace` es única.** Historial SQLite y cache IA deben
  comparar la misma forma canónica.
- **Compuerta de calidad antes de IA.** No se queman tokens sobre datos
  rotos; degradadas van a carpeta aparte.
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

Resultado auditado el 2026-05-30: `110 passed`. Sin llamadas a red ni Chrome
real — todo con fixtures/mocks. Si no usas `.codex-pydeps`, instala el paquete
con extras de desarrollo antes de correr tests.

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
- **Sprint 2 (extracción metodológica)** parcialmente completo: migración de aprendizajes de v1
  productivo: `core.utils`, `core.redux`, `core.extractor_ia.cache`,
  `core.calidad`, `core.tipo_cambio`, `core.nse`, formato auditable.
  `AGENTS.md` + scaffold + checklist + fuentes documentales. Falta endurecer
  el template como CLI funcional mínimo o declararlo definitivamente como
  scaffold guiado.
- **Sprint 3** Sector empleo (Empleos Perú + Computrabajo + SERVIR)
  como segundo consumidor — disparará los nuevos patrones que merezcan
  subir a `core/`.
- **Sprint 4** Empaquetar la metodología como skill/agente reutilizable para
  distintos proveedores IA.

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
