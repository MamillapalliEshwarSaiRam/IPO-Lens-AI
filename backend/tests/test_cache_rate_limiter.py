import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base
from app.services.cache import cache_service, make_cache_key
from app.services.rate_limiter import RateLimiter


def test_rate_limiter_blocks_after_limit() -> None:
    limiter = RateLimiter(max_calls=2, window_seconds=60)
    assert limiter.allow("newsapi")
    assert limiter.allow("newsapi")
    assert not limiter.allow("newsapi")


@pytest.mark.asyncio
async def test_cache_set_and_get(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/cache.db")
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    key = make_cache_key("mock", {"company": "Anthropic"})
    async with Session() as db:
        assert await cache_service.get(db, key) is None
        await cache_service.set(db, key, "mock", {"ok": True}, ttl_seconds=60)
        cached = await cache_service.get(db, key)
        assert cached == {"ok": True}

