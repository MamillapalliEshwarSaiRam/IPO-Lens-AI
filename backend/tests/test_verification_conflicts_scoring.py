from app.agents.conflicts import detect_conflicts
from app.agents.scoring import calculate_ipo_score
from app.agents.state import ClaimDraft, SourceDraft
from app.agents.verification import verify_claims
from app.core.enums import ClaimCategory, SourceType, VerificationStatus


def test_verification_marks_sec_unavailable_as_not_publicly_available() -> None:
    source = SourceDraft(
        source_id="sec-1",
        url="https://www.sec.gov/edgar/search/",
        title="SEC EDGAR",
        publisher="SEC",
        source_type=SourceType.SEC_FILING,
        source_quality_score=1.0,
    )
    claim = ClaimDraft(
        text="Anthropic revenue is not publicly available in official filings.",
        category=ClaimCategory.FINANCIAL,
        value="Not publicly available",
        source_ids=["sec-1"],
    )
    verified = verify_claims([claim], [source])[0]
    assert verified.verification_status == VerificationStatus.NOT_PUBLICLY_AVAILABLE
    assert verified.confidence_score >= 0.9


def test_conflict_detection_preserves_disagreement() -> None:
    claims = [
        ClaimDraft(
            text="Source A reported Anthropic at a $61.5B valuation.",
            category=ClaimCategory.VALUATION,
            value="61.5",
            unit="USD billions",
            verification_status=VerificationStatus.ESTIMATED,
            confidence_score=0.65,
        ),
        ClaimDraft(
            text="Source B reported Anthropic at a $60B valuation.",
            category=ClaimCategory.VALUATION,
            value="60",
            unit="USD billions",
            verification_status=VerificationStatus.ESTIMATED,
            confidence_score=0.6,
        ),
    ]
    updated = detect_conflicts(claims)
    assert {claim.verification_status for claim in updated} == {VerificationStatus.CONFLICTING}


def test_revenue_claims_with_different_period_basis_do_not_conflict() -> None:
    claims = [
        ClaimDraft(
            text="SEC company facts include a latest revenue fact of 109896000000 USD for period ending 2026-03-31.",
            category=ClaimCategory.FINANCIAL,
            value="109896000000",
            unit="USD",
            date_context="2026-03-31",
            verification_status=VerificationStatus.VERIFIED,
            confidence_score=0.95,
        ),
        ClaimDraft(
            text="Alpha Vantage reports Alphabet Inc.'s trailing twelve-month revenue as 422498009000.",
            category=ClaimCategory.FINANCIAL,
            value="422498009000",
            unit="USD",
            date_context="Current Alpha Vantage company overview",
            verification_status=VerificationStatus.ESTIMATED,
            confidence_score=0.72,
        ),
    ]

    updated = detect_conflicts(claims)

    assert {claim.verification_status for claim in updated} == {
        VerificationStatus.VERIFIED,
        VerificationStatus.ESTIMATED,
    }


def test_revenue_claims_for_same_period_can_conflict() -> None:
    claims = [
        ClaimDraft(
            text="SEC company facts include a latest revenue fact of 109896000000 USD for period ending 2026-03-31.",
            category=ClaimCategory.FINANCIAL,
            value="109896000000",
            unit="USD",
            date_context="2026-03-31",
            verification_status=VerificationStatus.VERIFIED,
            confidence_score=0.95,
        ),
        ClaimDraft(
            text="Another source reports revenue of 110000000000 USD for period ending 2026-03-31.",
            category=ClaimCategory.FINANCIAL,
            value="110000000000",
            unit="USD",
            date_context="2026-03-31",
            verification_status=VerificationStatus.ESTIMATED,
            confidence_score=0.72,
        ),
    ]

    updated = detect_conflicts(claims)

    assert {claim.verification_status for claim in updated} == {VerificationStatus.CONFLICTING}


