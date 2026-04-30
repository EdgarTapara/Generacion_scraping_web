# Runbook de operación

> Guía de qué hacer cuando algo se rompe en producción. Se va llenando con cada incidente.

## Corrida normal (cuando Fase E esté lista)

```bash
python -m sectores.inmobiliario.main --portal urbania --operacion alquiler --paginas 25
```

## Troubleshooting

### "Chrome no inicia"
1. Verificar que Chrome está actualizado
2. Intentar con `version_main` fijo en `BrowserManager` si falla la autodetección

### "Gemini devuelve 429 / rate limit"
- El fallback automático debería cambiar a `GEMINI_API_KEY_2`
- Si ambas agotan cuota: el pipeline continúa sin IA, los campos quedan vacíos

### "El Excel maestro se corrompió"
- La fuente de verdad es el SQLite (`historial_<sector>.db`)
- Regenerar el Excel con un script helper (pendiente de crear en Fase E)

### "Un portal cambió su HTML y el scraper deja de extraer"
- Revisar si los selectores `data-qa` / `data-test` siguen vigentes
- Grabar fixture nuevo con `scripts/grabar_fixture.py` (pendiente)
- Ajustar selectores en `sectores/<sector>/portales/<portal>.py`
