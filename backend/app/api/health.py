from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session, ping

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: Literal["ok"]


@router.get("/health")
async def health() -> Health:
    """Liveness: the process is up. No dependencies, so restarts aren't triggered by a DB blip."""
    return Health(status="ok")


@router.get("/health/db", responses={503: {"description": "Database unreachable"}})
async def health_db(session: Annotated[AsyncSession, Depends(get_session)]) -> Health:
    """Readiness: the app can serve traffic because the DB answers."""
    try:
        await ping(session)
    except (OSError, SQLAlchemyError) as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "database unreachable") from exc
    return Health(status="ok")
