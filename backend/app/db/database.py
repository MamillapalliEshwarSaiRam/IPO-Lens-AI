from typing import AsyncGenerator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.models import Base

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(ensure_watchlist_schema)


def ensure_watchlist_schema(sync_conn) -> None:
    inspector = inspect(sync_conn)
    table_names = inspector.get_table_names()
    if "watchlist" not in table_names:
        return

    columns = {column["name"] for column in inspector.get_columns("watchlist")}
    if "next_check_at" not in columns:
        sync_conn.execute(text("ALTER TABLE watchlist ADD COLUMN next_check_at DATETIME"))
        sync_conn.execute(
            text(
                """
                UPDATE watchlist
                SET next_check_at = COALESCE(last_checked_at, created_at, CURRENT_TIMESTAMP)
                WHERE next_check_at IS NULL
                """
            )
        )
    if "last_error" not in columns:
        sync_conn.execute(text("ALTER TABLE watchlist ADD COLUMN last_error TEXT"))
    sync_conn.execute(
        text("CREATE INDEX IF NOT EXISTS ix_watchlist_next_check_at ON watchlist (next_check_at)")
    )


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
