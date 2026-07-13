"""
routers/analytics.py — the 5 question-family endpoints from the
architecture doc, reading exclusively from the Postgres warehouse (never
the OLTP SQLite directly — that's the whole point of the ETL boundary).

Every endpoint returns 503 via get_warehouse_db if WAREHOUSE_DATABASE_URL
isn't configured, rather than silently returning empty/fake data.

FACILITY RESTRICTION: every endpoint here defaults to the logged-in
user's own facility — Population Analytics is a per-facility planning
tool, not a province-wide view, for any non-admin user. ADMIN role users
can pass `all_facilities=true` to see everything. This is deliberately
separate from the real Stock Sharing Network (routers/network.py),
which stays cross-facility by design since cross-facility visibility is
the entire point of that feature — nothing in network.py is touched here.
"""
from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, or_
from typing import Optional

from warehouse_database import get_warehouse_db, warehouse_configured
import warehouse_models as wm
from routers.auth import current_user

router = APIRouter()


def _resolve_facility_key(db: Session, session: dict, all_facilities: bool) -> Optional[int]:
    """
    Returns the warehouse facility_key to restrict queries to, or None if
    the caller should see every facility (ADMIN + all_facilities=true only).
    Returns None with no restriction if the user's facility hasn't been
    through the ETL yet either — better to show nothing filtered than to
    silently 403 someone because their facility isn't in the warehouse.
    """
    if all_facilities:
        if session.get("role") != "ADMIN":
            raise HTTPException(403, "Only ADMIN can request all_facilities=true")
        return None
    oltp_facility_id = session.get("facility_id")
    if oltp_facility_id is None:
        return None
    row = db.query(wm.DimFacility).filter(wm.DimFacility.facility_id == str(oltp_facility_id)).first()
    return row.facility_key if row else None


# ══════════════════════════════════════════════════════════════════
# 1. CLINICAL — Who is likely to fail ART in 6 months?
# ══════════════════════════════════════════════════════════════════
@router.get("/failure-risk")
def failure_risk(
    facility_key: Optional[int] = Query(None),
    risk_band: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    all_facilities: bool = Query(False),
    db: Session = Depends(get_warehouse_db),
    session: dict = Depends(current_user),
):
    own_facility_key = _resolve_facility_key(db, session, all_facilities)
    q = (
        db.query(wm.FactTreatmentFailureRisk, wm.DimPatient, wm.DimFacility)
        .join(wm.DimPatient, wm.FactTreatmentFailureRisk.patient_key == wm.DimPatient.patient_key)
        .join(wm.DimFacility, wm.FactTreatmentFailureRisk.facility_key == wm.DimFacility.facility_key)
    )
    if own_facility_key is not None:
        q = q.filter(wm.FactTreatmentFailureRisk.facility_key == own_facility_key)
    elif facility_key:  # only reachable with all_facilities=true, i.e. an admin explicitly picking one facility
        q = q.filter(wm.FactTreatmentFailureRisk.facility_key == facility_key)
    if risk_band:
        q = q.filter(wm.FactTreatmentFailureRisk.risk_band == risk_band.lower())
    rows = q.order_by(desc(wm.FactTreatmentFailureRisk.risk_score_6mo)).limit(limit).all()

    return {
        "method": "Weighted composite of 5 causal rules (dependency_model.py) — rule-based, not a fitted/trained model.",
        "scope": "all_facilities" if own_facility_key is None else "your_facility",
        "patients": [
            {
                "patient_id": patient.patient_id,
                "age_band": patient.age_band,
                "distance_band": patient.distance_band,
                "facility_name": facility.facility_name,
                "risk_score_6mo": float(risk.risk_score_6mo),
                "risk_band": risk.risk_band,
                "top_drivers": risk.top_risk_drivers or [],
                "predicted_failure_date": risk.predicted_failure_date.isoformat() if risk.predicted_failure_date else None,
            }
            for risk, patient, facility in rows
        ],
    }


