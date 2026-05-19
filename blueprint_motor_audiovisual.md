# Blueprint Técnico: Motor de Edición Audiovisual Inteligente por Nodos

> Tipo de documento: arquitectura de ingeniería ejecutable
>  
> Versión del documento: 1.0
>  
> Estado: decisión final para MVP
>  
> Alcance: blueprint listo para desarrollo real

---

## Tabla de contenidos

1. Principios de arquitectura
2. Decisiones definitivas del MVP
3. Arquitectura final del sistema
4. Stack exacto
5. Flujo técnico end-to-end
6. Contrato técnico estable
7. Render procedural con FFmpeg
8. Cache, invalidación y reutilización
9. Pipeline IA narrativo
10. Persistencia, versionado y migraciones
11. Empaquetado desktop y operación en Windows
12. Estructura del repositorio
13. Roadmap realista
14. Prioridades y riesgos reales

---

## 1. Principios de arquitectura

Este proyecto no es un editor NLE generalista. Es un sistema de composición procedural por escenas para videos largos de YouTube, donde la unidad primaria de trabajo es `SceneNode`.

Reglas rectoras del MVP:

1. El núcleo técnico es el compositor procedural con FFmpeg.
2. La IA propone estructura narrativa; no toma decisiones visuales finales ni ejecuta render.
3. Cada escena es independiente, renderizable por separado y reutilizable.
4. El sistema debe sobrevivir fallos parciales sin corromper proyectos.
5. La persistencia del proyecto debe ser portable, legible y versionable.
6. El MVP evita dependencias distribuidas innecesarias.
7. Todo contrato estable debe definirse antes del editor visual.

Consecuencia arquitectónica directa:

- `SceneNode` es la entidad central del dominio.
- El render es asíncrono, local y orientado a trabajos.
- El cache canónico vive en disco.
- El proyecto vive en un archivo `.avproj`.
- SQLite se usa para catálogo e índices, no como formato de proyecto.

---

## 2. Decisiones definitivas del MVP

Esta sección cierra las contradicciones previas. Estas decisiones son finales para MVP.

### 2.1 Cola de trabajos: `cola local simple`, no `Celery + Redis`

Decisión:

- El MVP usa una cola local en el backend Python, implementada con `asyncio.Queue` y uno o dos workers controlados por la aplicación.
- No se usa Celery.
- No se usa Redis.

Por qué:

- El producto es local-first y single-user.
- Celery + Redis añade instalación, operaciones, observabilidad y puntos de fallo que no aportan valor real en MVP.
- El render ya ocurre mediante subprocesos FFmpeg; no se necesita un orquestador distribuido para el primer producto usable.

Resultado:

- API asíncrona con jobs locales persistidos mínimamente.
- Posibilidad futura de sustituir la cola por una implementación distribuida sin cambiar el contrato del job.

### 2.2 Persistencia: `.avproj JSON` para proyectos, `SQLite` para catálogo local

Decisión:

- El proyecto se guarda en un archivo `.avproj` JSON.
- SQLite se usa exclusivamente para:
  - índice global de assets
  - búsqueda FTS
  - metadata derivada de assets
  - historial local de jobs si se decide persistirlo

Por qué:

- El `.avproj` es portable, versionable y fácil de migrar.
- SQLite es excelente para consultas locales y búsquedas, pero no es el formato adecuado para intercambiar o respaldar proyectos completos.

Resultado:

- Fuente de verdad del proyecto: `.avproj`
- Fuente de verdad del inventario global de assets: `library.db`

### 2.3 Render engine: `FFmpeg puro`, no `MoviePy`

Decisión:

- El render se implementa con `ffmpeg` y `ffprobe` directos.
- Python construye instrucciones y ejecuta subprocesos.
- No se usa MoviePy en el MVP.

Por qué:

- MoviePy simplifica casos triviales, pero introduce lentitud, consumo de memoria, rutas de error adicionales y una abstracción que se rompe precisamente donde este proyecto se vuelve interesante.
- El proyecto necesita control determinista del pipeline de render.

Resultado:

- Un único motor de composición.
- Menos capas de abstracción frágiles.
- Mejor debugging con comandos FFmpeg reproducibles.

### 2.4 Backend: API asíncrona con jobs locales; render no bloqueante

Decisión:

- El backend expone endpoints HTTP y WebSocket.
- Las solicitudes de render crean jobs.
- El render se ejecuta fuera del hilo de request.
- El backend no hace render síncrono dentro de la llamada HTTP.

Por qué:

- Incluso un nodo pequeño puede tardar varios segundos.
- El usuario debe poder seguir editando mientras renderiza.
- La UI necesita estados de cola, progreso, error y retry.

Resultado:

- `POST /jobs/render-node` crea un job.
- `GET /jobs/{id}` consulta estado.
- WebSocket emite progreso.

### 2.5 Cache: `cache canónico en disco`, no cache híbrida compleja

