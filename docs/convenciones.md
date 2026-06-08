# Convenciones de código

## Idioma

- **Español** para dominio: `anuncio`, `anunciante`, `distrito`, `sector`, `historial`, `portal`, `publicacion_id`.
- **Inglés** para tecnología: `browser`, `scraper`, `fetcher`, `batch`, `retry`, `parser`, `driver`, `cache`.
- **Docstrings** en español, breves, orientadas al "por qué" (no al "qué").
- **Comentarios** sólo cuando el "por qué" no sea obvio desde el código.

## Estructura de módulos

- Un patrón sube a `core/` **sólo cuando aparece en al menos 2 proyectos/sectores** (YAGNI).
- Cada proyecto (`<mi_proyecto>/`, copia de `plantilla_proyecto/`) importa de
  `core/`, **nunca al revés**.
- `__init__.py` de cada paquete expone API pública con `__all__`.
- Los helpers específicos del proyecto viven en el proyecto. No "preventivamente" en core.

## Fallback en cascada

Toda fuente de campo debe tener fallback. El patrón canónico es:

```
Redux state primario → DOM con selectores estables → regex sobre texto → None
```

Cada nivel registra su resultado en el `diagnostico` de la corrida para
que la compuerta de calidad sepa cuánto se perdió.

## Errores y warnings

| Caso | Acción |
|---|---|
| Regla de negocio violada (precio < 0, distrito desconocido) | Warning en columna `warnings`. **No** rechazar la fila. |
| Error recuperable (timeout de un elemento, Redux faltante en una página) | `logger.warning` y continuar. |
| Error de portal (cero tarjetas en N páginas, selectores obsoletos) | `logger.error`. La compuerta de calidad debe haberlo detectado igualmente. |
| Excepción inesperada en una fila | Try/except a nivel fila — la corrida no se detiene por una fila rota. |

## Logging

- Niveles: `INFO` (hitos de corrida), `WARNING` (recuperables), `ERROR` (fallas de portal).
- Formato: `%(asctime)s [%(levelname)s] %(message)s`.
- Un archivo por corrida en `<sector>/resultados/logs/scraping_YYYYMMDD_HHMMSS.log`.
- `core.logging.configurar_logging(carpeta_logs)` se llama una vez al inicio de `main()`.

## Cache de IA

- Clave: `(publicacion_id, descripcion_hash, campo)`.
- **`publicacion_id`** se genera con `core.utils.publicacion_id(sector, portal, operacion, enlace, posting_id)`.
- **`descripcion_hash`** se genera con `core.utils.descripcion_hash(texto)`. NO usar otra implementación; el hash debe coincidir byte a byte en todo el pipeline.
- Si dos lugares calculan el hash distinto, no hay hit y se queman tokens innecesarios.

## Periodos (mes / trimestre / año)

El BCRP razona y publica en **trimestres**. Todo sector con fecha debe
materializar columnas de periodo derivadas de `fecha_publicacion`:

- `agregar_columnas_periodo(df, "fecha_publicacion")` agrega `anio` (int),
  `trimestre` (`YYYY-T{1..4}`) y `mes` (`YYYY-MM`).
- Formato **ordenable lexicográficamente** y sin ambigüedad de locale:
  `2026-T2`, `2026-05`. Nada de `"II-2026"` ni `"mayo"`.
- Se calculan **una vez** en la limpieza, después de tener la fecha ISO.
  Así las mismas columnas fluyen al Excel (vista) y al snapshot SQLite
  (consultas `GROUP BY trimestre`), sin recalcular.
- Para que lleguen a SQL hay que declararlas en `campos_snapshot`:
  `("anio","INTEGER"), ("trimestre","TEXT"), ("mes","TEXT")`.

## Auditoría visual del Excel

- Header de hoja: fondo `#1F4E79`, fuente blanca negrita.
- Celda con valor **observado**: estilo normal.
- Celda con valor **imputado** (TC estimado, etc.): fuente roja `#C00000`.
- Helpers en `core.tipo_cambio.formato` y `core.reportes.formato`.

## Testing

- **Sin llamadas a red** en tests. Fixtures HTML/JSON grabadas en `tests/fixtures/`.
- Mocks para DeepSeek (`monkeypatch openai.OpenAI`) y Selenium driver.
- Cobertura objetivo: ≥ 70% en `core/`.
- Tests del núcleo en `tests/core/`. Cada proyecto lleva sus propios tests.

## Secretos

- `.env` siempre en `.gitignore`.
- `.env.example` con placeholders vacíos y comentarios sobre qué cargar.
- Ningún API key commiteado, nunca. Ni siquiera en comentarios.

## Reportes legibles para humanos

El usuario final del scraping inmobiliario (analista BCRP, no técnico)
abre el Excel y debe poder:
1. Ver el dato observado sin saber Python ni SQL.
2. Distinguir lo observado de lo imputado (columnas en rojo).
3. Ubicar la auditoría: TC fecha usada, fuente, regla.

Si una mejora del scraper rompe esto, no es mejora.