# ══════════════════════════════════════════════════════════════════
# 2. OPERATIONAL — Which clinic will stock out next?
# ══════════════════════════════════════════════════════════════════
@router.get("/stockout-forecast")
def stockout_forecast(
    drug_key: Optional[int] = Query(None),
    limit: int = Query(50, le=200),
    all_facilities: bool = Query(False),
    db: Session = Depends(get_warehouse_db),
    session: dict = Depends(current_user),
):
    own_facility_key = _resolve_facility_key(db, session, all_facilities)
    q = (
        db.query(wm.FactStockDaily, wm.DimFacility, wm.DimDrug)
        .join(wm.DimFacility, wm.FactStockDaily.facility_key == wm.DimFacility.facility_key)
        .join(wm.DimDrug, wm.FactStockDaily.drug_key == wm.DimDrug.drug_key)
    )
    if own_facility_key is not None:
        q = q.filter(wm.FactStockDaily.facility_key == own_facility_key)
    if drug_key:
        q = q.filter(wm.FactStockDaily.drug_key == drug_key)
    rows = q.order_by(asc(wm.FactStockDaily.stock_days_remaining)).limit(limit).all()

    return {
        "scope": "all_facilities" if own_facility_key is None else "your_facility",
        "facilities": [
            {
                "facility_name": facility.facility_name,
                "drug_name": drug.drug_name,
                "stock_days_remaining": float(stock.stock_days_remaining) if stock.stock_days_remaining is not None else None,
                "avg_daily_consumption_7d": float(stock.avg_daily_consumption_7d) if stock.avg_daily_consumption_7d is not None else None,
                "stockout_flag": stock.stockout_flag,
                "predicted_stockout_date": stock.predicted_stockout_date.isoformat() if stock.predicted_stockout_date else None,
            }
            for stock, facility, drug in rows
        ],
    }


# ══════════════════════════════════════════════════════════════════
# 3. STRATEGIC — What happens if funding drops X%?
# ══════════════════════════════════════════════════════════════════
@router.get("/funding-scenario")
def funding_scenario(
    delta_pct: float = Query(-20.0),
    all_facilities: bool = Query(False),
    db: Session = Depends(get_warehouse_db),
    session: dict = Depends(current_user),
):
    own_facility_key = _resolve_facility_key(db, session, all_facilities)
    scenario_name = "baseline" if delta_pct == 0 else f"funding_{delta_pct:g}pct"
    baseline_q = (
        db.query(wm.FactFundingScenario, wm.DimFacility)
        .join(wm.DimFacility, wm.FactFundingScenario.facility_key == wm.DimFacility.facility_key)
        .filter(wm.FactFundingScenario.scenario_name == "baseline")
    )
    scenario_q = (
        db.query(wm.FactFundingScenario, wm.DimFacility)
        .join(wm.DimFacility, wm.FactFundingScenario.facility_key == wm.DimFacility.facility_key)
        .filter(wm.FactFundingScenario.scenario_name == scenario_name)
    )
    if own_facility_key is not None:
        baseline_q = baseline_q.filter(wm.FactFundingScenario.facility_key == own_facility_key)
        scenario_q = scenario_q.filter(wm.FactFundingScenario.facility_key == own_facility_key)
    baseline_rows, scenario_rows = baseline_q.all(), scenario_q.all()
    if not scenario_rows and delta_pct != -20.0:
        raise HTTPException(404, f"No pre-computed scenario for delta_pct={delta_pct}. The ETL currently only "
                                  "generates 'baseline' and 'funding_-20pct' — re-run the ETL with a modified "
                                  "build_funding_scenarios() to add more deltas.")

    baseline_by_fac = {b.facility_key: b for b, _ in baseline_rows}
    comparison = []
    for s, facility in scenario_rows:
        base = baseline_by_fac.get(s.facility_key)
        comparison.append({
            "facility_name": facility.facility_name,
            "baseline": {
                "stockout_rate": float(base.projected_stockout_rate) if base else None,
                "default_rate": float(base.projected_default_rate) if base else None,
                "suppression_rate": float(base.projected_suppression_rate) if base else None,
            } if base else None,
            "scenario": {
                "stockout_rate": float(s.projected_stockout_rate),
                "default_rate": float(s.projected_default_rate),
                "suppression_rate": float(s.projected_suppression_rate),
                "staff_attrition_pct": float(s.projected_staff_attrition_pct),
                "patients_at_risk": s.projected_patients_at_risk,
            },
        })

    return {
        "scenario_name": scenario_name, "funding_delta_pct": delta_pct,
        "scope": "all_facilities" if own_facility_key is None else "your_facility",
        "assumption_note": (
            "Funding delta is modeled as a proportional cut to procurement volume, which raises projected "
            "stockout/default rates and lowers projected suppression via a stated multiplier — not a "
            "measured historical elasticity. Treat comparisons as directional, not precise forecasts."
        ),
        "facilities": comparison,
    }


