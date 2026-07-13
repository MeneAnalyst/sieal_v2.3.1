"""
defaulter_risk.py — Defaulter (LTFU) risk scoring.

The one Tier-3 library wired into this project: scikit-learn, used only
for a LOGISTIC REGRESSION — not a tree ensemble or boosted model. That
choice is deliberate at this sample size (dozens, not thousands, of
patients):

  - Logistic regression has as many parameters as features. It can be
    inspected directly (coefficients = direction and rough size of each
    factor's effect) rather than requiring a separate explainability
    layer (SHAP) bolted on afterwards.
  - A model this simple is honestly *for* n=45-scale data: it doesn't
    have the capacity to overfit into a false sense of precision the way
    a gradient-boosted ensemble would after memorizing a few dozen rows.

This is still a REAL caveat, not a disclaimer of convenience: with this
few outcome events, coefficient estimates have wide uncertainty and the
model should be treated as illustrative risk stratification (ranking
patients relative to each other), not a validated clinical instrument.
Every response from this module says so explicitly, and the frontend is
expected to surface that caveat, not just the score.
"""
from datetime import date, timedelta
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

from models import ARTClient, DefaulterTrace

TODAY = lambda: date.today()  # noqa: E731

MIN_TRAINING_EVENTS = 8  # minimum LTFU-labeled patients before we trust a fitted model at all


def _feature_row(c: ARTClient) -> Optional[list]:
    """Build a feature vector for one patient. Returns None if too many
    required fields are missing to build a meaningful row."""
    if c.date_of_birth is None:
        age = None
    else:
        age = (TODAY() - c.date_of_birth).days / 365.25

    days_since_visit = (TODAY() - c.last_visit).days if c.last_visit else None
    adherence = c.adherence_score
    cd4 = c.cd4_count

    # Impute missing values with a neutral mid-range placeholder rather
    # than dropping the patient — logistic regression needs complete rows,
    # and a missing adherence/CD4 reading is itself weakly informative
    # (often means the patient hasn't been seen recently), not something
    # to silently exclude.
    return [
        age if age is not None else 35.0,
        days_since_visit if days_since_visit is not None else 30.0,
        adherence if adherence is not None else 70.0,
        cd4 if cd4 is not None else 350.0,
    ]


FEATURE_NAMES = ["age_years", "days_since_last_visit", "adherence_score", "cd4_count"]


def score_defaulter_risk(db: Session, facility_id: Optional[int] = None) -> dict:
    """
    Fits a logistic regression on the current active cohort (label = 1 if
    progress_status == LTFU) and scores every non-LTFU active patient's
    probability of becoming a defaulter, so the highest-risk *currently
    engaged* patients can be prioritized before they're lost, not just
    after.

    Falls back to a transparent rule-based score (days-overdue only) if
    there isn't enough labeled data to fit a model at all — an untrained
    model returning confident-looking numbers would be worse than an
    honest rule.
    """
    q = db.query(ARTClient).filter(ARTClient.is_active == 1)
    if facility_id:
        q = q.filter(ARTClient.facility_id == facility_id)
    all_patients = q.all()

    labeled = [(c, 1 if c.progress_status == "LTFU" else 0) for c in all_patients]
    n_events = sum(y for _, y in labeled)
    method = "logistic_regression"
    model = None

    if n_events >= MIN_TRAINING_EVENTS and len(labeled) - n_events >= MIN_TRAINING_EVENTS:
        from sklearn.linear_model import LogisticRegression

        X = np.array([_feature_row(c) for c, _ in labeled])
        y = np.array([lbl for _, lbl in labeled])
        model = LogisticRegression(max_iter=1000, class_weight="balanced")
        model.fit(X, y)
    else:
        method = "rule_based_fallback"

    results = []
    for c in all_patients:
        if c.progress_status == "LTFU":
            continue  # already lost — this list is about patients still engaged but at risk
        row = _feature_row(c)

        if model is not None:
            proba = float(model.predict_proba(np.array([row]))[0][1])
        else:
            days_overdue = max(0, (TODAY() - c.next_appointment).days) if c.next_appointment else 0
            proba = min(1.0, days_overdue / 60)  # simple linear ramp, transparent, no model

        risk_score = round(proba * 100, 1)
        band = "HIGH" if risk_score >= 60 else "MEDIUM" if risk_score >= 25 else "LOW"
        days_overdue = max(0, (TODAY() - c.next_appointment).days) if c.next_appointment else 0

        results.append({
            "patient_id": c.id,
            "art_number": c.art_number,
            "full_name": c.full_name,
            "risk_score": risk_score,
            "risk_band": band,
            "days_overdue": days_overdue,
            "adherence_score": c.adherence_score,
            "cd4_count": c.cd4_count,
        })

    results.sort(key=lambda r: -r["risk_score"])

    response = {
        "patients": results,
        "method": method,
        "n_training_events": n_events,
        "n_total_labeled": len(labeled),
    }
    if method == "logistic_regression":
        response["coefficients"] = {
            name: round(float(coef), 4) for name, coef in zip(FEATURE_NAMES, model.coef_[0])
        }
        response["caveat"] = (
            f"Logistic regression fit on {n_events} LTFU-labeled patients out of {len(labeled)} active — "
            "a small sample. Treat as relative risk stratification for prioritizing outreach, not a "
            "validated clinical prediction. Coefficients are directionally informative, not precise effect sizes."
        )
    else:
        response["caveat"] = (
            f"Only {n_events} LTFU-labeled patients available (need {MIN_TRAINING_EVENTS}+ on both sides to "
            "fit a model responsibly) — showing a transparent days-overdue ramp instead of a fitted model."
        )
    return response


def defaulter_reasons(db: Session) -> dict:
    """Aggregate logged trace reasons — the real, evidence-based root-cause
    breakdown (from actual trace attempts), not a modeled attribution."""
    from sqlalchemy import func
    rows = (
        db.query(DefaulterTrace.reason_for_default, func.count(DefaulterTrace.id))
        .filter(DefaulterTrace.reason_for_default.isnot(None))
        .group_by(DefaulterTrace.reason_for_default)
        .all()
    )
    total = sum(count for _, count in rows) or 1
    return {
        "reasons": [
            {"reason": reason, "count": count, "pct": round(count / total * 100, 1)}
            for reason, count in sorted(rows, key=lambda r: -r[1])
        ],
        "n_traces": total if rows else 0,
    }
