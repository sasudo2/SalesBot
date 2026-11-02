import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.schemas import HealthResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse)
def health_endpoint(response: Response, db: Annotated[Session, Depends(get_db)]) -> HealthResponse:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database health check failed")
        response.status_code = 503
        return HealthResponse(status="degraded", db=False)
    return HealthResponse(status="ok", db=True)
