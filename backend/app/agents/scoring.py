from typing import Dict, List

from app.agents.state import ClaimDraft
from app.core.enums import ClaimCategory, ConfidenceLevel, VerificationStatus
from app.schemas import ScoreBreakdown


def calculate_ipo_score(claims: List[ClaimDraft]) -> ScoreBreakdown:
    verified_count = len([c for c in claims if c.verification_status == VerificationStatus.VERIFIED])
    estimated_count = len([c for c in claims if c.verification_status == VerificationStatus.ESTIMATED])
    unsupported_count = len([c for c in claims if c.verification_status == VerificationStatus.UNSUPPORTED])
    unavailable_financials = [
        c
        for c in claims
        if c.category == ClaimCategory.FINANCIAL
        and c.verification_status == VerificationStatus.NOT_PUBLICLY_AVAILABLE
    ]
    conflicts = len([c for c in claims if c.verification_status == VerificationStatus.CONFLICTING])
    has_s1 = any("s-1" in c.text.lower() and c.verification_status == VerificationStatus.VERIFIED for c in claims)

    financial_maturity = 7 + min(8, verified_count * 2) + min(4, estimated_count)
    if unavailable_financials:
        financial_maturity = min(financial_maturity, 11)

    market_position = 8
    if any(c.category == ClaimCategory.COMPETITOR for c in claims):
        market_position += 5
    if any(c.category == ClaimCategory.MARKET for c in claims):
        market_position += 3
    market_position = min(market_position, 20)

    governance = 4
    if has_s1:
        governance += 8
    if any(c.category == ClaimCategory.IPO_READINESS and c.verification_status == VerificationStatus.VERIFIED for c in claims):
        governance += 2
    governance = min(governance, 15)

    risk_profile = 14
    risk_claims = [c for c in claims if c.category == ClaimCategory.RISK]
    risk_profile -= min(8, len(risk_claims) * 2)
    risk_profile = max(0, min(risk_profile, 20))

    ipo_signals = 2
    if has_s1:
        ipo_signals = 10
    elif any(c.category == ClaimCategory.IPO_READINESS and c.verification_status == VerificationStatus.ESTIMATED for c in claims):
        ipo_signals = 5

    evidence_quality = min(
        10,
        int((verified_count * 1.4) + (estimated_count * 0.6) - (unsupported_count * 1.2) - conflicts),
    )
    evidence_quality = max(0, evidence_quality)

    total = financial_maturity + market_position + governance + risk_profile + ipo_signals + evidence_quality
    caps_applied: List[str] = []

    if unavailable_financials and total > 65:
        total = 65
        caps_applied.append("Capped at 65 because reliable public financial data is unavailable.")

    if claims:
        unsupported_ratio = unsupported_count / len(claims)
        if unsupported_ratio > 0.5 and total > 50:
            total = 50
            caps_applied.append("Capped at 50 because most claims are unsupported.")

    if not has_s1:
        caps_applied.append("No official S-1 filing found; IPO is not treated as confirmed.")

    return ScoreBreakdown(
        financial_maturity=financial_maturity,
        market_position=market_position,
        governance_and_filing_readiness=governance,
        risk_profile=risk_profile,
        ipo_signals=ipo_signals,
        evidence_quality=evidence_quality,
        total=max(0, min(100, total)),
        caps_applied=caps_applied,
        rationale=(
            "Score emphasizes evidence quality and penalizes missing official financials, "
            "unsupported claims, conflicts, and lack of an IPO registration statement."
        ),
    )


def confidence_from_score_and_claims(score: ScoreBreakdown, claims: List[ClaimDraft]) -> ConfidenceLevel:
    if not claims:
        return ConfidenceLevel.LOW
    verified_or_unavailable = [
        claim
        for claim in claims
        if claim.verification_status
        in {VerificationStatus.VERIFIED, VerificationStatus.NOT_PUBLICLY_AVAILABLE}
    ]
    ratio = len(verified_or_unavailable) / len(claims)
    if ratio >= 0.7 and score.evidence_quality >= 7:
        return ConfidenceLevel.HIGH
    if ratio >= 0.4 and score.evidence_quality >= 3:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def score_dict(score: ScoreBreakdown) -> Dict[str, object]:
    return score.model_dump()

