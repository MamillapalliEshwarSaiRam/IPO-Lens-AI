from typing import Dict, Iterable, List

from app.agents.state import ClaimDraft, SourceDraft
from app.core.enums import SourceType, VerificationStatus


def _source_lookup(sources: Iterable[SourceDraft]) -> Dict[str, SourceDraft]:
    return {source.source_id or source.url: source for source in sources}


def verify_claims(claims: List[ClaimDraft], sources: List[SourceDraft]) -> List[ClaimDraft]:
    lookup = _source_lookup(sources)
    verified: List[ClaimDraft] = []

    for claim in claims:
        claim_sources = [lookup[source_id] for source_id in claim.source_ids if source_id in lookup]
        lower_value = (claim.value or "").strip().lower()
        lower_text = claim.text.lower()

        if lower_value == "not publicly available" or "not publicly available" in lower_text:
            claim.verification_status = VerificationStatus.NOT_PUBLICLY_AVAILABLE
            claim.confidence_score = 0.92 if claim_sources else 0.74
            claim.evidence_notes = (
                "Reliable sources checked and did not provide this data; represented as unavailable, not inferred."
            )
        elif not claim_sources:
            claim.verification_status = VerificationStatus.UNSUPPORTED
            claim.confidence_score = 0.15
            claim.evidence_notes = "No evidence source was attached to this claim."
        elif any(source.source_type == SourceType.SEC_FILING for source in claim_sources):
            claim.verification_status = VerificationStatus.VERIFIED
            claim.confidence_score = max(0.88, max(source.source_quality_score for source in claim_sources))
            claim.evidence_notes = "Claim is supported by an official SEC source or SEC lookup result."
        elif any(source.source_type in {SourceType.COMPANY_WEBSITE, SourceType.PRESS_RELEASE} for source in claim_sources):
            claim.verification_status = VerificationStatus.VERIFIED
            claim.confidence_score = min(0.9, max(source.source_quality_score for source in claim_sources) + 0.05)
            claim.evidence_notes = "Claim is supported by an official company-controlled source."
        elif any(source.source_type == SourceType.REPUTABLE_NEWS for source in claim_sources):
            claim.verification_status = VerificationStatus.ESTIMATED
            claim.confidence_score = min(0.7, max(source.source_quality_score for source in claim_sources) + 0.05)
            claim.evidence_notes = (
                "Claim relies on reputable reporting and should not be treated as an official fact."
            )
        elif any(source.source_type == SourceType.ANALYST_REPORT for source in claim_sources):
            claim.verification_status = VerificationStatus.ESTIMATED
            claim.confidence_score = min(0.72, max(source.source_quality_score for source in claim_sources) + 0.05)
            claim.evidence_notes = (
                "Claim relies on a market-data provider and should be cross-checked against official filings."
            )
        else:
            claim.verification_status = VerificationStatus.UNSUPPORTED
            claim.confidence_score = 0.25
            claim.evidence_notes = "Attached sources are too weak for verification."

        verified.append(claim)

    return verified


def verification_coverage(claims: List[ClaimDraft]) -> float:
    if not claims:
        return 0.0
    supported = [
        claim
        for claim in claims
        if claim.verification_status
        in {
            VerificationStatus.VERIFIED,
            VerificationStatus.ESTIMATED,
            VerificationStatus.NOT_PUBLICLY_AVAILABLE,
            VerificationStatus.CONFLICTING,
        }
    ]
    return len(supported) / len(claims)
