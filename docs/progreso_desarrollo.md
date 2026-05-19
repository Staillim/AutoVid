# Progreso de desarrollo

## 2026-05-19 — Hito 2.2 completado

### Hito

AssetLibrary — índice local de assets con SQLite y SQLAlchemy 2.x.

### Entregado

- `backend/app/services/asset_library.py`:
  - `import_asset(path)` — importa archivo, extrae metadata con ffprobe, calcula SHA-256, idempotente
  - `get(asset_id)` — retorna un asset por ID
  - `list(kind?)` — lista todos los assets, filtrable por tipo
  - `search(query)` — búsqueda por nombre de archivo (case-insensitive)
  - `remove(asset_id)` — elimina del índice (no borra el archivo físico)
  - `count()` — total de assets registrados
  - `dispose()` — libera conexiones SQLite (necesario en Windows)
- modelo ORM `AssetRow` con SQLAlchemy DeclarativeBase
- excepciones tipadas: `AssetImportError`, `AssetNotFoundError`
- soporte de extensiones: `.mp4 .mov .mkv .avi .webm` (video), `.jpg .jpeg .png .webp .gif .bmp` (imagen), `.mp3 .wav .aac .ogg .flac .m4a` (audio)
- `backend/tests/test_asset_library.py` — 14 tests con fixture `lib_factory` que garantiza dispose() en Windows
- SQLAlchemy formalizado en `pyproject.toml`
- suite completa: **43/43 tests pasan**

### Verificación realizada

- `python -m pytest tests/ -v` → 43 passed, 0 failed
- tests con assets reales del smoke test: metadata de video extraida con ffprobe (1280x720, 30fps, 6000ms)
- idempotencia verificada: importar mismo archivo dos veces retorna mismo asset_id

### Bug resuelto en tests

- Windows bloquea el archivo `.db` de SQLite si el engine no se descarta antes del cleanup del `TemporaryDirectory`
- solución: fixture `lib_factory` en pytest que llama `lib.dispose()` antes del cleanup
- convención establecida: toda `AssetLibrary` debe ser descartada antes de borrar el directorio que contiene su `.db`

### Lo siguiente

1. Hito 2.3 — Persistencia de jobs en SQLite
2. Hito 2.4 — Eventos de progreso WebSocket

---


### Hito

ProjectService — persistencia de archivos `.avproj` en disco.

### Entregado

- `backend/app/services/project_service.py` con operaciones:
  - `open(path)` — carga y valida un `.avproj` desde disco
  - `save(project, path)` — serializa y escribe con `updated_at` actualizado
  - `create(name, ...)` — crea un proyecto nuevo en memoria con UUID generado
  - `is_compatible(path)` — verifica `schema_version` antes de cargar
  - `check_schema_version(project)` — valida si el modelo ya cargado es del schema actual
- excepciones tipadas: `ProjectNotFoundError`, `ProjectParseError`, `ProjectSaveError`
- `backend/tests/test_project_service.py` — 15 tests cubriendo todos los casos
- nuevos endpoints en `api/routes/projects.py`:
  - `POST /projects/open`
  - `POST /projects/save`
  - `POST /projects/create`
  - `POST /projects/check-compatibility`
- suite completa: **29/29 tests pasan**

### Verificación realizada

- `python -m pytest tests/ -v` → 29 passed, 0 failed
- ciclo completo create → save → open verificado en tests

### Lo siguiente

1. Hito 2.2 — AssetLibrary con SQLite

---


### Hitos

Validación del motor de render en entorno real Windows.

### Entregado

- entorno Python 3.11.9 verificado
- dependencias del backend instaladas (`pip install -e ".[dev]"`)
- corrección de 3 tests con comparación de paths en Windows (forward-slash vs backslash)
- **14/14 tests pasan** con pytest 8.4.2
- **smoke test ejecutado con FFmpeg 8.1** y completado con exit code 0
- artefactos generados y verificados:
  - `scene.mp4` → 2.1 MB
  - `preview.png` → 249 KB
  - `render_manifest.json` → 7.6 KB
  - `subtitles.ass` → 0.6 KB

### Verificación realizada

- `python -m pytest tests/ -v` → 14 passed, 0 failed
- `python scripts/smoke_render.py` → exit code 0, todos los artefactos generados y no vacíos
- FFmpeg 8.1 full_build disponible en PATH
- Font `C:/Windows/Fonts/arial.ttf` resuelta automáticamente por el script

### Bugs corregidos

- `tests/test_render_compiler.py` — asserts de paths usaban forward-slashes; se normalizaron con `Path()` para compatibilidad Windows
- `tests/test_runtime_settings.py` — mismo problema con comparación de `ffmpeg_path`

### Decisiones aplicadas

- La convención de tests para paths cross-platform es comparar `Path(actual) == Path(expected)` en vez de comparar strings directamente

### Lo siguiente

1. Verificar API REST local (`GET /health`, `POST /projects/validate`)
2. Exportar JSON Schema desde Pydantic a `shared/jsonschema/`
3. Iniciar Hito 2.1 — ProjectService (abrir/guardar .avproj)

---

## 2026-05-19 — Inicio de fase 1

### Hito

Inicio de fase 1 con foco en arquitectura ejecutable.

### Entregado

- estructura base del repo
- backend Python inicial
- modelos Pydantic para proyecto, escena, overlays, textos, subtitulos y assets
- compilador de escena a `TimelineScene`
- servicio de fingerprint para cache
- endpoints base para healthcheck, validacion de proyecto y compilacion de escena
- pruebas iniciales del compilador
- `RenderPlan` tipado con entradas, etapas y outputs esperados
- `FfmpegCommandBuilder` para escenas simples
- `RenderPipeline` que conecta compilacion, fingerprint, plan y comando
- `RenderJobManager` local con cola en memoria y worker asincrono
- endpoints de jobs para preparar renders en segundo plano
- generador de subtitulos `.ass` para cues segmentados
- ejecutor local de FFmpeg con validacion de `scene.mp4` y `preview.png`
- comando separado para generar preview desde la escena final
- el pipeline de jobs ahora apunta a ejecucion real, no solo preparacion
- `render_manifest.json` persistido por escena dentro del cache
- servicio de lectura/escritura de manifests para trazabilidad y debugging
- settings centrales de runtime para `ffmpeg`, `ffprobe`, cache, logs y fuentes
- el pipeline ahora resuelve paths desde configuracion en vez de asumir valores fijos
- endpoint de inspeccion de runtime para diagnostico local
- healthcheck enriquecido con estado de `ffmpeg`, `ffprobe`, cache y logs
- reporte de readiness para saber si el entorno esta listo para render
- fixture `.avproj` minimo en `shared/examples`
- script de smoke test para generar assets sinteticos y ejecutar una escena real
- documentacion operativa del smoke test

### Verificacion realizada

- compilacion sintactica de `backend/app` y `backend/tests` con el runtime Python disponible
- validacion funcional pendiente por falta de dependencias instaladas (`fastapi`, `pydantic`, `pytest`) en el entorno actual
- validacion funcional de FFmpeg pendiente por ausencia de binario verificado en este entorno

### Decisiones aplicadas en codigo

- proyectos en `.avproj`
- biblioteca de assets fuera del proyecto
- cache por fingerprint
- jobs locales como direccion tecnica del backend
- FFmpeg como motor unico de render

### Lo siguiente

1. verificar ejecucion real con FFmpeg y assets de ejemplo controlados
2. exportar JSON Schema compartido desde Pydantic
3. introducir persistencia opcional de jobs y eventos de progreso
4. convertir el smoke test en chequeo automatizable del primer render end-to-end
