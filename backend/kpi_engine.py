"""
kpi_engine.py — RESILIENCE-ART KPI Matrix implementation
──────────────────────────────────────────────────────────
Design principle: every formula here is DESCRIPTIVE or a closed-form
OR/statistics calculation (counting, ratios, Monte Carlo sampling from a
specified distribution, safety-stock formulas, Kaplan-Meier, a documented
beta-binomial update). Nothing here FITS PARAMETERS to this dataset.

Deliberately NOT implemented, and why:
  - Renal Impairment Rate / TB-HIV Co-infection / IRIS Incidence /
    Post-Transition Adherence: no backing tables exist (RenalRecord,
    TBRecord, IRISEvent, RegimenChange). These need a new clinical module,
    not a KPI wiring pass. Adding them now would mean fabricated schema
    AND fabricated data.
  - Root-Cause Attribution: implemented as point-biserial correlation
    (scipy), NOT SHAP on a trained model. At n=45 (and far fewer actual
    outcome *events*), a fit model's SHAP values would be noise dressed
    up as insight. Correlation strength is honest at this sample size;
    a trained model's feature importances would not be.
  - "Bayesian Posterior" is a genuine beta-binomial conjugate update
    with a literature-sourced prior — not a fitted/learned model.

Caveats surfaced in each function's docstring / return payload rather than
hidden, so the frontend can label things accurately.
"""
from datetime import date, timedelta
from typing import Optional
import random
import math

import numpy as np
from scipy import stats
from sqlalchemy import func
from sqlalchemy.orm import Session

from models import ARTClient, Batch, Drug, DispenseRecord, ExpiryLoss, VLResult, Facility

TODAY = lambda: date.today()  # noqa: E731 — overridable in tests


# ═══════════════════════════════════════════════════════════════════
# LAYER 1 — OPERATIONAL RESILIENCE
# ═══════════════════════════════════════════════════════════════════

def adc(drug_id: int, db: Session, window_days: int = 90) -> float:
    """Average Daily Consumption. Matches routers/forecast.py's own ADC
    window (both are 90 days) — kept as a named parameter here so the two
    modules stay reconcilable if either window is changed independently
    in future, rather than duplicating a magic number silently."""
    since = TODAY() - timedelta(days=window_days)
    total = (
        db.query(func.sum(DispenseRecord.quantity))
        .join(Batch)
        .filter(Batch.drug_id == drug_id, DispenseRecord.dispense_date >= since)
        .scalar() or 0
    )
    return total / window_days


def current_stock(drug_id: int, db: Session) -> int:
    return (
        db.query(func.sum(Batch.quantity_remaining))
        .filter(Batch.drug_id == drug_id, Batch.quantity_remaining > 0)
        .scalar() or 0
    )


def days_of_stock_remaining(drug_id: int, db: Session) -> dict:
    a = adc(drug_id, db)
    stock = current_stock(drug_id, db)
    dsr = round(stock / a, 1) if a > 0 else 999.0
    if dsr < 30:
        status = "CRITICAL"
    elif dsr < 90:
        status = "LOW"
    elif dsr < 180:
        status = "MODERATE"
    else:
        status = "ADEQUATE"
    return {"drug_id": drug_id, "adc": round(a, 2), "stock": stock, "dsr": dsr, "status": status}


def safe_to_donate(drug_id: int, db: Session) -> int:
    """Current_Stock - (ADC * 120). Must be > 0 to enable transfer."""
    a = adc(drug_id, db)
    return round(current_stock(drug_id, db) - a * 120)


def inventory_fill_rate(drug_id: int, db: Session) -> float:
    """(Current Stock / Target Stock) * 100, Target = ADC * 180."""
    a = adc(drug_id, db)
    target = a * 180
    if target <= 0:
        return 0.0
    return round(min(current_stock(drug_id, db) / target * 100, 300), 1)  # cap display at 300%


