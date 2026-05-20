# Runbook de operación

> Guía de qué hacer cuando algo se rompe en producción.

## Corrida normal

```bash
# Inmobiliario (ejemplo de referencia — para producción real usar v1/)
python -m sectores.inmobiliario.main --portal urbania --operacion alquiler --paginas 5

# Sector nuevo
python -m sectores.<mi_sector>.main --portal <portal> --paginas 5
```

## Troubleshooting

### "Chrome no inicia"

1. Verificar que Chrome está actualizado (`chrome://version`).
2. Setear env var `CHROME_VERSION_MAIN=<N>` (la versión major instalada)
   antes de correr. `BrowserManager` la respeta automáticamente.
3. Si el error es `WinError 6` al cerrar: ya está manejado por el
   monkeypatch en `core.browser.manager`. Si reaparece, revisar que el
   monkeypatch sigue siendo idempotente.

### "DeepSeek devuelve 429 / rate limit"

- El fallback automático debería cambiar de `DEEPSEEK_MODEL` (Flash) a
  `DEEPSEEK_MODEL_2` (Pro). Revisar logs: debería decir
  "Reintentos agotados. Cambiando a modelo alternativo...".
- Si ambos modelos fallan, el pipeline continúa con cache/regex y los
  campos no resueltos quedan vacíos. No hay corrida fallida por esto.

### "El Excel maestro se corrompió"

- **No paniquear**: la fuente de verdad es SQLite (`historial_<sector>.db`).
- Borrar el Excel y re-correr: `ExcelAcumulativo` lo recrea desde cero
  con la corrida actual; el historial completo se reconstruye con
  un helper de re-export desde SQLite (ver TODO en `docs/`).

### "Una corrida quedó marcada como DEGRADADA"

- Buscar el archivo en `<sector>/resultados/degradadas/<portal>_<op>_degradado_*.xlsx`.
- Hoja **Resumen** dice el motivo (qué umbral se violó).
- No tocar el historial — la corrida no entró ahí por diseño.
- Si el motivo es "Redux/DOM match insuficiente" en Navent: revisar si
  el portal cambió estructura.

### "Un portal cambió su HTML y el scraper deja de extraer"

1. Reproducir manualmente abriendo el listado del portal.
2. Inspeccionar el HTML; si es SPA Next.js, comprobar que `__NEXT_DATA__`
   sigue existiendo.
3. Si el blob JSON cambió de estructura: actualizar
   `core.redux.extraer_redux_state` claves esperadas por el sector.
4. Si los selectores DOM cambiaron: actualizar `sectores/<x>/portales/<portal>.py`.
5. Grabar fixture HTML nuevo en `tests/fixtures/<portal>/` para
   prevenir regresiones.

### "Tipo de cambio BCRP devuelve vacío"

- BCRPData no devuelve fines de semana ni feriados. El módulo cae a
  "fecha anterior más cercana"; si TODAS las fechas requeridas están
  fuera de calendario hábil, no se imputa nada y los precios USD/PEN
  no se cruzan.
- Si la API está caída: el cache local sigue funcionando; sólo no se
  baja lo nuevo. Reintentar después.

### "El historial SQLite acumuló datos basura de una corrida buggy"

- Identificar la corrida en la tabla `corridas` (filtrar por fecha + portal).
- `UPDATE anuncios SET activo = 0 WHERE ...` para inhabilitar las filas
  contaminadas. **No DELETE** — preferir soft-delete para mantener
  trazabilidad.
- Si fue una corrida entera: `DELETE FROM corridas WHERE id = ?`.

## Mantenimiento periódico

- Revisar **cobertura por campo** en los logs:
  ```
  Cobertura urbania/alquiler [n=42]: precio=100% distrito=95% descripcion=88% ...
  ```
  Caídas bruscas vs corrida anterior indican que algo cambió en el portal.

- **Vaciar logs viejos**: `core.utils` no incluye purga automática
  (vive en v1/utils.py). Si los logs ocupan demasiado, agregar `cron`
  o purgar manualmente: `<sector>/resultados/logs/scraping_*.log`.

- **Refrescar el cache de TC**: el cache crece despacio (1 fila/día), no
  requiere mantenimiento.

- **Vacuum del SQLite**: cuando el archivo `historial_<sector>.db`
  supere los 100 MB, considerar `VACUUM;` para compactar.

## Cuando un agente IA construye un sector nuevo

Antes de aceptar el PR, verificar:

- [ ] El sector no importa nada de otro sector (sólo de `core/`).
- [ ] Hay tests sin red en `tests/sectores/<x>/`.
- [ ] El `main.py` respeta la compuerta de calidad (no manda degradadas
      al historial).
- [ ] El `extractor_ia.py` usa `CachePublicaciones` (no llamadas directas
      sin cache).
- [ ] `.env.example` está actualizado con las nuevas keys que el sector
      requiera.
