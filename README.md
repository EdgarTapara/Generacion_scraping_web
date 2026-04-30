# bcrp-scraping

Sistema de scraping reutilizable del Departamento de Estudios Económicos — BCRP Arequipa.

Framework modular emergido del refactor del scraper inmobiliario `v1/` validado en producción. Cada sector nuevo (empleo, financiero, etc.) se construye reusando el núcleo `core/`, no reescribiendo.

## Estructura

```
bcrp-scraping/
├── core/                   # Núcleo reutilizable extraído de v1/
│   ├── browser/            BrowserManager (undetected-chromedriver)
│   ├── extractor_ia/       DeepSeek OpenAI-compatible con fallback de modelos
│   ├── historial/          SQLite genérico multi-sector
│   ├── limpieza/           Helpers genéricos: números, fechas, moneda
│   ├── modelos/            AnuncioBase Pydantic
│   ├── reportes/           Excel acumulativo con merge + dedup
│   └── logging/            Logging estructurado
├── sectores/
│   └── inmobiliario/       Sector validado sobre core/
│       ├── config.py, modelos.py, limpieza.py, historial.py
│       ├── extractor_ia.py, scraper.py, main.py, utils_sector.py
│       └── portales/       navent.py, properati.py, remax.py
├── docs/
├── tests/
│   ├── core/               Tests del núcleo (browser, limpieza, historial, reportes, IA)
│   ├── sectores/inmobiliario/  Tests del sector (modelos, utils, limpieza, export)
│   └── fixtures/navent/    Fixture JSON del Redux state (sin red)
└── scripts/
```

## Estado actual

- **Sprint 0**: completado (auditoría y diseño → `PLAN_PROYECTO_SCRAPING_BCRP.md`)
- **Sprint 1**: **completado** (A-F) — 94 tests pasando
  - Fase A/B/C: scaffold + `core/browser/` + `core/logging/` + `core/modelos/` + `core/limpieza/`
  - Fase D: `core/extractor_ia/` (DeepSeek + fallback) + `core/historial/` (SQLite generico)
  - Fase E: `core/reportes/` (Excel acumulativo) + migración `sectores/inmobiliario/` a depender de `core/`
  - Fase F: tests de regresión (fixture Redux + parsers puros + roundtrip SQLite/Excel)

El código `v1/` original vive intacto en `../../INMOBILIARIA/PROYECTO DE SCRAPING NUEVA METODOLOGIA/v1/`. La versión migrada `sectores/inmobiliario/` corre sobre `core/` y reproduce el mismo output (mismo Excel, mismo historial, mismos estados).

## Corrida

```bash
python -m sectores.inmobiliario.main                   # todos los portales + operaciones
python -m sectores.inmobiliario.main --portal urbania --paginas 5
python -m sectores.inmobiliario.main --sin-ia --headless
```

## Tests

```bash
python -m pytest tests/ -v
```

## Requisitos

- Python ≥ 3.11
- Chrome instalado (para `undetected-chromedriver`)
- `.env` con `DEEPSEEK_API_KEY` (opcional; pipeline corre sin IA con cobertura reducida)

## Setup

```bash
pip install -e .
cp .env.example .env
# editar .env con las API keys
```

## Plan maestro

Ver [`../PLAN_PROYECTO_SCRAPING_BCRP.md`](../PLAN_PROYECTO_SCRAPING_BCRP.md) para roadmap, arquitectura y decisiones.
