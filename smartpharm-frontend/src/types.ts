// Domain types mirroring the FastAPI Pydantic responses.
// Keep in sync with backend/schemas.py and backend/routers/*.py

export type KanbanStatus = "CRITICAL" | "LOW" | "MODERATE" | "ADEQUATE";

export interface User {
  id: number;
  username: string;
  full_name: string;
  role: "ADMIN" | "PHARMACIST" | "CLINICIAN" | "VIEWER";
  facility_id: number;
  facility_name: string;
  facility_dhis2: string;
}

export interface DashboardSummary {
  date: string;
  total_clients: number;
  due_today: number;
  due_this_week: number;
  ltfu_count: number;
  red_alerts: number;
  amber_alerts: number;
  total_active_batches: number;
  dispensed_today: number;
  dispensed_this_month: number;
  daily_trend: { date: string; qty: number }[];
  /** Relevant KPIs */
  eci_flagged: number;
  treatment_failure_count: number;
  vl_suppression_pct: number | null;
  avg_adherence: number | null;
  donatable_drug_count: number;
}

export interface Patient {
  id: number;
  art_number: string;
  tb_number: string | null;
  full_name: string;
  date_of_birth: string | null;
  gender: string | null;
  treatment_combination: string | null;
  visit_type: "PHARMACY" | "CLINICAL";
  progress_status: string;
  cd4_count: number | null;
  vl_result: number | null;
  vl_suppressed: boolean;
  adherence_score: number | null;
  stock_status: string;
  last_visit: string | null;
  next_appointment: string | null;
  is_eci_flag: boolean;
  eci_reason: string | null;
}

export interface Batch {
  id: number;
  drug_id: number;
  drug_name: string;
  drug_strength: string;
  batch_number: string;
  expiry_date: string;
  quantity_received: number;
  quantity_remaining: number;
  alert_status: "RED" | "AMBER" | "GREEN";
  days_to_expiry: number;
  scan_logged?: boolean;
}

export interface Drug {
  id: number;
  name: string;
  strength: string;
  form: string;
  category: string;
}

/**
 * DSR row — Days of Stock Remaining, per Section 4C of the OR spec.
 * adc is Average Daily Consumption over a 90-day trailing window.
 */
export interface DsrRow {
  drug_id: number;
  drug_name: string;
  strength: string;
  total_stock: number;
  adc: number;
  dsr: number;
  status: KanbanStatus;
  monthly_consumption: number;
  /** Section 4B: Current_Stock − (ADC × 120). Only positive => can donate. */
  donatable_surplus: number;
}

export interface NetworkFacility {
  id: number;
  name: string;
  dhis2_code: string;
  facility_type: string;
  district: string;
  is_current: boolean;
  lat: number | null;
  lng: number | null;
}

export interface DonorRecommendation {
  facility_id: number;
  facility_name: string;
  current_stock: number;
  safe_to_donate: number;
  can_cover_full: boolean;
  recommended_qty: number;
  dsr_before: number;
  dsr_after: number;
  distance_km: number | null;
  is_real_data: boolean;
}

export interface FinderResult {
  drug_name: string;
  quantity_needed: number;
  total_donors: number;
  can_fully_cover: boolean;
  combined_available: number;
  recommendations: DonorRecommendation[];
  data_note: string;
}

export interface StockTransfer {
  id: number;
  drug_name: string;
  donor_name: string;
  receiver_name: string;
  quantity_requested: number;
  quantity_approved: number | null;
  quantity_to_repay: number | null;
  quantity_repaid: number;
  status: "REQUESTED" | "APPROVED" | "COMPLETED" | "REPAID" | "REJECTED";
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  source?: "template" | "claude";
  note?: string;
}

export interface StrategicAlert {
  severity: "critical" | "high" | "medium" | "info";
  category: "clinical" | "stock" | "network";
  title: string;
  detail: string;
}

export interface StrategicBrief {
  alerts: StrategicAlert[];
  narrative: string;
  source: "template" | "claude";
  note?: string;
}

// ── KPI Engine ──────────────────────────────────────────────────────
export interface RateStat {
  rate: number | null;
  n: number;
  [key: string]: unknown;
}

export interface NotAvailableKpi {
  status: "not_available";
  reason: string;
}

