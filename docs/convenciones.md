# Convenciones de código

## Idioma

- **Español** para dominio: `anuncio`, `anunciante`, `distrito`, `sector`, `historial`, `portal`
- **Inglés** para tecnología: `browser`, `scraper`, `fetcher`, `batch`, `retry`, `parser`, `driver`
- **Docstrings** en español, breves, orientadas al "por qué"
- **Comentarios** solo cuando el "por qué" no sea obvio desde el código

## Estructura de módulos

- Un patrón sube a `core/` **solo cuando aparece en al menos 2 sectores** (YAGNI)
- Cada sector en `sectores/<sector>/` importa de `core/`, nunca al revés
- `__init__.py` de cada paquete expone la API pública con `__all__`

## Errores y warnings

- Violaciones de reglas de negocio → warning en columna `warnings`, **no** rechazar la fila
- Errores de red / parseo → log `WARNING` y continuar
- Errores que detienen un portal → log `ERROR`

## Logging

- Niveles: `INFO` (hitos de corrida), `WARNING` (recuperables), `ERROR` (fallas de portal)
- Formato: `%(asctime)s [%(levelname)s] %(message)s`
- Rotación: un archivo por corrida en `<sector>/resultados/logs/scraping_YYYYMMDD_HHMMSS.log`

## Testing

- Sin llamadas a red en tests. Fixtures HTML grabados en `tests/fixtures/`
- Mocks para Gemini API y Selenium driver
- Cobertura objetivo: ≥ 70% en `core/`

## Secretos

- `.env` siempre en `.gitignore`
- `.env.example` con placeholders vacíos
- Ningún API key commiteado, nunca
