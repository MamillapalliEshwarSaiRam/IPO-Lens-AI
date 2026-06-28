import { ExternalLink } from "lucide-react";

import { StatusBadge } from "@/components/status-badge";
import type { Claim, Source } from "@/types/api";

export function EvidenceTable({ claims, sources }: { claims: Claim[]; sources: Source[] }) {
  const sourceById = new Map(sources.map((source) => [source.id, source]));
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-zinc-200 text-sm">
        <thead>
          <tr className="text-left text-xs font-semibold uppercase tracking-normal text-zinc-500">
            <th className="whitespace-nowrap py-3 pr-4">Claim</th>
            <th className="whitespace-nowrap px-4 py-3">Status</th>
            <th className="whitespace-nowrap px-4 py-3">Confidence</th>
            <th className="whitespace-nowrap px-4 py-3">Date Context</th>
            <th className="whitespace-nowrap px-4 py-3">Evidence</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100">
          {claims.map((claim) => (
            <tr key={claim.id} className="align-top">
              <td className="max-w-xl py-4 pr-4 leading-6 text-ink">{claim.text}</td>
              <td className="px-4 py-4">
                <StatusBadge status={claim.verification_status} />
              </td>
              <td className="whitespace-nowrap px-4 py-4 font-medium text-graphite">
                {Math.round(claim.confidence_score * 100)}%
              </td>
              <td className="px-4 py-4 text-graphite">{claim.date_context ?? "Not specified"}</td>
              <td className="min-w-64 px-4 py-4">
                <div className="space-y-2">
                  {claim.source_ids.length === 0 ? (
                    <span className="text-zinc-500">No source attached</span>
                  ) : (
                    claim.source_ids.map((sourceId) => {
                      const source = sourceById.get(sourceId);
                      if (!source) {
                        return (
                          <span key={sourceId} className="block text-zinc-500">
                            Missing source metadata
                          </span>
                        );
                      }
                      return (
                        <a
                          key={source.id}
                          className="inline-flex items-center gap-1 font-medium text-signal hover:underline"
                          href={source.url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {source.publisher ?? source.title}
                          <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                        </a>
                      );
                    })
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