def fefo_compliance_rate(db: Session, lookback_days: int = 90) -> dict:
    """% of dispenses where the batch chosen was the earliest-expiring
    batch of that drug available (received before the dispense date) at
    dispense time.

    APPROXIMATION: quantity_remaining is a current snapshot, not a
    historical one, so we can't perfectly reconstruct "available" batches
    at the exact moment of a past dispense. We approximate "available" as
    any batch of that drug received on/before the dispense date. This is
    conservative in one direction: a batch that had already fully
    depleted by dispense time may be incorrectly counted as an available,
    unchosen, earlier-expiring option. Treat this as a good-faith estimate,
    not an audit-grade compliance figure, unless a stock-ledger history
    table is added.
    """
    since = TODAY() - timedelta(days=lookback_days)
    dispenses = (
        db.query(DispenseRecord, Batch)
        .join(Batch, DispenseRecord.batch_id == Batch.id)
        .filter(DispenseRecord.dispense_date >= since)
        .all()
    )
    if not dispenses:
        return {"rate": None, "n": 0, "note": "No dispenses in lookback window"}

    compliant = 0
    for disp, batch in dispenses:
        candidates = (
            db.query(Batch)
            .filter(Batch.drug_id == batch.drug_id, Batch.received_date <= disp.dispense_date)
            .all()
        )
        earliest_expiry = min((c.expiry_date for c in candidates), default=batch.expiry_date)
        if batch.expiry_date <= earliest_expiry:
            compliant += 1

    return {"rate": round(compliant / len(dispenses) * 100, 1), "n": len(dispenses), "approximate": True}


def expiry_loss_rate(db: Session, window_days: int = 180) -> dict:
    """UNIT-based, not value-based: no unit-cost field exists on Drug/Batch.
    (Lost quantity / total received quantity) * 100 over the window."""
    since = TODAY() - timedelta(days=window_days)
    lost = (
        db.query(func.sum(ExpiryLoss.quantity_lost))
        .filter(ExpiryLoss.loss_date >= since)
        .scalar() or 0
    )
    received = (
        db.query(func.sum(Batch.quantity_received))
        .filter(Batch.received_date >= since)
        .scalar() or 0
    )
    rate = round(lost / received * 100, 2) if received > 0 else 0.0
    return {"rate_percent": rate, "unit_based": True, "quantity_lost": lost, "quantity_received": received}


def network_equity_score(db: Session, dsr_threshold_days: int = 90) -> dict:
    """% of facilities in the network with adequate stock (DSR >= threshold),
    averaged across drugs.

    CAVEAT: only the logged-in facility has a real Batch table (no
    facility_id on Batch — this is a single-facility inventory schema).
    Peer-facility stock is simulated with the SAME seeded-random approach
    already used in routers/network.py's `who_can_share` endpoint
    (random.seed(facility_id * drug_id)), for consistency with the rest
    of the Stock Network feature. This is demo/simulated peer data, not
    live multi-facility telemetry — surfaced via `simulated: True`.
    """
    facilities = db.query(Facility).all()
    drugs = db.query(Drug).all()
    if not facilities or not drugs:
        return {"score": None, "simulated": True, "n_facilities": 0}

    adequate_count = 0
    total_count = 0
    for f in facilities:
        adequate_drugs = 0
        for d in drugs:
            a = adc(d.id, db)
            stock = current_stock(d.id, db)
            if not f.is_current:
                rnd = random.Random(f.id * d.id)
                stock = max(0, stock + rnd.randint(-200, 400))
                a = max(0.1, a * rnd.uniform(0.5, 1.5))
            dsr = stock / a if a > 0 else 999
            if dsr >= dsr_threshold_days:
                adequate_drugs += 1
        facility_pct = adequate_drugs / len(drugs) if drugs else 0
        if facility_pct >= 0.5:  # majority of drugs adequate -> facility counts as "adequate"
            adequate_count += 1
        total_count += 1

    return {
        "score": round(adequate_count / total_count * 100, 1) if total_count else None,
        "n_facilities": total_count,
        "n_adequate": adequate_count,
        "simulated": True,
    }


# ═══════════════════════════════════════════════════════════════════
# LAYER 2 — CLINICAL SURVEILLANCE (real, rule-based — not trained models)
# ═══════════════════════════════════════════════════════════════════

