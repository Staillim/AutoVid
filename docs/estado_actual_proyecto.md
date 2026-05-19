# Estado Actual del Proyecto

Fecha de corte: 2026-05-19 (actualizado tras validación Fase 1)

## Resumen ejecutivo

El proyecto se encuentra en **fase 1 avanzada de backend arquitectonico**.

Ya existe una base tecnica consistente para el motor de render por nodos, con contratos estables, pipeline interno de render, cache por escena, manifiestos de salida, jobs locales y configuracion centralizada de runtime.

Todavia **no se considera un producto usable de punta a punta**, porque falta validar el primer render real en este entorno con dependencias del backend y binarios FFmpeg operativos.

## Estado general

### Completado

- blueprint tecnico consolidado
- estructura inicial del proyecto
- backend base en Python
- contratos Pydantic del dominio
- compilacion de `SceneNode -> TimelineScene`
- `RenderPlan`
- generacion de comando FFmpeg
- generacion de subtitulos `.ass`
- ejecutor de FFmpeg para escena y preview
- `render_manifest.json` por escena
- `JobManager` local asincrono
- configuracion centralizada de runtime
- healthcheck enriquecido para readiness de render
- smoke test controlado con assets sinteticos
- **entorno Python 3.11.9 validado con dependencias instaladas**
- **14/14 tests unitarios pasando en Windows**
- **smoke test ejecutado con FFmpeg 8.1 real → scene.mp4 + preview.png + render_manifest.json generados**
- **API REST verificada: /health, /projects/validate, /runtime/settings**
- **JSON Schema exportado a shared/jsonschema/ (6 modelos)**

### Parcialmente completado

- pipeline de render real con FFmpeg (validado en smoke, falta validar flujos multi-escena)

### Pendiente

- exportar tipos TypeScript desde JSON Schema (con json-schema-to-typescript)
- persistencia de jobs (actualmente solo en memoria)
- eventos de progreso en tiempo real (WebSocket)
- frontend/editor visual
- pipeline IA narrativo
- export final multi-escena validado
- `ProjectService` para abrir/guardar `.avproj` desde disco
- `AssetLibrary` con SQLite para indice de assets

## Arquitectura implementada hasta ahora

### Backend

Ubicacion principal:

- [backend/app](C:\Users\stail\Documents\1Nuevos\Proyec%20DAlg\backend\app)

Componentes ya implementados:

- [main.py](C:\Users\stail\Documents\1Nuevos\Proyec%20DAlg\backend\app\main.py): arranque de FastAPI y registro de rutas
- [models.py](C:\Users\stail\Documents\1Nuevos\Proyec%20DAlg\backend\app\domain\models.py): contratos de proyecto, escena, render, jobs y runtime health
- [render_compiler.py](C:\Users\stail\Documents\1Nuevos\Proyec%20DAlg\backend\app\services\render_compiler.py): compilacion de escena editable a escena renderizable
- [render_plan_builder.py](C:\Users\stail\Documents\1Nuevos\Proyec%20DAlg\backend\app\services\render_plan_builder.py): construccion de `RenderPlan`
- [ffmpeg_command_builder.py](C:\Users\stail\Documents\1Nuevos\Proyec%20DAlg\backend\app\services\ffmpeg_command_builder.py): construccion del comando FFmpeg
- [ffmpeg_executor.py](C:\Users\stail\Documents\1Nuevos\Proyec%20DAlg\backend\app\services\ffmpeg_executor.py): ejecucion y validacion de outputs
- [subtitle_ass_builder.py](C:\Users\stail\Documents\1Nuevos\Proyec%20DAlg\backend\app\services\subtitle_ass_builder.py): generacion de subtitulos `.ass`
- [render_pipeline.py](C:\Users\stail\Documents\1Nuevos\Proyec%20DAlg\backend\app\services\render_pipeline.py): orquestacion de compilacion, plan, comando, manifest y ejecucion
- [render_manifest_service.py](C:\Users\stail\Documents\1Nuevos\Proyec%20DAlg\backend\app\services\render_manifest_service.py): escritura y lectura de `render_manifest.json`
- [job_manager.py](C:\Users\stail\Documents\1Nuevos\Proyec%20DAlg\backend\app\services\job_manager.py): cola local de jobs
- [settings.py](C:\Users\stail\Documents\1Nuevos\Proyec%20DAlg\backend\app\core\settings.py): configuracion de runtime
- [runtime_diagnostics.py](C:\Users\stail\Documents\1Nuevos\Proyec%20DAlg\backend\app\services\runtime_diagnostics.py): healthcheck operativo del entorno

### API disponible

Rutas actuales:

