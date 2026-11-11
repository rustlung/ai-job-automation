from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.routes.web import require_internal_token
from app.database.session import get_db_session
from app.services.run_diagnostics import RunDiagnosticsNotFoundError, RunDiagnosticsService

router = APIRouter(prefix="/internal/diagnostics", tags=["internal diagnostics"])


@router.get("/runs/{run_id}", dependencies=[Depends(require_internal_token)])
def get_run_diagnostics(run_id: str, db: Session = Depends(get_db_session)) -> dict:
    try:
        return RunDiagnosticsService(db).get(run_id)
    except RunDiagnosticsNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error_code": "run_not_found"}) from exc


@router.get("/runs", dependencies=[Depends(require_internal_token)])
def get_recent_run_diagnostics(limit: int = Query(default=10, ge=1, le=50), db: Session = Depends(get_db_session)) -> dict:
    return {"runs": RunDiagnosticsService(db).recent(limit)}