Decisión:

- El cache real vive en disco dentro del proyecto.
- La memoria solo se usa como estado efímero de ejecución.
- No existe un cache híbrido persistente memoria+disco en MVP.

Por qué:

- El render produce artefactos pesados.
- La memoria no es un medio adecuado para persistencia ni reutilización entre sesiones.
- El usuario necesita que el cache sobreviva cierre, reinicio y crash.

Resultado:

- Todo render reutilizable se representa como archivos y manifests.
- El backend puede reconstruir estado desde disco.

### 2.6 Assets: `locales únicamente` en MVP

Decisión:

- El MVP trabaja solo con assets locales importados a una biblioteca.
- No hay búsqueda online automática.
- No hay scraping ni ingestion remota.

Por qué:

- Mantiene el sistema predecible.
- Evita acoplar IA narrativa con disponibilidad incierta de internet.
- Reduce complejidad legal, operativa y de rate limits.

Resultado:

- La IA sugiere escenas y entidades.
- El matching visual se hace contra la biblioteca local indexada.

---

## 3. Arquitectura final del sistema

### 3.1 Vista de alto nivel

```text
Usuario
  |
  v
Tauri Desktop Shell
  |
  +--> Frontend React/TypeScript
  |      - Canvas de nodos
  |      - Panel de propiedades
  |      - Panel de assets
  |      - Monitor de jobs
  |
  +--> Backend Python Sidecar
         - API FastAPI
         - JobManager local
         - IA narrativa
         - Asset Library
         - Project Storage
         - Render Compiler
         - FFmpeg Executor
```

### 3.2 Módulos del backend

1. `project_service`
   - abre, valida, guarda y migra `.avproj`

2. `asset_library`
   - importa assets
   - ejecuta `ffprobe`
   - genera thumbnails y previews
   - indexa metadata en SQLite

3. `analysis_service`
   - transcribe audio si existe
   - analiza guion/transcripción
   - genera `NarrativeAnalysis`
   - produce `SceneDraft[]`

4. `scene_builder`
   - convierte `SceneDraft[]` en `SceneNode[]`
   - aplica defaults visuales
   - resuelve referencias de assets sugeridos

5. `render_compiler`
   - transforma `SceneNode` en `TimelineScene`
   - valida rangos
   - genera plan de render

6. `ffmpeg_executor`
   - materializa comandos FFmpeg
   - ejecuta subprocesos
   - captura stderr
   - genera preview

7. `job_manager`
   - cola local
   - workers
   - estados y retry

8. `cache_service`
   - calcula hashes
   - detecta invalidaciones
   - resuelve reutilización de escenas y export final

### 3.3 Módulos del frontend

1. `NodeCanvas`
   - secuencia visual lineal con React Flow
   - reordenación manual

2. `PropertiesPanel`
   - edición de background, overlays, textos, zoom y subtítulos

3. `AssetPanel`
   - búsqueda local, filtros y drag & drop

4. `TimelinePreviewPanel`
   - preview de nodo y preview de export final

5. `JobPanel`
   - cola, progreso, errores y retry

### 3.4 Principio de separación crítica

La UI no conoce FFmpeg.

La UI solo conoce:

- `Project`
- `SceneNode`
- `AssetRef`
- estados de jobs

El backend traduce eso a `TimelineScene` y luego a ejecución FFmpeg.

---

## 4. Stack exacto

## 4.1 Frontend

- Framework: `React 18`
- Lenguaje: `TypeScript 5`
- Build tool: `Vite`
- Canvas visual: `React Flow`
- Estado local/global: `Zustand`
- Sincronización servidor/UI: `TanStack Query`
- Estilos: `Tailwind CSS`
- Componentes base: `shadcn/ui`
- Runtime desktop: WebView gestionado por `Tauri 2`

Decisión visual de nodos:

- Grafo lineal editable.
- Las aristas solo expresan orden narrativo.
- En MVP no existen dependencias de datos entre escenas.
- El canvas no es un sistema de nodos generalista.

## 4.2 Backend

- Lenguaje: `Python 3.11`
- API: `FastAPI`
- Validación y schemas: `Pydantic v2`
- Base de datos local: `SQLite 3`
- ORM ligero para biblioteca: `SQLAlchemy 2.x`
- Cola de trabajos: implementación propia con `asyncio.Queue`
- Comunicación de progreso: `WebSocket`
- Procesos externos: `subprocess.Popen` con argumentos listados, nunca shell

## 4.3 IA narrativa

- Transcripción local: `faster-whisper`
- Análisis narrativo principal: proveedor LLM remoto con salida JSON estructurada
- Fallback local opcional: `Ollama`

Decisión para MVP:

- Si hay internet y credenciales configuradas, usar modelo remoto estructurado.
- Si no hay credenciales, el producto puede seguir funcionando con editor manual.
- La transcripción sí debe poder correr localmente.

