import type { Source } from "@/types/api";

export function SourceQuality({ sources }: { sources: Source[] }) {
  return (
    <div className="space-y-3">
      {sources.map((source) => (
        <div key={source.id}>
          <div className="flex items-center justify-between gap-3 text-sm">
            <span className="font-medium text-ink">{source.publisher ?? source.title}</span>
            <span className="text-graphite">{Math.round(source.source_quality_score * 100)}%</span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded bg-zinc-100">
            <div
              className="h-full rounded bg-mint"
              style={{ width: `${Math.max(4, source.source_quality_score * 100)}%` }}
            />
          </div>
          <p className="mt-1 text-xs text-zinc-500">{source.source_type}</p>
        </div>
      ))}
    </div>
  );
}