export interface KpiDashboard {
  layer1_operational: {
    per_drug: { drug_id: number; drug_name: string; adc: number; stock: number; dsr: number; status: string; safe_to_donate: number; fill_rate: number }[];
    fefo_compliance: { rate: number | null; n: number; approximate?: boolean; note?: string };
    expiry_loss: { rate_percent: number; unit_based: boolean; quantity_lost: number; quantity_received: number };
    network_equity: { score: number | null; n_facilities: number; n_adequate: number; simulated: boolean };
  };
  layer2_clinical: {
    eci_rate: RateStat;
    treatment_failure_rate: RateStat;
    vl_suppression_rate: RateStat;
    ltfu_rate: RateStat;
    renal_impairment_rate: NotAvailableKpi;
    tb_hiv_coinfection_rate: NotAvailableKpi;
    iris_incidence: NotAvailableKpi;
    post_transition_adherence_rate: NotAvailableKpi;
  };
  layer3_strategic: {
    programmatic_health_index: {
      phi: number;
      components: Record<string, { value: number; weight: number }>;
      note: string;
    };
  };
}

export interface RetentionPoint { day: number; retention: number }

export interface StockoutProbability {
  probability: number;
  horizon_days: number;
  current_stock?: number;
  adc?: number;
  n_simulations?: number;
  alert?: boolean;
  note?: string;
}

export interface ReorderPoint {
  reorder_point: number;
  lead_time_days: number;
  service_level: number;
  z_score: number;
  demand_std_dev: number;
  method: string;
}

export interface RootCauseFactor {
  correlation: number;
  p_value: number;
  n: number;
  contribution_percent: number;
}

export interface RootCauseResult {
  outcome: string;
  factors: Record<string, RootCauseFactor>;
  method: string;
  n: number;
}

// ── Defaulter Management ───────────────────────────────────────────
export interface DefaulterRiskPatient {
  patient_id: number;
  art_number: string;
  full_name: string;
  risk_score: number;
  risk_band: "LOW" | "MEDIUM" | "HIGH";
  days_overdue: number;
  adherence_score: number | null;
  cd4_count: number | null;
}

export interface DefaulterRiskResult {
  patients: DefaulterRiskPatient[];
  method: "logistic_regression" | "rule_based_fallback";
  n_training_events: number;
  n_total_labeled: number;
  coefficients?: Record<string, number>;
  caveat: string;
}

export interface DefaulterReason { reason: string; count: number; pct: number }
export interface DefaulterReasonsResult { reasons: DefaulterReason[]; n_traces: number }

export interface DefaulterTraceLog {
  id: number;
  trace_date: string;
  trace_method: string | null;
  trace_outcome: string | null;
  reason_for_default: string | null;
  notes: string | null;
  logged_by: string | null;
}

// ── Population Analytics (warehouse) ────────────────────────────────
export interface FailureRiskPatient {
  patient_id: string;
  age_band: string;
  distance_band: string;
  facility_name: string;
  risk_score_6mo: number;
  risk_band: "low" | "medium" | "high" | "critical";
  top_drivers: string[];
  predicted_failure_date: string | null;
}
export interface FailureRiskResult { method: string; patients: FailureRiskPatient[] }

export interface StockoutForecastRow {
  facility_name: string;
  drug_name: string;
  stock_days_remaining: number | null;
  avg_daily_consumption_7d: number | null;
  stockout_flag: boolean;
  predicted_stockout_date: string | null;
}
export interface StockoutForecastResult { facilities: StockoutForecastRow[] }

export interface FundingScenarioFacility {
  facility_name: string;
  baseline: { stockout_rate: number; default_rate: number; suppression_rate: number } | null;
  scenario: { stockout_rate: number; default_rate: number; suppression_rate: number; staff_attrition_pct: number; patients_at_risk: number };
}
export interface FundingScenarioResult {
  scenario_name: string; funding_delta_pct: number; assumption_note: string; facilities: FundingScenarioFacility[];
}

export interface RedistributionRec {
  drug_name: string; source_facility: string; target_facility: string; recommended_qty: number;
  source_surplus_days: number; target_days_remaining: number; urgency_score: number;
  estimated_transport_cost: number | null; status: string;
}
export interface RedistributionResult { method: string; recommendations: RedistributionRec[] }

export interface InterventionEffectiveness { intervention_name: string; n_patients: number; avg_effect_size: number; avg_cost_per_default_averted: number }
export interface InterventionEffectivenessResult { method: string; interventions: InterventionEffectiveness[] }

export interface WarehouseStatus { configured: boolean }
