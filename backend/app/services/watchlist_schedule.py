from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Watchlist

SCHEDULER_BATCH_SIZE = 5
FAILURE_RETRY_DELAY = timedelta(hours=6)


def ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def next_check_at_for_frequency(frequency: str, now: datetime) -> datetime:
    normalized_now = ensure_aware_utc(now)
    if frequency == "daily":
        return normalized_now + timedelta(days=1)
    return normalized_now + timedelta(days=7)


def retry_check_at(now: datetime) -> datetime:
    return ensure_aware_utc(now) + FAILURE_RETRY_DELAY


async def due_watchlist_items(
    db: AsyncSession,
    now: datetime,
    *,
    limit: int = SCHEDULER_BATCH_SIZE,
    exclude_ids: Iterable[str] | None = None,
) -> list[Watchlist]:
    excluded: set[str] = set(exclude_ids or [])
    query: Select[tuple[Watchlist]] = (
        select(Watchlist)
        .where(
            Watchlist.active.is_(True),
            Watchlist.next_check_at.is_not(None),
            Watchlist.next_check_at <= ensure_aware_utc(now),
        )
        .order_by(Watchlist.next_check_at.asc(), Watchlist.created_at.asc())
        .limit(limit)
    )
    if excluded:
        query = query.where(Watchlist.id.not_in(excluded))

    result = await db.execute(query)
    return list(result.scalars().all())


async def mark_watchlist_check_success(
    db: AsyncSession, watchlist: Watchlist, *, now: datetime | None = None
) -> None:
    checked_at = ensure_aware_utc(now or datetime.now(UTC))
    watchlist.last_checked_at = checked_at
    watchlist.next_check_at = next_check_at_for_frequency(watchlist.frequency, checked_at)
    watchlist.last_error = None


async def mark_watchlist_check_failure(
    db: AsyncSession, watchlist_id: str, error_message: str, *, now: datetime | None = None
) -> None:
    result = await db.execute(select(Watchlist).where(Watchlist.id == watchlist_id))
    watchlist = result.scalar_one_or_none()
    if not watchlist:
        return

    failed_at = ensure_aware_utc(now or datetime.now(UTC))
    watchlist.last_error = error_message[:2000]
    watchlist.next_check_at = retry_check_at(failed_at)
    await db.commit()