## 4.4 Render

- Motor: `ffmpeg` y `ffprobe`
- Encapsulación: constructor de plan de render + generador de comandos por capas
- Subtítulos: `.ass` generado por backend
- Texto animado: filtros `drawtext`, `fade`, `scale`, `alpha`, o prerender a PNG según el caso

## 4.5 Almacenamiento

- Proyecto: archivo `.avproj`
- Biblioteca de assets: `library.db`
- Cache de escenas: directorios por hash dentro del proyecto
- Exports finales: carpeta `exports/`
- Configuración de app: `AppData` del usuario

---

## 5. Flujo técnico end-to-end

### 5.1 Flujo de creación asistida

1. Usuario crea proyecto.
2. Usuario importa assets locales.
3. Backend indexa assets y genera previews.
4. Usuario carga guion o audio.
5. Si entra audio:
   - `faster-whisper` transcribe
   - se produce `Transcript`
6. `analysis_service` envía guion/transcripción al LLM.
7. El LLM devuelve `NarrativeAnalysis`.
8. `scene_builder` convierte análisis en `SceneDraft[]`.
9. `scene_builder` materializa `SceneNode[]`.
10. Frontend muestra nodos.
11. Usuario ajusta manualmente.
12. Usuario renderiza nodo individual o export final.

### 5.2 Flujo de render de un nodo

1. Frontend envía `scene_node_id`.
2. Backend carga proyecto.
3. `render_compiler` normaliza `SceneNode` a `TimelineScene`.
4. `cache_service` calcula fingerprint.
5. Si el cache es válido:
   - retorna artefacto ya renderizado
6. Si no es válido:
   - `job_manager` crea job
   - worker llama `ffmpeg_executor`
   - se genera `scene.mp4`, `preview.png`, `render_manifest.json`
7. Backend emite progreso.
8. Frontend actualiza estado del nodo.

### 5.3 Flujo de export final

1. Se determina orden final de escenas.
2. Se valida cache de cada escena.
3. Las escenas faltantes se renderizan.
4. Se genera lista concat.
5. Se concatena por FFmpeg.
6. Se muxea audio maestro.
7. Se genera export final y manifest de export.

---

## 6. Contrato técnico estable

Esta sección define el contrato canónico del dominio. Todo desarrollo debe respetarlo.

### 6.1 Principios del contrato

1. Los contratos persistidos no incluyen estado efímero de jobs.
2. Los paths absolutas no se guardan dentro de escenas.
3. Las escenas referencian assets por `asset_id`.
4. Todo schema persistido lleva `schema_version`.
5. Los campos nuevos deben ser backward-compatible dentro del mismo major.

### 6.2 Tipos base

```typescript
type UUID = string;
type ISODateTime = string;
type Milliseconds = number;
type Frames = number;
type AssetKind = "video" | "image" | "audio";
type NarrativeRole =
  | "hook"
  | "setup"
  | "context"
  | "argument"
  | "evidence"
  | "transition"
  | "payoff"
  | "cta";
```

### 6.3 `AssetRef`

```typescript
interface AssetRef {
  asset_id: UUID;
  kind: AssetKind;
}
```

### 6.4 `Overlay`

```typescript
interface Overlay {
  id: UUID;
  asset: AssetRef;
  start_ms: Milliseconds;
  end_ms: Milliseconds;
  x_pct: number;        // 0.0 - 1.0
  y_pct: number;        // 0.0 - 1.0
  width_pct: number;    // 0.0 - 1.0
  height_pct: number;   // 0.0 - 1.0
  opacity: number;      // 0.0 - 1.0
  enter_anim: "none" | "fade" | "slide_up" | "pop";
  exit_anim: "none" | "fade";
  z_index: number;
}
```

### 6.5 `TextBlock`

```typescript
interface TextBlock {
  id: UUID;
  content: string;
  start_ms: Milliseconds;
  end_ms: Milliseconds;
  anchor: "top_left" | "top_center" | "center" | "bottom_center";
  x_offset_px: number;
  y_offset_px: number;
  font_family: string;
  font_size_px: number;
  font_weight: 400 | 500 | 600 | 700 | 800;
  color_rgba: string;
  stroke_rgba: string | null;
  stroke_width_px: number;
  bg_rgba: string | null;
  padding_px: number;
  anim: "none" | "fade" | "pop";
  z_index: number;
}
```

### 6.6 `ZoomMotion`

```typescript
interface ZoomMotion {
  mode: "none" | "zoom_in" | "zoom_out";
  start_ms: Milliseconds;
  end_ms: Milliseconds;
  start_scale: number;
  end_scale: number;
  anchor: "center";
}
```

### 6.7 `SubtitleTrack`

```typescript
interface SubtitleCue {
  id: UUID;
  start_ms: Milliseconds;
  end_ms: Milliseconds;
  text: string;
}

interface SubtitleTrack {
  enabled: boolean;
  mode: "segment";
  cues: SubtitleCue[];
  style_preset: "default_youtube";
}
```

