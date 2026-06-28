export type VerificationStatus =
  | "verified"
  | "estimated"
  | "unsupported"
  | "not_publicly_available"
  | "conflicting";

export type ConfidenceLevel = "High" | "Medium" | "Low";

export type AgentStatus = "pending" | "running" | "completed" | "failed" | "skipped";

export interface Company {
  id: string;
  name: string;
  website?: string | null;
  sector?: string | null;
  is_public: boolean;
  ticker?: string | null;
  cik?: string | null;
  description?: string | null;
}

export interface Source {
  id: string;
  company_id?: string | null;
  url: string;
  title: string;
  publisher?: string | null;
  published_date?: string | null;
  retrieved_at?: string | null;
  source_type: string;
  source_quality_score: number;
}

export interface Claim {
  id: string;
  company_id: string;
  text: string;
  category: string;
  value?: string | null;
  unit?: string | null;
  date_context?: string | null;
  source_ids: string[];
  verification_status: VerificationStatus;
  confidence_score: number;
  evidence_notes?: string | null;
  created_at: string;
}

export interface ResearchReport {
  id: string;
  company_id: string;
  created_at: string;
  report_status: "running" | "completed" | "failed" | "partial";
  executive_summary?: string | null;
  ipo_readiness_score?: number | null;
  confidence_level?: ConfidenceLevel | null;
  bull_case?: string | null;
  bear_case?: string | null;
  key_risks: string[];
  key_claim_ids: string[];
  source_ids: string[];
  score_breakdown: Record<string, unknown>;
  sections: Record<string, string[]>;
  unavailable_data: string[];
  conflicting_claim_ids: string[];
}

export interface AgentRun {
  id: string;
  report_id: string;
  agent_name: string;
  status: AgentStatus;
  started_at: string;
  completed_at?: string | null;
  duration_ms?: number | null;
  input_summary?: string | null;
  output_summary?: string | null;
  error_message?: string | null;
  token_estimate: number;
  cost_estimate: number;
}

export interface ReportDetail {
  report: ResearchReport;
  company: Company;
  claims: Claim[];
  sources: Source[];
  agent_runs: AgentRun[];
}

export interface ResearchStartResponse {
  run_id: string;
  report_id: string;
  status: "running" | "completed" | "failed" | "partial";
  message: string;
}

export interface ProgressEvent {
  run_id: string;
  agent_name: string;
  status: AgentStatus;
  partial_result_summary: string;
  timestamp: string;
  metadata: Record<string, unknown>;
}

export interface HealthResponse {
  status: string;
  database: string;
  providers: Record<string, string>;
  langgraph_available: boolean;
}

export interface AgentToolPolicy {
  agent_name: string;
  provider: string;
  tool_name: string;
  purpose: string;
  evidence_role: string;
  source_quality: string;
  free_tier: boolean;
  suggested_alternatives: string[];
}

export interface AgentToolPolicyResponse {
  agents: Record<string, AgentToolPolicy[]>;
}

export interface WatchlistItem {
  id: string;
  company_id: string;
  company?: Company | null;
  created_at: string;
  frequency: string;
  last_checked_at?: string | null;
  next_check_at?: string | null;
  last_report_id?: string | null;
  last_error?: string | null;
  active: boolean;
}

export interface MonitoringAlert {
  id: string;
  company_id: string;
  watchlist_id?: string | null;
  report_id: string;
  previous_report_id?: string | null;
  created_at: string;
  alert_type: string;
  severity: "low" | "medium" | "high" | string;
  title: string;
  description: string;
  claim_ids: string[];
  alert_metadata: Record<string, unknown>;
  acknowledged: boolean;
  company?: Company | null;
}
