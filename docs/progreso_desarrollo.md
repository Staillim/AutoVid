# Progreso de desarrollo

## 2026-05-19 — Hito 2.4 completado

### Hito

WebSocket de progreso en tiempo real para jobs de render.

### Entregado

- `backend/app/domain/models.py`:
  - `JobProgressEventType` — enum con 5 tipos: `job_queued`, `job_started`, `ffmpeg_progress`, `job_completed`, `job_failed`
  - `FfmpegProgressData` — modelo Pydantic para datos de progreso FFmpeg
  - `JobProgressEvent` — evento estructurado y versionable con `schema_version`, `event_type`, `job_id`, `timestamp`, `data`
- `backend/app/services/progress_broadcaster.py` (nuevo):
  - `ProgressBroadcaster` — event bus pub/sub para eventos de progreso
  - `subscribe(job_id)` → `asyncio.Queue` con maxsize 64 (backpressure)
  - `unsubscribe(job_id, queue)` — remueve listener, idempotente
  - `emit(event_type, job_id, data)` — thread-safe, cruza thread boundary con `run_coroutine_threadsafe`
  - `close(job_id)` — envía sentinel (None) a todos los listeners
  - `close_all()` — cierra todos los listeners activos
  - Backpressure: si queue está llena, descarta evento más antiguo
- `backend/app/services/ffmpeg_executor.py`:
  - `execute()` ahora acepta `progress_callback: Callable[[dict], None] | None`
  - Usa `subprocess.Popen` + `-progress pipe:1` en vez de `subprocess.run`
  - Parsea output estructurado de FFmpeg (key=value) línea por línea
  - Corrige bug: `out_time_ms` de FFmpeg está en microsegundos, se convierte a ms
  - Emite progreso: `frame`, `fps`, `time_ms`, `speed`, `percent`
  - Sin callback: consume stdout para evitar bloqueo de pipe
- `backend/app/services/render_pipeline.py`:
  - `execute_scene_render()` acepta `progress_callback` kwarg
  - Inyecta callback al `FfmpegExecutor.execute()`
- `backend/app/services/job_manager.py`:
  - Acepta `broadcaster: ProgressBroadcaster | None`
  - `_make_progress_callback()` crea callback que emite al broadcaster
  - `_wrapped_processor()` detecta si processor soporta `progress_callback` via `inspect.signature`
  - Emite `job_queued` en `submit()`, `job_started` en `_mark_running()`, `job_completed`/`job_failed` en transiciones finales
  - `dispose()` cierra broadcaster
- `backend/app/api/routes/jobs.py`:
  - `WebSocket /api/jobs/ws/{job_id}` — endpoint para recibir eventos de progreso
  - Se suscribe al broadcaster, envía eventos al cliente, cleanup en disconnect
- `backend/app/runtime.py`:
  - `progress_broadcaster` singleton global
  - Inyectado en `render_job_manager`
- `backend/app/main.py`:
  - `lifespan()` cierra `progress_broadcaster` en shutdown
- `backend/tests/test_progress_websocket.py` (nuevo, 19 tests):
  - Broadcaster: subscribe, emit, multi-subscriber, isolation, unsubscribe, close, backpressure, emit_raw
  - Integration: submit emits queued, worker emits started/completed, worker emits failed
  - FFmpeg: progress parsing, callback called, percent capped at 100, missing fields handled
  - WebSocket: connection + events, disconnect cleanup
- suite completa: **74/74 tests pasan** (55 anteriores + 19 nuevos)

### Verificación realizada

- `python -m pytest tests/ -v` → 74 passed, 0 failed
- Cero regresiones en tests existentes

### Contrato de eventos WebSocket

Cada mensaje es JSON con estructura:
```json
{
  "schema_version": "1.0.0",
  "event_type": "job_queued|job_started|ffmpeg_progress|job_completed|job_failed",
  "job_id": "uuid",
  "timestamp": "2026-05-19T00:00:00+00:00",
  "data": { ... }
}
```

