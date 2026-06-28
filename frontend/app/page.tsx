"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  ArrowRight,
  Bell,
  Database,
  FileText,
  Play,
  Search,
  Server,
  ShieldCheck,
  Trash2,
  X
} from "lucide-react";

import {
  addWatchlist,
  deleteWatchlist,
  getAgentToolPolicy,
  getHealth,
  getMonitoringAlerts,
  getReports,
  getWatchlist,
  runWatchlistCheck,
  startResearch
} from "@/lib/api";
import type { AgentToolPolicyResponse, HealthResponse, MonitoringAlert, ReportDetail, WatchlistItem } from "@/types/api";

export default function DashboardPage() {
  const router = useRouter();
  const [companyName, setCompanyName] = useState("Anthropic");
  const [watchName, setWatchName] = useState("Anthropic");
  const [reports, setReports] = useState<ReportDetail[]>([]);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [alerts, setAlerts] = useState<MonitoringAlert[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [toolPolicy, setToolPolicy] = useState<AgentToolPolicyResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dismissedAlertIds, setDismissedAlertIds] = useState<string[]>([]);

  const notificationAlerts = useMemo(
    () =>
      alerts.filter(
        (alert) =>
          !alert.acknowledged &&
          alert.alert_type !== "baseline_created" &&
          !dismissedAlertIds.includes(alert.id)
      ),
    [alerts, dismissedAlertIds]
  );
  const notificationAlert = notificationAlerts[0];

  useEffect(() => {
    void refreshDashboard();
  }, []);

  async function refreshDashboard() {
    const [reportData, watchData, alertData, healthData, policyData] = await Promise.allSettled([
      getReports(),
      getWatchlist(),
      getMonitoringAlerts(),
      getHealth(),
      getAgentToolPolicy()
    ]);
    if (reportData.status === "fulfilled") setReports(reportData.value);
    if (watchData.status === "fulfilled") setWatchlist(watchData.value);
    if (alertData.status === "fulfilled") setAlerts(alertData.value);
    if (healthData.status === "fulfilled") setHealth(healthData.value);
    if (policyData.status === "fulfilled") setToolPolicy(policyData.value);
  }

  async function submitResearch(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const response = await startResearch(companyName);
      router.push(`/research/${response.run_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to start research.");
    } finally {
      setLoading(false);
    }
  }

  async function submitWatchlist(event: FormEvent) {
    event.preventDefault();
    await addWatchlist(watchName);
    await refreshDashboard();
  }

  async function checkNow(companyId: string) {
    const response = await runWatchlistCheck(companyId);
    router.push(`/research/${response.run_id}`);
  }

  async function removeWatchlist(companyId: string) {
    await deleteWatchlist(companyId);
    await refreshDashboard();
  }

  return (
    <div className="space-y-8">
      <section className="grid gap-6 lg:grid-cols-[1.35fr_0.65fr]">
        <div>
          <p className="text-sm font-semibold uppercase tracking-normal text-signal">Analyst dashboard</p>
          <h1 className="mt-3 max-w-4xl text-4xl font-semibold tracking-normal text-ink">
            IPO readiness research that shows its evidence.
          </h1>
          <p className="mt-4 max-w-3xl text-base leading-7 text-graphite">
            Run multi-agent company research with claim-level verification, source quality scoring,
            conflict detection, and explicit unavailable-data handling.
          </p>
        </div>
        <div className="rounded border border-zinc-200 bg-white p-5 shadow-panel">
          <div className="flex items-center gap-2 text-sm font-semibold text-ink">
            <Server className="h-4 w-4 text-mint" aria-hidden="true" />
            API/source health
          </div>
          <div className="mt-4 space-y-2 text-sm">
            <HealthRow label="Database" value={health?.database ?? "unknown"} />
            <HealthRow label="LangGraph" value={health?.langgraph_available ? "available" : "not installed"} />
            {health &&
              Object.entries(health.providers).map(([provider, status]) => (
                <HealthRow key={provider} label={provider.replace(/_/g, " ")} value={status} />
              ))}
          </div>
        </div>
      </section>

      {notificationAlert && (
        <NotificationBanner
          alert={notificationAlert}
          alertCount={notificationAlerts.length}
          onDismiss={() =>
            setDismissedAlertIds((current) =>
              current.includes(notificationAlert.id)
                ? current
                : [...current, notificationAlert.id]
            )
          }
          onOpen={() => router.push(`/reports/${notificationAlert.report_id}`)}
        />
      )}

      <section className="rounded border border-zinc-200 bg-white p-5 shadow-panel">
        <div className="mb-4 flex items-center gap-2">
          <Search className="h-5 w-5 text-signal" aria-hidden="true" />
          <h2 className="text-lg font-semibold text-ink">Search company</h2>
        </div>
        <form className="flex flex-col gap-3 sm:flex-row" onSubmit={submitResearch}>
          <input
            className="focus-ring min-h-12 flex-1 rounded border border-zinc-300 bg-white px-4 text-base text-ink"
            value={companyName}
            onChange={(event) => setCompanyName(event.target.value)}
            placeholder="SpaceX, Anthropic, OpenAI, Stripe, Databricks"
          />
          <button
            className="focus-ring inline-flex min-h-12 items-center justify-center gap-2 rounded bg-ink px-5 font-semibold text-white disabled:cursor-not-allowed disabled:bg-zinc-400"
            disabled={loading || !companyName.trim()}
            type="submit"
          >
            {loading ? "Starting" : "Run research"}
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </button>
        </form>
        {error && <p className="mt-3 text-sm font-medium text-danger">{error}</p>}
      </section>

      <section className="rounded border border-zinc-200 bg-white p-5 shadow-panel">
        <div className="mb-4 flex items-center gap-2">
          <ShieldCheck className="h-5 w-5 text-mint" aria-hidden="true" />
          <h2 className="text-lg font-semibold text-ink">Agent tool policy</h2>
        </div>
        <div className="grid gap-3 lg:grid-cols-2">
          {toolPolicy ? (
            Object.entries(toolPolicy.agents).map(([agentName, tools]) => (
              <div key={agentName} className="rounded border border-zinc-200 p-4">
                <div className="font-semibold text-ink">{agentName}</div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {tools.map((tool) => (
                    <span
                      key={`${agentName}-${tool.provider}-${tool.tool_name}`}
                      className="rounded border border-zinc-200 bg-zinc-50 px-2 py-1 text-xs font-medium text-graphite"
                      title={tool.purpose}
                    >
                      {tool.provider.replace(/_/g, " ")} · {tool.tool_name.replace(/_/g, " ")}
                    </span>
                  ))}
                </div>
                <p className="mt-3 text-xs leading-5 text-zinc-500">
                  {tools[0]?.evidence_role ?? "Configured evidence policy."}
                </p>
              </div>
            ))
          ) : (
            <p className="text-sm text-graphite">Tool policy loading from the backend.</p>
          )}
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="rounded border border-zinc-200 bg-white p-5 shadow-panel">
          <div className="mb-4 flex items-center gap-2">
            <FileText className="h-5 w-5 text-signal" aria-hidden="true" />
            <h2 className="text-lg font-semibold text-ink">Recent research reports</h2>
          </div>
          <div className="space-y-3">
            {reports.length === 0 ? (
              <p className="text-sm text-graphite">No reports yet. Run Anthropic to start live provider research.</p>
            ) : (
              reports.map((item) => (
                <button
                  key={item.report.id}
                  className="focus-ring flex w-full items-center justify-between gap-4 rounded border border-zinc-200 p-4 text-left hover:border-signal"
                  onClick={() => router.push(`/reports/${item.report.id}`)}
                >
                  <div>
                    <div className="font-semibold text-ink">{item.company.name}</div>
                    <div className="mt-1 text-sm text-graphite">
                      Score {item.report.ipo_readiness_score ?? "N/A"} · {item.report.confidence_level ?? "Low"} confidence
                    </div>
                  </div>
                  <ArrowRight className="h-4 w-4 text-zinc-500" aria-hidden="true" />
                </button>
              ))
            )}
          </div>
        </div>

        <div className="rounded border border-zinc-200 bg-white p-5 shadow-panel">
          <div className="mb-4 flex items-center gap-2">
            <Bell className="h-5 w-5 text-ember" aria-hidden="true" />
            <h2 className="text-lg font-semibold text-ink">Watchlist</h2>
          </div>
          <form className="mb-4 flex gap-2" onSubmit={submitWatchlist}>
            <input
              className="focus-ring min-h-11 flex-1 rounded border border-zinc-300 px-3 text-sm"
              value={watchName}
              onChange={(event) => setWatchName(event.target.value)}
              placeholder="Company to monitor"
            />
            <button className="focus-ring inline-flex min-h-11 items-center gap-2 rounded bg-signal px-4 text-sm font-semibold text-white">
              Add
            </button>
          </form>
          <div className="space-y-3">
            {watchlist.length === 0 ? (
              <p className="text-sm text-graphite">No monitored companies yet.</p>
            ) : (
              watchlist.map((item) => (
                <div key={item.id} className="flex items-center justify-between gap-3 rounded border border-zinc-200 p-4">
                  <div>
                    <div className="font-semibold text-ink">{item.company?.name ?? item.company_id}</div>
                    <div className="mt-1 text-sm text-graphite">
                      Frequency: {item.frequency}
                      {item.last_checked_at ? ` · Last checked ${new Date(item.last_checked_at).toLocaleDateString()}` : ""}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <button
                      className="focus-ring inline-flex items-center gap-2 rounded border border-zinc-300 px-3 py-2 text-sm font-semibold text-ink hover:border-signal"
                      onClick={() => checkNow(item.company_id)}
                    >
                      <Play className="h-4 w-4" aria-hidden="true" />
                      Check now
                    </button>
                    <button
                      className="focus-ring inline-flex h-10 w-10 items-center justify-center rounded border border-zinc-300 text-zinc-600 hover:border-danger hover:text-danger"
                      onClick={() => removeWatchlist(item.company_id)}
                      title="Remove from watchlist"
                      type="button"
                    >
                      <Trash2 className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </section>

      <section className="rounded border border-zinc-200 bg-white p-5 shadow-panel">
        <div className="mb-3 flex items-center gap-2">
          <Database className="h-5 w-5 text-mint" aria-hidden="true" />
          <h2 className="text-lg font-semibold text-ink">Monitoring alerts</h2>
        </div>
        <div className="space-y-3">
          {alerts.length === 0 ? (
            <p className="text-sm leading-6 text-graphite">
              No monitoring alerts yet. Run a watchlist check to create a baseline, then run it again to detect material changes.
            </p>
          ) : (
            alerts.slice(0, 6).map((alert) => (
              <button
                key={alert.id}
                className="focus-ring block w-full rounded border border-zinc-200 p-4 text-left hover:border-signal"
                onClick={() => router.push(`/reports/${alert.report_id}`)}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`rounded px-2 py-1 text-xs font-semibold uppercase tracking-normal ${alert.severity === "high" ? "bg-red-100 text-red-800" : alert.severity === "medium" ? "bg-amber-100 text-amber-900" : "bg-zinc-100 text-zinc-700"}`}>
                    {alert.severity}
                  </span>
                  <span className="text-xs font-medium uppercase tracking-normal text-zinc-500">
                    {alert.alert_type.replace(/_/g, " ")}
                  </span>
                  <span className="text-xs text-zinc-400">{new Date(alert.created_at).toLocaleString()}</span>
                </div>
                <div className="mt-2 font-semibold text-ink">{alert.title}</div>
                <p className="mt-1 line-clamp-2 text-sm leading-6 text-graphite">{alert.description}</p>
              </button>
            ))
          )}
        </div>
      </section>
    </div>
  );
}

function HealthRow({ label, value }: { label: string; value: string }) {
  const isGood = value === "ok" || value === "configured" || value === "available";
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="capitalize text-graphite">{label}</span>
      <span className={`rounded px-2 py-1 text-xs font-semibold ${isGood ? "bg-emerald-100 text-emerald-800" : "bg-zinc-100 text-zinc-700"}`}>
        {value}
      </span>
    </div>
  );
}

function NotificationBanner({
  alert,
  alertCount,
  onDismiss,
  onOpen
}: {
  alert: MonitoringAlert;
  alertCount: number;
  onDismiss: () => void;
  onOpen: () => void;
}) {
  const severityClass =
    alert.severity === "high"
      ? "border-red-200 bg-red-50 text-red-900"
      : alert.severity === "medium"
        ? "border-amber-200 bg-amber-50 text-amber-950"
        : "border-zinc-200 bg-white text-ink";
  const iconClass =
    alert.severity === "high"
      ? "text-danger"
      : alert.severity === "medium"
        ? "text-caution"
        : "text-zinc-600";

  return (
    <section className={`rounded border p-4 shadow-panel ${severityClass}`}>
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <button className="focus-ring flex min-w-0 flex-1 items-start gap-3 rounded text-left" onClick={onOpen}>
          <AlertTriangle className={`mt-1 h-5 w-5 shrink-0 ${iconClass}`} aria-hidden="true" />
          <span className="min-w-0">
            <span className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold uppercase tracking-normal">
                {alert.severity} monitoring alert
              </span>
              {alertCount > 1 && (
                <span className="rounded border border-current px-2 py-0.5 text-xs font-semibold">
                  {alertCount} active
                </span>
              )}
            </span>
            <span className="mt-1 block font-semibold text-ink">{alert.title}</span>
            <span className="mt-1 line-clamp-2 block text-sm leading-6 text-graphite">
              {alert.description}
            </span>
          </span>
        </button>
        <button
          className="focus-ring inline-flex h-10 w-10 shrink-0 items-center justify-center rounded border border-current/30 hover:bg-white/60"
          onClick={onDismiss}
          title="Dismiss alert"
          type="button"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </section>
  );
}
