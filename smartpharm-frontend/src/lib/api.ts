import type {
  DashboardSummary, Patient, Batch, Drug, DsrRow, NetworkFacility,
  FinderResult, StockTransfer, User, StrategicBrief,
  KpiDashboard, RetentionPoint, StockoutProbability, ReorderPoint, RootCauseResult,
  DefaulterRiskResult, DefaulterReasonsResult, DefaulterTraceLog,
  FailureRiskResult, StockoutForecastResult, FundingScenarioResult, RedistributionResult,
  InterventionEffectivenessResult, WarehouseStatus,
} from "@/types";

export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api";

const TOKEN_KEY = "sp_tok";
const USER_KEY = "sp_user";

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}
export function setSession(token: string, user: User) {
  sessionStorage.setItem(TOKEN_KEY, token);
  sessionStorage.setItem(USER_KEY, JSON.stringify(user));
}
export function getUser(): User | null {
  const raw = sessionStorage.getItem(USER_KEY);
  return raw ? (JSON.parse(raw) as User) : null;
}
export function clearSession() {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
}

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(opts.headers as Record<string, string> | undefined),
  };
  const res = await fetch(`${API_URL}${path}`, { ...opts, headers });
  if (res.status === 401) {
    clearSession();
    window.location.href = "/login";
    throw new ApiError("Session expired", 401);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(body.detail ?? res.statusText, res.status);
  }
  if (res.status === 204) return {} as T;
  return res.json() as Promise<T>;
}

