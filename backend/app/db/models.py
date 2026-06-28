import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy import JSON as SAJSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    sector: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    ticker: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    cik: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    reports: Mapped[List["ResearchReport"]] = relationship(back_populates="company")
    claims: Mapped[List["Claim"]] = relationship(back_populates="company")
    sources: Mapped[List["Source"]] = relationship(back_populates="company")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[Optional[str]] = mapped_column(ForeignKey("companies.id"), nullable=True)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    publisher: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    published_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_quality_score: Mapped[float] = mapped_column(Float, default=0.0)

    company: Mapped[Optional["Company"]] = relationship(back_populates="sources")


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    date_context: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_ids: Mapped[List[str]] = mapped_column(SAJSON, default=list)
    verification_status: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    company: Mapped["Company"] = relationship(back_populates="claims")


class ResearchReport(Base):
    __tablename__ = "research_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    report_status: Mapped[str] = mapped_column(String(64), nullable=False)
    executive_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ipo_readiness_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    confidence_level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    bull_case: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bear_case: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_risks: Mapped[List[str]] = mapped_column(SAJSON, default=list)
    key_claim_ids: Mapped[List[str]] = mapped_column(SAJSON, default=list)
    source_ids: Mapped[List[str]] = mapped_column(SAJSON, default=list)
    score_breakdown: Mapped[Dict[str, Any]] = mapped_column(SAJSON, default=dict)
    sections: Mapped[Dict[str, Any]] = mapped_column(SAJSON, default=dict)
    unavailable_data: Mapped[List[str]] = mapped_column(SAJSON, default=list)
    conflicting_claim_ids: Mapped[List[str]] = mapped_column(SAJSON, default=list)

    company: Mapped["Company"] = relationship(back_populates="reports")
    agent_runs: Mapped[List["AgentRun"]] = relationship(back_populates="report")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    report_id: Mapped[str] = mapped_column(ForeignKey("research_reports.id"), nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    input_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_estimate: Mapped[int] = mapped_column(Integer, default=0)
    cost_estimate: Mapped[float] = mapped_column(Float, default=0.0)

    report: Mapped["ResearchReport"] = relationship(back_populates="agent_runs")
    tool_calls: Mapped[List["ToolCall"]] = relationship(back_populates="agent_run")


class ToolCall(Base):
    __tablename__ = "tool_calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agent_run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), nullable=False, index=True)
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(255), nullable=False)
    request_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    agent_run: Mapped["AgentRun"] = relationship(back_populates="tool_calls")


class Watchlist(Base):
    __tablename__ = "watchlist"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    frequency: Mapped[str] = mapped_column(String(32), default="weekly")
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_check_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=True, index=True
    )
    last_report_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class MonitoringAlert(Base):
    __tablename__ = "monitoring_alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    watchlist_id: Mapped[Optional[str]] = mapped_column(ForeignKey("watchlist.id"), nullable=True, index=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("research_reports.id"), nullable=False, index=True)
    previous_report_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    claim_ids: Mapped[List[str]] = mapped_column(SAJSON, default=list)
    alert_metadata: Mapped[Dict[str, Any]] = mapped_column(SAJSON, default=dict)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)


class CacheEntry(Base):
    __tablename__ = "cache_entries"

    key: Mapped[str] = mapped_column(String(500), primary_key=True)
    provider: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    response_json: Mapped[Dict[str, Any]] = mapped_column(SAJSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