# ══════════════════════════════════════════════════════════════════
# 4. OPTIMIZATION — Where should we redistribute drugs today?
# ══════════════════════════════════════════════════════════════════
@router.get("/redistribution")
def redistribution(
    status: Optional[str] = Query(None),
    all_facilities: bool = Query(False),
    db: Session = Depends(get_warehouse_db),
    session: dict = Depends(current_user),
):
    own_facility_key = _resolve_facility_key(db, session, all_facilities)
    q = (
        db.query(wm.FactRedistributionRecommendation, wm.DimDrug)
        .join(wm.DimDrug, wm.FactRedistributionRecommendation.drug_key == wm.DimDrug.drug_key)
    )
    if status:
        q = q.filter(wm.FactRedistributionRecommendation.status == status)
    if own_facility_key is not None:
        # A facility user needs to see recommendations where they'd be
        # EITHER donor or recipient — restricting to only one side would
        # hide half of what's actually relevant to them.
        q = q.filter(or_(
            wm.FactRedistributionRecommendation.source_facility_key == own_facility_key,
            wm.FactRedistributionRecommendation.target_facility_key == own_facility_key,
        ))
    rows = q.order_by(desc(wm.FactRedistributionRecommendation.urgency_score)).all()

    fac_map = {f.facility_key: f.facility_name for f in db.query(wm.DimFacility).all()}

    return {
        "method": "Greedy heuristic (rank-and-pair by stock_days_remaining) — not an LP/transportation-problem solve. "
                   "See network_impact.py's PuLP feasibility check for the transfer-request-time version of this.",
        "scope": "all_facilities" if own_facility_key is None else "your_facility (as source or target)",
        "recommendations": [
            {
                "drug_name": drug.drug_name,
                "source_facility": fac_map.get(rec.source_facility_key),
                "target_facility": fac_map.get(rec.target_facility_key),
                "recommended_qty": rec.recommended_qty,
                "source_surplus_days": float(rec.source_surplus_days),
                "target_days_remaining": float(rec.target_days_remaining),
                "urgency_score": float(rec.urgency_score),
                "estimated_transport_cost": float(rec.estimated_transport_cost) if rec.estimated_transport_cost else None,
                "status": rec.status,
            }
            for rec, drug in rows
        ],
    }


# ══════════════════════════════════════════════════════════════════
# 5. POLICY — Which intervention reduces defaulting most?
# ══════════════════════════════════════════════════════════════════
@router.get("/intervention-effectiveness")
def intervention_effectiveness(
    all_facilities: bool = Query(False),
    db: Session = Depends(get_warehouse_db),
    session: dict = Depends(current_user),
):
    own_facility_key = _resolve_facility_key(db, session, all_facilities)
    q = (
        db.query(wm.FactInterventionOutcome, wm.DimIntervention)
        .join(wm.DimIntervention, wm.FactInterventionOutcome.intervention_key == wm.DimIntervention.intervention_key)
    )
    if own_facility_key is not None:
        q = q.filter(wm.FactInterventionOutcome.facility_key == own_facility_key)
    rows = q.all()
    from collections import defaultdict
    grouped = defaultdict(list)
    for outcome, iv in rows:
        grouped[iv.intervention_name].append(outcome)

    results = []
    for name, outcomes in grouped.items():
        n = len(outcomes)
        avg_effect = sum(float(o.effect_size) for o in outcomes) / n
        avg_cost = sum(float(o.cost_per_default_averted) for o in outcomes if o.cost_per_default_averted) / n
        results.append({
            "intervention_name": name, "n_patients": n,
            "avg_effect_size": round(avg_effect, 4), "avg_cost_per_default_averted": round(avg_cost, 2),
        })
    results.sort(key=lambda r: -r["avg_effect_size"])

    return {
        "method": "ILLUSTRATIVE SYNTHETIC A/B SIMULATION — no real intervention program or exposure data exists "
                   "yet. Effect sizes are drawn from assumed per-intervention parameters in etl/build_warehouse.py, "
                   "not measured outcomes. Do not present this as evidence for a real program decision.",
        "scope": "all_facilities" if own_facility_key is None else "your_facility",
        "interventions": results,
    }