### 6.8 `NarrativeBlock`

```typescript
interface NarrativeBlock {
  source_start_ms: Milliseconds | null;
  source_end_ms: Milliseconds | null;
  summary: string;
  transcript_excerpt: string;
  entities: string[];
  narrative_role: NarrativeRole;
  confidence: number; // 0.0 - 1.0
}
```

### 6.9 `SceneNode`

`SceneNode` es el contrato central del sistema.

```typescript
interface SceneNode {
  id: UUID;
  order: number;
  title: string;
  enabled: boolean;

  duration_ms: Milliseconds;

  narrative: NarrativeBlock;

  background: {
    asset: AssetRef;
    trim_in_ms: Milliseconds;
    trim_out_ms: Milliseconds;
    loop_mode: "loop" | "freeze_last_frame" | "cut";
    fit_mode: "cover";
    blur_background: false;
  };

  overlays: Overlay[];
  texts: TextBlock[];
  zoom: ZoomMotion;
  subtitles: SubtitleTrack;

  tags: string[];

  ui: {
    canvas_x: number;
    canvas_y: number;
    color_hint: string | null;
  };
}
```

Reglas:

- Toda escena tiene exactamente un background.
- `duration_ms` es la duración canónica de la escena.
- `trim_out_ms` debe ser mayor que `trim_in_ms`.
- `order` define secuencia final.
- `enabled=false` excluye la escena del export final, pero no la elimina.

### 6.10 `TimelineScene`

`TimelineScene` no es el contrato de edición. Es el contrato compilado para render.

```typescript
interface TimelineScene {
  scene_id: UUID;
  width: number;
  height: number;
  fps: number;
  duration_ms: Milliseconds;

  background_clip: {
    absolute_path: string;
    trim_in_ms: Milliseconds;
    trim_out_ms: Milliseconds;
    loop_mode: "loop" | "freeze_last_frame" | "cut";
  };

  overlay_clips: Array<{
    id: UUID;
    absolute_path: string;
    start_ms: Milliseconds;
    end_ms: Milliseconds;
    x_px: number;
    y_px: number;
    width_px: number;
    height_px: number;
    opacity: number;
    enter_anim: "none" | "fade" | "slide_up" | "pop";
    exit_anim: "none" | "fade";
    z_index: number;
  }>;

  text_clips: Array<{
    id: UUID;
    content: string;
    start_ms: Milliseconds;
    end_ms: Milliseconds;
    x_px: number;
    y_px: number;
    style: {
      font_file: string;
      font_size_px: number;
      color_rgba: string;
      stroke_rgba: string | null;
      stroke_width_px: number;
      bg_rgba: string | null;
      padding_px: number;
    };
    anim: "none" | "fade" | "pop";
    z_index: number;
  }>;

  zoom: ZoomMotion;

  subtitle_ass_path: string | null;
}
```

Decisión clave:

- `TimelineScene` se genera en backend.
- Nunca se persiste en `.avproj`.
- Si el render falla, se puede serializar temporalmente a JSON para debugging.

### 6.11 Formato `.avproj`

```json
{
  "schema_version": "1.0.0",
  "project_id": "6ec5f0a7-df21-4a8f-b4b2-7be4b4d9e201",
  "created_at": "2026-05-19T15:00:00Z",
  "updated_at": "2026-05-19T16:20:00Z",
  "name": "Video GTA 6",
  "settings": {
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "video_codec": "h264",
    "audio_codec": "aac",
    "master_audio_asset_id": "1a2b3c4d-0001",
    "subtitle_language": "es",
    "export_preset": "youtube_1080p"
  },
  "library_binding": {
    "library_id": "default-local-library"
  },
  "analysis": {
    "source_type": "script",
    "source_asset_id": null,
    "source_text_sha256": "abc123",
    "last_analysis_id": "analysis_001",
    "last_analysis_provider": "remote_llm",
    "last_analysis_model": "structured-default"
  },
  "nodes": [],
  "scene_order": [],
  "notes": ""
}
```

Decisiones:

- `scene_order` es canónico; no se infiere del array.
- `nodes` puede almacenarse en cualquier orden físico.
- No se almacenan paths absolutas en el proyecto.

---

## 7. Render procedural con FFmpeg

## 7.1 Prioridad absoluta

El compositor procedural es la pieza más crítica del proyecto. Si esta parte falla, todo el producto falla aunque la IA y la UI estén completas.

## 7.2 Estrategia para evitar `filtergraphs` gigantes

Decisión:

- El render de cada escena se compone en etapas controladas.
- No se construye un monstruo único con todas las transformaciones posibles a la vez.

Pipeline por escena:

1. Normalizar background.
2. Aplicar motion base al background.
3. Componer overlays en capas ordenadas.
4. Aplicar textos.
5. Aplicar subtítulos.
6. Emitir salida final de la escena.

