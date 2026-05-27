# sectores/_template — plantilla para arrancar un sector nuevo

Copiá este directorio entero a `sectores/<mi_sector>/` y empezá a
ajustar. La estructura ya refleja todas las dependencias correctas a
`core/`; sólo tenés que llenar lo específico de tu sector.

```
sectores/<mi_sector>/
├── README.md              ← describe el sector y sus portales
├── __init__.py
├── config.py              ← URLs, paths, umbrales, .env, CODIGO_POR_PORTAL
├── modelos.py             ← AnuncioBase → AnuncioMiSector con campos extra
├── limpieza.py            ← pipeline_limpieza(datos_crudos, ...) -> DataFrame
├── scraper.py             ← fachada delgada; sólo rutea al portal_scraper
├── portal_scrapers/       ← uno por portal — la lógica de parsing vive acá
│   ├── __init__.py
│   ├── common.py          ← helpers compartidos entre portales del sector
│   ├── portal_a.py        ← scrape_listados_portal_a(...) -> list[dict]
│   └── portal_b.py
├── extractor_ia.py        ← prompt + caller a DeepSeekExtractor + cache
├── main.py                ← CLI orquestador + reporte mantenimiento en fallos
└── resultados/            ← (gitignore'd) DB, Excel, logs, snapshots, reportes
    ├── snapshots_frontend/         ← HTML capturado por corrida
    └── reportes_mantenimiento_frontend/  ← Markdown para IA auditora
```

**Patrón inviolable**: `scraper.py` es una fachada que **sólo rutea**. La
lógica de cada portal vive en `portal_scrapers/<portal>.py`. Cambios de
selectores / parser → tocás el módulo del portal, NO la fachada.

## Checklist de 9 pasos

Está en [`../../docs/agregar_nuevo_sector.md`](../../docs/agregar_nuevo_sector.md). Léelo en
paralelo con este scaffold.

## Hooks de `core/` esperados

Cada archivo `.py` de este template ya tiene los `from core.* import …`
relevantes y `# TODO:` con anclas para que un agente IA pueda generar
el resto sin descubrir las dependencias por su cuenta.
