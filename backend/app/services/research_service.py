import json
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import ResearchOrchestrator
from app.agents.state import WorkflowResult
from app.core.enums import AgentStatus, ReportStatus
from app.core.logging import get_logger
from app.db.database import AsyncSessionLocal
from app.db.models import (
    AgentRun,
    Claim,
    Company,
    MonitoringAlert,
    ResearchReport,
    Source,
    ToolCall,
    Watchlist,
    utc_now,
)
from app.schemas import ResearchRequest
from app.services.event_bus import event_bus
from app.services.watchlist_schedule import next_check_at_for_frequency

logger = get_logger(__name__)


class ResearchService:
    def __init__(self) -> None:
        self.orchestrator = ResearchOrchestrator()

    async def create_research_run(self, db: AsyncSession, request: ResearchRequest) -> ResearchReport:
        company = await self.get_or_create_company(db, request.company_name)
        report = ResearchReport(
            company_id=company.id,
            report_status=ReportStatus.RUNNING.value,
            executive_summary="Research workflow is running.",
            key_risks=[],
            key_claim_ids=[],
            source_ids=[],
            score_breakdown={},
            sections={},
            unavailable_data=[],
            conflicting_claim_ids=[],
        )
        db.add(report)
        await db.commit()
        await db.refresh(report)
        return report

    async def run_research_background(self, report_id: str, request: ResearchRequest) -> None:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(ResearchReport).where(ResearchReport.id == report_id))
            report = result.scalar_one_or_none()
            if not report:
                logger.error("report_not_found", extra={"report_id": report_id})
                return
            company_result = await db.execute(select(Company).where(Company.id == report.company_id))
            company = company_result.scalar_one()

            async def publish(agent_name, status, summary, metadata=None):
                await event_bus.publish(report_id, agent_name, status, summary, metadata or {})

            try:
                workflow_result = await self.orchestrator.run(
                    company_name=request.company_name,
                    prompt=request.prompt,
                    run_id=report_id,
                    publish=publish,
                    use_mock_data=request.use_mock_data,
                    mock_scenario=request.mock_scenario,
                )
                await self.persist_workflow_result(db, report, company, workflow_result)
                await event_bus.publish(
                    report_id,
                    "System",
                    AgentStatus.COMPLETED,
                    "Research workflow completed.",
                    {"terminal": True, "report_id": report_id},
                )
            except Exception as exc:
                logger.exception("research_workflow_failed", extra={"report_id": report_id})
                report.report_status = ReportStatus.FAILED.value
                report.executive_summary = (
                    "Research workflow failed before a complete report could be generated."
                )
                await db.commit()
                await event_bus.publish(
                    report_id,
                    "System",
                    AgentStatus.FAILED,
                    "Research workflow failed.",
                    {"terminal": True, "error": str(exc), "report_id": report_id},
                )

    async def persist_workflow_result(
        self,
        db: AsyncSession,
        report: ResearchReport,
        company: Company,
        workflow_result: WorkflowResult,
    ) -> ResearchReport:
        company_data = workflow_result.company
        company.website = company_data.get("website")
        company.sector = company_data.get("sector")
        company.is_public = bool(company_data.get("is_public"))
        company.ticker = company_data.get("ticker")
        company.cik = company_data.get("cik")
        company.description = company_data.get("description")

        sources: List[Source] = []
        for source_draft in workflow_result.sources:
            source = Source(
                id=source_draft.source_id,
                company_id=company.id,
                url=source_draft.url,
                title=source_draft.title,
                publisher=source_draft.publisher,
                published_date=parse_datetime(source_draft.published_date),
                source_type=source_draft.source_type.value,
                source_quality_score=source_draft.source_quality_score,
            )
            db.add(source)
            sources.append(source)

        claims: List[Claim] = []
        for claim_draft in workflow_result.claims:
            claim = Claim(
                company_id=company.id,
                text=claim_draft.text,
                category=claim_draft.category.value,
                value=claim_draft.value,
                unit=claim_draft.unit,
                date_context=claim_draft.date_context,
                source_ids=claim_draft.source_ids,
                verification_status=claim_draft.verification_status.value,
                confidence_score=claim_draft.confidence_score,
                evidence_notes=claim_draft.evidence_notes,
            )
            db.add(claim)
            claims.append(claim)

        await db.flush()
        claim_ids = [claim.id for claim in claims]
        source_ids = [source.id for source in sources]
        conflicting_claim_ids = [
            claim.id for claim in claims if claim.verification_status == "conflicting"
        ]

        report_data = workflow_result.report
        report.report_status = report_data["report_status"]
        report.executive_summary = report_data["executive_summary"]
        report.ipo_readiness_score = report_data["ipo_readiness_score"]
        report.confidence_level = report_data["confidence_level"]
        report.bull_case = report_data["bull_case"]
        report.bear_case = report_data["bear_case"]
        report.key_risks = report_data["key_risks"]
        report.key_claim_ids = claim_ids
        report.source_ids = source_ids
        report.score_breakdown = report_data["score_breakdown"]
        report.sections = report_data["sections"]
        report.unavailable_data = report_data["unavailable_data"]
        report.conflicting_claim_ids = conflicting_claim_ids

        await self.create_monitoring_alerts_for_report(db, company, report, claims)

        agent_run_id_by_name: Dict[str, str] = {}
        for run_draft in workflow_result.agent_runs:
            agent_run = AgentRun(
                report_id=report.id,
                agent_name=run_draft.agent_name,
                status=run_draft.status.value,
                started_at=run_draft.started_at,
                completed_at=run_draft.completed_at,
                duration_ms=run_draft.duration_ms,
                input_summary=run_draft.input_summary,
                output_summary=run_draft.output_summary,
                error_message=run_draft.error_message,
                token_estimate=run_draft.token_estimate,
                cost_estimate=run_draft.cost_estimate,
            )
            db.add(agent_run)
            await db.flush()
            agent_run_id_by_name[run_draft.agent_name] = agent_run.id

        for call_draft in workflow_result.tool_calls:
            agent_run_id = agent_run_id_by_name.get(call_draft.agent_name)
            if not agent_run_id:
                continue
            db.add(
                ToolCall(
                    agent_run_id=agent_run_id,
                    tool_name=call_draft.tool_name,
                    provider=call_draft.provider,
                    request_summary=call_draft.request_summary,
                    response_summary=call_draft.response_summary,
                    status=call_draft.status,
                    duration_ms=call_draft.duration_ms,
                    cache_hit=call_draft.cache_hit,
                    error_message=call_draft.error_message,
                )
            )

        await db.commit()
        await db.refresh(report)
        logger.info(
            "research_report_completed",
            extra={
                "report_id": report.id,
                "company_id": company.id,
                "claim_count": len(claims),
                "source_count": len(sources),
            },
        )
        return report

    async def get_or_create_company(self, db: AsyncSession, company_name: str) -> Company:
        normalized = company_name.strip()
        result = await db.execute(select(Company).where(Company.name == normalized))
        company = result.scalar_one_or_none()
        if company:
            return company
        company = Company(name=normalized)
        db.add(company)
        await db.commit()
        await db.refresh(company)
        return company

    async def get_report_detail(self, db: AsyncSession, report_id: str) -> Optional[Dict[str, object]]:
        report_result = await db.execute(select(ResearchReport).where(ResearchReport.id == report_id))
        report = report_result.scalar_one_or_none()
        if not report:
            return None
        company_result = await db.execute(select(Company).where(Company.id == report.company_id))
        company = company_result.scalar_one()
        claims_result = await db.execute(select(Claim).where(Claim.company_id == company.id))
        claims = list(claims_result.scalars().all())
        claim_ids = set(report.key_claim_ids or [])
        if claim_ids:
            claims = [claim for claim in claims if claim.id in claim_ids]
        sources_result = await db.execute(select(Source).where(Source.company_id == company.id))
        sources = list(sources_result.scalars().all())
        source_ids = set(report.source_ids or [])
        if source_ids:
            sources = [source for source in sources if source.id in source_ids]
        runs_result = await db.execute(select(AgentRun).where(AgentRun.report_id == report.id))
        agent_runs = list(runs_result.scalars().all())
        return {
            "report": report,
            "company": company,
            "claims": claims,
            "sources": sources,
            "agent_runs": agent_runs,
        }

    async def create_watchlist_item(
        self, db: AsyncSession, company_name: str, frequency: str
    ) -> Watchlist:
        company = await self.get_or_create_company(db, company_name)
        result = await db.execute(
            select(Watchlist).where(Watchlist.company_id == company.id, Watchlist.active.is_(True))
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        item = Watchlist(company_id=company.id, frequency=frequency, active=True)
        db.add(item)
        await db.commit()
        await db.refresh(item)
        return item

    async def run_watchlist_check(self, db: AsyncSession, company_id: str) -> Optional[ResearchReport]:
        result = await db.execute(
            select(Watchlist).where(Watchlist.company_id == company_id, Watchlist.active.is_(True))
        )
        watchlist = result.scalar_one_or_none()
        if not watchlist:
            return None

        from app.services.watchlist_checks import start_watchlist_check

        run = await start_watchlist_check(db, watchlist.id)
        if not run:
            return None
        return await db.get(ResearchReport, run.report_id)

    async def create_monitoring_alerts_for_report(
        self,
        db: AsyncSession,
        company: Company,
        report: ResearchReport,
        current_claims: List[Claim],
    ) -> None:
        result = await db.execute(
            select(Watchlist).where(Watchlist.company_id == company.id, Watchlist.active.is_(True))
        )
        watchlist = result.scalar_one_or_none()
        if not watchlist:
            return

        previous_report_id = watchlist.last_report_id
        if previous_report_id == report.id:
            return

        previous_claims: List[Claim] = []
        previous_report = None
        if previous_report_id:
            previous_report_result = await db.execute(
                select(ResearchReport).where(ResearchReport.id == previous_report_id)
            )
            previous_report = previous_report_result.scalar_one_or_none()
            if previous_report:
                previous_claims = await self.claims_for_report(db, previous_report)

        alerts = self.detect_monitoring_alerts(
            company=company,
            watchlist=watchlist,
            report=report,
            previous_report=previous_report,
            current_claims=current_claims,
            previous_claims=previous_claims,
        )
        for alert in alerts:
            db.add(alert)

        checked_at = utc_now()
        watchlist.last_checked_at = checked_at
        watchlist.next_check_at = next_check_at_for_frequency(watchlist.frequency, checked_at)
        watchlist.last_report_id = report.id
        watchlist.last_error = None

    async def claims_for_report(self, db: AsyncSession, report: ResearchReport) -> List[Claim]:
        if not report.key_claim_ids:
            return []
        result = await db.execute(select(Claim).where(Claim.id.in_(report.key_claim_ids)))
        return list(result.scalars().all())

    def detect_monitoring_alerts(
        self,
        company: Company,
        watchlist: Watchlist,
        report: ResearchReport,
        previous_report: Optional[ResearchReport],
        current_claims: List[Claim],
        previous_claims: List[Claim],
    ) -> List[MonitoringAlert]:
        if not previous_report:
            return [
                self.monitoring_alert(
                    company,
                    watchlist,
                    report,
                    previous_report_id=None,
                    alert_type="baseline_created",
                    severity="low",
                    title=f"Baseline created for {company.name}",
                    description="Future watchlist checks will compare new evidence against this report.",
                    claim_ids=[],
                    metadata={"report_status": report.report_status},
                )
            ]

        alerts: List[MonitoringAlert] = []
        previous_texts = {normalize_claim_text(claim.text) for claim in previous_claims}
        new_claims = [
            claim for claim in current_claims if normalize_claim_text(claim.text) not in previous_texts
        ]

        registration_claims = [
            claim
            for claim in new_claims
            if claim.category == "ipo_readiness"
            and claim.verification_status == "verified"
            and any(form in claim.text.lower() for form in ["s-1", "f-1"])
            and str(claim.value).lower() != "not publicly available"
        ]
        if registration_claims:
            alerts.append(
                self.monitoring_alert(
                    company,
                    watchlist,
                    report,
                    previous_report.id,
                    "new_ipo_filing",
                    "high",
                    f"New IPO filing evidence for {company.name}",
                    registration_claims[0].text,
                    [claim.id for claim in registration_claims],
                    {"claim_count": len(registration_claims)},
                )
            )

        funding_or_valuation_claims = [
            claim
            for claim in new_claims
            if claim.category in {"funding", "valuation"}
            and claim.verification_status in {"verified", "estimated", "conflicting"}
        ]
        if funding_or_valuation_claims:
            alerts.append(
                self.monitoring_alert(
                    company,
                    watchlist,
                    report,
                    previous_report.id,
                    "funding_or_valuation_change",
                    "medium",
                    f"New funding or valuation signal for {company.name}",
                    funding_or_valuation_claims[0].text,
                    [claim.id for claim in funding_or_valuation_claims],
                    {"claim_count": len(funding_or_valuation_claims)},
                )
            )

        risk_claims = [
            claim
            for claim in new_claims
            if claim.category == "risk"
            and claim.verification_status in {"verified", "estimated", "conflicting"}
        ]
        if risk_claims:
            alerts.append(
                self.monitoring_alert(
                    company,
                    watchlist,
                    report,
                    previous_report.id,
                    "risk_event",
                    "medium",
                    f"New risk signal for {company.name}",
                    risk_claims[0].text,
                    [claim.id for claim in risk_claims],
                    {"claim_count": len(risk_claims)},
                )
            )

        conflicting_claims = [
            claim for claim in new_claims if claim.verification_status == "conflicting"
        ]
        if conflicting_claims:
            alerts.append(
                self.monitoring_alert(
                    company,
                    watchlist,
                    report,
                    previous_report.id,
                    "new_conflict",
                    "medium",
                    f"New conflicting evidence for {company.name}",
                    conflicting_claims[0].text,
                    [claim.id for claim in conflicting_claims],
                    {"claim_count": len(conflicting_claims)},
                )
            )

        score_delta = score_change(previous_report.ipo_readiness_score, report.ipo_readiness_score)
        if score_delta is not None and abs(score_delta) >= 10:
            direction = "increased" if score_delta > 0 else "decreased"
            alerts.append(
                self.monitoring_alert(
                    company,
                    watchlist,
                    report,
                    previous_report.id,
                    "score_change",
                    "medium",
                    f"IPO readiness score {direction} for {company.name}",
                    f"Score changed by {score_delta:+d} points since the previous watchlist report.",
                    [],
                    {
                        "previous_score": previous_report.ipo_readiness_score,
                        "current_score": report.ipo_readiness_score,
                        "delta": score_delta,
                    },
                )
            )

        return alerts

    def monitoring_alert(
        self,
        company: Company,
        watchlist: Watchlist,
        report: ResearchReport,
        previous_report_id: Optional[str],
        alert_type: str,
        severity: str,
        title: str,
        description: str,
        claim_ids: List[str],
        metadata: Dict[str, object],
    ) -> MonitoringAlert:
        return MonitoringAlert(
            company_id=company.id,
            watchlist_id=watchlist.id,
            report_id=report.id,
            previous_report_id=previous_report_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            description=description,
            claim_ids=claim_ids,
            alert_metadata=metadata,
        )


def parse_datetime(value: Optional[str]):
    if not value:
        return None
    try:
        return datetime_from_iso(value)
    except ValueError:
        return None


def datetime_from_iso(value: str):
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    from datetime import datetime

    return datetime.fromisoformat(value)


def normalize_claim_text(value: str) -> str:
    return " ".join(value.lower().split())


def score_change(previous: Optional[int], current: Optional[int]) -> Optional[int]:
    if previous is None or current is None:
        return None
    return current - previous


def sse_payload(event) -> str:
    return "event: progress\ndata: " + json.dumps(event.model_dump(mode="json")) + "\n\n"


research_service = ResearchService()
