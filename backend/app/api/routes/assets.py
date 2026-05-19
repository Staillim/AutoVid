from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.domain.models import AssetRecord, AssetKind
from app.runtime import asset_library
from app.services.asset_library import AssetImportError, AssetNotFoundError

router = APIRouter(prefix="/assets", tags=["assets"])

class ImportAssetRequest(BaseModel):
    absolute_path: str

@router.get("", response_model=List[AssetRecord])
def list_assets(
    kind: Optional[str] = Query(None, description="Filtrar por tipo de asset (ej: video, image, audio)"),
    q: Optional[str] = Query(None, description="Término de búsqueda parcial en el path")
) -> List[AssetRecord]:
    if q:
        return asset_library.search(q)
    
    asset_kind = None
    if kind:
        try:
            asset_kind = AssetKind(kind)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Tipo de asset inválido: {kind}")
            
    return asset_library.list(kind=asset_kind)

@router.get("/{asset_id}", response_model=AssetRecord)
def get_asset(asset_id: str) -> AssetRecord:
    try:
        return asset_library.get(asset_id)
    except AssetNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/import", response_model=AssetRecord)
def import_asset(request: ImportAssetRequest) -> AssetRecord:
    try:
        return asset_library.import_asset(request.absolute_path)
    except AssetImportError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al importar: {str(e)}")

@router.delete("/{asset_id}", status_code=204)
def delete_asset(asset_id: str):
    removed = asset_library.remove(asset_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Asset no encontrado")
    return None
