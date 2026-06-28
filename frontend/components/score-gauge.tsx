import { Gauge } from "lucide-react";

export function ScoreGauge({ score }: { score?: number | null }) {
  if (score === null || score === undefined) {
    return (
      <div className="flex items-center gap-4">
        <div className="flex h-20 w-20 items-center justify-center rounded border border-zinc-200 bg-white">
          <Gauge className="h-9 w-9 text-zinc-500" aria-hidden="true" />
        </div>
        <div>
          <div className="text-5xl font-semibold tracking-normal text-ink">N/A</div>
          <div className="mt-1 text-sm font-medium text-graphite">IPO readiness score not applicable</div>
        </div>
      </div>
    );
  }
  const value = score ?? 0;
  const tone = value >= 75 ? "text-mint" : value >= 50 ? "text-caution" : "text-danger";
  return (
    <div className="flex items-center gap-4">
      <div className="flex h-20 w-20 items-center justify-center rounded border border-zinc-200 bg-white">
        <Gauge className={`h-9 w-9 ${tone}`} aria-hidden="true" />
      </div>
      <div>
        <div className="text-5xl font-semibold tracking-normal text-ink">{value}</div>
        <div className="mt-1 text-sm font-medium text-graphite">IPO readiness score out of 100</div>
      </div>
    </div>
  );
}
