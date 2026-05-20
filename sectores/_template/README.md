# sectores/_template — plantilla para arrancar un sector nuevo

Copiá este directorio entero a `sectores/<mi_sector>/` y empezá a
ajustar. La estructura ya refleja todas las dependencias correctas a
`core/`; sólo tenés que llenar lo específico de tu sector.

```
sectores/<mi_sector>/
├── README.md              ← describe el sector y sus portales
├── __init__.py            ← exporta API pública del sector
├── config.py              ← URLs, paths, umbrales, .env por sector
├── modelos.py             ← AnuncioBase → AnuncioMiSector con campos extra
├── limpieza.py            ← pipeline_limpieza(datos_crudos, ...) -> DataFrame
├── scraper.py             ← orquesta los portales del sector
├── portales/
│   ├── __init__.py
│   ├── portal_a.py        ← scrape_portal_a(driver, ...) -> list[dict]
│   └── portal_b.py
├── extractor_ia.py        ← prompt + caller a DeepSeekExtractor + cache
├── main.py                ← CLI orquestador (argparse + ejecutar_scraping)
└── resultados/            ← (gitignore'd) DB, Excel, logs por corrida
```

## Checklist de 9 pasos

Está en [`../../docs/agregar_nuevo_sector.md`](../../docs/agregar_nuevo_sector.md). Léelo en
paralelo con este scaffold.

## Hooks de `core/` esperados

Cada archivo `.py` de este template ya tiene los `from core.* import …`
relevantes y `# TODO:` con anclas para que un agente IA pueda generar
el resto sin descubrir las dependencias por su cuenta.