Regla práctica:

- En MVP solo habrá un background, hasta 3 overlays, hasta 3 bloques de texto, un zoom base y subtítulos segmentados.
- Esa restricción mantiene el grafo de filtros pequeño y testeable.

## 7.3 Estrategia de compilación

Python no genera comandos libremente desde strings sueltas. Genera un `RenderPlan`.

```python
class RenderPlan(BaseModel):
    scene_id: str
    inputs: list[str]
    filter_steps: list[dict]
    output_path: str
```

Luego un `FfmpegCommandBuilder` transforma `RenderPlan` en argumentos FFmpeg.

Ventajas:

- debugging reproducible
- separación entre validación y ejecución
- tests unitarios del plan sin invocar FFmpeg

## 7.4 Estrategia de texto

Decisión MVP:

- Títulos y rótulos: `drawtext`
- Subtítulos: archivo `.ass`

Por qué:

- `drawtext` resuelve bien textos cortos y animaciones simples.
- `.ass` es más estable para múltiples cues y estilo consistente.

## 7.5 Estrategia de animación

Animaciones permitidas en MVP:

- overlay fade
- overlay slide up
- overlay pop
- text fade
- text pop
- zoom in
- zoom out

No se implementan:

- keyframes arbitrarios
- tracking motion
- máscaras avanzadas
- color grading complejo

## 7.6 Comandos y ejecución

Reglas:

1. Siempre usar argumentos como lista, no shell string.
2. Registrar comando expandido en logs.
3. Capturar `stdout`, `stderr`, código de salida y duración.
4. Hacer timeout configurable por job.
5. Validar existencia y tamaño del archivo de salida tras FFmpeg.

## 7.7 Pruebas mínimas del compositor

Antes del editor visual deben existir tests de:

1. background video solo
2. background imagen loop a duración fija
3. background + overlay fade
4. background + texto pop
5. background + subtítulos `.ass`
6. background + zoom in
7. escena con overlay fuera de rango rechazada por validador

---

## 8. Cache, invalidación y reutilización

## 8.1 Principio de cache

La cache no se basa en timestamps solamente. Se basa en fingerprints deterministas.

### 8.2 Qué se cachea

Por escena:

- `scene.mp4`
- `preview.png`
- `render_manifest.json`
- `timeline_scene.json` opcional para debugging

Por export final:

- `final.mp4`
- `export_manifest.json`

### 8.3 Huella de una escena

El fingerprint de una escena se calcula con SHA-256 sobre:

1. `schema_version` del render
2. settings relevantes del proyecto
3. `SceneNode` normalizado
4. metadata de assets usados
5. hash de contenido de subtítulos `.ass`
6. versión del compositor

No se incluyen:

- coordenadas del canvas
- selección visual del usuario en UI
- estados de jobs

### 8.4 Hash de asset

Cada asset importado guarda:

- `content_sha256`
- tamaño en bytes
- duración
- resolución
- fps si aplica
- `imported_at`
- `last_seen_mtime`

Regla:

- El hash fuerte del asset se calcula al importar.
- En aperturas normales se compara tamaño + `mtime`.
- Si cambia cualquiera de esos dos, se recalcula hash fuerte y se invalida lo afectado.

### 8.5 Invalidez de cache

Se invalida una escena cuando cambia:

- cualquier campo renderizable del `SceneNode`
- cualquier asset usado por la escena
- cualquier setting global que afecte salida
- la versión del compositor
- el contenido de subtítulos

No se invalida cuando cambia:

- posición del nodo en canvas
- tags no usados para render
- nombre del proyecto

### 8.6 Reutilización de escenas

La reutilización se hace por fingerprint, no por nombre.

Si dos escenas en proyectos distintos comparten el mismo fingerprint:

- En MVP no se comparte cache entre proyectos.
- La reutilización se limita al mismo proyecto.

Decisión:

- cache por proyecto, no cache global

Por qué:

- simplifica limpieza
- evita colisiones y dependencias ocultas
- mejora portabilidad del proyecto

### 8.7 Render parcial

Render parcial significa:

- renderizar una sola escena
- renderizar un subconjunto contiguo
- exportar final reutilizando escenas ya válidas

El sistema debe soportar:

1. `render_node(scene_id)`
2. `render_range(start_order, end_order)`
3. `export_final()`

### 8.8 Cache de previews

Regla:

- El preview estático se deriva del render de escena si existe.
- Si la escena no está renderizada, se puede generar preview rápido de background.

Decisión:

- `preview.png` canónico sale del render completo.
- `draft_preview.png` es efímero y no participa en fingerprint.

### 8.9 Cache del export final

Fingerprint del export final:

1. lista ordenada de fingerprints de escenas activas
2. settings globales de export
3. asset del audio maestro
4. versión del concatenador

---

## 9. Pipeline IA narrativo

