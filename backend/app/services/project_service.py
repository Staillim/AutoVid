"""ProjectService — abre, guarda y crea archivos .avproj desde disco."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from pydantic import ValidationError

from app.domain.models import (
    AnalysisMetadata,
    LibraryBinding,
    ProjectModel,
    ProjectSettings,
    SCHEMA_VERSION,
)

if TYPE_CHECKING:
    pass


class ProjectServiceError(Exception):
    """Error base del ProjectService."""


class ProjectNotFoundError(ProjectServiceError):
    """El archivo .avproj no existe en la ruta indicada."""


class ProjectParseError(ProjectServiceError):
    """El archivo existe pero no pudo parsearse como ProjectModel válido."""


class ProjectSaveError(ProjectServiceError):
    """No se pudo guardar el archivo .avproj."""


class ProjectService:
    """Gestiona la persistencia de proyectos en disco como archivos .avproj."""

    # ---------- lectura ----------

    def open(self, path: str | Path) -> ProjectModel:
        """Abre un archivo .avproj desde disco y retorna el ProjectModel validado.

        Raises:
            ProjectNotFoundError: si el archivo no existe.
            ProjectParseError: si el JSON no es válido o no pasa la validación Pydantic.
        """
        file_path = Path(path)
        if not file_path.exists():
            raise ProjectNotFoundError(f"archivo no encontrado: {file_path}")

        try:
            raw = file_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ProjectParseError(f"no se pudo leer el archivo: {exc}") from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProjectParseError(f"JSON inválido en {file_path.name}: {exc}") from exc

        try:
            return ProjectModel.model_validate(data)
        except ValidationError as exc:
            raise ProjectParseError(
                f"el archivo {file_path.name} no cumple el schema del dominio: {exc}"
            ) from exc

    # ---------- escritura ----------

    def save(self, project: ProjectModel, path: str | Path) -> Path:
        """Serializa el ProjectModel y lo escribe en disco.

        Actualiza `updated_at` antes de guardar.

        Returns:
            El Path donde se guardó el archivo.

        Raises:
            ProjectSaveError: si no se pudo escribir el archivo.
        """
        file_path = Path(path)
        updated = project.model_copy(
            update={"updated_at": datetime.now(timezone.utc).isoformat()}
        )
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(
                updated.model_dump_json(indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            raise ProjectSaveError(f"no se pudo guardar en {file_path}: {exc}") from exc
        return file_path

    # ---------- creación ----------

    def create(
        self,
        *,
        name: str,
        library_id: str = "default-local-library",
        settings: ProjectSettings | None = None,
    ) -> ProjectModel:
        """Crea un nuevo ProjectModel en memoria con valores iniciales.

        No escribe a disco. Para persistir, llama a `save()` después.
        """
        now = datetime.now(timezone.utc).isoformat()
        return ProjectModel(
            project_id=str(uuid4()),
            created_at=now,
            updated_at=now,
            name=name,
            settings=settings or ProjectSettings(),
            library_binding=LibraryBinding(library_id=library_id),
            analysis=AnalysisMetadata(source_type="manual"),
            nodes=[],
            scene_order=[],
            notes="",
        )

    # ---------- validación de compatibilidad ----------

    def check_schema_version(self, project: ProjectModel) -> bool:
        """Retorna True si el schema_version del proyecto coincide con el actual."""
        return project.schema_version == SCHEMA_VERSION

    def is_compatible(self, path: str | Path) -> tuple[bool, str]:
        """Verifica si un archivo .avproj es compatible sin cargarlo completamente.

        Returns:
            (True, "") si es compatible.
            (False, motivo) si hay algún problema.
        """
        file_path = Path(path)
        if not file_path.exists():
            return False, f"archivo no encontrado: {file_path}"

        try:
            raw = file_path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            return False, str(exc)

        version = data.get("schema_version", "")
        if not version:
            return False, "schema_version ausente"
        if version != SCHEMA_VERSION:
            return False, f"schema_version {version!r} no compatible con {SCHEMA_VERSION!r}"
        return True, ""
