from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base, Company, Watchlist
from app.services.watchlist_schedule import (
    due_watchlist_items,
    mark_watchlist_check_failure,
    next_check_at_for_frequency,
)


def test_daily_next_check_at_calculation() -> None:
    now = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)

    assert next_check_at_for_frequency("daily", now) == now + timedelta(days=1)


def test_weekly_next_check_at_calculation() -> None:
    now = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)

    assert next_check_at_for_frequency("weekly", now) == now + timedelta(days=7)


@pytest.mark.asyncio
async def test_due_watchlist_query_limits_active_due_items(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/watchlist.db")
    Session = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with Session() as db:
        due_items = []
        for index in range(6):
            company = Company(name=f"Due {index}")
            db.add(company)
            await db.flush()
            item = Watchlist(
                company_id=company.id,
                active=True,
                next_check_at=now - timedelta(minutes=index + 1),
            )
            db.add(item)
            due_items.append(item)

        future_company = Company(name="Future")
        inactive_company = Company(name="Inactive")
        db.add_all([future_company, inactive_company])
        await db.flush()
        db.add(
            Watchlist(
                company_id=future_company.id,
                active=True,
                next_check_at=now + timedelta(minutes=30),
            )
        )
        db.add(
            Watchlist(
                company_id=inactive_company.id,
                active=False,
                next_check_at=now - timedelta(minutes=30),
            )
        )
        await db.commit()

        results = await due_watchlist_items(db, now, limit=5, exclude_ids={due_items[-1].id})

    assert len(results) == 5
    assert all(item.active for item in results)
    assert due_items[-1].id not in {item.id for item in results}
    result_times = [item.next_check_at for item in results]
    assert result_times == sorted(result_times)


@pytest.mark.asyncio
async def test_failure_retry_behavior_sets_error_and_retries_in_six_hours(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/retry.db")
    Session = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with Session() as db:
        company = Company(name="Retry Co")
        db.add(company)
        await db.flush()
        watchlist = Watchlist(company_id=company.id, active=True, next_check_at=now)
        db.add(watchlist)
        await db.commit()

        await mark_watchlist_check_failure(db, watchlist.id, "provider timeout", now=now)
        updated = await db.get(Watchlist, watchlist.id)

    assert updated is not None
    assert updated.last_error == "provider timeout"
    assert updated.next_check_at == now + timedelta(hours=6)
