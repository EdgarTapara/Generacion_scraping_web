# Runbook de operacion

> Guia de que hacer cuando algo se rompe en produccion.

## Corrida normal

```bash
python -m sectores.inmobiliario.main --portal urbania --operacion alquiler --paginas 25
```

## Troubleshooting

### "Chrome no inicia"
1. Verificar que Chrome esta actualizado.
2. Intentar con `version_main` fijo en `BrowserManager` si falla la autodeteccion.

### "DeepSeek devuelve 429 / rate limit"
- El fallback automatico deberia cambiar de `DEEPSEEK_MODEL` a `DEEPSEEK_MODEL_2`.
- Si ambos modelos fallan: el pipeline continua con cache/regex y los campos no resueltos quedan vacios.

### "El Excel maestro se corrompio"
- La fuente de verdad es el SQLite (`historial_<sector>.db`).
- Regenerar el Excel desde SQLite cuando exista el helper de reconstruccion.

### "Un portal cambio su HTML y el scraper deja de extraer"
- Revisar si los selectores `data-qa` / `data-test` siguen vigentes.
- Grabar fixture nuevo con `scripts/grabar_fixture.py` cuando exista.
- Ajustar selectores en `sectores/<sector>/portales/<portal>.py`.
