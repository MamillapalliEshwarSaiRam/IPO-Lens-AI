import pytest
from pydantic import ValidationError

from app.core.enums import ClaimCategory, VerificationStatus
from app.schemas import ClaimCreate


def test_claim_schema_accepts_atomic_claim() -> None:
    claim = ClaimCreate(
        company_id="company-1",
        text="Anthropic revenue is not publicly available in official filings.",
        category=ClaimCategory.FINANCIAL,
        value="Not publicly available",
        source_ids=["source-1"],
        verification_status=VerificationStatus.NOT_PUBLICLY_AVAILABLE,
        confidence_score=0.92,
        evidence_notes="SEC checked; no public filing found.",
    )
    assert claim.text.startswith("Anthropic revenue")
    assert claim.verification_status == VerificationStatus.NOT_PUBLICLY_AVAILABLE


def test_claim_schema_rejects_empty_claim() -> None:
    with pytest.raises(ValidationError):
        ClaimCreate(
            company_id="company-1",
            text=" ",
            category=ClaimCategory.FINANCIAL,
            verification_status=VerificationStatus.UNSUPPORTED,
            confidence_score=0.1,
        )

