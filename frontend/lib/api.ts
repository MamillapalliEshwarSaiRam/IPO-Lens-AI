import type {
  AgentToolPolicyResponse,
  HealthResponse,
  MonitoringAlert,
  ReportDetail,
  ResearchStartResponse,
  WatchlistItem
} from "@/types/api";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001";

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    cache: "no-store"
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function startResearch(companyName: string): Promise<ResearchStartResponse> {
  return jsonFetch<ResearchStartResponse>("/api/research", {
    method: "POST",
    body: JSON.stringify({
      company_name: companyName,
      prompt: `Analyze ${companyName} IPO readiness`,
      use_mock_data: false
    })
  });
}

export async function getReport(reportId: string): Promise<ReportDetail> {
  return jsonFetch<ReportDetail>(`/api/reports/${reportId}`);
}

export async function getReports(): Promise<ReportDetail[]> {
  return jsonFetch<ReportDetail[]>("/api/reports");
}

export async function getHealth(): Promise<HealthResponse> {
  return jsonFetch<HealthResponse>("/api/health");
}

export async function getAgentToolPolicy(): Promise<AgentToolPolicyResponse> {
  return jsonFetch<AgentToolPolicyResponse>("/api/agents/tools");
}

export async function getWatchlist(): Promise<WatchlistItem[]> {
  return jsonFetch<WatchlistItem[]>("/api/watchlist");
}

export async function getMonitoringAlerts(): Promise<MonitoringAlert[]> {
  return jsonFetch<MonitoringAlert[]>("/api/monitoring-alerts");
}

export async function addWatchlist(companyName: string): Promise<WatchlistItem> {
  return jsonFetch<WatchlistItem>("/api/watchlist", {
    method: "POST",
    body: JSON.stringify({ company_name: companyName, frequency: "weekly" })
  });
}

export async function deleteWatchlist(companyId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/watchlist/${companyId}`, {
    method: "DELETE",
    cache: "no-store"
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }
}

export async function runWatchlistCheck(companyId: string): Promise<ResearchStartResponse> {
  return jsonFetch<ResearchStartResponse>(`/api/watchlist/${companyId}/run-check`, {
    method: "POST"
  });
}

export function researchEventsUrl(runId: string): string {
  return `${API_BASE}/api/research/${runId}/events`;
}