La IA entra desde el inicio, pero solo en la capa de estructura narrativa.

## 9.1 Qué hace la IA

1. divide el contenido en escenas
2. resume cada escena
3. detecta entidades
4. clasifica rol narrativo
5. sugiere duración base
6. sugiere palabras clave para matching de assets

## 9.2 Qué no hace la IA

1. no decide filtergraphs
2. no genera comandos FFmpeg
3. no decide layout final exacto
4. no selecciona automáticamente assets definitivos sin validación

## 9.3 Pipeline exacto

### Entrada

Una de estas dos:

- `script_text`
- `audio_asset_id`

### Etapa A: adquisición

Si entra audio:

1. resolver asset
2. transcribir con `faster-whisper`
3. producir:
   - texto completo
   - segmentos temporales

Si entra texto:

1. normalizar saltos y puntuación
2. calcular hash del texto

### Etapa B: análisis narrativo

Se envía una estructura compacta al modelo:

- texto o transcripción
- duración total si existe
- idioma
- objetivo de salida JSON

Salida requerida:

```json
{
  "analysis_id": "analysis_001",
  "language": "es",
  "global_summary": "string",
  "scenes": [
    {
      "scene_index": 1,
      "summary": "string",
      "transcript_excerpt": "string",
      "start_ms": 0,
      "end_ms": 22000,
      "entities": ["Rockstar", "GTA 6"],
      "narrative_role": "hook",
      "keywords": ["precio", "lanzamiento", "trailer"],
      "visual_intent": "announcement emphasis",
      "confidence": 0.91
    }
  ]
}
```

### Etapa C: validación fuerte

`Pydantic` valida:

- campos requeridos
- rangos de tiempo
- roles narrativos válidos
- escenas ordenadas
- duraciones positivas

Si falla:

1. reintentar una vez con prompt correctivo
2. si vuelve a fallar, devolver análisis fallido sin bloquear edición manual

### Etapa D: matching de assets

Para cada escena:

1. buscar assets locales por keywords y entidades en SQLite FTS
2. rankear por:
   - coincidencia textual
   - tags
   - tipo de asset
   - prioridad manual del usuario
3. devolver candidatos

### Etapa E: materialización a `SceneNode`

Reglas de construcción:

- `duration_ms = end_ms - start_ms` si viene de audio
- si viene de guion puro sin tiempo:
  - estimar por longitud textual y pacing base
  - permitir edición manual posterior
- primer asset candidato se propone como background
- overlays quedan vacíos salvo reglas simples
- texto puede prellenarse con título corto o dato destacado si la escena lo amerita

## 9.4 Modelos recomendados para MVP

### Transcripción

- Primario: `faster-whisper small` para rendimiento general
- Opción de calidad: `faster-whisper medium`

Decisión:

- `small` como default del producto
- `medium` opcional si la máquina lo soporta

### LLM narrativo

Perfil recomendado:

- modelo remoto con salida JSON estructurada y buena comprensión narrativa
- costo moderado
- latencia aceptable para textos largos

Configuración de producto:

- `provider_profile = remote_structured_default`
- `provider_profile = ollama_local_fallback` opcional

No se acopla el contrato del sistema al nombre de un modelo específico. El proveedor se configura en ajustes.

## 9.5 Contrato de salida IA a editor

La IA no crea directamente escenas finales de render. Crea `SceneDraft`.

```typescript
interface SceneDraft {
  scene_index: number;
  summary: string;
  transcript_excerpt: string;
  start_ms: number | null;
  end_ms: number | null;
  entities: string[];
  keywords: string[];
  narrative_role: NarrativeRole;
  confidence: number;
  suggested_background_asset_ids: string[];
}
```

`scene_builder` transforma `SceneDraft -> SceneNode`.

---

## 10. Persistencia, versionado y migraciones

## 10.1 Estrategia de versionado

El proyecto usa `schema_version` semántica:

- `major.minor.patch`

Reglas:

- `major`: ruptura incompatible del formato persistido
- `minor`: campos nuevos compatibles
- `patch`: correcciones no estructurales

Versión inicial del proyecto:

- `1.0.0`

### 10.2 Compatibilidad

El backend solo abre:

- misma major
- minors anteriores de la misma major si existe migración disponible

### 10.3 Sistema de migraciones

Migraciones obligatorias en cadena:

```python
MIGRATORS = {
    "1.0.0": migrate_1_0_0_to_1_1_0,
    "1.1.0": migrate_1_1_0_to_2_0_0,
}
```

Reglas:

1. El archivo original se respalda antes de migrar.
2. Toda migración produce un nuevo objeto validado por schema destino.
3. Si falla una migración, el proyecto no se sobrescribe.

### 10.4 Qué no debe persistirse

No persistir:

- progreso de jobs
- PIDs de procesos
- rutas temporales de sistema
- paths absolutas de assets
- flags de UI efímeros

---

