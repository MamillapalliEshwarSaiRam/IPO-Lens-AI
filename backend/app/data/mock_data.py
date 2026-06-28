from typing import Any, Dict, List

from app.core.enums import ClaimCategory, SourceType


MOCK_COMPANIES: Dict[str, Dict[str, Any]] = {
    "anthropic": {
        "name": "Anthropic",
        "website": "https://www.anthropic.com",
        "sector": "Artificial intelligence",
        "is_public": False,
        "ticker": None,
        "cik": None,
        "description": (
            "Anthropic is an AI research and product company known for the Claude family "
            "of AI assistants and enterprise AI platform offerings."
        ),
    },
    "stripe": {
        "name": "Stripe",
        "website": "https://stripe.com",
        "sector": "Financial technology",
        "is_public": False,
        "ticker": None,
        "cik": None,
        "description": "Stripe provides payments and financial infrastructure software for businesses.",
    },
    "openai": {
        "name": "OpenAI",
        "website": "https://openai.com",
        "sector": "Artificial intelligence",
        "is_public": False,
        "ticker": None,
        "cik": None,
        "description": "OpenAI develops AI models, products, and APIs including ChatGPT.",
    },
}


ANTHROPIC_SOURCES: List[Dict[str, Any]] = [
    {
        "url": "https://www.anthropic.com/company",
        "title": "Anthropic company information",
        "publisher": "Anthropic",
        "source_type": SourceType.COMPANY_WEBSITE,
        "source_quality_score": 0.82,
        "published_date": None,
    },
    {
        "url": "https://www.sec.gov/edgar/search/",
        "title": "SEC EDGAR company and filings search",
        "publisher": "U.S. Securities and Exchange Commission",
        "source_type": SourceType.SEC_FILING,
        "source_quality_score": 1.0,
        "published_date": None,
    },
    {
        "url": "https://example.com/reputable-news-anthropic-funding-a",
        "title": "Reported Anthropic funding round and valuation",
        "publisher": "Mock Reputable News A",
        "source_type": SourceType.REPUTABLE_NEWS,
        "source_quality_score": 0.62,
        "published_date": "2025-03-01T00:00:00+00:00",
    },
    {
        "url": "https://example.com/reputable-news-anthropic-funding-b",
        "title": "Alternative reported Anthropic valuation figure",
        "publisher": "Mock Reputable News B",
        "source_type": SourceType.REPUTABLE_NEWS,
        "source_quality_score": 0.58,
        "published_date": "2025-03-02T00:00:00+00:00",
    },
    {
        "url": "https://example.com/reputable-news-ai-market",
        "title": "Enterprise AI market competition report",
        "publisher": "Mock Industry News",
        "source_type": SourceType.REPUTABLE_NEWS,
        "source_quality_score": 0.55,
        "published_date": "2025-02-15T00:00:00+00:00",
    },
]


ANTHROPIC_AGENT_OUTPUTS: Dict[str, Dict[str, Any]] = {
    "Company Profile Agent": {
        "summary": "Company profile found from official company website and reputable secondary sources.",
        "claims": [
            {
                "text": "Anthropic develops the Claude family of AI assistants and enterprise AI products.",
                "category": ClaimCategory.COMPANY_PROFILE,
                "source_indexes": [0],
                "value": "Claude AI assistant and enterprise AI products",
                "date_context": "Current company positioning",
            },
            {
                "text": "Anthropic is privately held and does not trade under a public ticker.",
                "category": ClaimCategory.COMPANY_PROFILE,
                "source_indexes": [1],
                "value": "Private company",
                "date_context": "SEC public issuer lookup",
            },
        ],
    },
    "SEC Filing Agent": {
        "summary": "SEC EDGAR checked; no public-company filings or IPO registration statement found in mock data.",
        "claims": [
            {
                "text": "Anthropic has no S-1 registration statement identified in the checked SEC EDGAR mock dataset.",
                "category": ClaimCategory.IPO_READINESS,
                "source_indexes": [1],
                "value": "Not publicly available",
                "date_context": "SEC EDGAR mock check",
            },
            {
                "text": "Anthropic audited IPO financial statements are not publicly available in the checked SEC filings.",
                "category": ClaimCategory.FINANCIAL,
                "source_indexes": [1],
                "value": "Not publicly available",
                "date_context": "SEC EDGAR mock check",
            },
        ],
    },
    "Financial Signals Agent": {
        "summary": "Financial signals gathered; public financial statements unavailable and valuation reports conflict.",
        "claims": [
            {
                "text": "Anthropic revenue is not publicly available in official filings.",
                "category": ClaimCategory.FINANCIAL,
                "source_indexes": [1],
                "value": "Not publicly available",
                "unit": "USD",
                "date_context": "Current public filings check",
            },
            {
                "text": "One reputable media source reported Anthropic at a $61.5B valuation.",
                "category": ClaimCategory.VALUATION,
                "source_indexes": [2],
                "value": "61.5",
                "unit": "USD billions",
                "date_context": "Reported March 2025",
            },
            {
                "text": "A second reputable media source reported Anthropic at a $60B valuation.",
                "category": ClaimCategory.VALUATION,
                "source_indexes": [3],
                "value": "60",
                "unit": "USD billions",
                "date_context": "Reported March 2025",
            },
            {
                "text": "Anthropic profitability is not publicly available in official filings.",
                "category": ClaimCategory.FINANCIAL,
                "source_indexes": [1],
                "value": "Not publicly available",
                "unit": "USD",
                "date_context": "Current public filings check",
            },
        ],
    },
    "Market & Competitor Agent": {
        "summary": "Competitor set identified with market-position claims kept qualitative.",
        "claims": [
            {
                "text": "Anthropic competes with OpenAI, Google DeepMind, Meta AI, and other frontier AI labs.",
                "category": ClaimCategory.COMPETITOR,
                "source_indexes": [4],
                "value": "OpenAI, Google DeepMind, Meta AI",
                "date_context": "Current competitive landscape",
            },
            {
                "text": "Anthropic's market opportunity is tied to enterprise AI adoption, but exact addressable market sizing is not verified in the available mock sources.",
                "category": ClaimCategory.MARKET,
                "source_indexes": [4],
                "value": "Not publicly available",
                "date_context": "Current market landscape",
            },
        ],
    },
    "Risk Agent": {
        "summary": "Risk analysis found regulatory, concentration, competition, profitability, and infrastructure risks.",
        "claims": [
            {
                "text": "Anthropic faces regulatory risk because frontier AI companies are subject to evolving AI safety, privacy, and competition oversight.",
                "category": ClaimCategory.RISK,
                "source_indexes": [4],
                "value": "Regulatory risk",
                "date_context": "Current risk landscape",
            },
            {
                "text": "Anthropic's profitability path is not publicly verifiable from official filings.",
                "category": ClaimCategory.RISK,
                "source_indexes": [1],
                "value": "Not publicly available",
                "date_context": "Current public filings check",
            },
        ],
    },
}


