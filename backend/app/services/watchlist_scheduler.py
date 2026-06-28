import asyncio
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.logging import get_logger
from app.db.database import AsyncSessionLocal
from app.db.models import Watchlist
from app.services.watchlist_checks import run_watchlist_check
from app.services.watchlist_schedule import (
    SCHEDULER_BATCH_SIZE,
    due_watchlist_items,
    mark_watchlist_check_failure,
    mark_watchlist_check_success,
)

logger = get_logger(__name__)


class WatchlistSchedulerService:
    def __init__(self) -> None:
        self.scheduler: AsyncIOScheduler | None = None
        self.running_watchlist_ids: set[str] = set()
        self._tasks: set[asyncio.Task[None]] = set()

    def start(self) -> None:
        if self.scheduler and self.scheduler.running:
            return

        self.scheduler = AsyncIOScheduler(timezone=UTC)
        self.scheduler.add_job(
            self.run_due_checks,
            "interval",
            minutes=30,
            id="watchlist_monitoring",
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.start()
        logger.info("watchlist_scheduler_started")

    async def stop(self) -> None:
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("watchlist_scheduler_stopped")
        if self._tasks:
            for task in self._tasks:
                task.cancel()
            await asyncio.gather(*self._tasks, return_exceptions=True)

    async def run_due_checks(self) -> None:
        now = datetime.now(UTC)
        async with AsyncSessionLocal() as db:
            watchlist_items = await due_watchlist_items(
                db,
                now,
                limit=SCHEDULER_BATCH_SIZE,
                exclude_ids=self.running_watchlist_ids,
            )

        for watchlist in watchlist_items:
            if watchlist.id in self.running_watchlist_ids:
                continue
            self.running_watchlist_ids.add(watchlist.id)
            task = asyncio.create_task(self._run_one(watchlist.id))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def _run_one(self, watchlist_id: str) -> None:
        try:
            await run_watchlist_check(watchlist_id)
            await self._mark_success(watchlist_id)
            logger.info("watchlist_check_completed", extra={"watchlist_id": watchlist_id})
        except Exception as exc:
            logger.exception("watchlist_check_failed", extra={"watchlist_id": watchlist_id})
            async with AsyncSessionLocal() as db:
                await mark_watchlist_check_failure(db, watchlist_id, str(exc))
        finally:
            self.running_watchlist_ids.discard(watchlist_id)

    async def _mark_success(self, watchlist_id: str) -> None:
        async with AsyncSessionLocal() as db:
            watchlist = await db.get(Watchlist, watchlist_id)
            if not watchlist:
                return
            await mark_watchlist_check_success(db, watchlist)
            await db.commit()


watchlist_scheduler = WatchlistSchedulerService()
