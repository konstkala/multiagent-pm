import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import RateLimitedError
from app.core.logging import log_fields
from app.db.models import RateLimitBucket

logger = logging.getLogger(__name__)


async def hit(session: AsyncSession, key: str, limit: int, window: timedelta) -> None:
    """Count one attempt for `key`; raise once the window's limit is passed.

    Commits at once, so a failed sign-in still counts. Old buckets are cleaned up later by a job.
    """
    seconds = int(window.total_seconds())
    start = int(datetime.now(UTC).timestamp()) // seconds * seconds
    statement = (
        insert(RateLimitBucket)
        .values(key=key, window_start=datetime.fromtimestamp(start, UTC), count=1)
        .on_conflict_do_update(
            index_elements=["key", "window_start"],
            set_={"count": RateLimitBucket.count + 1},
        )
        .returning(RateLimitBucket.count)
    )
    count = (await session.execute(statement)).scalar_one()
    await session.commit()
    if count > limit:
        logger.warning("security.rate_limited", extra=log_fields(key=key.split(":")[0]))
        raise RateLimitedError("Too many attempts. Wait a few minutes and try again.")
