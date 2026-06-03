# Auditoria de alineamiento - 2026-05-30

## Pregunta revisada

El objetivo base del proyecto es crear una libreria/herramienta metodologica
para que agentes IA construyan scrapers sectoriales BCRP reutilizando el
aprendizaje de inmobiliaria, empleo, diarios/PDF y APIs oficiales. No debe
derivar hacia un scraper inmobiliario ni hacia una dependencia conceptual de
un proveedor IA especifico.

## Veredicto directo

El proyecto no esta totalmente desviado, pero la documentacion maestra si
estaba desalineada. El codigo ya contiene varias decisiones correctas; el
riesgo es que un agente lea el plan viejo y reconstruya una vision equivocada.

## Evidencia de que el nucleo si va en la direccion correcta

- `AGENTS.md` existe y ya esta escrito para agentes IA.
- `core.historial` implementa memoria SQLite multi-sector, ciclo de vida,
  `estado_calidad`, `id_fuente` y reruns idempotentes.
- `core.reportes` implementa Excel acumulativo y regeneracion desde SQLite.
- `core.calidad` evita que corridas degradadas entren al historial.
- `core.extractor_ia` usa interfaz + cache; DeepSeek es adaptador, no regla
  metodologica.
- `core.tipo_cambio` consume BCRP DataAPI y conserva auditoria de conversion.
- `core.ingesta` y `docs/fuentes_documentales.md` capturan aprendizajes de
  diarios/PDF.
- `core.limpieza` contiene periodos `anio`, `trimestre`, `mes` y precio
  publicado conservador para clasificados.
- Tests completos: `110 passed` con `PYTHONPATH='.codex-pydeps;.'`.

## Brechas detectadas

1. `PLAN_PROYECTO_SCRAPING_BCRP.md` estaba viejo: hablaba de Sprint 1,
   84 tests y Gemini/`google.generativeai`.
2. La narrativa externa podia hacer creer que inmobiliario era el producto.
   Debe quedar claro que inmobiliario es fuente de aprendizaje y ejemplo.
3. La documentacion no declaraba con suficiente fuerza que `AGENTS.md`/skill
   es un entregable principal.
4. `sectores/_template/main.py` es un scaffold con TODOs y `NotImplementedError`;
   por tanto, no debe venderse como CLI listo para produccion.
5. Empleo todavia no valida `core` como segundo sector consumidor dentro de
   este repo. El aprendizaje existe en proyecto externo, pero falta migrarlo
   o crear un adaptador real.
6. La imagen generada antes tomo senales del plan viejo, por eso incluyo
   Gemini y una lectura demasiado centrada en inmobiliario.

## Correcciones aplicadas

- Reescrito `PLAN_PROYECTO_SCRAPING_BCRP.md` hacia v0.4, con objetivo base,
  estado real, roadmap actual y riesgos.
- Actualizado `AGENTS.md` para declarar el contrato con agentes IA y separar
  metodologia de proveedor IA.
- Actualizado `README.md` con la brujula correcta, tests actuales y roadmap.
- Actualizado `docs/agregar_nuevo_sector.md` para moderar promesas y explicar
  IA como adaptador reemplazable.
- Actualizado `docs/runbook_operacion.md` con comando real de tests y
  regeneracion de Excel desde SQLite.

## Proximos pasos recomendados

1. Crear `docs/decisiones_metodologicas.md` con origen de cada decision:
   inmobiliaria web, empleo, diarios/PDF, API BCRP.
2. Decidir si `sectores/_template/main.py` sera un CLI minimo ejecutable o
   solo un scaffold guiado. Hoy es scaffold.
3. Migrar o reimplementar un primer sector `empleo` consumidor de `core`.
   Sin eso, la transversalidad sigue parcialmente no probada.
4. Convertir esta metodologia en skill instalable para Codex/Claude/otros
   agentes, con checklist, criterios de aceptacion y ejemplos.
5. Regenerar la imagen de referencia usando esta version corregida, sin
   centrarla en Gemini ni en inmobiliario.
