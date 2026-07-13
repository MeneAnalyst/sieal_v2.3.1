"""
RESILIENCE-ART v1.0 — DEPENDENCY MODEL / SYNTHETIC ENGINE CORE
================================================================
Encodes the causal rules that drive every downstream question.
This module is deliberately separated from the raw generator
(patient/facility assignment) so the rules can be unit-tested
and tuned independently — this IS the engine that gives your
warehouse facts (risk scores, stockout predictions, scenario
projections) something real to compute over.

Rules implemented (as specified):
  1. distance > 10km            -> +35% default risk
  2. stockout                    -> VL rebound 60-120 days later
  3. CD4 < 200                    -> TB risk rises exponentially
  4. adherence < 80%               -> suppression failure probability rises
  5. facility overloaded             -> longer turnaround -> delayed suppression
"""

import math
import random
from dataclasses import dataclass, field
from datetime import date, timedelta

random.seed(42)

# ------------------------------------------------------------------
# 1. DISTANCE -> DEFAULT RISK
# ------------------------------------------------------------------
def default_risk_multiplier(distance_km: float, base_risk: float) -> float:
    """distance > 10km adds +35% relative risk of defaulting."""
    if distance_km > 10:
        return base_risk * 1.35
    return base_risk


# ------------------------------------------------------------------
# 2. STOCKOUT -> VL REBOUND (60-120 day lag)
# ------------------------------------------------------------------
def schedule_vl_rebound(stockout_date: date) -> date:
    """
    A stockout doesn't show up in outcomes immediately — it shows up
    as a viral load rebound 60-120 days later. This is the delay the
    'stockout forecast' fact needs to account for when it estimates
    downstream clinical harm, not just pharmacy KPIs.
    """
    lag_days = random.randint(60, 120)
    return stockout_date + timedelta(days=lag_days)


def vl_rebound_probability(days_of_stockout_exposure: int) -> float:
    """Longer a patient goes without stock, higher chance of rebound."""
    # saturating curve: quick exposure = low prob, 30+ days ~ near-certain
    return 1 - math.exp(-days_of_stockout_exposure / 12)


# ------------------------------------------------------------------
# 3. CD4 < 200 -> EXPONENTIAL TB RISK
# ------------------------------------------------------------------
def tb_risk(cd4_count: int, baseline_risk: float = 0.02) -> float:
    """
    Below CD4 200 (AHD threshold per MoHCC guidelines), TB risk should
    grow exponentially as CD4 falls further, not linearly.
    """
    if cd4_count >= 200:
        return baseline_risk
    severity = (200 - cd4_count) / 200  # 0 -> 1 as CD4 -> 0
    return min(baseline_risk * math.exp(4 * severity), 0.95)


# ------------------------------------------------------------------
# 4. ADHERENCE < 80% -> SUPPRESSION FAILURE PROBABILITY
# ------------------------------------------------------------------
def suppression_failure_probability(adherence_pct: float, base_failure: float = 0.05) -> float:
    """
    Adherence under 80% sharply raises failure probability.
    Smooth logistic-style penalty rather than a hard cliff, so the
    risk model doesn't produce discontinuities at exactly 80%.
    """
    if adherence_pct >= 80:
        return base_failure
    gap = (80 - adherence_pct) / 80
    return min(base_failure + gap * 0.6, 0.9)


# ------------------------------------------------------------------
# 5. FACILITY OVERLOAD -> TURNAROUND DELAY -> DELAYED SUPPRESSION
# ------------------------------------------------------------------
def turnaround_days(base_days: int, patient_load: int, capacity: int) -> int:
    """Turnaround time degrades once a facility exceeds design capacity."""
    if capacity <= 0:
        return base_days
    overload_ratio = patient_load / capacity
    if overload_ratio <= 1.0:
        return base_days
    extra = int(base_days * (overload_ratio - 1) * 2)  # scales with degree of overload
    return base_days + extra


def is_overloaded(patient_load: int, capacity: int, threshold: float = 1.15) -> bool:
    return capacity > 0 and (patient_load / capacity) > threshold


def delayed_suppression_probability(turnaround_days_value: int, base_prob: float = 0.05) -> float:
    """Longer lab turnaround -> longer time to detect/react -> more delayed suppression."""
    if turnaround_days_value <= 14:
        return base_prob
    extra_weeks = (turnaround_days_value - 14) / 7
    return min(base_prob + extra_weeks * 0.04, 0.8)


# ------------------------------------------------------------------
# COMPOSITE: 6-MONTH TREATMENT FAILURE RISK SCORE
# (this is what populates fact_treatment_failure_risk)
# ------------------------------------------------------------------
@dataclass
class PatientSnapshot:
    patient_id: str
    facility_id: str
    distance_km: float
    cd4_count: int
    adherence_pct: float
    facility_patient_load: int
    facility_capacity: int
    recent_stockout_exposure_days: int = 0
    base_default_risk: float = 0.08


@dataclass
class RiskResult:
    patient_id: str
    risk_score_6mo: float
    risk_band: str
    top_drivers: list = field(default_factory=list)


def score_failure_risk(snap: PatientSnapshot) -> RiskResult:
    drivers = []

    # 1. distance
    default_risk = default_risk_multiplier(snap.distance_km, snap.base_default_risk)
    if snap.distance_km > 10:
        drivers.append("distance>10km")

    # 3. TB / CD4 (used as a severity co-factor, not the primary axis)
    tb_component = tb_risk(snap.cd4_count)
    if snap.cd4_count < 200:
        drivers.append("cd4<200")

    # 4. adherence
    suppression_fail = suppression_failure_probability(snap.adherence_pct)
    if snap.adherence_pct < 80:
        drivers.append("adherence<80%")

    # 5. facility overload
    tat = turnaround_days(base_days=7, patient_load=snap.facility_patient_load,
                            capacity=snap.facility_capacity)
    delayed_supp = delayed_suppression_probability(tat)
    if is_overloaded(snap.facility_patient_load, snap.facility_capacity):
        drivers.append("facility_overloaded")

    # 2. stockout exposure -> rebound probability
    rebound_prob = vl_rebound_probability(snap.recent_stockout_exposure_days)
    if snap.recent_stockout_exposure_days > 0:
        drivers.append("recent_stockout_exposure")

    # Weighted composite — weights are the tunable knob; start conservative
    # and recalibrate against real outcome data once labeled data exists.
    composite = (
        0.25 * default_risk +
        0.15 * tb_component +
        0.30 * suppression_fail +
        0.15 * delayed_supp +
        0.15 * rebound_prob
    )
    composite = min(composite, 0.98)

    if composite < 0.15:
        band = "low"
    elif composite < 0.35:
        band = "medium"
    elif composite < 0.6:
        band = "high"
    else:
        band = "critical"

    return RiskResult(snap.patient_id, round(composite, 4), band, drivers)


if __name__ == "__main__":
    # sanity check
    example = PatientSnapshot(
        patient_id="P001", facility_id="F014", distance_km=14.2,
        cd4_count=160, adherence_pct=68, facility_patient_load=1800,
        facility_capacity=1400, recent_stockout_exposure_days=25
    )
    result = score_failure_risk(example)
    print(result)
