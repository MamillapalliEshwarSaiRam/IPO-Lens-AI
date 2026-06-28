from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class AgentToolPolicy:
    agent_name: str
    provider: str
    tool_name: str
    purpose: str
    evidence_role: str
    source_quality: str
    free_tier: bool = True
    suggested_alternatives: tuple[str, ...] = ()


AGENT_TOOL_POLICIES: tuple[AgentToolPolicy, ...] = (
    AgentToolPolicy(
        agent_name="Identity Resolution Agent",
        provider="sec_edgar",
        tool_name="company_search",
        purpose="Search EDGAR by company name to find public SEC identity candidates and CIKs.",
        evidence_role="Primary identity evidence for public filings and IPO candidates.",
        source_quality="official",
        suggested_alternatives=("SEC full-text search API", "OpenFIGI", "GLEIF LEI search"),
    ),
    AgentToolPolicy(
        agent_name="Identity Resolution Agent",
        provider="sec_edgar",
        tool_name="company_tickers_mapping",
        purpose="Check whether a resolved SEC identity has a confirmed ticker mapping.",
        evidence_role="Secondary ticker confirmation, not the primary IPO identity source.",
        source_quality="official",
        suggested_alternatives=("Nasdaq symbol directory", "OpenFIGI"),
    ),
    AgentToolPolicy(
        agent_name="Company Profile Agent",
        provider="finnhub",
        tool_name="company_profile",
        purpose="Fetch public-company profile metadata such as website, industry, and exchange.",
        evidence_role="Provider profile signal for public companies.",
        source_quality="market_data_provider",
        suggested_alternatives=("SEC submissions company metadata", "Wikidata", "OpenCorporates"),
    ),
    AgentToolPolicy(
        agent_name="Company Profile Agent",
        provider="alpha_vantage",
        tool_name="company_overview",
        purpose="Fetch public-company overview, sector, description, and high-level fundamentals.",
        evidence_role="Provider profile and fundamentals signal for public companies.",
        source_quality="market_data_provider",
        suggested_alternatives=("Financial Modeling Prep free tier", "Yahoo Finance unofficial libraries"),
    ),
    AgentToolPolicy(
        agent_name="SEC Filing Agent",
        provider="sec_edgar",
        tool_name="full_text_search",
        purpose="Search SEC EFTS full-text index directly for S-1/F-1 IPO registration filings by company name.",
        evidence_role="Primary official IPO filing discovery evidence.",
        source_quality="official",
        suggested_alternatives=("SEC submissions API", "NYSE IPO filings page", "Nasdaq IPO calendar"),
    ),
    AgentToolPolicy(
        agent_name="SEC Filing Agent",
        provider="sec_edgar",
        tool_name="submissions",
        purpose="Fetch recent SEC submissions and detect S-1, F-1, 10-K, 10-Q, and 8-K filings.",
        evidence_role="Primary official filing evidence.",
        source_quality="official",
        suggested_alternatives=("SEC full-text search API", "NYSE IPO filings page", "Nasdaq IPO calendar"),
    ),
    AgentToolPolicy(
        agent_name="Financial Signals Agent",
        provider="sec_edgar",
        tool_name="company_facts",
        purpose="Fetch SEC XBRL company facts for official reported financial metrics.",
        evidence_role="Primary official financial evidence for SEC registrants.",
        source_quality="official",
        suggested_alternatives=("SEC XBRL frames API", "Company 10-K/10-Q filing parser"),
    ),
    AgentToolPolicy(
        agent_name="Financial Signals Agent",
        provider="alpha_vantage",
        tool_name="company_overview",
        purpose="Fetch public-company market cap, TTM revenue, and profit margin where available.",
        evidence_role="Secondary market-data signal for public companies.",
        source_quality="market_data_provider",
        suggested_alternatives=("Finnhub metrics", "Financial Modeling Prep free tier", "Stooq"),
    ),
    AgentToolPolicy(
        agent_name="Market & Competitor Agent",
        provider="finnhub",
        tool_name="company_profile",
        purpose="Fetch industry classification used for market positioning context.",
        evidence_role="Provider classification signal.",
        source_quality="market_data_provider",
        suggested_alternatives=("SEC SIC codes", "Wikidata industries", "OpenCorporates classifications"),
    ),
    AgentToolPolicy(
        agent_name="Market & Competitor Agent",
        provider="newsapi",
        tool_name="search_company",
        purpose="Discover recent market, IPO, funding, and competitor-related reporting.",
        evidence_role="Discovery only; claims remain estimated unless verified elsewhere.",
        source_quality="news_discovery",
        suggested_alternatives=("GDELT 2.1", "MediaStack free tier", "Google News RSS"),
    ),
    AgentToolPolicy(
        agent_name="Risk Agent",
        provider="newsapi",
        tool_name="search_company",
        purpose="Discover legal, regulatory, investigation, antitrust, and other risk reporting.",
        evidence_role="Discovery only; claims remain estimated unless verified elsewhere.",
        source_quality="news_discovery",
        suggested_alternatives=("GDELT 2.1", "CourtListener RECAP", "FTC/DOJ/SEC press releases"),
    ),
    AgentToolPolicy(
        agent_name="Claim Extraction Agent",
        provider="local",
        tool_name="deterministic_claim_normalizer",
        purpose="Normalize raw agent output into atomic claims with source IDs and date context.",
        evidence_role="Structured transformation, not external evidence.",
        source_quality="local_rules",
        free_tier=True,
    ),
    AgentToolPolicy(
        agent_name="Source Verification Agent",
        provider="local",
        tool_name="verification_rules_engine",
        purpose="Assign verification status, confidence, and evidence notes from source metadata.",
        evidence_role="Deterministic verification policy.",
        source_quality="local_rules",
        free_tier=True,
    ),
    AgentToolPolicy(
        agent_name="Conflict Detection Agent",
        provider="local",
        tool_name="conflict_rules_engine",
        purpose="Detect conflicting financial, funding, and valuation claims.",
        evidence_role="Deterministic conflict policy.",
        source_quality="local_rules",
        free_tier=True,
    ),
    AgentToolPolicy(
        agent_name="IPO Scoring Agent",
        provider="local",
        tool_name="ipo_score_calculator",
        purpose="Calculate evidence-aware IPO readiness score with caps for missing or weak evidence.",
        evidence_role="Deterministic scoring policy.",
        source_quality="local_rules",
        free_tier=True,
    ),
    AgentToolPolicy(
        agent_name="Report Writer Agent",
        provider="local_structured_writer",
        tool_name="structured_report_writer",
        purpose="Create dashboard sections from verified, estimated, conflicting, and unavailable claims.",
        evidence_role="Structured synthesis from verified claim graph.",
        source_quality="local_rules",
        free_tier=True,
    ),
)


def tool_policy_as_dict() -> Dict[str, List[Dict[str, object]]]:
    grouped: Dict[str, List[Dict[str, object]]] = {}
    for policy in AGENT_TOOL_POLICIES:
        grouped.setdefault(policy.agent_name, []).append(
            {
                "agent_name": policy.agent_name,
                "provider": policy.provider,
                "tool_name": policy.tool_name,
                "purpose": policy.purpose,
                "evidence_role": policy.evidence_role,
                "source_quality": policy.source_quality,
                "free_tier": policy.free_tier,
                "suggested_alternatives": list(policy.suggested_alternatives),
            }
        )
    return grouped


def allowed_tools_for_agent(agent_name: str) -> List[AgentToolPolicy]:
    return [policy for policy in AGENT_TOOL_POLICIES if policy.agent_name == agent_name]


def is_tool_allowed(agent_name: str, provider: str, tool_name: str) -> bool:
    normalized_provider = provider.lower()
    normalized_tool = tool_name.lower()
    return any(
        policy.provider == normalized_provider and policy.tool_name == normalized_tool
        for policy in allowed_tools_for_agent(agent_name)
    )
