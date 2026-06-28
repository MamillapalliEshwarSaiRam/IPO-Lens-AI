from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ReportStatus
from app.db.database import AsyncSessionLocal
from app.db.models import Company, ResearchReport, Watchlist
from app.schemas import ResearchRequest
from app.services.research_service import research_service


@dataclass(frozen=True)
class WatchlistCheckRun:
    watchlist_id: str
    company_id: str
    report_id: str
    request: ResearchRequest


async def start_watchlist_check(
    db: AsyncSession, watchlist_id: str
) -> WatchlistCheckRun | None:
    result = await db.execute(
        select(Watchlist).where(Watchlist.id == watchlist_id, Watchlist.active.is_(True))
    )
    watchlist = result.scalar_one_or_none()
    if not watchlist:
        return None

    company_result = await db.execute(select(Company).where(Company.id == watchlist.company_id))
    company = company_result.scalar_one_or_none()
    if not company:
        return None

    request = ResearchRequest(
        company_name=company.name,
        prompt=f"Run watchlist monitoring check for {company.name}",
        use_mock_data=False,
    )
    report = await research_service.create_research_run(db, request)
    return WatchlistCheckRun(
        watchlist_id=watchlist.id,
        company_id=company.id,
        report_id=report.id,
        request=request,
    )


async def run_watchlist_check(watchlist_id: str) -> WatchlistCheckRun:
    async with AsyncSessionLocal() as db:
        run = await start_watchlist_check(db, watchlist_id)
        if not run:
            raise ValueError("Watchlist item not found")

    await research_service.run_research_background(run.report_id, run.request)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ResearchReport).where(ResearchReport.id == run.report_id))
        report = result.scalar_one()
        if report.report_status == ReportStatus.FAILED.value:
            raise RuntimeError(report.executive_summary or "Watchlist check failed")

    return run