## 11. Empaquetado desktop y operación en Windows

Esta sección define una estrategia realista de producción, no un ideal abstracto.

## 11.1 Decisión de empaquetado

El producto se distribuye como aplicación Tauri con backend Python congelado como sidecar ejecutable.

Decisión final:

- no se distribuye un script Python crudo
- no se depende de que el usuario tenga Python instalado
- el backend se empaqueta como binario autónomo

Herramienta recomendada:

- `PyInstaller` para MVP

Razonamiento:

- integración rápida
- sidecar sencillo en Windows
- menor complejidad inicial que mantener embebido un runtime Python manual

Alternativa futura:

- `Nuitka` si se necesita mejor cold start o empaquetado más optimizado

## 11.2 Componentes empaquetados

La app final contiene:

1. `frontend` compilado
2. `backend-sidecar.exe`
3. `ffmpeg.exe`
4. `ffprobe.exe`
5. fuentes requeridas para `drawtext`
6. configuración base

No se empaquetan por defecto:

- modelos Whisper pesados
- caches de proyecto
- biblioteca de assets del usuario

## 11.3 Whisper en producción

Decisión:

- la librería sí va en el backend
- los pesos de modelo se descargan en primer uso a `AppData`

Por qué:

- evita instaladores gigantes
- permite cambiar `small` por `medium`
- hace más manejable el update del producto

Directorio recomendado:

- `%LOCALAPPDATA%/NodeAV/models/whisper/`

## 11.4 Directorios de ejecución en Windows

Usar:

- Config: `%APPDATA%/NodeAV/`
- Runtime/cache global de app: `%LOCALAPPDATA%/NodeAV/`
- Proyectos: ubicación elegida por el usuario

Nunca escribir dentro de:

- `Program Files`
- directorio de instalación de Tauri

## 11.5 Rutas Unicode

Reglas obligatorias:

1. Toda ruta interna en Python usa `pathlib.Path`.
2. Todo JSON persistido se escribe en UTF-8.
3. Todos los subprocess usan lista de argumentos.
4. No usar shell quoting manual.
5. Normalizar rutas resueltas antes de pasarlas a FFmpeg.

Consideraciones adicionales:

- Python 3.11 ya usa APIs Unicode de Windows.
- Tauri debe declararse `longPathAware` en el manifiesto si se detecta necesidad.
- El backend debe rechazar rutas imposibles de resolver antes de invocar FFmpeg.

## 11.6 Binarios FFmpeg

Decisión:

- FFmpeg se distribuye junto a la app.
- No se depende del PATH del sistema.

Estrategia:

- el backend resuelve rutas internas de `ffmpeg.exe` y `ffprobe.exe`
- se registra explícitamente la versión al iniciar
- si falta el binario, la app entra en estado de error de instalación

## 11.7 Permisos y seguridad operativa

El sidecar solo necesita:

- lectura de proyectos
- lectura de assets
- escritura en carpetas del proyecto
- escritura en `AppData`
- ejecución de sidecars locales

No necesita:

- permisos de administrador
- servicios de Windows
- puertos expuestos públicamente

## 11.8 Estrategia de arranque

1. Tauri inicia.
2. Lanza `backend-sidecar.exe` en localhost.
3. Espera healthcheck.
4. Frontend se conecta.
5. Si backend falla:
   - mostrar error de arranque con logs y ruta de diagnóstico

## 11.9 Portabilidad del proyecto

Regla:

- el proyecto debe abrir en otra máquina si:
  - el `.avproj` está intacto
  - los assets fueron relocados correctamente

Soporte operativo:

- comando `Relocate Missing Assets`
- rebind por `content_sha256` cuando sea posible

---

## 12. Estructura del repositorio

```text
nodeav/
├── apps/
│   └── desktop/
│       ├── src/
│       ├── src-tauri/
│       └── package.json
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── features/
│   │   │   ├── nodes/
│   │   │   ├── assets/
│   │   │   ├── jobs/
│   │   │   └── projects/
│   │   ├── lib/
│   │   └── stores/
│   └── package.json
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── domain/
│   │   ├── infra/
│   │   │   ├── ffmpeg/
│   │   │   ├── assets/
│   │   │   ├── db/
│   │   │   └── ai/
│   │   ├── services/
│   │   └── main.py
│   ├── tests/
│   └── pyproject.toml
├── shared/
│   ├── jsonschema/
│   └── examples/
├── docs/
│   └── blueprint_motor_audiovisual.md
└── scripts/
```

Decisión:

- el backend se organiza por dominio + infraestructura
- los schemas compartidos se generan desde Pydantic y se exportan a JSON Schema

---

## 13. Roadmap realista

## Fase 1: Motor de render estable

### Objetivo

Construir el compositor procedural y el contrato del proyecto.

### Entregables

