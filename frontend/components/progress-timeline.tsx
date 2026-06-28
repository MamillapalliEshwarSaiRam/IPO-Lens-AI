import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";

import type { ProgressEvent } from "@/types/api";

export function ProgressTimeline({ events }: { events: ProgressEvent[] }) {
  const timeline = collapseEventsByAgent(events);

  return (
    <div className="space-y-3">
      {timeline.map(({ event, updateCount }) => {
        const Icon =
          event.status === "completed"
            ? CheckCircle2
            : event.status === "failed"
              ? XCircle
              : event.status === "running"
                ? Loader2
                : Circle;
        const color =
          event.status === "completed"
            ? "text-mint"
            : event.status === "failed"
            ? "text-danger"
            : "text-signal";
        return (
          <div key={event.agent_name} className="flex gap-3">
            <Icon className={`mt-1 h-5 w-5 shrink-0 ${color} ${event.status === "running" ? "animate-spin" : ""}`} />
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-medium text-ink">{event.agent_name}</p>
                <p className="text-xs uppercase tracking-normal text-zinc-500">{event.status}</p>
                {updateCount > 1 && (
                  <p className="text-xs text-zinc-400">{updateCount} updates</p>
                )}
              </div>
              <p className="mt-1 text-sm leading-6 text-graphite">{event.partial_result_summary}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function collapseEventsByAgent(events: ProgressEvent[]) {
  const byAgent = new Map<string, { event: ProgressEvent; updateCount: number }>();
  const order: string[] = [];

  for (const event of events) {
    const current = byAgent.get(event.agent_name);
    if (!current) {
      order.push(event.agent_name);
      byAgent.set(event.agent_name, { event, updateCount: 1 });
    } else {
      byAgent.set(event.agent_name, {
        event,
        updateCount: current.updateCount + 1
      });
    }
  }

  return order.map((agentName) => byAgent.get(agentName)!);
}
