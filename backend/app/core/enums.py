from enum import Enum


class SourceType(str, Enum):
    SEC_FILING = "SEC filing"
    COMPANY_WEBSITE = "Company website"
    PRESS_RELEASE = "Press release"
    REPUTABLE_NEWS = "Reputable news"
    ANALYST_REPORT = "Analyst report"
    BLOG = "Blog"
    SOCIAL_MEDIA = "Social media"
    UNKNOWN = "Unknown"


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    ESTIMATED = "estimated"
    UNSUPPORTED = "unsupported"
    NOT_PUBLICLY_AVAILABLE = "not_publicly_available"
    CONFLICTING = "conflicting"


class ClaimCategory(str, Enum):
    COMPANY_PROFILE = "company_profile"
    FINANCIAL = "financial"
    FUNDING = "funding"
    VALUATION = "valuation"
    MARKET = "market"
    COMPETITOR = "competitor"
    RISK = "risk"
    IPO_READINESS = "ipo_readiness"


class AgentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ReportStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class ConfidenceLevel(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

