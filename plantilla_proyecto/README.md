# plantilla_proyecto — estructura estándar de un scraper BCRP

Este directorio **es el estándar**: define *qué archivos y cuántos* tiene
cualquier scraper nuevo del BCRP. Copialo entero a `<mi_proyecto>/`,
renombralo, y llená lo específico. Toda la metodología reutilizable ya vive
en `core/`; acá sólo va lo propio del proyecto.

> Los imports internos son **relativos** (`from . import config`,
> `from .scraper import …`). Por eso al copiar+renombrar el paquete no hay
> que editar ningún import para que enlace.

## Estructura estándar (no inventar archivos nuevos sin razón)

```
mi_proyecto/
├── README.md              ← describe el proyecto y sus portales/fuentes
├── __init__.py
├── config.py              ← URLs, paths, umbrales, .env, CODIGO_POR_PORTAL
├── modelos.py             ← AnuncioBase → AnuncioMiProyecto con campos extra
├── limpieza.py            ← pipeline_limpieza(datos_crudos, ...) -> DataFrame
├── scraper.py             ← fachada delgada; sólo rutea al portal_scraper
├── portal_scrapers/       ← uno por portal — la lógica de parsing vive acá
│   ├── __init__.py
│   ├── common.py          ← helpers compartidos entre portales del proyecto
│   ├── portal_a.py        ← scrape_listados_portal_a(...) -> list[dict]
│   └── portal_b.py
├── extractor_ia.py        ← prompt + caller a DeepSeekExtractor + cache
├── main.py                ← CLI orquestador + reporte mantenimiento en fallos
└── resultados/            ← (gitignore'd) DB, Excel, logs, snapshots, reportes
    ├── snapshots_frontend/         ← HTML capturado por corrida
    └── reportes_mantenimiento_frontend/  ← Markdown para IA auditora
```

Ese conjunto de archivos es **el contrato de estructura**: 8 módulos `.py`
+ `portal_scrapers/` + `resultados/`. Un proyecto nuevo debería verse igual,
sin importar el sector (empleo, inmobiliario, diarios/PDF, APIs…). Si un
proyecto necesita un archivo que no está acá, primero preguntá si el patrón
debería subir a `core/`.

## Cómo consume `core/` un proyecto standalone

`core/` es metodología compartida. Un proyecto en otra carpeta/repo **no
copia `core/` entero**: trae sólo los módulos que importa, anota su
procedencia y corre la poda. Ver
[`../docs/distribucion_proyecto_nuevo.md`](../docs/distribucion_proyecto_nuevo.md).

## Patrón inviolable

`scraper.py` es una fachada que **sólo rutea**. La lógica de cada portal
vive en `portal_scrapers/<portal>.py`. Cambios de selectores / parser →
tocás el módulo del portal, NO la fachada.

## Checklist paso a paso

Está en [`../docs/agregar_nuevo_sector.md`](../docs/agregar_nuevo_sector.md).
Léelo en paralelo con este scaffold.

## Hooks de `core/` esperados

Cada `.py` de esta plantilla ya trae los `from core.* import …` relevantes y
`# TODO:` con anclas, para que un agente IA genere el resto sin redescubrir
las dependencias.
