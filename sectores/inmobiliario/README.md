# sectores/inmobiliario — ejemplo de referencia

> ⚠️ **No es código de producción.** Sirve como ejemplo cableado que muestra
> cómo un sector consume `core/`. La implementación productiva de
> scraping inmobiliario BCRP vive en
> `../../../INMOBILIARIA/PROYECTO DE SCRAPING NUEVA METODOLOGIA/v1/`.

## Por qué existe este directorio

Cuando una persona (o un agente IA) quiere construir un sector nuevo
necesita ver **un caso completo** que ya consume `core/browser`,
`core/historial`, `core/extractor_ia`, etc. Mantener una versión
"vitrina" del sector inmobiliario sirve exactamente para eso.

## Qué NO hacer aquí

- **No replicar nuevas funcionalidades de v1.** Si un patrón nuevo
  resuelve algo que vale la pena reutilizar, sube directo a `core/`.
  Este directorio sigue siendo una vitrina de cómo se cablean los
  módulos de `core/`, no un fork del v1 real.

- **No correr este sector como producción.** El v1 original tiene
  configuraciones reales (paths, base NSE, .env, etc.) que no quedan
  reflejadas aquí. Para correr inmobiliario en producción usar v1/.

## Qué SÍ hacer aquí

- **Leer los `__init__.py`** de cada submódulo para entender qué
  importa de `core/` y cómo lo combina.
- **Estudiar `main.py`** como ejemplo de orquestador (fases scraping
  → limpieza → IA → historial → reportes).
- **Replicar el patrón** en `sectores/_template/` cuando inicies un
  sector nuevo.

## Diferencias respecto al v1 productivo

| Aspecto | v1 (producción) | sectores/inmobiliario (referencia) |
|---|---|---|
| Mantenimiento | Activo, recibe mejoras | Snapshot ilustrativo |
| Cobertura de portales | Urbania, AdondeVivir, Properati, REMAX | Igual, pero pueden quedar desfasados |
| Base NSE | `04. BASE DE UBICACIONES.xlsx` real | Ruta de ejemplo |
| Tipo de cambio | Apunta a SQLite real | Cache aislada |
| Tests | No tiene tests automatizados (notebook humano) | `tests/sectores/inmobiliario/` cubre fixtures |

## Para construir un sector nuevo

Ver [`../../docs/agregar_nuevo_sector.md`](../../docs/agregar_nuevo_sector.md)
y el scaffold en [`../_template/`](../_template/).