- `/health`
- `/projects/validate`
- `/projects/compile-scene`
- `/jobs`
- `/jobs/{job_id}`
- `/jobs/render-scene`
- `/runtime/settings`

## Contratos de dominio ya definidos

Los siguientes contratos ya existen en codigo:

- `ProjectModel`
- `SceneNode`
- `Overlay`
- `TextBlock`
- `SubtitleTrack`
- `TimelineScene`
- `RenderPlan`
- `RenderJobResult`
- `RenderSceneManifest`
- `RuntimeHealthReport`

Esto significa que la base del dominio principal ya esta congelada a un nivel suficiente para seguir desarrollando sin improvisar el modelo central del sistema.

## Estado del motor de render

### Ya implementado

- compilacion de una escena a estructura renderizable
- resolucion de assets por `asset_id`
- conversion de posiciones relativas a pixeles
- zoom basico
- overlays basicos
- textos con `drawtext`
- subtitulos segmentados `.ass`
- comando de render de escena
- comando de generacion de preview
- escritura de manifiesto por escena

### Falta validar en ejecucion real

- compatibilidad de los filtros FFmpeg en un entorno real
- manejo real de fuentes en `drawtext`
- escritura real de `scene.mp4`
- escritura real de `preview.png`
- comportamiento ante errores reales de FFmpeg

## Estado del cache

Ya implementado:

- fingerprint por escena
- cache por proyecto
- estructura de salida por escena
- `render_manifest.json` persistido

Pendiente:

- validacion completa del reuse real de cache tras renders exitosos
- lectura del manifest para saltar render automaticamente
- invalidacion completa en flujos multi-escena

## Estado del runtime

Ya implementado:

- settings centralizados
- resolucion de `ffmpeg`, `ffprobe`, cache y logs
- reporte de readiness para render

Pendiente:

- probar el healthcheck con binarios reales en el entorno final
- integrar mejor rutas de fuentes para Windows/Tauri

## Estado de pruebas

Ubicacion:

- [backend/tests](C:\Users\stail\Documents\1Nuevos\Proyec%20DAlg\backend\tests)

Existe cobertura base para:

- compilador de render
- fingerprint de escena
- `RenderPlan`
- construccion de comandos FFmpeg
- subtitulos `.ass`
- runtime settings
- runtime diagnostics
- fixture minimo de proyecto

Limitacion actual:

- no se han corrido pruebas funcionales completas porque el entorno actual no tiene instaladas las dependencias del backend ni se ha validado FFmpeg real en esta sesion

## Smoke test

Ya existe:

- script: [backend/scripts/smoke_render.py](C:\Users\stail\Documents\1Nuevos\Proyec%20DAlg\backend\scripts\smoke_render.py)
- guia: [docs/smoke_test_render.md](C:\Users\stail\Documents\1Nuevos\Proyec%20DAlg\docs\smoke_test_render.md)
- fixture ejemplo: [shared/examples/minimal_project.avproj](C:\Users\stail\Documents\1Nuevos\Proyec%20DAlg\shared\examples\minimal_project.avproj)

Objetivo del smoke test:

- generar assets sinteticos
- ejecutar una escena real
- producir `scene.mp4`
- producir `preview.png`
- producir `render_manifest.json`

Estado:

- preparado
- no verificado todavia en ejecucion real dentro de este entorno

## Estado del frontend

No implementado todavia.

No existe aun:

- app React
- canvas de nodos
- panel de propiedades
- panel de assets
- visualizacion de jobs

## Estado del pipeline IA

No implementado todavia.

Solo existe la definicion arquitectonica en el blueprint y el contrato de hacia donde debe conectarse el sistema.

## Riesgo actual principal

El principal riesgo ya no es de modelado ni de arquitectura base.

El riesgo actual es de **integracion real del pipeline de render**:

- FFmpeg real
- fuentes reales
- entorno Python real
- verificacion end-to-end de artefactos

## Proximo objetivo recomendado

El siguiente hito recomendado es:

1. instalar o conectar dependencias reales del backend
2. verificar `/health`
3. ejecutar [backend/scripts/smoke_render.py](C:\Users\stail\Documents\1Nuevos\Proyec%20DAlg\backend\scripts\smoke_render.py)
4. corregir los primeros errores reales de integracion
5. cerrar el primer render end-to-end confirmado

## Evaluacion honesta

El proyecto esta en un **buen estado de fundacion tecnica**, especialmente para backend y arquitectura del motor.

Todavia no esta en fase de producto usable, pero ya supero la etapa de idea o blueprint aislado. Ahora existe una base de codigo coherente sobre la cual se puede iterar de forma seria.
