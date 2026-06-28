import type { ReactNode } from "react";

export function ReportCard({
  title,
  children,
  action
}: {
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section className="rounded border border-zinc-200 bg-white p-5 shadow-panel">
      <div className="mb-4 flex items-start justify-between gap-4">
        <h2 className="text-lg font-semibold tracking-normal text-ink">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

