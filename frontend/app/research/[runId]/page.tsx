"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, AlertTriangle, RefreshCw } from "lucide-react";

import { ProgressTimeline } from "@/components/progress-timeline";
import { getReport, researchEventsUrl } from "@/lib/api";
import type { ProgressEvent, ReportDetail } from "@/types/api";

export default function ResearchRunPage({ params }: { params: { runId: string } }) {
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [report, setReport] = useState<ReportDetail | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);

  useEffect(() => {
    let poll: ReturnType<typeof setInterval> | undefined;
    let closed = false;

    async function loadReport() {
      try {
        const data = await getReport(params.runId);
        if (closed) return;
        setReport(data);
        if (data.report.report_status !== "running" && poll) {
          clearInterval(poll);
        }
      } catch {
        // The report may not exist yet if the user refreshed before completion.
      }
    }

    const eventSource = new EventSource(researchEventsUrl(params.runId));
    eventSource.onmessage = (message) => {
      const event = JSON.parse(message.data) as ProgressEvent;
      setEvents((current) => [...current, event]);
      if (event.metadata.terminal) {
        eventSource.close();
        void loadReport();
      }
    };
    eventSource.addEventListener("progress", (message) => {
      const event = JSON.parse((message as MessageEvent).data) as ProgressEvent;
      setEvents((current) => [...current, event]);
      if (event.metadata.terminal) {
        eventSource.close();
        void loadReport();
      }
    });
    eventSource.onerror = () => {
      setStreamError("Live event stream disconnected. The run may still complete.");
      eventSource.close();
      void loadReport();
    };
    void loadReport();
    poll = setInterval(() => {
      void loadReport();
    }, 2000);
    return () => {
      closed = true;
      eventSource.close();
      if (poll) clearInterval(poll);
    };
  }, [params.runId]);

  const degraded = useMemo(
    () => events.some((event) => Boolean(event.metadata.degraded) || event.status === "failed"),
    [events]
  );
  const reportSummaryTitle =
    report?.report.report_status === "completed"
      ? "Final report summary"
      : report?.report.report_status === "failed"
        ? "Failure summary"
        : report?.report.report_status === "partial"
          ? "Partial report summary"
          : "Partial result summary";

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm font-semibold uppercase tracking-normal text-signal">Research run</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-normal text-ink">Live agent progress</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-graphite">
            Independent data gathering runs first, then claim extraction, verification, conflict detection,
            scoring, and final report writing.
          </p>
        </div>
        {report && (
          <Link
            href={`/reports/${report.report.id}`}
            className="focus-ring inline-flex min-h-11 items-center justify-center gap-2 rounded bg-ink px-4 font-semibold text-white"
          >
            Open report
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        )}
      </div>

      {degraded && (
        <div className="flex gap-3 rounded border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <p>One or more sources failed. The workflow is continuing with degraded confidence.</p>
        </div>
      )}

      {streamError && (
        <div className="rounded border border-zinc-200 bg-white p-4 text-sm text-graphite">{streamError}</div>
      )}

      <section className="rounded border border-zinc-200 bg-white p-5 shadow-panel">
        {events.length === 0 ? (
          report && report.report.report_status !== "running" ? (
            <div className="flex flex-col gap-2 text-graphite">
              <div className="font-medium text-ink">Report is ready.</div>
              <p className="text-sm leading-6">
                Live event history was not available for this run, so the page recovered from the
                persisted report record.
              </p>
            </div>
          ) : (
            <div className="flex items-center gap-3 text-graphite">
              <RefreshCw className="h-5 w-5 animate-spin text-signal" aria-hidden="true" />
              Waiting for the first agent update.
            </div>
          )
        ) : (
          <ProgressTimeline events={events} />
        )}
      </section>

      {report && (
        <section className="rounded border border-zinc-200 bg-white p-5 shadow-panel">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-lg font-semibold text-ink">{reportSummaryTitle}</h2>
            <span className="rounded border border-zinc-200 px-2 py-1 text-xs font-semibold uppercase tracking-normal text-graphite">
              {report.report.report_status}
            </span>
          </div>
          <p className="mt-3 text-sm leading-6 text-graphite">{report.report.executive_summary}</p>
        </section>
      )}
    </div>
  );
}
