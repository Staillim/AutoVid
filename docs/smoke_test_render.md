# Smoke Test de Render

Este documento define el primer smoke test controlado del motor de render.

## Objetivo

Validar el pipeline completo de una escena:

1. diagnostico de runtime
2. generacion de assets sinteticos
3. compilacion de `SceneNode -> TimelineScene`
4. generacion de `.ass`
5. render de `scene.mp4`
6. generacion de `preview.png`
7. escritura de `render_manifest.json`

## Script

Ubicacion:

- [backend/scripts/smoke_render.py](C:\Users\stail\Documents\1Nuevos\Proyec%20DAlg\backend\scripts\smoke_render.py)

## Requisitos

- `ffmpeg` y `ffprobe` accesibles por settings o variables de entorno
- dependencias Python del backend instaladas
- una fuente valida para `drawtext`

## Variables de entorno soportadas

- `NODEAV_RUNTIME_ROOT`
- `NODEAV_CACHE_ROOT`
- `NODEAV_LOGS_ROOT`
- `NODEAV_FFMPEG_PATH`
- `NODEAV_FFPROBE_PATH`
- `NODEAV_FONT_ROOT`

## Ejecucion esperada

Desde `backend/`:

```powershell
python scripts\smoke_render.py
```

## Salidas esperadas

Dentro de `backend/.smoke/`:

- `assets/background.mp4`
- `assets/overlay.png`
- `project/cache/smoke-project-001/scenes/.../scene.mp4`
- `project/cache/smoke-project-001/scenes/.../preview.png`
- `project/cache/smoke-project-001/scenes/.../render_manifest.json`

## Criterio de exito

El smoke test se considera exitoso si:

1. el script termina con exit code `0`
2. `scene.mp4` existe y no esta vacio
3. `preview.png` existe y no esta vacio
4. `render_manifest.json` contiene fingerprint, comandos y execution details