def eci_rate(db: Session) -> dict:
    new_or_rtt = db.query(ARTClient).filter(
        ARTClient.progress_status.in_(["NEW_INITIATION", "RTT"]), ARTClient.is_active == 1
    ).all()
    if not new_or_rtt:
        return {"rate": None, "n": 0}
    flagged = sum(1 for c in new_or_rtt if c.cd4_count is not None and c.cd4_count < 200)
    return {"rate": round(flagged / len(new_or_rtt) * 100, 1), "n": len(new_or_rtt), "flagged": flagged}


def treatment_failure_rate(db: Session) -> dict:
    """(Patients with 2 CONSECUTIVE VL >= 1000 / Total active on ART) * 100.
    Uses real per-patient VL history (vl_results table), sorted by
    sample_date, looking for any two consecutive readings both >= 1000.
    This is the WHO-aligned confirmed-failure definition — deliberately
    stricter than the single-reading ECI treatment-failure trigger, which
    is a broad screening net by design. The two are not meant to agree.
    """
    active = db.query(ARTClient).filter(ARTClient.is_active == 1).all()
    if not active:
        return {"rate": None, "n": 0}

    failed = 0
    evaluable = 0
    for c in active:
        history = (
            db.query(VLResult)
            .filter(VLResult.patient_id == c.id)
            .order_by(VLResult.sample_date)
            .all()
        )
        if len(history) < 2:
            continue
        evaluable += 1
        for i in range(len(history) - 1):
            if history[i].result >= 1000 and history[i + 1].result >= 1000:
                failed += 1
                break

    return {
        "rate": round(failed / evaluable * 100, 1) if evaluable else None,
        "n_evaluable": evaluable,
        "n_total_active": len(active),
        "failed": failed,
        "note": "Only patients with >=2 VL results are evaluable for this confirmed-failure definition.",
    }


def vl_suppression_rate(db: Session) -> dict:
    total = db.query(ARTClient).filter(ARTClient.is_active == 1, ARTClient.vl_result.isnot(None)).count()
    if total == 0:
        return {"rate": None, "n": 0}
    suppressed = db.query(ARTClient).filter(
        ARTClient.is_active == 1, ARTClient.vl_result.isnot(None), ARTClient.vl_suppressed == 1
    ).count()
    return {"rate": round(suppressed / total * 100, 1), "n": total, "suppressed": suppressed}


def ltfu_rate(db: Session, overdue_days: int = 30) -> dict:
    active = db.query(ARTClient).filter(ARTClient.is_active == 1).count()
    if active == 0:
        return {"rate": None, "n": 0}
    ltfu = db.query(ARTClient).filter(
        ARTClient.is_active == 1,
        ARTClient.next_appointment < TODAY() - timedelta(days=overdue_days),
    ).count()
    return {"rate": round(ltfu / active * 100, 1), "n": active, "ltfu": ltfu}


def not_available_kpis() -> dict:
    """
    Honest placeholders for the KPI matrix rows that need a clinical
    module (new DB tables + real data) we don't have yet: Renal
    Impairment Rate, TB-HIV Co-infection Rate, IRIS Incidence, and
    Post-Transition Adherence Rate. Rather than silently dropping these
    rows from the matrix, the frontend renders them as visibly
    "Not yet available" so the full KPI surface stays honest about
    what is and isn't backed by real data.
    """
    reasons = {
        "renal_impairment_rate": "Requires a RenalRecord table (serum creatinine, eGFR trajectory) — not yet built.",
        "tb_hiv_coinfection_rate": "Requires a TBRecord table (diagnosis, drug resistance) — not yet built.",
        "iris_incidence": "Requires an IRISEvent table (event date, manifestation, severity) — not yet built.",
        "post_transition_adherence_rate": "Requires a RegimenChange table to anchor the pre/post window — not yet built.",
    }
    return {key: {"status": "not_available", "reason": reason} for key, reason in reasons.items()}


