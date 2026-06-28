import asyncio
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import Select, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import LANGGRAPH_AVAILABLE
from app.agents.tool_registry import tool_policy_as_dict
from app.core.config import get_settings
from app.core.enums import ReportStatus
from app.db.database import get_session
from app.db.models import Claim, Company, MonitoringAlert, ResearchReport, Source, Watchlist
from app.schemas import (
    AgentToolPolicyResponse,
    ClaimRead,
    CompanyRead,
    HealthResponse,
    MonitoringAlertRead,
    ReportDetail,
    ResearchRequest,
    ResearchStartResponse,
    SourceRead,
    WatchlistCreate,
    WatchlistRead,
)
from app.services.event_bus import event_bus
from app.services.research_service import research_service, sse_payload
from app.services.watchlist_checks import start_watchlist_check

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(db: AsyncSession = Depends(get_session)) -> HealthResponse:
    settings = get_settings()
    try:
        await db.execute(text("select 1"))
        database = "ok"
    except Exception:
        database = "error"
    return HealthResponse(
        status="ok" if database == "ok" else "degraded",
        database=database,
        providers={
            "sec_edgar": "configured" if settings.sec_user_agent else "missing_user_agent",
            "alpha_vantage": "configured" if settings.alpha_vantage_api_key else "missing_key",
            "finnhub": "configured" if settings.finnhub_api_key else "missing_key",
            "newsapi": "configured" if settings.news_api_key else "missing_key",
            "llm_compatible": "configured" if settings.llm_api_key else "missing_key",
        },
        langgraph_available=LANGGRAPH_AVAILABLE,
    )


@router.get("/agents/tools", response_model=AgentToolPolicyResponse)
async def get_agent_tool_policy() -> AgentToolPolicyResponse:
    return AgentToolPolicyResponse(agents=tool_policy_as_dict())


@router.post("/research", response_model=ResearchStartResponse, status_code=202)
async def start_research(
    request: ResearchRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
) -> ResearchStartResponse:
    report = await research_service.create_research_run(db, request)
    background_tasks.add_task(research_service.run_research_background, report.id, request)
    return ResearchStartResponse(
        run_id=report.id,
        report_id=report.id,
        status=ReportStatus.RUNNING,
        message="Research run started. Subscribe to the events endpoint for progress.",
    )


@router.get("/research/{run_id}/events")
async def research_events(run_id: str) -> StreamingResponse:
    async def event_stream():
        async for event in event_bus.subscribe(run_id):
            yield sse_payload(event)
            await asyncio.sleep(0)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/reports", response_model=List[ReportDetail])
async def list_reports(db: AsyncSession = Depends(get_session)) -> List[ReportDetail]:
    result = await db.execute(
        select(ResearchReport).order_by(ResearchReport.created_at.desc()).limit(10)
    )
    reports = list(result.scalars().all())
    details = []
    for report in reports:
        detail = await research_service.get_report_detail(db, report.id)
        if detail:
            details.append(ReportDetail(**detail))
    return details


@router.get("/reports/{report_id}", response_model=ReportDetail)
async def get_report(report_id: str, db: AsyncSession = Depends(get_session)) -> ReportDetail:
    detail = await research_service.get_report_detail(db, report_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Report not found")
    return ReportDetail(**detail)


@router.get("/reports/{report_id}/claims", response_model=List[ClaimRead])
async def get_report_claims(report_id: str, db: AsyncSession = Depends(get_session)) -> List[ClaimRead]:
    detail = await research_service.get_report_detail(db, report_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Report not found")
    return [ClaimRead.model_validate(claim) for claim in detail["claims"]]


@router.get("/reports/{report_id}/sources", response_model=List[SourceRead])
async def get_report_sources(report_id: str, db: AsyncSession = Depends(get_session)) -> List[SourceRead]:
    detail = await research_service.get_report_detail(db, report_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Report not found")
    return [SourceRead.model_validate(source) for source in detail["sources"]]


@router.post("/watchlist", response_model=WatchlistRead, status_code=201)
async def create_watchlist_item(
    payload: WatchlistCreate,
    db: AsyncSession = Depends(get_session),
) -> WatchlistRead:
    item = await research_service.create_watchlist_item(db, payload.company_name, payload.frequency)
    company = await get_company(db, item.company_id)
    return watchlist_read(item, company)


@router.get("/watchlist", response_model=List[WatchlistRead])
async def list_watchlist(db: AsyncSession = Depends(get_session)) -> List[WatchlistRead]:
    result = await db.execute(select(Watchlist).where(Watchlist.active.is_(True)))
    items = list(result.scalars().all())
    response = []
    for item in items:
        company = await get_company(db, item.company_id)
        response.append(watchlist_read(item, company))
    return response


@router.get("/monitoring-alerts", response_model=List[MonitoringAlertRead])
async def list_monitoring_alerts(db: AsyncSession = Depends(get_session)) -> List[MonitoringAlertRead]:
    result = await db.execute(
        select(MonitoringAlert).order_by(MonitoringAlert.created_at.desc()).limit(25)
    )
    alerts = list(result.scalars().all())
    response = []
    for alert in alerts:
        company = await get_company(db, alert.company_id)
        alert_read = MonitoringAlertRead.model_validate(alert)
        alert_read.company = CompanyRead.model_validate(company)
        response.append(alert_read)
    return response


@router.delete("/watchlist/{company_id}", status_code=204)
async def delete_watchlist_item(company_id: str, db: AsyncSession = Depends(get_session)) -> None:
    result = await db.execute(
        select(Watchlist).where(Watchlist.company_id == company_id, Watchlist.active.is_(True))
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    item.active = False
    await db.commit()


@router.post("/watchlist/{company_id}/run-check", response_model=ResearchStartResponse, status_code=202)
async def run_watchlist_check(
    company_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
) -> ResearchStartResponse:
    result = await db.execute(
        select(Watchlist).where(Watchlist.company_id == company_id, Watchlist.active.is_(True))
    )
    watchlist = result.scalar_one_or_none()
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist item not found")

    run = await start_watchlist_check(db, watchlist.id)
    if not run:
        raise HTTPException(status_code=404, detail="Company not found")

    background_tasks.add_task(research_service.run_research_background, run.report_id, run.request)
    return ResearchStartResponse(
        run_id=run.report_id,
        report_id=run.report_id,
        status=ReportStatus.RUNNING,
        message="Manual watchlist check started.",
    )


async def get_company(db: AsyncSession, company_id: str) -> Company:
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


def watchlist_read(item: Watchlist, company: Company) -> WatchlistRead:
    return WatchlistRead(
        id=item.id,
        company_id=item.company_id,
        company=company,
        created_at=item.created_at,
        frequency=item.frequency,
        last_checked_at=item.last_checked_at,
        next_check_at=item.next_check_at,
        last_report_id=item.last_report_id,
        last_error=item.last_error,
        active=item.active,
    )
