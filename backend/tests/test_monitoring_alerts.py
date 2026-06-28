from app.db.models import Claim, Company, ResearchReport, Watchlist
from app.services.research_service import ResearchService


def test_monitoring_detects_new_s1_claim() -> None:
    company = Company(id="company-1", name="Example IPO")
    watchlist = Watchlist(id="watch-1", company_id="company-1")
    previous = ResearchReport(id="report-old", company_id="company-1", ipo_readiness_score=40)
    current = ResearchReport(id="report-new", company_id="company-1", ipo_readiness_score=42)
    claim = Claim(
        id="claim-1",
        company_id="company-1",
        text="SEC EFTS full-text search found S-1 filing evidence for Example IPO dated 2026-01-15.",
        category="ipo_readiness",
        value="0001234567-26-000001",
        verification_status="verified",
        confidence_score=1.0,
    )

    alerts = ResearchService().detect_monitoring_alerts(
        company=company,
        watchlist=watchlist,
        report=current,
        previous_report=previous,
        current_claims=[claim],
        previous_claims=[],
    )

    assert len(alerts) == 1
    assert alerts[0].alert_type == "new_ipo_filing"
    assert alerts[0].severity == "high"


def test_monitoring_creates_baseline_without_previous_report() -> None:
    company = Company(id="company-1", name="Example IPO")
    watchlist = Watchlist(id="watch-1", company_id="company-1")
    current = ResearchReport(id="report-new", company_id="company-1", report_status="completed")

    alerts = ResearchService().detect_monitoring_alerts(
        company=company,
        watchlist=watchlist,
        report=current,
        previous_report=None,
        current_claims=[],
        previous_claims=[],
    )

    assert len(alerts) == 1
    assert alerts[0].alert_type == "baseline_created"