def test_market_cap_and_private_valuation_do_not_conflict() -> None:
    claims = [
        ClaimDraft(
            text="Alpha Vantage reports Alphabet Inc.'s market capitalization as 4639851282000.",
            category=ClaimCategory.VALUATION,
            value="4639851282000",
            unit="USD",
            date_context="Current Alpha Vantage company overview",
            verification_status=VerificationStatus.ESTIMATED,
            confidence_score=0.72,
        ),
        ClaimDraft(
            text="A news report estimated the company's private valuation at $60B.",
            category=ClaimCategory.VALUATION,
            value="60",
            unit="USD billions",
            date_context="Current reporting",
            verification_status=VerificationStatus.ESTIMATED,
            confidence_score=0.6,
        ),
    ]

    updated = detect_conflicts(claims)

    assert {claim.verification_status for claim in updated} == {VerificationStatus.ESTIMATED}


def test_profit_margin_and_net_income_do_not_conflict() -> None:
    claims = [
        ClaimDraft(
            text="Alpha Vantage reports profit margin as 0.379.",
            category=ClaimCategory.FINANCIAL,
            value="0.379",
            unit="ratio",
            date_context="Current Alpha Vantage company overview",
            verification_status=VerificationStatus.ESTIMATED,
            confidence_score=0.72,
        ),
        ClaimDraft(
            text="SEC company facts include net income of 34540000000 USD for period ending 2026-03-31.",
            category=ClaimCategory.FINANCIAL,
            value="34540000000",
            unit="USD",
            date_context="2026-03-31",
            verification_status=VerificationStatus.VERIFIED,
            confidence_score=0.95,
        ),
    ]

    updated = detect_conflicts(claims)

    assert {claim.verification_status for claim in updated} == {
        VerificationStatus.ESTIMATED,
        VerificationStatus.VERIFIED,
    }


def test_funding_claims_for_different_rounds_do_not_conflict() -> None:
    claims = [
        ClaimDraft(
            text="The company raised $1B in a Series E round.",
            category=ClaimCategory.FUNDING,
            value="1",
            unit="USD billions",
            date_context="2024",
            verification_status=VerificationStatus.ESTIMATED,
            confidence_score=0.65,
        ),
        ClaimDraft(
            text="The company raised $2B in a Series F round.",
            category=ClaimCategory.FUNDING,
            value="2",
            unit="USD billions",
            date_context="2025",
            verification_status=VerificationStatus.ESTIMATED,
            confidence_score=0.65,
        ),
    ]

    updated = detect_conflicts(claims)

    assert {claim.verification_status for claim in updated} == {VerificationStatus.ESTIMATED}


def test_ipo_score_caps_when_financials_missing() -> None:
    claims = [
        ClaimDraft(
            text="Revenue is not publicly available.",
            category=ClaimCategory.FINANCIAL,
            value="Not publicly available",
            verification_status=VerificationStatus.NOT_PUBLICLY_AVAILABLE,
            confidence_score=0.95,
        ),
        ClaimDraft(
            text="Company has a verified official product page.",
            category=ClaimCategory.COMPANY_PROFILE,
            value="Product page",
            verification_status=VerificationStatus.VERIFIED,
            confidence_score=0.9,
        ),
        ClaimDraft(
            text="Company competes in a large market.",
            category=ClaimCategory.MARKET,
            value="Large market",
            verification_status=VerificationStatus.ESTIMATED,
            confidence_score=0.55,
        ),
    ]
    score = calculate_ipo_score(claims)
    assert score.total <= 65
    assert any("No official S-1" in cap for cap in score.caps_applied)


def test_ipo_score_caps_when_most_claims_unsupported() -> None:
    claims = [
        ClaimDraft(
            text=f"Unsupported claim {index}",
            category=ClaimCategory.MARKET,
            verification_status=VerificationStatus.UNSUPPORTED,
            confidence_score=0.1,
        )
        for index in range(4)
    ]
    claims.append(
        ClaimDraft(
            text="Verified official product claim.",
            category=ClaimCategory.COMPANY_PROFILE,
            verification_status=VerificationStatus.VERIFIED,
            confidence_score=0.9,
        )
    )
    score = calculate_ipo_score(claims)
    assert score.total <= 50