def retention_curve(db: Session) -> dict:
    """Kaplan-Meier retention curve. KM is designed for exactly this kind
    of small/censored sample — this is a legitimate use of `lifelines`
    even at n=45, unlike a fitted risk-prediction model would be."""
    from lifelines import KaplanMeierFitter

    clients = db.query(ARTClient).filter(ARTClient.enrollment_date.isnot(None)).all()
    if len(clients) < 3:
        return {"points": [], "note": "Insufficient enrollment data"}

    durations, events = [], []
    for c in clients:
        start = c.enrollment_date
        end = c.last_visit or start
        duration = max((end - start).days, 0)
        event = 1 if c.progress_status == "LTFU" else 0  # 1 = event (lost), 0 = censored
        durations.append(duration)
        events.append(event)

    kmf = KaplanMeierFitter()
    kmf.fit(durations, event_observed=events)
    surv = kmf.survival_function_.reset_index()
    surv.columns = ["day", "retention"]
    points = [{"day": int(r.day), "retention": round(float(r.retention) * 100, 1)} for r in surv.itertuples()]
    return {"points": points, "n": len(clients)}


# ═══════════════════════════════════════════════════════════════════
# LAYER 3 — STRATEGIC INTELLIGENCE (closed-form OR/stats, no fitted ML)
# ═══════════════════════════════════════════════════════════════════

def stockout_probability(drug_id: int, db: Session, horizon_days: int = 28, n_sims: int = 5000) -> dict:
    """Monte Carlo: daily demand ~ Poisson(ADC). Probability that
    cumulative demand over `horizon_days` exceeds current usable stock."""
    a = adc(drug_id, db)
    stock = current_stock(drug_id, db)
    if a <= 0:
        return {"probability": 0.0, "horizon_days": horizon_days, "note": "No recent consumption to model"}

    rng = np.random.default_rng(seed=drug_id)  # deterministic per drug for demo reproducibility
    daily_demand = rng.poisson(lam=a, size=(n_sims, horizon_days))
    cumulative = daily_demand.sum(axis=1)
    prob = float(np.mean(cumulative >= stock))
    return {
        "probability": round(prob * 100, 1),
        "horizon_days": horizon_days,
        "current_stock": stock,
        "adc": round(a, 2),
        "n_simulations": n_sims,
        "alert": prob > 0.5,
    }


def optimal_reorder_point(drug_id: int, db: Session, lead_time_days: int = 14, service_level: float = 0.95) -> dict:
    """Classic safety-stock reorder point (Newsvendor/(s,S)-policy building
    block), NOT a full Markov Decision Process. reorder_point =
    ADC*lead_time + z*sigma*sqrt(lead_time), where sigma is the observed
    std-dev of daily dispensed quantity over the last 90 days.

    A full MDP needs an explicit holding-cost / stockout-cost / lead-time
    distribution model that hasn't been specified — this gives the same
    actionable "reorder at X units" output using standard inventory
    theory instead of badging a heuristic as something it isn't.
    """
    since = TODAY() - timedelta(days=90)
    daily_qtys = (
        db.query(DispenseRecord.dispense_date, func.sum(DispenseRecord.quantity).label("qty"))
        .join(Batch)
        .filter(Batch.drug_id == drug_id, DispenseRecord.dispense_date >= since)
        .group_by(DispenseRecord.dispense_date)
        .all()
    )
    qtys = np.array([row.qty for row in daily_qtys]) if daily_qtys else np.array([0.0])
    sigma = float(np.std(qtys)) if len(qtys) > 1 else 0.0

    a = adc(drug_id, db)
    z = stats.norm.ppf(service_level)  # e.g. 1.645 for 95%
    reorder_point = a * lead_time_days + z * sigma * math.sqrt(lead_time_days)

    return {
        "reorder_point": round(reorder_point),
        "lead_time_days": lead_time_days,
        "service_level": service_level,
        "z_score": round(z, 3),
        "demand_std_dev": round(sigma, 2),
        "method": "safety_stock_formula",  # honestly labeled, not "MDP"
    }