def get_mock_company(company_name: str) -> Dict[str, Any]:
    key = company_name.strip().lower()
    return MOCK_COMPANIES.get(
        key,
        {
            "name": company_name.strip(),
            "website": None,
            "sector": None,
            "is_public": False,
            "ticker": None,
            "cik": None,
            "description": (
                "Company profile unavailable in the deterministic mock dataset. "
                "Use live providers for broader coverage."
            ),
        },
    )


def get_mock_sources(company_name: str) -> List[Dict[str, Any]]:
    if company_name.strip().lower() == "anthropic":
        return ANTHROPIC_SOURCES
    return [
        {
            "url": "https://www.sec.gov/edgar/search/",
            "title": "SEC EDGAR company and filings search",
            "publisher": "U.S. Securities and Exchange Commission",
            "source_type": SourceType.SEC_FILING,
            "source_quality_score": 1.0,
            "published_date": None,
        }
    ]


def get_agent_outputs(company_name: str) -> Dict[str, Dict[str, Any]]:
    if company_name.strip().lower() == "anthropic":
        return ANTHROPIC_AGENT_OUTPUTS
    return {
        "Company Profile Agent": {
            "summary": "No official company profile found in deterministic mock data.",
            "claims": [
                {
                    "text": f"{company_name.strip()} company profile is not publicly available in mock data.",
                    "category": ClaimCategory.COMPANY_PROFILE,
                    "source_indexes": [],
                    "value": "Not publicly available",
                    "date_context": "Mock data lookup",
                }
            ],
        },
        "SEC Filing Agent": {
            "summary": "SEC EDGAR mock check completed with no filing match.",
            "claims": [
                {
                    "text": f"{company_name.strip()} SEC IPO filings are not publicly available in mock data.",
                    "category": ClaimCategory.IPO_READINESS,
                    "source_indexes": [0],
                    "value": "Not publicly available",
                    "date_context": "SEC EDGAR mock check",
                }
            ],
        },
        "Financial Signals Agent": {
            "summary": "No reliable financial data found in deterministic mock data.",
            "claims": [
                {
                    "text": f"{company_name.strip()} revenue is not publicly available in reliable mock sources.",
                    "category": ClaimCategory.FINANCIAL,
                    "source_indexes": [0],
                    "value": "Not publicly available",
                    "date_context": "Mock data lookup",
                }
            ],
        },
        "Market & Competitor Agent": {
            "summary": "Market and competitor data unavailable in deterministic mock data.",
            "claims": [],
        },
        "Risk Agent": {
            "summary": "Risk profile cannot be fully assessed from deterministic mock data.",
            "claims": [
                {
                    "text": f"{company_name.strip()} risk profile is unsupported without reliable sources.",
                    "category": ClaimCategory.RISK,
                    "source_indexes": [],
                    "value": "Unsupported",
                    "date_context": "Mock data lookup",
                }
            ],
        },
    }

