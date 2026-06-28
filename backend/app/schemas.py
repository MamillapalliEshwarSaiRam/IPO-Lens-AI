from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import (
    AgentStatus,
    ClaimCategory,
    ConfidenceLevel,
    ReportStatus,
    SourceType,
    VerificationStatus,
)


class CompanyBase(BaseModel):
    name: str
    website: Optional[str] = None
    sector: Optional[str] = None
    is_public: bool = False
    ticker: Optional[str] = None
    cik: Optional[str] = None
    description: Optional[str] = None


class CompanyRead(CompanyBase):
    id: str

    model_config = ConfigDict(from_attributes=True)


class SourceBase(BaseModel):
    url: str
    title: str
    publisher: Optional[str] = None
    published_date: Optional[datetime] = None
    retrieved_at: Optional[datetime] = None
    source_type: SourceType
    source_quality_score: float = Field(ge=0, le=1)


class SourceCreate(SourceBase):
    company_id: Optional[str] = None


class SourceRead(SourceBase):
    id: str
    company_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ClaimBase(BaseModel):
    text: str
    category: ClaimCategory
    value: Optional[str] = None
    unit: Optional[str] = None
    date_context: Optional[str] = None
    source_ids: List[str] = Field(default_factory=list)
    verification_status: VerificationStatus
    confidence_score: float = Field(ge=0, le=1)
    evidence_notes: Optional[str] = None

    @field_validator("text")
    @classmethod
    def claim_text_must_be_atomic(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("claim text cannot be empty")
        return value.strip()


class ClaimCreate(ClaimBase):
    company_id: str


class ClaimRead(ClaimBase):
    id: str
    company_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScoreBreakdown(BaseModel):
    financial_maturity: int = Field(ge=0, le=25)
    market_position: int = Field(ge=0, le=20)
    governance_and_filing_readiness: int = Field(ge=0, le=15)
    risk_profile: int = Field(ge=0, le=20)
    ipo_signals: int = Field(ge=0, le=10)
    evidence_quality: int = Field(ge=0, le=10)
    total: int = Field(ge=0, le=100)
    caps_applied: List[str] = Field(default_factory=list)
    rationale: str = ""


class AgentRunRead(BaseModel):
    id: str
    report_id: str
    agent_name: str
    status: AgentStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    error_message: Optional[str] = None
    token_estimate: int = 0
    cost_estimate: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class ToolCallRead(BaseModel):
    id: str
    agent_run_id: str
    tool_name: str
    provider: str
    request_summary: Optional[str] = None
    response_summary: Optional[str] = None
    status: str
    duration_ms: Optional[int] = None
    cache_hit: bool = False
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ResearchReportRead(BaseModel):
    id: str
    company_id: str
    created_at: datetime
    report_status: ReportStatus
    executive_summary: Optional[str] = None
    ipo_readiness_score: Optional[int] = None
    confidence_level: Optional[ConfidenceLevel] = None
    bull_case: Optional[str] = None
    bear_case: Optional[str] = None
    key_risks: List[str] = Field(default_factory=list)
    key_claim_ids: List[str] = Field(default_factory=list)
    source_ids: List[str] = Field(default_factory=list)
    score_breakdown: Dict[str, Any] = Field(default_factory=dict)
    sections: Dict[str, Any] = Field(default_factory=dict)
    unavailable_data: List[str] = Field(default_factory=list)
    conflicting_claim_ids: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ReportDetail(BaseModel):
    report: ResearchReportRead
    company: CompanyRead
    claims: List[ClaimRead]
    sources: List[SourceRead]
    agent_runs: List[AgentRunRead] = Field(default_factory=list)


class ResearchRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    prompt: Optional[str] = None
    use_mock_data: bool = False
    mock_scenario: Optional[str] = Field(
        default=None,
        description="Optional deterministic scenario: default, news_failure, private_unavailable.",
    )


class ResearchStartResponse(BaseModel):
    run_id: str
    report_id: str
    status: ReportStatus
    message: str


class ProgressEvent(BaseModel):
    run_id: str
    agent_name: str
    status: AgentStatus
    partial_result_summary: str
    timestamp: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str
    database: str
    providers: Dict[str, str]
    langgraph_available: bool


class AgentToolPolicyRead(BaseModel):
    agent_name: str
    provider: str
    tool_name: str
    purpose: str
    evidence_role: str
    source_quality: str
    free_tier: bool = True
    suggested_alternatives: List[str] = Field(default_factory=list)


class AgentToolPolicyResponse(BaseModel):
    agents: Dict[str, List[AgentToolPolicyRead]]


class WatchlistCreate(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    frequency: str = Field(default="weekly", pattern="^(daily|weekly)$")


class WatchlistRead(BaseModel):
    id: str
    company_id: str
    company: Optional[CompanyRead] = None
    created_at: datetime
    frequency: str
    last_checked_at: Optional[datetime] = None
    next_check_at: Optional[datetime] = None
    last_report_id: Optional[str] = None
    last_error: Optional[str] = None
    active: bool

    model_config = ConfigDict(from_attributes=True)


class MonitoringAlertRead(BaseModel):
    id: str
    company_id: str
    watchlist_id: Optional[str] = None
    report_id: str
    previous_report_id: Optional[str] = None
    created_at: datetime
    alert_type: str
    severity: str
    title: str
    description: str
    claim_ids: List[str] = Field(default_factory=list)
    alert_metadata: Dict[str, Any] = Field(default_factory=dict)
    acknowledged: bool = False
    company: Optional[CompanyRead] = None

    model_config = ConfigDict(from_attributes=True)
