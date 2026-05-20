# bcrp-scraping

Librería de **metodologías** de scraping reutilizables del Departamento
de Estudios Económicos — BCRP Arequipa.

> **No es una colección de scrapers.** Es el núcleo de patrones y
> herramientas que cada scraper nuevo (empleo, financiero, comercio…)
> reutiliza en vez de reinventar. Si vienes a construir un sector nuevo
> con un agente IA, leé primero [`AGENTS.md`](AGENTS.md).

## Filosofía en 3 líneas

1. **Lo que es reusable entre sectores vive en `core/`**: anti-bot,
   cookies, parser Redux, historial SQLite, cache IA, tipo de cambio
   BCRP, NSE, control de calidad, formato auditable Excel.
2. **Lo que es sector-específico vive en `sectores/<x>/`** y consume `core/`.
3. **Para construir un sector nuevo** se copia `sectores/_template/` y
   se sigue [`docs/agregar_nuevo_sector.md`](docs/agregar_nuevo_sector.md).

## Estructura

```
bcrp-scraping/
├── AGENTS.md              ← instrucciones para agentes IA
├── README.md              ← (este archivo)
├── pyproject.toml
├── core/                  ← núcleo reutilizable
│   ├── utils/             normalizar_enlace, hashes, publicacion_id
│   ├── redux/             parser __NEXT_DATA__ + búsqueda recursiva
│   ├── browser/           BrowserManager (undetected-chromedriver, anti-bot)
│   ├── limpieza/          parsear_numero, moneda_a_iso, limpiar_precio_pe, fechas_es
│   ├── modelos/           AnuncioBase Pydantic + EstadoAnuncio
│   ├── extractor_ia/      DeepSeekExtractor + CachePublicaciones SQLite
│   ├── historial/         HistorialSQLite multi-sector con ciclo de vida
│   ├── calidad/           Compuerta pre-IA (umbrales + señales)
│   ├── tipo_cambio/       BCRP DataAPI + cache + conversión auditable
│   ├── nse/               Clasificador NSE por lookup (sin ML)
│   ├── reportes/          Excel acumulativo + formato visual
│   └── logging/           Logging por corrida
├── sectores/
│   ├── _template/         scaffold para sectores nuevos
│   └── inmobiliario/      ejemplo de referencia (NO producción)
├── docs/
│   ├── arquitectura.md    capas, módulos, flujo
│   ├── convenciones.md    idioma, estilo, errores
│   ├── agregar_nuevo_sector.md   checklist 10 pasos
│   └── runbook_operacion.md      troubleshooting
└── tests/
    ├── core/              tests del núcleo (sin red)
    └── sectores/          tests por sector con fixtures
```

## Metodologías que aporta cada módulo de `core/`

| Módulo | Patrón clave que captura |
|---|---|
| `core.browser` | Una sola instancia de Chrome con `undetected_chromedriver`, monkeypatch para `WinError 6` en Windows, override `CHROME_VERSION_MAIN`, delays aleatorios por tipo de página, cierre best-effort de cookies. |
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
- **`core/` jamás importa de `sectores/`.** Dirección de dependencia
  estricta de un solo sentido.

## Corrida (ejemplo de referencia)

```bash
# El v1 productivo vive aparte. Acá sólo el ejemplo cableado:
python -m sectores.inmobiliario.main --portal urbania --paginas 5 --sin-ia
```

Para producción real del scraping inmobiliario usar:

```
../../INMOBILIARIA/PROYECTO DE SCRAPING NUEVA METODOLOGIA/v1/
```

## Tests

```bash
python -m pytest tests/ -v
```

Sin llamadas a red ni Chrome — todo con fixtures.

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
- **Sprint 2 (extracción metodológica)** ✓ Migración de aprendizajes de v1
  productivo: `core.utils`, `core.redux`, `core.extractor_ia.cache`,
  `core.calidad`, `core.tipo_cambio`, `core.nse`, formato auditable.
  AGENTS.md + scaffold + checklist. (este sprint)
- **Sprint 3** Sector empleo (Empleos Perú + Computrabajo + SERVIR)
  como segundo consumidor — disparará los nuevos patrones que merezcan
  subir a `core/`.

## Para agentes IA

Ver [`AGENTS.md`](AGENTS.md). En particular:
- Convención de capas (`core/` ↔ `sectores/<x>/`).
- Cuándo subir un patrón a `core/`.
- Cómo construir un sector nuevo en 10 pasos.
- Anti-patrones (importar de sectores en core, llamar a red en tests, etc.).
