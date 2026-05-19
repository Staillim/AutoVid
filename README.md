# NodeAV

Motor de edicion audiovisual inteligente por nodos para videos largos de YouTube.

## Estado actual

El proyecto esta en construccion de fase 1:

- blueprint tecnico consolidado
- contratos de dominio iniciales en backend
- compilador inicial de `SceneNode -> TimelineScene`
- fingerprint de cache por escena
- API minima para validar y compilar escenas
- `RenderPlan` y generacion inicial de comando FFmpeg
- `JobManager` local para preparar renders asincronos
- generacion de subtitulos `.ass`
- ejecutor FFmpeg para escena y preview
- `render_manifest.json` por escena en el cache
- settings de runtime centralizados para sidecar/desktop
- healthcheck de runtime con readiness de render
- smoke test controlado con assets sinteticos

## Prioridad de ingenieria

1. compositor procedural estable
2. contrato persistente de proyecto
3. cache determinista
4. editor visual
5. IA narrativa

## Estructura inicial

```text
backend/
docs/
shared/
blueprint_motor_audiovisual.md
README.md
```

## Siguiente objetivo inmediato

Ejecutar el smoke test controlado con FFmpeg real y usarlo como base del primer render end-to-end verificable.