1. `SceneNode` y `.avproj` v1.0.0
2. `asset_library` con importación y `ffprobe`
3. `render_compiler`
4. `ffmpeg_executor`
5. cache por escena
6. tests automatizados del compositor
7. API mínima para renderizar una escena

### Riesgos

1. filtergraph inestable
2. diferencias entre video e imagen de fondo
3. fuentes y subtítulos en Windows
4. invalidación incorrecta de cache

### Dependencias

- ninguna

### Criterio de éxito

El sistema renderiza de forma determinista una escena con:

- background
- overlay
- texto
- zoom
- subtítulos

## Fase 2: Editor visual

### Objetivo

Exponer el sistema al usuario con edición por nodos y jobs asíncronos.

### Entregables

1. canvas lineal con React Flow
2. panel de propiedades
3. panel de assets
4. cola local de jobs
5. WebSocket de progreso
6. render parcial de escena
7. export final con concatenación

### Riesgos

1. divergencia entre contrato UI y backend
2. UX confusa si el nodo muestra opciones no soportadas por render
3. errores de concurrencia al editar mientras renderiza

### Dependencias

- Fase 1 completa

### Criterio de éxito

El usuario puede crear, editar, reordenar, renderizar y exportar sin usar IA.

## Fase 3: IA narrativa

### Objetivo

Automatizar la creación inicial de escenas desde guion o audio.

### Entregables

1. transcripción local con `faster-whisper`
2. análisis narrativo estructurado
3. `SceneDraft[]`
4. materialización automática a `SceneNode[]`
5. matching de assets por FTS
6. fallback limpio si falla la IA

### Riesgos

1. salida JSON inválida
2. escenas con duraciones pobres
3. sugerencias visuales insuficientes por biblioteca escasa

### Dependencias

- Fase 1 y 2 completas

### Criterio de éxito

Un usuario puede cargar audio o guion y obtener una primera secuencia editable de escenas.

## Fase 4: Automatización avanzada

### Objetivo

Reducir trabajo manual repetitivo sin comprometer control.

### Entregables

1. preasignación más inteligente de overlays
2. presets visuales por rol narrativo
3. rerender por rango
4. historial de variantes por escena
5. mejoras de ranking de assets

### Riesgos

1. exceso de automatización que opaque el control del usuario
2. deuda técnica si entra antes de robustecer el compositor

### Dependencias

- Fases 1, 2 y 3 estables

### Criterio de éxito

La automatización ahorra tiempo real sin degradar previsibilidad.

---

## 14. Prioridades y riesgos reales

## 14.1 Prioridad absoluta

La prioridad absoluta del proyecto es construir un compositor procedural sólido alrededor de `SceneNode`.

Orden real de importancia:

1. `SceneNode` estable
2. `TimelineScene` correcto
3. `FFmpeg` encapsulado y testeado
4. cache confiable
5. editor visual
6. IA narrativa

## 14.2 Lo que NO es el principal riesgo

La IA no es el principal riesgo técnico.

La IA puede fallar y el sistema seguir siendo útil si:

- el editor manual funciona
- el render es estable
- el proyecto persiste bien

## 14.3 Riesgos reales del MVP

### Riesgo 1: Compositor procedural frágil

Impacto: crítico

Mitigación:

- limitar combinatoria del MVP
- tests por caso
- `RenderPlan` validable

### Riesgo 2: Contrato de escena mal definido

Impacto: crítico

Mitigación:

- congelar `SceneNode` v1 antes de UI
- versionado semántico
- migraciones explícitas

### Riesgo 3: Cache incorrecta

Impacto: alto

Mitigación:

- fingerprints deterministas
- manifests por render
- invalidación por cambio de asset y compositor

### Riesgo 4: Empaquetado Windows deficiente

Impacto: alto

Mitigación:

- sidecar congelado
- FFmpeg incluido
- rutas Unicode y logs de arranque

### Riesgo 5: IA con salida inconsistente

Impacto: medio

Mitigación:

- validación Pydantic
- retry único
- fallback manual

## 14.4 Regla de gobierno del proyecto

Ninguna feature nueva entra si no respeta estas condiciones:

1. cabe dentro de `SceneNode` o de un cambio versionado de schema
2. no rompe el compositor existente
3. tiene estrategia de cache
4. tiene comportamiento claro en ausencia de IA

---

## Conclusión operativa

La arquitectura final del MVP queda definida así:

- desktop app con `Tauri`
- frontend `React + TypeScript + React Flow`
- backend `Python + FastAPI`
- jobs locales asíncronos sin Redis
- proyecto en `.avproj`
- catálogo global en `SQLite`
- IA narrativa estructural
- render exclusivamente con `FFmpeg`
- cache canónico en disco por proyecto

La decisión central del producto es inequívoca:

`SceneNode` es la unidad de negocio.

La decisión central de ingeniería también:

`FFmpeg` es el núcleo crítico y debe construirse primero.

Todo lo demás es soporte alrededor de esa realidad.