Para `ffmpeg_progress`, `data` contiene:
```json
{
  "frame": 123,
  "fps": 30.0,
  "time_ms": 4100,
  "speed": 1.23,
  "percent": 82.0
}
```

### Decisiones aplicadas

- FFmpeg usa `-progress pipe:1` (output estructurado) en vez de parsear stderr
- `out_time_ms` de FFmpeg está en microsegundos — se convierte a ms para el frontend
- Broadcaster es thread-safe: `run_coroutine_threadsafe` para cruzar thread boundary
- Backpressure con queue maxsize 64 — descarta evento más antiguo si está lleno
- Sentinel es `None` — consistente con WebSocket endpoint
- Processor wrapper usa `inspect.signature` para detectar soporte de `progress_callback`

### Lo siguiente

1. Cache hit detection en `RenderPipeline.execute_scene_render`
2. Export final multi-escena con concatenación FFmpeg

---

## 2026-05-19 — Hito 2.3 completado

### Hito

Persistencia de jobs en SQLite — los jobs sobreviven reinicios del backend.

### Entregado

- `backend/app/services/job_manager.py`:
  - Refactor completo: reemplaza `dict` in-memory por tabla SQLite `jobs`
  - ORM `JobRow` con SQLAlchemy 2.x (mismo patrón que `AssetRow`)
  - `dispose()` para liberar conexiones (Windows-safe)
  - `_persist_job()` — escribe/actualiza job en SQLite con `merge()`
  - `_get_job()` — lee job por ID desde DB
  - `_list_jobs()` — lista todos ordenados por `created_at DESC`
  - `_update_job_fields()` — actualiza campos de estado (running/completed/failed)
  - `result_json` — serialización de `RenderJobResult` como JSON en SQLite
  - Transiciones de estado persistidas: `queued → running → completed/failed`
- `backend/app/core/settings.py`:
  - Nuevo campo `jobs_db_path` con default `cwd / "jobs.db"`
  - Env var `NODEAV_JOBS_DB` para configuración custom
- `backend/app/runtime.py`:
  - `RenderJobManager` ahora recibe `db_path=app_settings.jobs_db_path`
- `backend/app/main.py`:
  - `lifespan()` llama `render_job_manager.dispose()` en shutdown
- `backend/tests/test_job_manager.py` — 12 tests:
  - `test_submit_persists_job` — persiste con status QUEUED
  - `test_get_returns_persisted_job` — lectura desde DB
  - `test_get_returns_none_for_unknown` — job inexistente
  - `test_list_returns_all_jobs_sorted` — orden descendente
  - `test_job_survives_manager_restart` — supervivencia a restart
  - `test_completed_job_persists_result` — resultado serializado
  - `test_failed_job_persists_error` — mensaje de error persistido
  - `test_worker_loop_persists_transitions` — queued→running→completed
  - `test_worker_loop_persists_failure` — fallo del processor
  - `test_job_row_to_record_roundtrip` — serialización/deserialización
  - `test_list_empty_db` — lista vacía
  - `test_db_file_created` — archivo DB se crea al instanciar
- suite completa: **55/55 tests pasan** (43 anteriores + 12 nuevos)

### Verificación realizada

- `python -m pytest tests/ -v` → 55 passed, 0 failed
- Cero regresiones en tests existentes

### Decisiones aplicadas

- DB separada (`jobs.db`) de `library.db` para evitar acoplamiento
- Mismo patrón ORM que AssetLibrary: `DeclarativeBase`, sesiones síncronas, `dispose()`
- `RenderJobRecord` no cambió — compatibilidad total con contratos existentes
- `result` se serializa como JSON via `model_dump_json()` de Pydantic v2
- Fixture de tests usa `shutil.rmtree(ignore_errors=True)` + `gc.collect()` para Windows

### Lo siguiente

1. Hito 2.4 — Eventos de progreso WebSocket
2. Cache hit detection en `RenderPipeline.execute_scene_render`

---

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
