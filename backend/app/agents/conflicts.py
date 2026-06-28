from collections import defaultdict
import re
from typing import Dict, List, Tuple

from app.agents.state import ClaimDraft
from app.core.enums import ClaimCategory, VerificationStatus


CONFLICT_CATEGORIES = {
    ClaimCategory.VALUATION,
    ClaimCategory.FUNDING,
    ClaimCategory.FINANCIAL,
}


def _claim_text(claim: ClaimDraft) -> str:
    return f"{claim.text} {claim.date_context or ''} {claim.unit or ''}".lower()


def _unit_key(claim: ClaimDraft) -> str:
    text = _claim_text(claim)
    unit = (claim.unit or "").lower()
    if "ratio" in unit or "margin" in text or "percent" in unit or "%" in unit:
        return "ratio"
    currency = "usd" if "usd" in text or "$" in text else "currency_unspecified"
    if "billion" in text or "bn" in text:
        scale = "billions"
    elif "million" in text or re.search(r"\bmm\b", text):
        scale = "millions"
    else:
        scale = "absolute"
    return f"{currency}:{scale}"


def _period_basis(claim: ClaimDraft) -> str:
    text = _claim_text(claim)
    if "trailing twelve-month" in text or "trailing twelve month" in text or "ttm" in text:
        return "ttm"
    if "period ending" in text:
        return f"period:{claim.date_context or 'unspecified'}"
    if "quarter" in text or "quarterly" in text:
        return f"quarter:{claim.date_context or 'unspecified'}"
    if "fiscal year" in text or "annual" in text:
        return f"annual:{claim.date_context or 'unspecified'}"
    return claim.date_context or "unspecified"


def _financial_metric(claim: ClaimDraft) -> str:
    text = _claim_text(claim)
    if "revenue" in text or "sales" in text:
        return "revenue"
    if "profit margin" in text or "margin" in text:
        return "profit_margin"
    if "net income" in text or "net loss" in text:
        return "net_income"
    if "ebitda" in text:
        return "ebitda"
    if "cash flow" in text or "free cash flow" in text:
        return "cash_flow"
    if "profitability" in text or "profit" in text:
        return "profitability"
    return "financial_unspecified"


def _valuation_metric(claim: ClaimDraft) -> str:
    text = _claim_text(claim)
    if "market capitalization" in text or "market cap" in text:
        return "market_cap"
    if "enterprise value" in text:
        return "enterprise_value"
    if "post-money" in text or "post money" in text:
        return "post_money_valuation"
    if "pre-money" in text or "pre money" in text:
        return "pre_money_valuation"
    if "valuation" in text:
        return "valuation"
    return "valuation_unspecified"


def _funding_basis(claim: ClaimDraft) -> str:
    text = _claim_text(claim)
    series = re.search(r"\bseries\s+([a-z0-9]+)\b", text)
    if series:
        return f"series:{series.group(1)}"
    if "seed" in text:
        return "seed"
    if "ipo" in text:
        return "ipo"
    if "round" in text:
        return claim.date_context or "round_unspecified"
    return claim.date_context or "funding_unspecified"


def _scope_key(claim: ClaimDraft) -> str:
    text = _claim_text(claim)
    if "segment" in text or "business unit" in text:
        return "segment"
    if "consolidated" in text:
        return "consolidated"
    return "scope_unspecified"


def _group_key(claim: ClaimDraft) -> Tuple[str, str, str, str, str]:
    if claim.category == ClaimCategory.FINANCIAL:
        return (
            claim.category.value,
            _financial_metric(claim),
            _period_basis(claim),
            _unit_key(claim),
            _scope_key(claim),
        )
    if claim.category == ClaimCategory.VALUATION:
        return (
            claim.category.value,
            _valuation_metric(claim),
            claim.date_context or "unspecified",
            _unit_key(claim),
            _scope_key(claim),
        )
    if claim.category == ClaimCategory.FUNDING:
        return (
            claim.category.value,
            "funding_amount",
            _funding_basis(claim),
            _unit_key(claim),
            _scope_key(claim),
        )
    return (claim.category.value, "metric_unspecified", claim.date_context or "", _unit_key(claim), _scope_key(claim))


def detect_conflicts(claims: List[ClaimDraft]) -> List[ClaimDraft]:
    groups: Dict[Tuple[str, str, str, str, str], List[ClaimDraft]] = defaultdict(list)
    for claim in claims:
        if claim.category in CONFLICT_CATEGORIES and claim.value:
            if str(claim.value).lower() != "not publicly available":
                groups[_group_key(claim)].append(claim)

    for grouped_claims in groups.values():
        values = {claim.value for claim in grouped_claims if claim.value}
        if len(values) <= 1:
            continue
        for claim in grouped_claims:
            claim.verification_status = VerificationStatus.CONFLICTING
            claim.confidence_score = min(claim.confidence_score, 0.52)
            claim.evidence_notes = (
                "Multiple sources report different values; the platform preserves the conflict "
                "instead of choosing a single unsupported fact."
            )

    return claims


def conflicting_claims(claims: List[ClaimDraft]) -> List[ClaimDraft]:
    return [claim for claim in claims if claim.verification_status == VerificationStatus.CONFLICTING]