def root_cause_attribution(db: Session, outcome: str = "ltfu") -> dict:
    """Point-biserial correlation between a binary outcome and candidate
    numeric factors — an honest, interpretable substitute for SHAP at
    this sample size. Returns normalized |r| as a rough "% contribution",
    clearly NOT a causal or trained-model attribution.
    """
    clients = db.query(ARTClient).filter(ARTClient.is_active == 1).all()
    if len(clients) < 10:
        return {"factors": [], "note": "Insufficient sample for correlation analysis"}

    rows = []
    for c in clients:
        if outcome == "ltfu":
            y = 1 if (c.next_appointment and c.next_appointment < TODAY() - timedelta(days=30)) else 0
        else:  # treatment_failure proxy: unsuppressed VL
            if c.vl_result is None:
                continue
            y = 0 if c.vl_suppressed else 1
        age = (TODAY() - c.date_of_birth).days / 365.25 if c.date_of_birth else None
        rows.append({
            "y": y,
            "cd4_count": c.cd4_count,
            "adherence_score": c.adherence_score,
            "age": age,
        })

    factors = {}
    ys = np.array([r["y"] for r in rows])
    for key in ["cd4_count", "adherence_score", "age"]:
        xs, valid_ys = [], []
        for r in rows:
            if r[key] is not None:
                xs.append(r[key])
                valid_ys.append(r["y"])
        if len(xs) >= 10 and len(set(valid_ys)) > 1:
            r_val, p_val = stats.pointbiserialr(valid_ys, xs)
            factors[key] = {"correlation": round(float(r_val), 3), "p_value": round(float(p_val), 3), "n": len(xs)}

    total_abs_r = sum(abs(f["correlation"]) for f in factors.values()) or 1
    for f in factors.values():
        f["contribution_percent"] = round(abs(f["correlation"]) / total_abs_r * 100, 1)

    return {"outcome": outcome, "factors": factors, "method": "point_biserial_correlation", "n": len(rows)}


def bayesian_confidence(db: Session, patient_id: int, prior_failure_rate: float = 0.05, prior_strength: float = 20) -> dict:
    """Genuine beta-binomial conjugate update — not a fitted model.
    Prior: Beta(a0, b0) centered on `prior_failure_rate` (WHO 3rd-95
    target implies ~5% population failure rate) with `prior_strength`
    pseudo-observations. Likelihood: patient's own VL history
    (successes = suppressed readings, failures = unsuppressed readings).
    Posterior mean + 95% credible interval returned.
    """
    a0 = prior_failure_rate * prior_strength
    b0 = (1 - prior_failure_rate) * prior_strength

    history = db.query(VLResult).filter(VLResult.patient_id == patient_id).all()
    failures = sum(1 for h in history if h.result >= 1000)
    successes = len(history) - failures

    a_post = a0 + failures
    b_post = b0 + successes
    mean = a_post / (a_post + b_post)
    ci_low, ci_high = stats.beta.ppf([0.025, 0.975], a_post, b_post)

    return {
        "patient_id": patient_id,
        "posterior_mean_failure_risk": round(mean * 100, 1),
        "credible_interval_95": [round(float(ci_low) * 100, 1), round(float(ci_high) * 100, 1)],
        "prior_failure_rate": prior_failure_rate,
        "n_vl_results": len(history),
        "method": "beta_binomial_conjugate_update",
    }


def programmatic_health_index(db: Session) -> dict:
    """Composite weighted score. WEIGHTS ARE ILLUSTRATIVE, not derived —
    surfaced explicitly rather than presented as a validated instrument.
    Renal Safety term is dropped (no backing schema) and remaining
    weights are renormalized to sum to 1.0.
    """
    vl = vl_suppression_rate(db)
    ltfu = ltfu_rate(db)
    equity = network_equity_score(db)

    drugs = db.query(Drug).all()
    fill_rates = [inventory_fill_rate(d.id, db) for d in drugs] if drugs else [0]
    avg_fill = min(sum(fill_rates) / len(fill_rates), 100) if fill_rates else 0

    components = {
        "vl_suppression": (vl["rate"] or 0, 0.35),
        "fill_rate": (avg_fill, 0.25),
        "retention": (100 - (ltfu["rate"] or 0), 0.20),
        "network_equity": (equity["score"] or 0, 0.20),
    }
    total_weight = sum(w for _, w in components.values())
    score = sum(val * w for val, w in components.values()) / total_weight

    return {
        "phi": round(score, 1),
        "components": {k: {"value": round(v, 1), "weight": round(w / total_weight, 2)} for k, (v, w) in components.items()},
        "note": "Weights are illustrative (not clinically validated); Renal Safety term omitted — no backing data model exists.",
    }