export const api = {
  // ── Auth ──────────────────────────────────────────────────
  provinces: () => request<{ name: string; code: string }[]>("/auth/provinces"),
  districts: (provinceCode: string) =>
    request<{ name: string; code: string }[]>(`/auth/districts?province_code=${provinceCode}`),
  facilities: (provinceCode: string, districtCode: string) =>
    request<{ id: number; name: string; dhis2_code: string; facility_type: string; district: string }[]>(
      `/auth/facilities?province_code=${provinceCode}&district_code=${districtCode}`
    ),
  login: (username: string, password: string, facility_id?: number) =>
    request<{ token: string; user: User }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password, facility_id }),
    }),
  logout: () => request("/auth/logout", { method: "POST" }),

  // ── Dashboard ─────────────────────────────────────────────
  dashboardSummary: () => request<DashboardSummary>("/dashboard/summary"),

  // ── Patients ──────────────────────────────────────────────
  patients: (params?: { search?: string; status?: string }) => {
    const qs = new URLSearchParams(params as Record<string, string>).toString();
    return request<Patient[]>(`/patients/${qs ? `?${qs}` : ""}`);
  },
  patient: (id: number) => request<Patient>(`/patients/${id}`),
  patientStats: (id: number) =>
    request<{
      vl_history: { result: number; date: string; suppressed: boolean }[];
      treatment_failure_bayesian: {
        posterior_probability: number;
        credible_interval_95: [number, number];
        evidence_readings: number;
        method: string;
      } | null;
      cd4_slope_per_month: number | null;
      cd4_trend: "up" | "down" | "flat";
    }>(`/patients/${id}/stats`),
  eciList: () => request<Patient[]>("/patients/eci"),
  refreshEci: () => request<{ newly_flagged: number }>("/patients/refresh-eci", { method: "POST" }),
  createPatient: (payload: Record<string, unknown>) =>
    request<Patient>("/patients/", { method: "POST", body: JSON.stringify(payload) }),
  updatePatient: (id: number, payload: Record<string, unknown>) =>
    request<Patient>(`/patients/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deactivatePatient: (id: number) =>
    request<void>(`/patients/${id}`, { method: "DELETE" }),

  // ── Stock / Forecast (FEFO + Kanban + Donatable) ─────────────
  stock: () => request<Batch[]>("/stock/"),
  stockAlerts: () => request<Batch[]>("/stock/alerts"),
  drugs: () => request<Drug[]>("/drugs/"),
  dsr: () => request<DsrRow[]>("/forecast/dsr"),
  createDrug: (payload: { name: string; strength?: string; form?: string; category?: string }) =>
    request<Drug>("/drugs/", { method: "POST", body: JSON.stringify(payload) }),
  receiveStock: (payload: {
    drug_id: number; batch_number: string; expiry_date: string; quantity_received: number;
    supplier?: string; gtin?: string | null; scan_logged?: number;
  }) => request<Batch>("/stock/receive", { method: "POST", body: JSON.stringify(payload) }),
  recordLoss: (payload: { batch_id: number; quantity_lost: number; reason_code: string; notes?: string | null }) =>
    request("/stock/loss", { method: "POST", body: JSON.stringify(payload) }),
  updateBatch: (id: number, payload: { batch_number?: string; expiry_date?: string; supplier?: string; gtin?: string | null }) =>
    request<Batch>(`/stock/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteBatch: (id: number) =>
    request<void>(`/stock/${id}`, { method: "DELETE" }),

  // ── PIN-gated QR scanning (Section: missing scanning feature) ──
  verifyPin: (pin: string) => request<{ verified: boolean; session_minutes: number }>(
    "/auth/verify-pin", { method: "POST", body: JSON.stringify({ pin }) }
  ),

  // ── Dispense (FEFO-enforced) ──────────────────────────────────
  dispense: (payload: { client_id: number; batch_id: number; quantity: number }) =>
    request<{ message: string; client: string; next_appointment: string; stock_remaining: number }>(
      "/dispense/", { method: "POST", body: JSON.stringify(payload) }
    ),
  dispenseRecent: (limit = 20) => request<{
    id: number; client_name: string; art_number: string; drug_name: string; quantity: number; dispense_date: string;
  }[]>(`/dispense/recent?limit=${limit}`),
  dispenseHistory: (clientId: number) => request<{
    drug_name: string; batch_number: string; quantity: number; dispense_date: string;
  }[]>(`/dispense/history/${clientId}`),

  // ── Appointments ──────────────────────────────────────────────
  appointmentsUpcoming: (days = 28) => request<Patient[]>(`/appointments/upcoming?days=${days}`),
  appointmentsLtfu: () => request<(Patient & { days_overdue: number })[]>("/appointments/ltfu"),
  appointmentsCalendar: () => request<{ date: string; pharmacy_count: number; clinical_count: number; total: number }[]>(
    "/appointments/calendar"
  ),
  markAttended: (clientId: number) => request<{ next_appointment: string }>(
    `/appointments/mark-attended/${clientId}`, { method: "POST" }
  ),
  cohortCalendar: (month?: string, defaulterThresholdDays = 14) =>
    request<{
      month: string; defaulter_threshold_days: number; total_cohorts: number;
      cohorts: {
        cohort: string; cohort_sort_key: string; total_members: number;
        pharmacy_count: number; clinical_count: number; expected_this_month: number;
        rtt_count: number; defaulter_count: number;
      }[];
    }>(`/appointments/cohorts${month ? `?month=${month}` : ""}${month ? "&" : "?"}defaulter_threshold_days=${defaulterThresholdDays}`),
  cohortMembers: (cohort: string) =>
    request<(Patient & { days_until: number | null; days_overdue: number })[]>(`/appointments/cohorts/${encodeURIComponent(cohort)}/members`),
  activityFeed: (limit = 15) => request<{
    id: number; client_id: number | null; client_name: string; art_number: string;
    drug_name: string; quantity: number; dispense_date: string; dispensed_by: string | null;
    is_eci_flag: boolean; eci_reason: string | null;
  }[]>(`/dashboard/activity-feed?limit=${limit}`),

  // ── Defaulter Management (primary Appointments component) ──────
  defaulterRisk: () => request<DefaulterRiskResult>("/appointments/defaulters"),
  defaulterReasons: () => request<DefaulterReasonsResult>("/appointments/defaulters/reasons"),
  defaulterHistory: (patientId: number) => request<DefaulterTraceLog[]>(`/appointments/defaulters/${patientId}/history`),
  logDefaulterTrace: (patientId: number, payload: { trace_method: string; trace_outcome: string; reason_for_default?: string; notes?: string }) =>
    request<DefaulterTraceLog>(`/appointments/defaulters/${patientId}/trace`, { method: "POST", body: JSON.stringify(payload) }),

  // ── KPI Engine (Layer 1 Operational / Layer 2 Clinical / Layer 3 Strategic) ──
  kpiDashboard: () => request<KpiDashboard>("/kpi/dashboard"),
  retentionCurve: () => request<{ points: RetentionPoint[]; n: number }>("/kpi/retention-curve"),
  stockoutProbability: (drugId: number, horizonDays = 28) =>
    request<StockoutProbability>(`/kpi/stockout-probability/${drugId}?horizon_days=${horizonDays}`),
  reorderPoint: (drugId: number, leadTimeDays = 14) =>
    request<ReorderPoint>(`/kpi/reorder-point/${drugId}?lead_time_days=${leadTimeDays}`),
  rootCause: (outcome: "ltfu" | "treatment_failure" = "ltfu") =>
    request<RootCauseResult>(`/kpi/root-cause?outcome=${outcome}`),
  networkTransferImpact: (payload: { drug_id: number; donor_facility_id: number; receiver_facility_id: number; quantity: number }) =>
    request<{ feasible: boolean; network_equity_before: number; network_equity_after: number; impact_score: number; recommendation: string; simulated: boolean }>(
      "/kpi/network-transfer-impact", { method: "POST", body: JSON.stringify(payload) }
    ),

  // ── Population Analytics (separate Postgres warehouse) ────────
  warehouseStatus: () => request<WarehouseStatus>("/warehouse/status"),
  warehouseRefresh: () => request<{ message: string }>("/warehouse/refresh", { method: "POST" }),
  failureRisk: (riskBand?: string) =>
    request<FailureRiskResult>(`/analytics/failure-risk${riskBand ? `?risk_band=${riskBand}` : ""}`),
  stockoutForecast: () => request<StockoutForecastResult>("/analytics/stockout-forecast"),
  fundingScenario: (deltaPct = -20) => request<FundingScenarioResult>(`/analytics/funding-scenario?delta_pct=${deltaPct}`),
  redistribution: () => request<RedistributionResult>("/analytics/redistribution"),
  interventionEffectiveness: () => request<InterventionEffectivenessResult>("/analytics/intervention-effectiveness"),

  // ── EHR Import ────────────────────────────────────────────────
  ehrTemplates: () => request<{ vl_csv: string; hts_csv: string; appointments_csv: string; pharmacy_register_csv: string }>("/ehr/templates"),
  ehrImport: (endpoint: "vl-import" | "hts-import" | "art-appointments-import" | "pharmacy-register-import", file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    const token = getToken();
    return fetch(`${API_URL}/ehr/${endpoint}`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: fd,
    }).then(async (r) => {
      if (!r.ok) throw new ApiError((await r.json().catch(() => ({}))).detail ?? r.statusText, r.status);
      return r.json() as Promise<{
        imported: number;
        skipped: number;
        created?: number;
        errors?: string[];
        skipped_art_numbers?: string[];
        format_detected?: string;
        positive_results_for_review?: { row: number; name: string; test_date: string; gender: string; address: string; entry_point: string }[];
        data_note?: string;
      }>;
    });
  },

  // ── Network (Safe-to-Donate gated transfers) ─────────────────
  networkFacilities: () => request<NetworkFacility[]>("/network/facilities"),
  networkSummary: () =>
    request<{ total_facilities: number; active_requests: number; completed_transfers: number; outstanding_obligations: number }>(
      "/network/summary"
    ),
  canShare: (drugId: number, quantityNeeded: number) =>
    request<FinderResult>(`/network/can-share?drug_id=${drugId}&quantity_needed=${quantityNeeded}`),
  requestTransfer: (payload: {
    drug_id: number; donor_facility_id: number; receiver_facility_id: number; quantity_requested: number;
  }) => request<StockTransfer>("/network/request", { method: "POST", body: JSON.stringify(payload) }),
  transfers: () => request<StockTransfer[]>("/network/transfers"),

  // ── AI Agent (proxied, key never leaves the backend; hybrid ─────
  // template/Claude — every response says which mode produced it) ──
  aiChat: (query: string) =>
    request<{ response: string; source: "template" | "claude"; note?: string }>(
      "/ai_agent/chat", { method: "POST", body: JSON.stringify({ query }) }
    ),
  aiReport: (report_type: string) =>
    request<{ content: string; source: "template" | "claude"; note?: string }>(
      "/ai/generate-report", { method: "POST", body: JSON.stringify({ report_type }) }
    ),
  aiBrief: () =>
    request<StrategicBrief>("/ai_agent/brief", { method: "POST" }),
  aiAnalyzeUpload: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    const token = getToken();
    return fetch(`${API_URL}/ai_agent/analyze-upload`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: fd,
    }).then(async (r) => {
      if (!r.ok) throw new ApiError((await r.json().catch(() => ({}))).detail ?? r.statusText, r.status);
      return r.json() as Promise<{ filename: string; profile: unknown; response: string; source: "template" | "claude"; note?: string }>;
    });
  },

  // ── Exports ───────────────────────────────────────────────
  // Export endpoints require Authorization: Bearer <token>, which a plain
  // <a href> can't send — so this fetches as a blob and triggers the
  // download client-side instead of linking directly to the API URL.
  downloadExport: async (dataset: "patients" | "stock" | "dispenses" | "losses" | "eci" | "transfers", format: string) => {
    const token = getToken();
    const res = await fetch(`${API_URL}/export/${dataset}?format=${format}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new ApiError((await res.json().catch(() => ({}))).detail ?? res.statusText, res.status);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${dataset}.${format}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },

  // ── Notice Board ────────────────────────────────────────────────
  notices: () => request<{
    id: number; title: string; message: string; priority: "INFO" | "WARNING" | "URGENT";
    facility_id: number | null; facility_name: string; created_by: string | null;
    created_at: string; expires_at: string | null;
  }[]>("/notices/"),
  createNotice: (payload: { title: string; message: string; priority: string; scope?: "global" | "facility"; expires_at?: string | null }) =>
    request("/notices/", { method: "POST", body: JSON.stringify(payload) }),
  deleteNotice: (id: number) => request<void>(`/notices/${id}`, { method: "DELETE" }),
};

export { ApiError };
