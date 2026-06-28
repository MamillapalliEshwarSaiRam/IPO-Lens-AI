from typing import Dict

import pytest

from app.agents.orchestrator import ResearchOrchestrator
from app.agents.state import SourceDraft, ToolCallDraft
from app.core.enums import AgentStatus, VerificationStatus
from app.providers.base import ProviderResponse
from app.providers.sec_edgar import parse_company_search_atom


@pytest.mark.asyncio
async def test_mocked_anthropic_full_run() -> None:
    events = []

    async def publish(
        agent_name: str,
        status: AgentStatus,
        summary: str,
        metadata: Dict[str, object] | None = None,
    ):
        events.append((agent_name, status, summary, metadata))

    result = await ResearchOrchestrator().run(
        company_name="Anthropic",
        prompt="Analyze Anthropic IPO readiness",
        run_id="run-1",
        publish=publish,
        use_mock_data=True,
    )

    assert result.report["ipo_readiness_score"] <= 65
    assert any(claim.verification_status == VerificationStatus.CONFLICTING for claim in result.claims)
    assert any("Report Writer Agent" == event[0] for event in events)


@pytest.mark.asyncio
async def test_news_failure_still_completes() -> None:
    async def publish(agent_name: str, status: AgentStatus, summary: str, metadata: Dict[str, object]):
        return None

    result = await ResearchOrchestrator().run(
        company_name="Anthropic",
        prompt="Analyze Anthropic IPO readiness",
        run_id="run-2",
        publish=publish,
        use_mock_data=True,
        mock_scenario="news_failure",
    )
    assert result.report["report_status"] == "completed"
    assert any(run.error_message for run in result.agent_runs)


@pytest.mark.asyncio
async def test_private_company_financials_are_unavailable() -> None:
    async def publish(agent_name: str, status: AgentStatus, summary: str, metadata: Dict[str, object]):
        return None

    result = await ResearchOrchestrator().run(
        company_name="SpaceX",
        prompt="Analyze SpaceX IPO readiness",
        run_id="run-3",
        publish=publish,
        use_mock_data=True,
        mock_scenario="private_unavailable",
    )
    financial_claims = [claim for claim in result.claims if claim.category.value == "financial"]
    assert financial_claims
    assert all(
        claim.verification_status == VerificationStatus.NOT_PUBLICLY_AVAILABLE
        for claim in financial_claims
    )


def test_public_company_reference_report_has_no_ipo_score() -> None:
    orchestrator = ResearchOrchestrator()
    report = {
        "report_status": "completed",
        "executive_summary": "Prior IPO readiness report.",
        "ipo_readiness_score": 60,
        "confidence_level": "Medium",
        "bull_case": "Prior bull case.",
        "bear_case": "Prior bear case.",
        "key_risks": [],
        "score_breakdown": {"total": 60},
        "sections": {"unavailable_data": []},
        "unavailable_data": [],
    }

    updated = orchestrator._public_company_reference_report(
        "Alphabet Inc.",
        {"is_public": True, "ticker": "GOOGL"},
        [],
        report,
    )

    assert updated["ipo_readiness_score"] is None
    assert updated["score_breakdown"]["not_applicable"] is True
    assert updated["score_breakdown"]["report_type"] == "public_company_reference_analysis"
    assert "already public" in updated["executive_summary"]


def test_sec_company_search_atom_parser_extracts_cik() -> None:
    atom = """
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <title>Example IPO Holdings Inc.</title>
        <link href="https://www.sec.gov/cgi-bin/browse-edgar?CIK=1234567"/>
        <company-info>
          <cik>1234567</cik>
        </company-info>
      </entry>
    </feed>
    """

    results = parse_company_search_atom(atom)

    assert results == [
        {
            "title": "Example IPO Holdings Inc.",
            "cik": "0001234567",
            "url": "https://www.sec.gov/cgi-bin/browse-edgar?CIK=1234567",
        }
    ]


def test_extract_full_text_hits_from_efts_payload() -> None:
    payload = {
        "hits": {
            "hits": [
                {
                    "_source": {
                        "csa_names": ["Example IPO Holdings Inc."],
                        "form": "S-1",
                        "root_form": "S-1",
                        "file_date": "2026-01-15",
                        "adsh": "0001234567-26-000001",
                    }
                }
            ]
        }
    }

    hits = ResearchOrchestrator()._extract_full_text_hits(payload)

    assert hits == [
        {
            "company_name": "Example IPO Holdings Inc.",
            "form": "S-1",
            "root_form": "S-1",
            "file_date": "2026-01-15",
            "filed_at": None,
            "accession_number": "0001234567-26-000001",
        }
    ]


@pytest.mark.asyncio
async def test_identity_resolution_prefers_sec_company_search_before_ticker_mapping(monkeypatch) -> None:
    calls = []

    async def fake_company_search(company_name: str) -> ProviderResponse:
        calls.append("company_search")
        return ProviderResponse(
            provider="sec_edgar",
            data={"results": [{"title": "Example IPO Holdings Inc.", "cik": "0001234567"}]},
            source_url="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany",
        )

    async def fake_find_cik(company_name: str) -> ProviderResponse:
        calls.append("find_cik")
        return ProviderResponse(
            provider="sec_edgar",
            data={"cik": None, "ticker": None, "title": None},
            source_url="https://www.sec.gov/files/company_tickers.json",
        )

    monkeypatch.setattr("app.agents.orchestrator.sec_edgar_client.company_search", fake_company_search)
    monkeypatch.setattr("app.agents.orchestrator.sec_edgar_client.find_cik", fake_find_cik)

    events = []

    async def publish(
        agent_name: str,
        status: AgentStatus,
        summary: str,
        metadata: Dict[str, object] | None = None,
    ):
        events.append((agent_name, status, summary, metadata))

    sources: list[SourceDraft] = []
    tool_calls: list[ToolCallDraft] = []
    agent_runs = []

    context = await ResearchOrchestrator()._resolve_live_identity(
        "Example IPO",
        sources,
        publish,
        agent_runs,
        tool_calls,
    )

    assert calls == ["company_search", "find_cik"]
    assert context["cik"] == "0001234567"
    assert context["ticker"] is None
    assert context["ticker_status"] == "unavailable"
    assert context["ipo_status"] == "confidential_or_unavailable"
    assert context["identity_output"]["claims"]
    assert any(event[0] == "Identity Resolution Agent" for event in events)
