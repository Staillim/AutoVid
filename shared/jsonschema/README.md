# JSON Schema — NodeAV

Schemas JSON generados automáticamente desde los modelos Pydantic del dominio.

Generados con: `python backend/scripts/export_schemas.py`

## Schemas disponibles

| Archivo | Modelo origen | Descripción |
|---|---|---|
| `project.json` | `ProjectModel` | Contrato completo del archivo `.avproj` |
| `scene_node.json` | `SceneNode` | Nodo de escena editable (contrato central del dominio) |
| `timeline_scene.json` | `TimelineScene` | Escena compilada lista para render (generada, no persistida) |
| `render_plan.json` | `RenderPlan` | Plan de render con inputs, etapas y outputs esperados |
| `render_job_record.json` | `RenderJobRecord` | Registro de un job de render con su estado y resultado |
| `runtime_health_report.json` | `RuntimeHealthReport` | Reporte de readiness del entorno (FFmpeg, dirs, binarios) |

## Uso

Estos schemas pueden usarse para:

- Validar archivos `.avproj` con herramientas externas
- Generar clientes TypeScript con `json-schema-to-typescript`
- Documentar la API del dominio sin depender del código Python

## Regenerar

```powershell
cd backend
python scripts\export_schemas.py
```
