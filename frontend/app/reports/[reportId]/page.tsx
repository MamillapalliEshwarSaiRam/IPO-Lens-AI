"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Building2, ExternalLink, Landmark } from "lucide-react";

import { EvidenceTable } from "@/components/evidence-table";
import { ReportCard } from "@/components/report-card";
import { ScoreGauge } from "@/components/score-gauge";
import { ConfidenceBadge, StatusBadge } from "@/components/status-badge";
import { SourceQuality } from "@/components/source-quality";
import { getReport } from "@/lib/api";
import type { Claim, ReportDetail } from "@/types/api";

export default function ReportPage({ params }: { params: { reportId: string } }) {
  const [detail, setDetail] = useState<ReportDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getReport(params.reportId).then(setDetail).catch((err) => {
      setError(err instanceof Error ? err.message : "Unable to load report.");
    });
  }, [params.reportId]);

  const claimsByStatus = useMemo(() => {
    const map: Record<string, Claim[]> = {};
    for (const claim of detail?.claims ?? []) {
      map[claim.verification_status] = [...(map[claim.verification_status] ?? []), claim];
    }
    return map;
  }, [detail]);

  if (error) {
    return <div className="rounded border border-red-200 bg-red-50 p-5 text-red-800">{error}</div>;
  }

  if (!detail) {
    return <div className="rounded border border-zinc-200 bg-white p-5 text-graphite">Loading report.</div>;
  }

  const { report, company, claims, sources } = detail;
  const breakdown = report.score_breakdown as Record<string, unknown>;
  const marketStatus = company.is_public
    ? {
        icon: Landmark,
        eyebrow: "Market status",
        label: `Publicly traded${company.ticker ? ` · ${company.ticker}` : ""}`,
        description: "This company appears to already be trading on the public market.",
        detail: company.cik ? `SEC identity available under CIK ${company.cik}.` : "Trading status confirmed from available evidence.",
        className: "border-mint/30 bg-[linear-gradient(135deg,rgba(15,118,110,0.14),rgba(255,255,255,0.94))] text-emerald-950",
        iconClassName: "border-mint/30 bg-white/75 text-mint",
        pillClassName: "bg-mint text-white",
      }
    : {
        icon: Building2,
        eyebrow: "Market status",
        label: "Not publicly traded",
        description: "This company is not currently being traded publicly based on the available evidence.",
        detail: company.cik
          ? `A public-market ticker was not confirmed${company.cik ? ` for CIK ${company.cik}` : ""}.`
          : "No confirmed public-market ticker was found from the current identity checks.",
        className: "border-zinc-300 bg-[linear-gradient(135deg,rgba(244,244,245,0.98),rgba(228,228,231,0.8))] text-zinc-900",
        iconClassName: "border-zinc-300 bg-white/80 text-zinc-700",
        pillClassName: "bg-zinc-900 text-white",
      };
  const MarketStatusIcon = marketStatus.icon;

  return (
    <div className="space-y-6">
      <Link href="/" className="inline-flex items-center gap-2 text-sm font-semibold text-graphite hover:text-ink">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Dashboard
      </Link>

      <section className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
        <div className="rounded border border-zinc-200 bg-white p-5 shadow-panel">
          <ScoreGauge score={report.ipo_readiness_score} />
          <div className="mt-5 flex flex-wrap gap-2">
            <ConfidenceBadge level={report.confidence_level} />
            <span className="rounded bg-zinc-100 px-2 py-1 text-xs font-semibold text-zinc-700">
              {report.report_status}
            </span>
          </div>
        </div>
        <div>
          <p className="text-sm font-semibold uppercase tracking-normal text-signal">IPO readiness report</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-normal text-ink">{company.name}</h1>
          <p className="mt-3 max-w-4xl text-sm leading-6 text-graphite">{report.executive_summary}</p>
          <div className={`mt-4 rounded-lg border p-4 shadow-sm ${marketStatus.className}`}>
            <div className="flex items-start gap-4">
              <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-lg border ${marketStatus.iconClassName}`}>
                <MarketStatusIcon className="h-5 w-5" aria-hidden="true" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[11px] font-semibold uppercase tracking-[0.08em] opacity-70">
                    {marketStatus.eyebrow}
                  </span>
                  <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.08em] ${marketStatus.pillClassName}`}>
                    {company.is_public ? "Live ticker" : "Private status"}
                  </span>
                </div>
                <div className="mt-2 text-base font-semibold">{marketStatus.label}</div>
                <p className="mt-1 text-sm leading-6 opacity-90">{marketStatus.description}</p>
                <p className="mt-2 text-xs font-medium opacity-75">{marketStatus.detail}</p>
              </div>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-3 text-sm text-graphite">
            {company.sector && <span>Sector: {company.sector}</span>}
            {company.website && (
              <a className="inline-flex items-center gap-1 font-medium text-signal hover:underline" href={company.website} target="_blank" rel="noreferrer">
                Company website
                <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
              </a>
            )}
            <span>{company.is_public ? "Public company" : "Private company"}</span>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3 xl:grid-cols-5">
        <Metric label="Verified" value={claimsByStatus.verified?.length ?? 0} tone="text-mint" />
        <Metric label="Estimated" value={claimsByStatus.estimated?.length ?? 0} tone="text-caution" />
        <Metric label="Conflicting" value={claimsByStatus.conflicting?.length ?? 0} tone="text-ember" />
        <Metric label="Unavailable" value={claimsByStatus.not_publicly_available?.length ?? 0} tone="text-zinc-600" />
        <Metric label="Unsupported" value={claimsByStatus.unsupported?.length ?? 0} tone="text-danger" />
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <ReportCard title="Score breakdown">
          <div className="space-y-3">
            <Breakdown label="Financial maturity" value={breakdown.financial_maturity} max={25} />
            <Breakdown label="Market position" value={breakdown.market_position} max={20} />
            <Breakdown label="Governance and filing" value={breakdown.governance_and_filing_readiness} max={15} />
            <Breakdown label="Risk profile" value={breakdown.risk_profile} max={20} />
            <Breakdown label="IPO signals" value={breakdown.ipo_signals} max={10} />
            <Breakdown label="Evidence quality" value={breakdown.evidence_quality} max={10} />
          </div>
          {Array.isArray(breakdown.caps_applied) && breakdown.caps_applied.length > 0 && (
            <div className="mt-5 rounded border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-900">
              {breakdown.caps_applied.join(" ")}
            </div>
          )}
        </ReportCard>

        <ReportCard title="Source quality breakdown">
          <SourceQuality sources={sources} />
        </ReportCard>
      </section>

      <ReportCard title="Key claims">
        <div className="grid gap-3 md:grid-cols-2">
          {claims.slice(0, 8).map((claim) => (
            <div key={claim.id} className="rounded border border-zinc-200 p-4">
              <div className="mb-3">
                <StatusBadge status={claim.verification_status} />
              </div>
              <p className="text-sm leading-6 text-ink">{claim.text}</p>
              <p className="mt-3 text-xs text-zinc-500">{claim.evidence_notes}</p>
            </div>
          ))}
        </div>
      </ReportCard>

      <ReportCard title="Evidence table">
        <EvidenceTable claims={claims} sources={sources} />
      </ReportCard>

      <section className="grid gap-6 lg:grid-cols-2">
        <ReportCard title="Financial signals">
          <SectionList values={report.sections.financial_signals ?? []} />
        </ReportCard>
        <ReportCard title="Market & competitors">
          <SectionList values={report.sections.market_and_competitors ?? []} />
        </ReportCard>
        <ReportCard title="Risk analysis">
          <SectionList values={report.sections.risk_analysis ?? report.key_risks} />
        </ReportCard>
        <ReportCard title="Bull case / Bear case">
          <div className="space-y-4 text-sm leading-6 text-graphite">
            <p>
              <span className="font-semibold text-ink">Bull case: </span>
              {report.bull_case}
            </p>
            <p>
              <span className="font-semibold text-ink">Bear case: </span>
              {report.bear_case}
            </p>
          </div>
        </ReportCard>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <ReportCard title="Conflicting claims">
          <SectionList values={report.sections.conflicting_claims ?? []} empty="No conflicting claims found." />
        </ReportCard>
        <ReportCard title="Unavailable data">
          <SectionList values={report.unavailable_data ?? []} empty="No unavailable data was flagged." />
        </ReportCard>
      </section>
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="rounded border border-zinc-200 bg-white p-4 shadow-panel">
      <div className={`text-3xl font-semibold ${tone}`}>{value}</div>
      <div className="mt-1 text-sm font-medium text-graphite">{label}</div>
    </div>
  );
}

function Breakdown({ label, value, max }: { label: string; value: unknown; max: number }) {
  const numeric = typeof value === "number" ? value : 0;
  return (
    <div>
      <div className="flex justify-between gap-3 text-sm">
        <span className="font-medium text-ink">{label}</span>
        <span className="text-graphite">
          {numeric}/{max}
        </span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded bg-zinc-100">
        <div className="h-full rounded bg-signal" style={{ width: `${Math.min(100, (numeric / max) * 100)}%` }} />
      </div>
    </div>
  );
}

function SectionList({ values, empty }: { values: string[]; empty?: string }) {
  if (!values || values.length === 0) {
    return <p className="text-sm text-graphite">{empty ?? "No entries available."}</p>;
  }
  return (
    <ul className="space-y-3 text-sm leading-6 text-graphite">
      {values.map((value, index) => (
        <li key={`${value}-${index}`} className="rounded border border-zinc-200 p-3">
          {value}
        </li>
      ))}
    </ul>
  );
}
