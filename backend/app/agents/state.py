from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.enums import AgentStatus, ClaimCategory, SourceType, VerificationStatus


@dataclass
class SourceDraft:
    url: str
    title: str
    publisher: str
    source_type: SourceType
    source_quality_score: float
    published_date: Optional[str] = None
    source_id: Optional[str] = None


@dataclass
class ClaimDraft:
    text: str
    category: ClaimCategory
    source_ids: List[str] = field(default_factory=list)
    value: Optional[str] = None
    unit: Optional[str] = None
    date_context: Optional[str] = None
    verification_status: VerificationStatus = VerificationStatus.UNSUPPORTED
    confidence_score: float = 0.0
    evidence_notes: Optional[str] = None


@dataclass
class AgentRunDraft:
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


@dataclass
class ToolCallDraft:
    agent_name: str
    tool_name: str
    provider: str
    request_summary: str
    response_summary: str
    status: str
    duration_ms: int
    cache_hit: bool = False
    error_message: Optional[str] = None


@dataclass
class WorkflowResult:
    company: Dict[str, Any]
    sources: List[SourceDraft]
    claims: List[ClaimDraft]
    report: Dict[str, Any]
    agent_runs: List[AgentRunDraft]
    tool_calls: List[ToolCallDraft]
