import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

from app.agents.conflicts import conflicting_claims, detect_conflicts
from app.agents.scoring import calculate_ipo_score, confidence_from_score_and_claims
from app.agents.state import AgentRunDraft, ClaimDraft, SourceDraft, ToolCallDraft, WorkflowResult
from app.agents.tool_registry import allowed_tools_for_agent, is_tool_allowed
from app.agents.verification import verify_claims
from app.core.config import get_settings
from app.core.enums import AgentStatus, ClaimCategory, SourceType, VerificationStatus
from app.data.mock_data import get_agent_outputs, get_mock_company, get_mock_sources
from app.providers.alpha_vantage import alpha_vantage_client
from app.providers.finnhub import finnhub_client
from app.providers.newsapi import newsapi_client
from app.providers.sec_edgar import sec_edgar_client

try:
    from langgraph.graph import END, StateGraph

    LANGGRAPH_AVAILABLE = True
except Exception:  # pragma: no cover - depends on optional runtime dependency at import time
    END = None
    StateGraph = None
    LANGGRAPH_AVAILABLE = False


ProgressPublisher = Callable[[str, AgentStatus, str, Dict[str, object]], Awaitable[None]]


class ResearchOrchestrator:
    def __init__(self) -> None:
        self.settings = get_settings()

    def build_graph(self) -> Optional[Any]:
        if not LANGGRAPH_AVAILABLE:
            return None
        graph = StateGraph(dict)
        graph.add_node("plan", lambda state: state)
        graph.add_node("identity_resolution", lambda state: state)
        graph.add_node("data_gathering", lambda state: state)
        graph.add_node("claim_extraction", lambda state: state)
        graph.add_node("verification", lambda state: state)
        graph.add_node("conflict_detection", lambda state: state)
        graph.add_node("scoring", lambda state: state)
        graph.add_node("report_writer", lambda state: state)
        graph.set_entry_point("plan")
        graph.add_edge("plan", "identity_resolution")
        graph.add_edge("identity_resolution", "data_gathering")
        graph.add_edge("data_gathering", "claim_extraction")
        graph.add_edge("claim_extraction", "verification")
        graph.add_edge("verification", "conflict_detection")
        graph.add_edge("conflict_detection", "scoring")
        graph.add_edge("scoring", "report_writer")
        graph.add_edge("report_writer", END)
        return graph.compile()

    def plan_agents(self, prompt: str) -> List[str]:
        lowered = prompt.lower()
        if "only" in lowered and "filing" in lowered:
            return ["SEC Filing Agent"]
        if "compare" in lowered:
            return [
                "Company Profile Agent",
                "SEC Filing Agent",
                "Financial Signals Agent",
                "Market & Competitor Agent",
                "Risk Agent",
            ]
        return [
            "Company Profile Agent",
            "SEC Filing Agent",
            "Financial Signals Agent",
            "Market & Competitor Agent",
            "Risk Agent",
        ]

    async def run(
        self,
        company_name: str,
        prompt: Optional[str],
        run_id: str,
        publish: ProgressPublisher,
        use_mock_data: bool = False,
        mock_scenario: Optional[str] = None,
    ) -> WorkflowResult:
        workflow_steps = 0
        agent_runs: List[AgentRunDraft] = []
        tool_calls: List[ToolCallDraft] = []

        async def publish_event(
            agent_name: str,
            status: AgentStatus,
            summary: str,
            metadata: Dict[str, object] = None,
        ) -> None:
            await publish(agent_name, status, summary, metadata or {})

        await publish_event(
            "Orchestrator Agent",
            AgentStatus.RUNNING,
            "Planning workflow and selecting agents based on the prompt.",
            {"model_route": "cheap_for_planning"},
        )
        start = datetime.now(timezone.utc)
        selected_agents = self.plan_agents(prompt or f"Analyze {company_name} IPO readiness")
        workflow_steps += 1
        agent_runs.append(
            AgentRunDraft(
                agent_name="Orchestrator Agent",
                status=AgentStatus.COMPLETED,
                started_at=start,
                completed_at=datetime.now(timezone.utc),
                duration_ms=elapsed_ms(start),
                input_summary=prompt or company_name,
                output_summary=f"Selected agents: {', '.join(selected_agents)}",
                token_estimate=180,
                cost_estimate=0.0001,
            )
        )
        await publish_event(
            "Orchestrator Agent",
            AgentStatus.COMPLETED,
            f"Selected {len(selected_agents)} data-gathering agents.",
            {"selected_agents": selected_agents, "langgraph_available": LANGGRAPH_AVAILABLE},
        )

        if workflow_steps >= self.settings.max_workflow_steps:
            raise RuntimeError("Workflow step limit exceeded before data gathering.")

        if use_mock_data or mock_scenario:
            company_data, sources, source_ids_by_index, gathered_outputs = await self._gather_mock_data(
                company_name=company_name,
                selected_agents=selected_agents,
                mock_scenario=mock_scenario,
                publish=publish_event,
                agent_runs=agent_runs,
                tool_calls=tool_calls,
            )
        else:
            company_data, sources, source_ids_by_index, gathered_outputs = await self._gather_live_data(
                company_name=company_name,
                selected_agents=selected_agents,
                publish=publish_event,
                agent_runs=agent_runs,
                tool_calls=tool_calls,
            )
        workflow_steps += len(gathered_outputs)

        raw_claims: List[Dict[str, Any]] = []
        for output in gathered_outputs:
            raw_claims.extend(output.get("claims", []))

        claims = await self._claim_extraction(
            company_name,
            raw_claims,
            source_ids_by_index,
            publish_event,
            agent_runs,
            tool_calls,
        )
        workflow_steps += 1
        claims = await self._verification(company_name, claims, sources, publish_event, agent_runs, tool_calls)
        workflow_steps += 1
        claims = await self._conflicts(company_name, claims, publish_event, agent_runs, tool_calls)
        workflow_steps += 1
        score = await self._scoring(company_name, claims, publish_event, agent_runs, tool_calls)
        workflow_steps += 1
        report = await self._report_writer(
            company_name,
            claims,
            score,
            publish_event,
            agent_runs,
            tool_calls,
        )
        workflow_steps += 1

        if workflow_steps > self.settings.max_workflow_steps:
            report["report_status"] = "partial"
            report["executive_summary"] += " Workflow step limit reached; report completed as partial."

        if company_data.get("is_public"):
            report = self._public_company_reference_report(company_name, company_data, claims, report)

        return WorkflowResult(
            company=company_data,
            sources=sources,
            claims=claims,
            report=report,
            agent_runs=agent_runs,
            tool_calls=tool_calls,
        )

    async def _gather_mock_data(
        self,
        company_name: str,
        selected_agents: List[str],
        mock_scenario: Optional[str],
        publish: ProgressPublisher,
        agent_runs: List[AgentRunDraft],
        tool_calls: List[ToolCallDraft],
    ) -> tuple[Dict[str, Any], List[SourceDraft], Dict[int, str], List[Dict[str, Any]]]:
        sources = [
            SourceDraft(
                source_id=str(uuid.uuid4()),
                url=source["url"],
                title=source["title"],
                publisher=source["publisher"],
                source_type=source["source_type"],
                source_quality_score=source["source_quality_score"],
                published_date=source.get("published_date"),
            )
            for source in get_mock_sources(company_name)
        ]
        source_ids_by_index = {index: source.source_id for index, source in enumerate(sources)}
        agent_outputs = get_agent_outputs(company_name)

        async def run_data_agent(agent_name: str) -> Dict[str, Any]:
            agent_start = datetime.now(timezone.utc)
            await publish(agent_name, AgentStatus.RUNNING, f"{agent_name} is gathering fixture evidence.")
            await asyncio.sleep(0.05)
            output = agent_outputs.get(agent_name, {"summary": f"{agent_name} skipped.", "claims": []})
            status = AgentStatus.COMPLETED
            error_message = None

            if mock_scenario == "news_failure" and agent_name == "Financial Signals Agent":
                output = {
                    "summary": "NewsAPI failed; continuing with SEC and official-source evidence only.",
                    "claims": [
                        {
                            "text": f"{company_name} revenue is not publicly available in official filings.",
                            "category": ClaimCategory.FINANCIAL,
                            "source_indexes": [1 if len(sources) > 1 else 0],
                            "value": "Not publicly available",
                            "date_context": "Provider failure fallback",
                        }
                    ],
                }
                error_message = "NewsAPI unavailable in mocked failure scenario."

            if mock_scenario == "private_unavailable" and agent_name == "Financial Signals Agent":
                output = {
                    "summary": "Private-company financials unavailable from reliable sources.",
                    "claims": [
                        {
                            "text": f"{company_name} revenue is not publicly available from reliable public sources.",
                            "category": ClaimCategory.FINANCIAL,
                            "source_indexes": [0],
                            "value": "Not publicly available",
                            "date_context": "Private-company fallback",
                        },
                        {
                            "text": f"{company_name} profitability is not publicly available from reliable public sources.",
                            "category": ClaimCategory.FINANCIAL,
                            "source_indexes": [0],
                            "value": "Not publicly available",
                            "date_context": "Private-company fallback",
                        },
                    ],
                }

            agent_runs.append(
                AgentRunDraft(
                    agent_name=agent_name,
                    status=status,
                    started_at=agent_start,
                    completed_at=datetime.now(timezone.utc),
                    duration_ms=elapsed_ms(agent_start),
                    input_summary=f"Fixture research for {company_name}",
                    output_summary=output["summary"],
                    error_message=error_message,
                    token_estimate=260,
                    cost_estimate=0.0002,
                )
            )
            tool_calls.append(
                ToolCallDraft(
                    agent_name=agent_name,
                    tool_name="fixture_provider_lookup",
                    provider="fixture",
                    request_summary=f"{agent_name} fixture lookup for {company_name}",
                    response_summary=output["summary"],
                    status="completed" if not error_message else "degraded",
                    duration_ms=elapsed_ms(agent_start),
                    cache_hit=True,
                    error_message=error_message,
                )
            )
            await publish(
                agent_name,
                status,
                output["summary"],
                {"degraded": bool(error_message), "claim_count": len(output.get("claims", []))},
            )
            return output

        outputs = await asyncio.gather(*[run_data_agent(agent) for agent in selected_agents])
        return get_mock_company(company_name), sources, source_ids_by_index, outputs

    async def _gather_live_data(
        self,
        company_name: str,
        selected_agents: List[str],
        publish: ProgressPublisher,
        agent_runs: List[AgentRunDraft],
        tool_calls: List[ToolCallDraft],
    ) -> tuple[Dict[str, Any], List[SourceDraft], Dict[int, str], List[Dict[str, Any]]]:
        sources: List[SourceDraft] = []
        context = await self._resolve_live_identity(
            company_name,
            sources,
            publish,
            agent_runs,
            tool_calls,
        )
        context["provider_cache"] = {}
        identity_output = context.pop("identity_output")

        async def run_live_agent(agent_name: str) -> Dict[str, Any]:
            agent_start = datetime.now(timezone.utc)
            await publish(
                agent_name,
                AgentStatus.RUNNING,
                f"{agent_name} is querying live providers.",
                {"allowed_tools": self._allowed_tool_metadata(agent_name)},
            )
            error_message = None
            try:
                output = await asyncio.wait_for(
                    self._execute_live_agent(agent_name, company_name, context, sources, tool_calls),
                    timeout=self.settings.agent_timeout_seconds,
                )
            except asyncio.TimeoutError:
                error_message = (
                    f"{agent_name} timed out after {self.settings.agent_timeout_seconds} seconds."
                )
                output = {
                    "summary": f"{agent_name} timed out; continuing with degraded confidence.",
                    "claims": [],
                }
            except Exception as exc:
                error_message = str(exc)
                output = {
                    "summary": f"{agent_name} failed; continuing with degraded confidence.",
                    "claims": [],
                }

            status = AgentStatus.COMPLETED
            agent_runs.append(
                AgentRunDraft(
                    agent_name=agent_name,
                    status=status,
                    started_at=agent_start,
                    completed_at=datetime.now(timezone.utc),
                    duration_ms=elapsed_ms(agent_start),
                    input_summary=f"Live research for {company_name}",
                    output_summary=output["summary"],
                    error_message=error_message,
                    token_estimate=0,
                    cost_estimate=0.0,
                )
            )
            await publish(
                agent_name,
                status,
                output["summary"],
                {"degraded": bool(error_message), "claim_count": len(output.get("claims", []))},
            )
            return output

        outputs = await asyncio.gather(*[run_live_agent(agent) for agent in selected_agents])
        return context["company"], sources, {}, [identity_output, *outputs]

    async def _execute_live_agent(
        self,
        agent_name: str,
        company_name: str,
        context: Dict[str, Any],
        sources: List[SourceDraft],
        tool_calls: List[ToolCallDraft],
    ) -> Dict[str, Any]:
        if agent_name == "Company Profile Agent":
            return await self._live_company_profile(company_name, context, sources, tool_calls)
        if agent_name == "SEC Filing Agent":
            return await self._live_sec_filings(company_name, context, sources, tool_calls)
        if agent_name == "Financial Signals Agent":
            return await self._live_financial_signals(company_name, context, sources, tool_calls)
        if agent_name == "Market & Competitor Agent":
            return await self._live_market(company_name, context, sources, tool_calls)
        if agent_name == "Risk Agent":
            return await self._live_risks(company_name, context, sources, tool_calls)
        return {"summary": f"{agent_name} skipped.", "claims": []}

    async def _resolve_live_identity(
        self,
        company_name: str,
        sources: List[SourceDraft],
        publish: ProgressPublisher,
        agent_runs: List[AgentRunDraft],
        tool_calls: List[ToolCallDraft],
    ) -> Dict[str, Any]:
        start = datetime.now(timezone.utc)
        await publish(
            "Identity Resolution Agent",
            AgentStatus.RUNNING,
            "Resolving company identity from SEC company search before ticker mapping.",
            {"allowed_tools": self._allowed_tool_metadata("Identity Resolution Agent")},
        )

        search_response = await sec_edgar_client.company_search(company_name)
        search_source_id = self._add_source(
            sources,
            search_response.source_url or "https://www.sec.gov/cgi-bin/browse-edgar",
            "SEC EDGAR company-name search",
            "U.S. Securities and Exchange Commission",
            SourceType.SEC_FILING,
            1.0,
        )
        self._record_tool_call(
            tool_calls,
            "Identity Resolution Agent",
            "company_search",
            search_response.provider,
            f"Search SEC EDGAR companies for {company_name}",
            "SEC company search returned results"
            if search_response.data.get("results")
            else "No SEC company search match",
            start,
            error=search_response.error,
        )

        search_results = search_response.data.get("results", [])
        best_search_match = self._best_company_search_match(company_name, search_results)
        search_cik = best_search_match.get("cik") if best_search_match else None
        search_title = best_search_match.get("title") if best_search_match else None

        ticker_start = datetime.now(timezone.utc)
        ticker_response = await sec_edgar_client.find_cik(company_name)
        ticker_source_id = self._add_source(
            sources,
            ticker_response.source_url or "https://www.sec.gov/files/company_tickers.json",
            "SEC company tickers mapping",
            "U.S. Securities and Exchange Commission",
            SourceType.SEC_FILING,
            0.95,
        )
        self._record_tool_call(
            tool_calls,
            "Identity Resolution Agent",
            "company_tickers_mapping",
            ticker_response.provider,
            f"Check SEC ticker mapping for {company_name}",
            "Ticker mapping returned a candidate"
            if ticker_response.data.get("cik")
            else "No ticker mapping candidate",
            ticker_start,
            error=ticker_response.error,
        )

        ticker_cik = ticker_response.data.get("cik")
        ticker = ticker_response.data.get("ticker")
        ticker_title = ticker_response.data.get("title")
        cik = search_cik or ticker_cik
        title = search_title or ticker_title or company_name
        ticker_is_confirmed = bool(ticker and ticker_cik and (not search_cik or ticker_cik == search_cik))
        ticker_status = "confirmed" if ticker_is_confirmed else "unavailable"
        if ticker_is_confirmed:
            ipo_status = "public"
        elif cik:
            ipo_status = "confidential_or_unavailable"
        else:
            ipo_status = "no_public_filing_found"

        claims: List[Dict[str, Any]] = []
        if search_cik:
            claims.append(
                {
                    "text": f"SEC EDGAR company search matched {company_name} to {title} with CIK {search_cik}.",
                    "category": ClaimCategory.COMPANY_PROFILE,
                    "source_ids": [search_source_id],
                    "value": search_cik,
                    "date_context": "Current SEC EDGAR company search",
                }
            )
        else:
            claims.append(
                {
                    "text": f"No SEC EDGAR company-search CIK was found for {company_name}.",
                    "category": ClaimCategory.COMPANY_PROFILE,
                    "source_ids": [search_source_id],
                    "value": "Not publicly available",
                    "date_context": "Current SEC EDGAR company search",
                }
            )

        if ticker_is_confirmed:
            claims.append(
                {
                    "text": f"SEC ticker mapping associates {title} with ticker {ticker}.",
                    "category": ClaimCategory.COMPANY_PROFILE,
                    "source_ids": [ticker_source_id],
                    "value": ticker,
                    "date_context": "Current SEC ticker mapping",
                }
            )
        else:
            claims.append(
                {
                    "text": f"No confirmed trading ticker was found for {company_name} in SEC ticker mapping.",
                    "category": ClaimCategory.IPO_READINESS,
                    "source_ids": [ticker_source_id],
                    "value": "Not publicly available",
                    "date_context": "Current SEC ticker mapping",
                }
            )

        claims.append(
            {
                "text": f"{company_name} IPO identity status is {ipo_status}; ticker status is {ticker_status}.",
                "category": ClaimCategory.IPO_READINESS,
                "source_ids": [search_source_id, ticker_source_id],
                "value": ipo_status,
                "date_context": "Identity resolution stage",
            }
        )

        agent_runs.append(
            AgentRunDraft(
                agent_name="Identity Resolution Agent",
                status=AgentStatus.COMPLETED,
                started_at=start,
                completed_at=datetime.now(timezone.utc),
                duration_ms=elapsed_ms(start),
                input_summary=f"Resolve SEC identity for {company_name}",
                output_summary=(
                    f"Resolved CIK={cik or 'unavailable'}, ticker={ticker or 'unavailable'}, "
                    f"ipo_status={ipo_status}."
                ),
                error_message=search_response.error or ticker_response.error,
                token_estimate=120,
                cost_estimate=0.0001,
            )
        )
        await publish(
            "Identity Resolution Agent",
            AgentStatus.COMPLETED,
            (
                f"Identity resolved: CIK {cik or 'not publicly available'}, "
                f"ticker {ticker or 'not publicly available'}."
            ),
            {
                "cik": cik,
                "ticker": ticker,
                "ticker_status": ticker_status,
                "ipo_status": ipo_status,
                "claim_count": len(claims),
                "degraded": bool(search_response.error or ticker_response.error),
            },
        )

        return {
            "company": {
                "name": title,
                "website": None,
                "sector": None,
                "is_public": ticker_is_confirmed,
                "ticker": ticker if ticker_is_confirmed else None,
                "cik": cik,
                "description": None,
            },
            "sec_lookup_source_id": search_source_id,
            "sec_company_search_source_id": search_source_id,
            "sec_ticker_source_id": ticker_source_id,
            "ticker": ticker if ticker_is_confirmed else None,
            "cik": cik,
            "ticker_status": ticker_status,
            "ipo_status": ipo_status,
            "identity_output": {
                "summary": f"Identity resolution completed with IPO status {ipo_status}.",
                "claims": claims,
            },
        }

    async def _live_company_profile(
        self,
        company_name: str,
        context: Dict[str, Any],
        sources: List[SourceDraft],
        tool_calls: List[ToolCallDraft],
    ) -> Dict[str, Any]:
        claims: List[Dict[str, Any]] = []
        ticker = context.get("ticker")
        sec_source_id = context["sec_lookup_source_id"]
        company = context["company"]
        if ticker:
            claims.append(
                {
                    "text": f"{company['name']} is associated with ticker {ticker} in SEC company ticker data.",
                    "category": ClaimCategory.COMPANY_PROFILE,
                    "source_ids": [sec_source_id],
                    "value": ticker,
                    "date_context": "Current SEC company ticker lookup",
                }
            )
            finnhub_source_id, finnhub_data = await self._call_finnhub_profile(
                "Company Profile Agent", ticker, context["provider_cache"], sources, tool_calls
            )
            if finnhub_data:
                if finnhub_data.get("weburl"):
                    company["website"] = finnhub_data.get("weburl")
                    claims.append(
                        {
                            "text": f"Finnhub lists {company['name']}'s company website as {finnhub_data['weburl']}.",
                            "category": ClaimCategory.COMPANY_PROFILE,
                            "source_ids": [finnhub_source_id],
                            "value": finnhub_data["weburl"],
                            "date_context": "Current Finnhub company profile",
                        }
                    )
                if finnhub_data.get("finnhubIndustry"):
                    company["sector"] = finnhub_data.get("finnhubIndustry")
                    claims.append(
                        {
                            "text": f"Finnhub classifies {company['name']} in the {finnhub_data['finnhubIndustry']} industry.",
                            "category": ClaimCategory.COMPANY_PROFILE,
                            "source_ids": [finnhub_source_id],
                            "value": finnhub_data["finnhubIndustry"],
                            "date_context": "Current Finnhub company profile",
                        }
                    )
            alpha_source_id, alpha_data = await self._call_alpha_overview(
                "Company Profile Agent", ticker, context["provider_cache"], sources, tool_calls
            )
            if alpha_data:
                if alpha_data.get("Description"):
                    company["description"] = alpha_data["Description"]
                    claims.append(
                        {
                            "text": f"Alpha Vantage describes {company['name']} as: {alpha_data['Description'][:240]}",
                            "category": ClaimCategory.COMPANY_PROFILE,
                            "source_ids": [alpha_source_id],
                            "value": "Public-company overview",
                            "date_context": "Current Alpha Vantage company overview",
                        }
                    )
                if alpha_data.get("Sector") and not company.get("sector"):
                    company["sector"] = alpha_data["Sector"]
        else:
            claims.append(
                {
                    "text": f"No public-company ticker was found for {company_name} in SEC company ticker data.",
                    "category": ClaimCategory.COMPANY_PROFILE,
                    "source_ids": [sec_source_id],
                    "value": "Not publicly available",
                    "date_context": "Current SEC company ticker lookup",
                }
            )
        return {
            "summary": f"Live company profile gathered with {len(claims)} claim(s).",
            "claims": claims,
        }

    async def _live_sec_filings(
        self,
        company_name: str,
        context: Dict[str, Any],
        sources: List[SourceDraft],
        tool_calls: List[ToolCallDraft],
    ) -> Dict[str, Any]:
        cik = context.get("cik")
        sec_source_id = context["sec_lookup_source_id"]
        claims: List[Dict[str, Any]] = []
        ipo_forms = ["S-1", "S-1/A", "F-1", "F-1/A"]
        full_text_start = datetime.now(timezone.utc)
        full_text_response = await sec_edgar_client.full_text_search(
            f'"{company_name}"',
            forms=ipo_forms,
            size=10,
        )
        full_text_source_id = self._add_source(
            sources,
            full_text_response.source_url or "https://efts.sec.gov/LATEST/search-index",
            f"SEC EFTS full-text search for {company_name} IPO registration forms",
            "U.S. Securities and Exchange Commission",
            SourceType.SEC_FILING,
            1.0,
        )
        full_text_hits = self._extract_full_text_hits(full_text_response.data)
        self._record_tool_call(
            tool_calls,
            "SEC Filing Agent",
            "full_text_search",
            full_text_response.provider,
            f"Search SEC EFTS for {company_name} in {', '.join(ipo_forms)}",
            f"{len(full_text_hits)} IPO registration search hit(s)"
            if not full_text_response.error
            else "SEC EFTS full-text search failed",
            full_text_start,
            error=full_text_response.error,
        )
        for hit in full_text_hits[:5]:
            form = hit.get("form") or hit.get("root_form") or "registration form"
            filed = hit.get("file_date") or hit.get("filed_at") or "unknown filing date"
            filer = hit.get("company_name") or company_name
            claims.append(
                {
                    "text": f"SEC EFTS full-text search found {form} filing evidence for {filer} dated {filed}.",
                    "category": ClaimCategory.IPO_READINESS,
                    "source_ids": [full_text_source_id],
                    "value": str(hit.get("accession_number") or form),
                    "date_context": str(filed),
                }
            )
        if not full_text_hits and not full_text_response.error:
            claims.append(
                {
                    "text": f"No S-1/F-1 registration filing was found for {company_name} in SEC EFTS full-text search.",
                    "category": ClaimCategory.IPO_READINESS,
                    "source_ids": [full_text_source_id],
                    "value": "Not publicly available",
                    "date_context": "Current SEC EFTS full-text search",
                }
            )

        if not cik:
            return {
                "summary": (
                    f"SEC EFTS checked for IPO forms; no public-company CIK was found. "
                    f"{len(full_text_hits)} full-text hit(s) were returned."
                ),
                "claims": [
                    *claims,
                    {
                        "text": f"{company_name} SEC IPO filings are not publicly available because no public-company CIK was found in SEC ticker data.",
                        "category": ClaimCategory.IPO_READINESS,
                        "source_ids": [sec_source_id],
                        "value": "Not publicly available",
                        "date_context": "Current SEC company ticker lookup",
                    }
                ],
            }

        start = datetime.now(timezone.utc)
        response = await sec_edgar_client.submissions(cik)
        source_id = self._add_source(
            sources,
            response.source_url or f"https://data.sec.gov/submissions/CIK{cik}.json",
            f"SEC submissions for CIK {cik}",
            "U.S. Securities and Exchange Commission",
            SourceType.SEC_FILING,
            1.0,
        )
        self._record_tool_call(
            tool_calls,
            "SEC Filing Agent",
            "submissions",
            response.provider,
            f"Fetch SEC submissions for CIK {cik}",
            "Submissions fetched" if not response.error else "Submissions fetch failed",
            start,
            error=response.error,
        )
        if response.error:
            return {
                "summary": "SEC submissions fetch failed; continuing with degraded confidence.",
                "claims": claims,
            }
        recent = response.data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        registration_filing = next(
            (filing for form in ipo_forms if (filing := self._latest_form(recent, form))),
            None,
        )
        if registration_filing:
            form = registration_filing["form"]
            claims.append(
                {
                    "text": f"{company_name} has an SEC {form} filing dated {registration_filing['filing_date']}.",
                    "category": ClaimCategory.IPO_READINESS,
                    "source_ids": [source_id],
                    "value": registration_filing["accession_number"],
                    "date_context": registration_filing["filing_date"],
                }
            )
        else:
            claims.append(
                {
                    "text": f"No S-1/F-1 registration statement was found in {company_name}'s latest SEC submissions.",
                    "category": ClaimCategory.IPO_READINESS,
                    "source_ids": [source_id],
                    "value": "Not publicly available",
                    "date_context": "Latest SEC submissions",
                }
            )
        for form in ["10-K", "10-Q", "8-K"]:
            filing = self._latest_form(recent, form)
            if filing:
                claims.append(
                    {
                        "text": f"{company_name}'s latest {form} filing in SEC submissions is dated {filing['filing_date']}.",
                        "category": ClaimCategory.IPO_READINESS,
                        "source_ids": [source_id],
                        "value": filing["accession_number"],
                        "date_context": filing["filing_date"],
                    }
                )
        return {
            "summary": (
                f"SEC EFTS and submissions checked; {len(full_text_hits)} IPO full-text hit(s) and "
                f"{len(forms)} recent filing entries were available."
            ),
            "claims": claims,
        }

    async def _live_financial_signals(
        self,
        company_name: str,
        context: Dict[str, Any],
        sources: List[SourceDraft],
        tool_calls: List[ToolCallDraft],
    ) -> Dict[str, Any]:
        claims: List[Dict[str, Any]] = []
        cik = context.get("cik")
        ticker = context.get("ticker")
        sec_source_id = context["sec_lookup_source_id"]
        if cik:
            start = datetime.now(timezone.utc)
            response = await sec_edgar_client.company_facts(cik)
            facts_source_id = self._add_source(
                sources,
                response.source_url or f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
                f"SEC company facts for CIK {cik}",
                "U.S. Securities and Exchange Commission",
                SourceType.SEC_FILING,
                1.0,
            )
            self._record_tool_call(
                tool_calls,
                "Financial Signals Agent",
                "company_facts",
                response.provider,
                f"Fetch SEC company facts for CIK {cik}",
                "Company facts fetched" if not response.error else "Company facts fetch failed",
                start,
                error=response.error,
            )
            revenue = self._latest_company_fact(
                response.data,
                [
                    "RevenueFromContractWithCustomerExcludingAssessedTax",
                    "Revenues",
                    "SalesRevenueNet",
                ],
            )
            if revenue:
                claims.append(
                    {
                        "text": f"SEC company facts include a latest revenue fact of {revenue['value']} {revenue['unit']} for period ending {revenue['end']}.",
                        "category": ClaimCategory.FINANCIAL,
                        "source_ids": [facts_source_id],
                        "value": str(revenue["value"]),
                        "unit": revenue["unit"],
                        "date_context": revenue["end"],
                    }
                )
            else:
                claims.append(
                    {
                        "text": f"{company_name} revenue is not publicly available in the checked SEC company facts.",
                        "category": ClaimCategory.FINANCIAL,
                        "source_ids": [facts_source_id],
                        "value": "Not publicly available",
                        "unit": "USD",
                        "date_context": "Current SEC company facts",
                    }
                )
        else:
            claims.extend(
                [
                    {
                        "text": f"{company_name} revenue is not publicly available from official SEC filings.",
                        "category": ClaimCategory.FINANCIAL,
                        "source_ids": [sec_source_id],
                        "value": "Not publicly available",
                        "unit": "USD",
                        "date_context": "Current SEC company ticker lookup",
                    },
                    {
                        "text": f"{company_name} profitability is not publicly available from official SEC filings.",
                        "category": ClaimCategory.FINANCIAL,
                        "source_ids": [sec_source_id],
                        "value": "Not publicly available",
                        "unit": "USD",
                        "date_context": "Current SEC company ticker lookup",
                    },
                ]
            )

        if ticker:
            alpha_source_id, alpha_data = await self._call_alpha_overview(
                "Financial Signals Agent", ticker, context["provider_cache"], sources, tool_calls
            )
            for field, label, unit, category in [
                ("MarketCapitalization", "market capitalization", "USD", ClaimCategory.VALUATION),
                ("RevenueTTM", "trailing twelve-month revenue", "USD", ClaimCategory.FINANCIAL),
                ("ProfitMargin", "profit margin", "ratio", ClaimCategory.FINANCIAL),
            ]:
                value = alpha_data.get(field) if alpha_data else None
                if value and value not in {"None", "-", "0"}:
                    claims.append(
                        {
                            "text": f"Alpha Vantage reports {company_name}'s {label} as {value}.",
                            "category": category,
                            "source_ids": [alpha_source_id],
                            "value": str(value),
                            "unit": unit,
                            "date_context": "Current Alpha Vantage company overview",
                        }
                    )
        return {
            "summary": f"Live financial signals gathered with {len(claims)} claim(s).",
            "claims": claims,
        }

    async def _live_market(
        self,
        company_name: str,
        context: Dict[str, Any],
        sources: List[SourceDraft],
        tool_calls: List[ToolCallDraft],
    ) -> Dict[str, Any]:
        claims: List[Dict[str, Any]] = []
        ticker = context.get("ticker")
        if ticker:
            finnhub_source_id, finnhub_data = await self._call_finnhub_profile(
                "Market & Competitor Agent", ticker, context["provider_cache"], sources, tool_calls
            )
            if finnhub_data and finnhub_data.get("finnhubIndustry"):
                claims.append(
                    {
                        "text": f"Finnhub industry data places {company_name} in {finnhub_data['finnhubIndustry']}.",
                        "category": ClaimCategory.MARKET,
                        "source_ids": [finnhub_source_id],
                        "value": finnhub_data["finnhubIndustry"],
                        "date_context": "Current Finnhub company profile",
                    }
                )
        articles, article_source_ids, error = await self._news_search(
            "Market & Competitor Agent", company_name, context["provider_cache"], sources, tool_calls
        )
        if article_source_ids:
            claims.append(
                {
                    "text": f"NewsAPI discovered {len(articles)} recent article(s) for {company_name}; these are discovery signals, not final verified facts.",
                    "category": ClaimCategory.MARKET,
                    "source_ids": article_source_ids[:5],
                    "value": str(len(articles)),
                    "date_context": "Current NewsAPI discovery search",
                }
            )
            for article in articles[:5]:
                title = article.get("title") or ""
                lowered = title.lower()
                if any(word in lowered for word in ["ipo", "funding", "valuation"]):
                    claims.append(
                        {
                            "text": f"News discovery surfaced reported IPO/funding/valuation context for {company_name}: {title}",
                            "category": ClaimCategory.IPO_READINESS,
                            "source_ids": [article["_source_id"]],
                            "value": "Reported, unverified",
                            "date_context": article.get("publishedAt") or "Current NewsAPI discovery search",
                        }
                    )
        elif error:
            claims.append(
                {
                    "text": f"News discovery for {company_name} failed; market news signals are not publicly available from the configured NewsAPI call.",
                    "category": ClaimCategory.MARKET,
                    "source_ids": [],
                    "value": "Not publicly available",
                    "date_context": "Current NewsAPI discovery search",
                }
            )
        return {
            "summary": f"Live market and competitor signals gathered with {len(claims)} claim(s).",
            "claims": claims,
        }

    async def _live_risks(
        self,
        company_name: str,
        context: Dict[str, Any],
        sources: List[SourceDraft],
        tool_calls: List[ToolCallDraft],
    ) -> Dict[str, Any]:
        claims: List[Dict[str, Any]] = []
        articles, _, error = await self._news_search(
            "Risk Agent", company_name, context["provider_cache"], sources, tool_calls
        )
        risk_keywords = ["lawsuit", "regulator", "regulatory", "probe", "investigation", "antitrust", "sec"]
        risk_articles = [
            article
            for article in articles
            if any(
                keyword in f"{article.get('title', '')} {article.get('description', '')}".lower()
                for keyword in risk_keywords
            )
        ]
        for article in risk_articles[:5]:
            claims.append(
                {
                    "text": f"News discovery surfaced potential risk context for {company_name}: {article.get('title')}",
                    "category": ClaimCategory.RISK,
                    "source_ids": [article["_source_id"]],
                    "value": "Reported, unverified",
                    "date_context": article.get("publishedAt") or "Current NewsAPI discovery search",
                }
            )
        if not risk_articles:
            claims.append(
                {
                    "text": f"Specific company risk events for {company_name} were not publicly available in the configured live news discovery results.",
                    "category": ClaimCategory.RISK,
                    "source_ids": [],
                    "value": "Not publicly available",
                    "date_context": "Current NewsAPI discovery search" if not error else "NewsAPI unavailable",
                }
            )
        return {
            "summary": f"Live risk signals gathered with {len(claims)} claim(s).",
            "claims": claims,
        }

    async def _call_finnhub_profile(
        self,
        agent_name: str,
        ticker: str,
        cache: Dict[str, Any],
        sources: List[SourceDraft],
        tool_calls: List[ToolCallDraft],
    ) -> tuple[str, Dict[str, Any]]:
        cache_key = f"finnhub_profile:{ticker}"
        if cache_key in cache:
            source_id, data = cache[cache_key]
            self._record_tool_call(
                tool_calls,
                agent_name,
                "company_profile",
                "finnhub",
                f"Fetch Finnhub profile for {ticker}",
                "Profile reused from workflow cache",
                datetime.now(timezone.utc),
                cache_hit=True,
            )
            return source_id, data
        start = datetime.now(timezone.utc)
        task_key = f"task:{cache_key}"
        reused_inflight = False
        if task_key in cache:
            reused_inflight = True
            response = await cache[task_key]
        else:
            cache[task_key] = asyncio.create_task(finnhub_client.company_profile(ticker))
            response = await cache[task_key]
            cache.pop(task_key, None)
        source_id = self._add_source(
            sources,
            response.source_url or "https://finnhub.io/api/v1/stock/profile2",
            f"Finnhub company profile for {ticker}",
            "Finnhub",
            SourceType.ANALYST_REPORT,
            0.68,
        )
        self._record_tool_call(
            tool_calls,
            agent_name,
            "company_profile",
            response.provider,
            f"Fetch Finnhub profile for {ticker}",
            "Profile fetched" if response.data else "Profile unavailable",
            start,
            error=response.error,
            cache_hit=reused_inflight,
        )
        data = response.data if not response.error else {}
        cache[cache_key] = (source_id, data)
        return source_id, data

    async def _call_alpha_overview(
        self,
        agent_name: str,
        ticker: str,
        cache: Dict[str, Any],
        sources: List[SourceDraft],
        tool_calls: List[ToolCallDraft],
    ) -> tuple[str, Dict[str, Any]]:
        cache_key = f"alpha_overview:{ticker}"
        if cache_key in cache:
            source_id, data = cache[cache_key]
            self._record_tool_call(
                tool_calls,
                agent_name,
                "company_overview",
                "alpha_vantage",
                f"Fetch Alpha Vantage overview for {ticker}",
                "Overview reused from workflow cache",
                datetime.now(timezone.utc),
                cache_hit=True,
            )
            return source_id, data
        start = datetime.now(timezone.utc)
        task_key = f"task:{cache_key}"
        reused_inflight = False
        if task_key in cache:
            reused_inflight = True
            response = await cache[task_key]
        else:
            cache[task_key] = asyncio.create_task(alpha_vantage_client.company_overview(ticker))
            response = await cache[task_key]
            cache.pop(task_key, None)
        source_id = self._add_source(
            sources,
            response.source_url or "https://www.alphavantage.co/query?function=OVERVIEW",
            f"Alpha Vantage company overview for {ticker}",
            "Alpha Vantage",
            SourceType.ANALYST_REPORT,
            0.68,
        )
        self._record_tool_call(
            tool_calls,
            agent_name,
            "company_overview",
            response.provider,
            f"Fetch Alpha Vantage overview for {ticker}",
            "Overview fetched" if response.data else "Overview unavailable",
            start,
            error=response.error,
            cache_hit=reused_inflight,
        )
        data = response.data if not response.error else {}
        cache[cache_key] = (source_id, data)
        return source_id, data

    async def _news_search(
        self,
        agent_name: str,
        company_name: str,
        cache: Dict[str, Any],
        sources: List[SourceDraft],
        tool_calls: List[ToolCallDraft],
    ) -> tuple[List[Dict[str, Any]], List[str], Optional[str]]:
        cache_key = f"news_search:{company_name.lower()}"
        if cache_key in cache:
            articles, source_ids, error = cache[cache_key]
            self._record_tool_call(
                tool_calls,
                agent_name,
                "search_company",
                "newsapi",
                f"Search NewsAPI for {company_name}",
                "Articles reused from workflow cache",
                datetime.now(timezone.utc),
                error=error,
                cache_hit=True,
            )
            return articles, source_ids, error
        start = datetime.now(timezone.utc)
        task_key = f"task:{cache_key}"
        reused_inflight = False
        if task_key in cache:
            reused_inflight = True
            response = await cache[task_key]
        else:
            cache[task_key] = asyncio.create_task(newsapi_client.search_company(company_name))
            response = await cache[task_key]
            cache.pop(task_key, None)
        self._record_tool_call(
            tool_calls,
            agent_name,
            "search_company",
            response.provider,
            f"Search NewsAPI for {company_name}",
            "Articles fetched" if response.data.get("articles") else "No articles returned",
            start,
            error=response.error,
            cache_hit=reused_inflight,
        )
        if response.error:
            result = ([], [], response.error)
            cache[cache_key] = result
            return result
        articles: List[Dict[str, Any]] = []
        source_ids: List[str] = []
        company_needle = company_name.lower()
        for article in response.data.get("articles", [])[:10]:
            url = article.get("url")
            title = article.get("title")
            if not url or not title:
                continue
            searchable = " ".join(
                str(article.get(field) or "") for field in ["title", "description", "content"]
            ).lower()
            if company_needle not in searchable:
                continue
            publisher = (article.get("source") or {}).get("name") or "NewsAPI source"
            source_id = self._add_source(
                sources,
                url,
                title,
                publisher,
                SourceType.REPUTABLE_NEWS,
                0.52,
                published_date=article.get("publishedAt"),
            )
            article = dict(article)
            article["_source_id"] = source_id
            articles.append(article)
            source_ids.append(source_id)
        result = (articles, source_ids, None)
        cache[cache_key] = result
        return result

    def _add_source(
        self,
        sources: List[SourceDraft],
        url: str,
        title: str,
        publisher: str,
        source_type: SourceType,
        source_quality_score: float,
        published_date: Optional[str] = None,
    ) -> str:
        for source in sources:
            if source.url == url and source.title == title:
                return source.source_id or source.url
        source_id = str(uuid.uuid4())
        sources.append(
            SourceDraft(
                source_id=source_id,
                url=url,
                title=title,
                publisher=publisher,
                source_type=source_type,
                source_quality_score=source_quality_score,
                published_date=published_date,
            )
        )
        return source_id

    def _record_tool_call(
        self,
        tool_calls: List[ToolCallDraft],
        agent_name: str,
        tool_name: str,
        provider: str,
        request_summary: str,
        response_summary: str,
        start: datetime,
        error: Optional[str] = None,
        cache_hit: bool = False,
    ) -> None:
        policy_allowed = is_tool_allowed(agent_name, provider, tool_name)
        policy_error = None if policy_allowed else f"Tool is not allowed by policy for {agent_name}."
        combined_error = "; ".join(message for message in [error, policy_error] if message)
        tool_calls.append(
            ToolCallDraft(
                agent_name=agent_name,
                tool_name=tool_name,
                provider=provider,
                request_summary=request_summary,
                response_summary=response_summary,
                status="failed" if error else "policy_violation" if not policy_allowed else "completed",
                duration_ms=elapsed_ms(start),
                cache_hit=cache_hit,
                error_message=combined_error or None,
            )
        )

    def _allowed_tool_metadata(self, agent_name: str) -> List[Dict[str, str]]:
        return [
            {
                "provider": policy.provider,
                "tool_name": policy.tool_name,
                "purpose": policy.purpose,
            }
            for policy in allowed_tools_for_agent(agent_name)
        ]

    def _best_company_search_match(
        self,
        company_name: str,
        results: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not results:
            return None
        needle = company_name.lower()
        for result in results:
            title = str(result.get("title") or "").lower()
            if needle in title:
                return result
        return results[0]

    def _latest_form(self, recent: Dict[str, Any], form: str) -> Optional[Dict[str, Any]]:
        forms = recent.get("form", [])
        filing_dates = recent.get("filingDate", [])
        accession_numbers = recent.get("accessionNumber", [])
        primary_documents = recent.get("primaryDocument", [])
        for index, current_form in enumerate(forms):
            if str(current_form).upper() == form.upper():
                return {
                    "form": current_form,
                    "filing_date": filing_dates[index] if index < len(filing_dates) else None,
                    "accession_number": (
                        accession_numbers[index] if index < len(accession_numbers) else None
                    ),
                    "primary_document": (
                        primary_documents[index] if index < len(primary_documents) else None
                    ),
                }
        return None

    def _extract_full_text_hits(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        hits = payload.get("hits", {}).get("hits")
        if hits is None:
            hits = payload.get("data", {}).get("hits", {}).get("hits", [])
        extracted: List[Dict[str, Any]] = []
        for hit in hits or []:
            source = hit.get("_source", hit)
            csa_names = source.get("csa_names") or source.get("display_names") or []
            company_name = None
            if isinstance(csa_names, list) and csa_names:
                company_name = str(csa_names[0])
            elif isinstance(csa_names, str):
                company_name = csa_names
            extracted.append(
                {
                    "company_name": company_name or source.get("company_name") or source.get("entity"),
                    "form": source.get("form"),
                    "root_form": source.get("root_form"),
                    "file_date": source.get("file_date"),
                    "filed_at": source.get("filedAt") or source.get("filed_at"),
                    "accession_number": source.get("adsh") or source.get("accessionNo"),
                }
            )
        return extracted

    def _latest_company_fact(
        self, data: Dict[str, Any], fact_names: List[str]
    ) -> Optional[Dict[str, Any]]:
        us_gaap = data.get("facts", {}).get("us-gaap", {})
        candidates: List[Dict[str, Any]] = []
        for fact_name in fact_names:
            fact = us_gaap.get(fact_name)
            if not fact:
                continue
            for unit, entries in fact.get("units", {}).items():
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    value = entry.get("val")
                    end = entry.get("end")
                    if value is None or not end:
                        continue
                    candidates.append(
                        {
                            "value": value,
                            "unit": unit,
                            "end": end,
                            "form": entry.get("form"),
                            "filed": entry.get("filed"),
                            "fact_name": fact_name,
                        }
                    )
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item.get("end") or "", item.get("filed") or ""), reverse=True)
        return candidates[0]

    async def _claim_extraction(
        self,
        company_name: str,
        raw_claims: List[Dict[str, Any]],
        source_ids_by_index: Dict[int, str],
        publish: ProgressPublisher,
        agent_runs: List[AgentRunDraft],
        tool_calls: List[ToolCallDraft],
    ) -> List[ClaimDraft]:
        start = datetime.now(timezone.utc)
        await publish("Claim Extraction Agent", AgentStatus.RUNNING, "Converting outputs into atomic claims.")
        claims: List[ClaimDraft] = []
        for item in raw_claims:
            explicit_source_ids = item.get("source_ids", [])
            indexed_source_ids = [
                source_ids_by_index[index]
                for index in item.get("source_indexes", [])
                if index in source_ids_by_index
            ]
            claim = ClaimDraft(
                text=item["text"],
                category=item["category"],
                value=item.get("value"),
                unit=item.get("unit"),
                date_context=item.get("date_context"),
                source_ids=list(dict.fromkeys([*explicit_source_ids, *indexed_source_ids])),
            )
            claims.append(claim)
        agent_runs.append(
            AgentRunDraft(
                agent_name="Claim Extraction Agent",
                status=AgentStatus.COMPLETED,
                started_at=start,
                completed_at=datetime.now(timezone.utc),
                duration_ms=elapsed_ms(start),
                input_summary=f"{len(raw_claims)} raw claims for {company_name}",
                output_summary=f"Extracted {len(claims)} atomic claims.",
                token_estimate=320,
                cost_estimate=0.0002,
            )
        )
        tool_calls.append(
            ToolCallDraft(
                agent_name="Claim Extraction Agent",
                tool_name="deterministic_claim_normalizer",
                provider="local",
                request_summary=f"Normalize claims for {company_name}",
                response_summary=f"{len(claims)} claims normalized",
                status="completed",
                duration_ms=elapsed_ms(start),
                cache_hit=True,
            )
        )
        await publish(
            "Claim Extraction Agent",
            AgentStatus.COMPLETED,
            f"Extracted {len(claims)} atomic claims.",
            {"claim_count": len(claims)},
        )
        return claims

    async def _verification(
        self,
        company_name: str,
        claims: List[ClaimDraft],
        sources: List[SourceDraft],
        publish: ProgressPublisher,
        agent_runs: List[AgentRunDraft],
        tool_calls: List[ToolCallDraft],
    ) -> List[ClaimDraft]:
        start = datetime.now(timezone.utc)
        await publish("Source Verification Agent", AgentStatus.RUNNING, "Checking claims against evidence.")
        verified = verify_claims(claims, sources)
        status_counts = count_statuses(verified)
        agent_runs.append(
            AgentRunDraft(
                agent_name="Source Verification Agent",
                status=AgentStatus.COMPLETED,
                started_at=start,
                completed_at=datetime.now(timezone.utc),
                duration_ms=elapsed_ms(start),
                input_summary=f"{len(claims)} claims for {company_name}",
                output_summary=f"Verification statuses: {status_counts}",
                token_estimate=380,
                cost_estimate=0.0003,
            )
        )
        tool_calls.append(
            ToolCallDraft(
                agent_name="Source Verification Agent",
                tool_name="verification_rules_engine",
                provider="local",
                request_summary="Assign verification status and confidence.",
                response_summary=str(status_counts),
                status="completed",
                duration_ms=elapsed_ms(start),
                cache_hit=True,
            )
        )
        await publish(
            "Source Verification Agent",
            AgentStatus.COMPLETED,
            "Verification complete; unsupported and unavailable data are explicitly marked.",
            {"status_counts": status_counts},
        )
        return verified

    async def _conflicts(
        self,
        company_name: str,
        claims: List[ClaimDraft],
        publish: ProgressPublisher,
        agent_runs: List[AgentRunDraft],
        tool_calls: List[ToolCallDraft],
    ) -> List[ClaimDraft]:
        start = datetime.now(timezone.utc)
        await publish("Conflict Detection Agent", AgentStatus.RUNNING, "Scanning claims for contradictions.")
        updated = detect_conflicts(claims)
        conflicts = conflicting_claims(updated)
        agent_runs.append(
            AgentRunDraft(
                agent_name="Conflict Detection Agent",
                status=AgentStatus.COMPLETED,
                started_at=start,
                completed_at=datetime.now(timezone.utc),
                duration_ms=elapsed_ms(start),
                input_summary=f"{len(claims)} verified claims for {company_name}",
                output_summary=f"Found {len(conflicts)} conflicting claims.",
                token_estimate=220,
                cost_estimate=0.0002,
            )
        )
        tool_calls.append(
            ToolCallDraft(
                agent_name="Conflict Detection Agent",
                tool_name="conflict_rules_engine",
                provider="local",
                request_summary="Detect contradictory values.",
                response_summary=f"{len(conflicts)} conflicts",
                status="completed",
                duration_ms=elapsed_ms(start),
                cache_hit=True,
            )
        )
        await publish(
            "Conflict Detection Agent",
            AgentStatus.COMPLETED,
            f"Found {len(conflicts)} conflicting claims.",
            {"conflict_count": len(conflicts)},
        )
        return updated

    async def _scoring(
        self,
        company_name: str,
        claims: List[ClaimDraft],
        publish: ProgressPublisher,
        agent_runs: List[AgentRunDraft],
        tool_calls: List[ToolCallDraft],
    ) -> Dict[str, Any]:
        start = datetime.now(timezone.utc)
        await publish("IPO Scoring Agent", AgentStatus.RUNNING, "Calculating evidence-aware IPO score.")
        score = calculate_ipo_score(claims)
        confidence = confidence_from_score_and_claims(score, claims)
        result = score.model_dump()
        result["confidence_level"] = confidence.value
        agent_runs.append(
            AgentRunDraft(
                agent_name="IPO Scoring Agent",
                status=AgentStatus.COMPLETED,
                started_at=start,
                completed_at=datetime.now(timezone.utc),
                duration_ms=elapsed_ms(start),
                input_summary=f"{len(claims)} claims for {company_name}",
                output_summary=f"IPO readiness score {score.total}/100 with {confidence.value} confidence.",
                token_estimate=460,
                cost_estimate=0.0008,
            )
        )
        tool_calls.append(
            ToolCallDraft(
                agent_name="IPO Scoring Agent",
                tool_name="ipo_score_calculator",
                provider="local",
                request_summary="Calculate IPO score with caps.",
                response_summary=f"{score.total}/100",
                status="completed",
                duration_ms=elapsed_ms(start),
                cache_hit=True,
            )
        )
        await publish(
            "IPO Scoring Agent",
            AgentStatus.COMPLETED,
            f"IPO readiness score calculated: {score.total}/100.",
            {"score": score.total, "caps_applied": score.caps_applied},
        )
        return result

    async def _report_writer(
        self,
        company_name: str,
        claims: List[ClaimDraft],
        score: Dict[str, Any],
        publish: ProgressPublisher,
        agent_runs: List[AgentRunDraft],
        tool_calls: List[ToolCallDraft],
    ) -> Dict[str, Any]:
        start = datetime.now(timezone.utc)
        await publish("Report Writer Agent", AgentStatus.RUNNING, "Writing final evidence-grounded report.")
        unavailable = [
            claim.text
            for claim in claims
            if claim.verification_status == VerificationStatus.NOT_PUBLICLY_AVAILABLE
        ]
        conflicts = [
            claim.text for claim in claims if claim.verification_status == VerificationStatus.CONFLICTING
        ]
        key_risks = [claim.text for claim in claims if claim.category == ClaimCategory.RISK]
        verified_claims = [
            claim.text for claim in claims if claim.verification_status == VerificationStatus.VERIFIED
        ]
        estimated_claims = [
            claim.text for claim in claims if claim.verification_status == VerificationStatus.ESTIMATED
        ]

        executive_summary = (
            f"{company_name} receives an evidence-aware IPO readiness score of {score['total']}/100. "
            "The report separates official facts, reported estimates, conflicts, and unavailable data. "
            "No IPO should be treated as confirmed unless an official filing or announcement is verified."
        )
        sections = {
            "company_overview": verified_claims[:4],
            "business_model": [
                claim.text
                for claim in claims
                if claim.category == ClaimCategory.COMPANY_PROFILE
            ],
            "financial_signals": [
                claim.text
                for claim in claims
                if claim.category
                in {ClaimCategory.FINANCIAL, ClaimCategory.FUNDING, ClaimCategory.VALUATION}
            ],
            "market_and_competitors": [
                claim.text
                for claim in claims
                if claim.category in {ClaimCategory.MARKET, ClaimCategory.COMPETITOR}
            ],
            "risk_analysis": key_risks,
            "conflicting_claims": conflicts,
            "unavailable_data": unavailable,
            "estimated_claims": estimated_claims,
        }
        report = {
            "report_status": "completed",
            "executive_summary": executive_summary,
            "ipo_readiness_score": score["total"],
            "confidence_level": score["confidence_level"],
            "bull_case": (
                "Bull case depends on verified product momentum, strong category position, and durable "
                "enterprise demand. It should be weighted carefully because private-company financials "
                "are not publicly available."
            ),
            "bear_case": (
                "Bear case centers on unverifiable financial maturity, regulatory exposure, heavy "
                "competition, infrastructure cost, and valuation uncertainty."
            ),
            "key_risks": key_risks,
            "score_breakdown": score,
            "sections": sections,
            "unavailable_data": unavailable,
        }
        agent_runs.append(
            AgentRunDraft(
                agent_name="Report Writer Agent",
                status=AgentStatus.COMPLETED,
                started_at=start,
                completed_at=datetime.now(timezone.utc),
                duration_ms=elapsed_ms(start),
                input_summary=f"{len(claims)} claims and score {score['total']}",
                output_summary="Final report generated with uncertainty preserved.",
                token_estimate=850,
                cost_estimate=0.0015,
            )
        )
        tool_calls.append(
            ToolCallDraft(
                agent_name="Report Writer Agent",
                tool_name="structured_report_writer",
                provider="local_structured_writer",
                request_summary="Synthesize final report from verified claims.",
                response_summary="Final dashboard report generated.",
                status="completed",
                duration_ms=elapsed_ms(start),
                cache_hit=False,
            )
        )
        await publish(
            "Report Writer Agent",
            AgentStatus.COMPLETED,
            "Final report ready.",
            {"report_status": "completed"},
        )
        return report

    def _public_company_reference_report(
        self,
        company_name: str,
        company_data: Dict[str, Any],
        claims: List[ClaimDraft],
        report: Dict[str, Any],
    ) -> Dict[str, Any]:
        ticker = company_data.get("ticker")
        public_claims = [
            claim.text
            for claim in claims
            if claim.category in {ClaimCategory.COMPANY_PROFILE, ClaimCategory.IPO_READINESS}
        ]
        sections = dict(report.get("sections") or {})
        sections["public_company_status"] = public_claims[:8]
        sections["unavailable_data"] = [
            *sections.get("unavailable_data", []),
            "IPO readiness score is not applicable because the company already has a confirmed public ticker.",
        ]
        score_breakdown = dict(report.get("score_breakdown") or {})
        score_breakdown.update(
            {
                "total": None,
                "not_applicable": True,
                "report_type": "public_company_reference_analysis",
                "rationale": (
                    "IPO readiness scoring is not applicable because the company is already public. "
                    "The report is retained as a public-company reference analysis."
                ),
            }
        )
        return {
            **report,
            "executive_summary": (
                f"{company_name} is already public"
                f"{f' under ticker {ticker}' if ticker else ''}. IPO readiness scoring is not applicable. "
                "This report is shown as a public-company reference analysis with evidence preserved."
            ),
            "ipo_readiness_score": None,
            "confidence_level": "High",
            "bull_case": (
                "Public-company reference case should be evaluated using public-market fundamentals, "
                "filings, and operating performance rather than IPO-readiness signals."
            ),
            "bear_case": (
                "IPO-readiness scoring is not applicable for an already-public issuer; risks should be "
                "reviewed through ongoing public-company disclosures."
            ),
            "score_breakdown": score_breakdown,
            "sections": sections,
            "unavailable_data": sections["unavailable_data"],
        }


def elapsed_ms(start: datetime) -> int:
    return int((datetime.now(timezone.utc) - start).total_seconds() * 1000)


def count_statuses(claims: List[ClaimDraft]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for claim in claims:
        counts[claim.verification_status.value] = counts.get(claim.verification_status.value, 0) + 1
    return counts
