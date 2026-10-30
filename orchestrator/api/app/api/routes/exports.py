from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database.session import get_db_session
from app.schemas.exports import ExportRequest, ExportSchemaRead
from app.services.exports import ExportService, ExportValidationError


router = APIRouter(prefix="/api/exports", tags=["exports"])


def get_export_service(db: Session = Depends(get_db_session)) -> ExportService:
    return ExportService(db)


@router.get("/schema", response_model=ExportSchemaRead)
def get_export_schema() -> ExportSchemaRead:
    return ExportService.schema()


@router.post("/vacancies")
def export_vacancies(
    payload: ExportRequest,
    service: ExportService = Depends(get_export_service),
) -> Response:
    try:
        dataset = service.vacancies_dataset(payload)
        content, media_type = service.render(dataset, payload.format)
        return _download(content, media_type, dataset.filename)
    except ExportValidationError as exc:
        raise HTTPException(status_code=422, detail={"error_code": "invalid_export_columns"}) from exc


@router.post("/applications")
def export_applications(
    payload: ExportRequest,
    service: ExportService = Depends(get_export_service),
) -> Response:
    try:
        dataset = service.applications_dataset(payload)
        content, media_type = service.render(dataset, payload.format)
        return _download(content, media_type, dataset.filename)
    except ExportValidationError as exc:
        raise HTTPException(status_code=422, detail={"error_code": "invalid_export_columns"}) from exc


def _download(content: bytes, media_type: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
