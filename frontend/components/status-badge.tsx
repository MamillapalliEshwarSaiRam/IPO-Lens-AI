import type { VerificationStatus } from "@/types/api";

const statusStyles: Record<VerificationStatus, string> = {
  verified: "bg-emerald-100 text-emerald-800 border-emerald-200",
  estimated: "bg-amber-100 text-amber-800 border-amber-200",
  unsupported: "bg-red-100 text-red-800 border-red-200",
  not_publicly_available: "bg-zinc-200 text-zinc-700 border-zinc-300",
  conflicting: "bg-orange-100 text-orange-800 border-orange-200"
};

const statusLabels: Record<VerificationStatus, string> = {
  verified: "Verified",
  estimated: "Estimated",
  unsupported: "Unsupported",
  not_publicly_available: "Not publicly available",
  conflicting: "Conflicting"
};

export function StatusBadge({ status }: { status: VerificationStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded px-2 py-1 text-xs font-semibold ring-1 ring-inset ${statusStyles[status]}`}
    >
      {statusLabels[status]}
    </span>
  );
}

export function ConfidenceBadge({ level }: { level?: string | null }) {
  const normalized = level ?? "Low";
  const style =
    normalized === "High"
      ? "bg-emerald-100 text-emerald-800 border-emerald-200"
      : normalized === "Medium"
        ? "bg-amber-100 text-amber-800 border-amber-200"
        : "bg-red-100 text-red-800 border-red-200";
  return (
    <span className={`inline-flex items-center rounded px-2 py-1 text-xs font-semibold ring-1 ring-inset ${style}`}>
      {normalized} confidence
    </span>
  );
}

