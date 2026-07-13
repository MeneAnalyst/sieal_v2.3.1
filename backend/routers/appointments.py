from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date, timedelta

from database import get_db
from models import ARTClient, DefaulterTrace
from routers.auth import current_user
import defaulter_risk

router = APIRouter()


def client_to_dict(c: ARTClient, today: date) -> dict:
    days_until = (c.next_appointment - today).days if c.next_appointment else None
    return {
        "id": c.id,
        "art_number": c.art_number,
        "full_name": c.full_name,
        "regime": c.regime,
        "visit_type": c.visit_type,
        "phone": c.phone,
        "last_visit": c.last_visit.isoformat() if c.last_visit else None,
        "next_appointment": c.next_appointment.isoformat() if c.next_appointment else None,
        "days_until": days_until,
    }


@router.get("/upcoming")
def upcoming(days: int = Query(30), db: Session = Depends(get_db)):
    today = date.today()
    until = today + timedelta(days=days)
    clients = (
        db.query(ARTClient)
        .filter(
            ARTClient.is_active == 1,
            ARTClient.next_appointment >= today,
            ARTClient.next_appointment <= until,
        )
        .order_by(ARTClient.next_appointment.asc())
        .all()
    )
    return [client_to_dict(c, today) for c in clients]


@router.get("/today")
def due_today(db: Session = Depends(get_db)):
    today = date.today()
    clients = db.query(ARTClient).filter(
        ARTClient.is_active == 1, ARTClient.next_appointment == today
    ).all()
    return [client_to_dict(c, today) for c in clients]


@router.get("/ltfu")
def ltfu(threshold: int = Query(14), db: Session = Depends(get_db)):
    """Clients overdue by more than `threshold` days — Lost To Follow Up."""
    today = date.today()
    cutoff = today - timedelta(days=threshold)
    clients = (
        db.query(ARTClient)
        .filter(ARTClient.is_active == 1, ARTClient.next_appointment < cutoff)
        .order_by(ARTClient.next_appointment.asc())
        .all()
    )
    result = []
    for c in clients:
        d = client_to_dict(c, today)
        d["days_overdue"] = (today - c.next_appointment).days if c.next_appointment else 0
        result.append(d)
    return result


@router.get("/cohorts")
def cohort_calendar(
    month: Optional[str] = Query(None, description="YYYY-MM — defaults to current month"),
    defaulter_threshold_days: int = Query(14, description="Days overdue before a cohort member counts as a defaulter"),
    db: Session = Depends(get_db),
):
    """
    Cohort Calendar — groups active patients by their ART initiation
    month ("JUL-2026" style cohort, per Zimbabwe MOHCC convention: a
    patient initiated 10/07/2026 belongs to the JUL-2026 cohort), split
    by visit type (PHARMACY = 6-month supply, CLINICAL = 3-month supply —
    matches VISIT_INTERVALS elsewhere in this codebase).

    For the requested month, returns per-cohort: total members, the
    3-month/6-month split, how many are expected back THIS month
    (next_appointment falls within it), how many are RTT (returning
    after a previously missed appointment), and how many currently sit
    past `defaulter_threshold_days` overdue — the same threshold concept
    as /ltfu, but broken down per-cohort rather than as one flat list.
    """
    today = date.today()
    if month:
        try:
            year, mon = int(month[:4]), int(month[5:7])
        except (ValueError, IndexError):
            raise HTTPException(400, "month must be in YYYY-MM format")
    else:
        year, mon = today.year, today.month

    month_start = date(year, mon, 1)
    month_end = date(year + 1, 1, 1) - timedelta(days=1) if mon == 12 else date(year, mon + 1, 1) - timedelta(days=1)
    defaulter_cutoff = today - timedelta(days=defaulter_threshold_days)

    clients = db.query(ARTClient).filter(ARTClient.is_active == 1, ARTClient.initiation_date.isnot(None)).all()

    cohorts: dict = {}
    for c in clients:
        label = c.initiation_date.strftime("%b-%Y").upper()
        if label not in cohorts:
            cohorts[label] = {
                "cohort": label,
                "cohort_sort_key": c.initiation_date.strftime("%Y-%m"),
                "total_members": 0,
                "pharmacy_count": 0,   # 6-month supply
                "clinical_count": 0,   # 3-month supply
                "expected_this_month": 0,
                "rtt_count": 0,
                "defaulter_count": 0,
            }
        row = cohorts[label]
        row["total_members"] += 1
        if c.visit_type == "PHARMACY":
            row["pharmacy_count"] += 1
        else:
            row["clinical_count"] += 1
        if c.next_appointment and month_start <= c.next_appointment <= month_end:
            row["expected_this_month"] += 1
        if c.progress_status == "RTT":
            row["rtt_count"] += 1
        if c.next_appointment and c.next_appointment < defaulter_cutoff:
            row["defaulter_count"] += 1

    result = sorted(cohorts.values(), key=lambda x: x["cohort_sort_key"], reverse=True)
    return {
        "month": f"{year:04d}-{mon:02d}",
        "defaulter_threshold_days": defaulter_threshold_days,
        "total_cohorts": len(result),
        "cohorts": result,
    }


@router.get("/cohorts/{cohort}/members")
def cohort_members(
    cohort: str,
    db: Session = Depends(get_db),
):
    """Drill-down: every active patient in one cohort (e.g. 'JUL-2026'),
    for the calendar's click-through view."""
    clients = db.query(ARTClient).filter(ARTClient.is_active == 1, ARTClient.initiation_date.isnot(None)).all()
    matched = [c for c in clients if c.initiation_date.strftime("%b-%Y").upper() == cohort.upper()]
    today = date.today()
    return [
        {
            **client_to_dict(c, today),
            "progress_status": c.progress_status,
            "days_overdue": (today - c.next_appointment).days if c.next_appointment and c.next_appointment < today else 0,
        }
        for c in sorted(matched, key=lambda c: c.next_appointment or date.max)
    ]


@router.get("/calendar")
def calendar_view(db: Session = Depends(get_db)):
    """Group upcoming 28-day appointments by date for calendar display."""
    today = date.today()
    until = today + timedelta(days=28)
    clients = (
        db.query(ARTClient)
        .filter(
            ARTClient.is_active == 1,
            ARTClient.next_appointment >= today,
            ARTClient.next_appointment <= until,
        )
        .all()
    )
    cal: dict = {}
    for c in clients:
        key = c.next_appointment.isoformat()
        if key not in cal:
            cal[key] = {
                "date": key,
                "pharmacy_count": 0,
                "clinical_count": 0,
                "total": 0,
                "clients": [],
            }
        if c.visit_type == "PHARMACY":
            cal[key]["pharmacy_count"] += 1
        else:
            cal[key]["clinical_count"] += 1
        cal[key]["total"] += 1
        cal[key]["clients"].append({"name": c.full_name, "art": c.art_number, "type": c.visit_type})
    return sorted(cal.values(), key=lambda x: x["date"])


@router.post("/mark-attended/{client_id}")
def mark_attended(client_id: int, db: Session = Depends(get_db)):
    """Mark a client as attended — triggers next appointment calculation."""
    from datetime import timedelta
    client = db.query(ARTClient).filter(ARTClient.id == client_id).first()
    if not client:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Client not found")
    interval = 180 if client.visit_type == "PHARMACY" else 90
    client.last_visit = date.today()
    client.next_appointment = date.today() + timedelta(days=interval)
    db.commit()
    return {
        "message": "Attendance recorded",
        "next_appointment": client.next_appointment.isoformat(),
    }


# ══════════════════════════════════════════════════════════════════
# Defaulter Management — the primary Appointments-page component
# ══════════════════════════════════════════════════════════════════

@router.get("/defaulters")
def defaulter_risk_list(db: Session = Depends(get_db), session: dict = Depends(current_user)):
    """Risk-stratified list of currently-active patients, scored by
    defaulter_risk.py. See that module's docstring for the honest
    small-sample caveat surfaced in every response."""
    return defaulter_risk.score_defaulter_risk(db, facility_id=session.get("facility_id"))


@router.get("/defaulters/reasons")
def defaulter_reasons_breakdown(db: Session = Depends(get_db), session: dict = Depends(current_user)):
    """Real, evidence-based root-cause breakdown from logged trace attempts
    (not a modeled attribution) — feeds the Root Cause bar chart."""
    return defaulter_risk.defaulter_reasons(db)


@router.post("/defaulters/{patient_id}/trace", status_code=201)
def log_trace_attempt(patient_id: int, payload: dict, db: Session = Depends(get_db), session: dict = Depends(current_user)):
    """Log a tracing attempt: method used, outcome, and (if known) the
    patient-reported reason for defaulting. This is the real data source
    behind the root-cause breakdown above — the more attempts logged, the
    more the chart reflects actual causes rather than assumptions."""
    patient = db.query(ARTClient).filter(ARTClient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "Patient not found")

    trace = DefaulterTrace(
        patient_id=patient_id,
        trace_date=date.today(),
        trace_method=payload.get("trace_method"),
        trace_outcome=payload.get("trace_outcome"),
        reason_for_default=payload.get("reason_for_default"),
        notes=payload.get("notes"),
        logged_by=session.get("full_name") or session.get("username"),
    )
    db.add(trace)

    # A "RETURNED" outcome is itself a meaningful clinical event — reflect
    # it back onto the patient record so the rest of the system (ECI,
    # dashboards) sees the update immediately rather than waiting for the
    # patient's next dispense to reset their status.
    if payload.get("trace_outcome") == "RETURNED":
        patient.progress_status = "RTT"
        from routers.patients import _auto_eci
        _auto_eci(patient)

    db.commit()
    db.refresh(trace)
    return {
        "id": trace.id,
        "patient_id": patient_id,
        "trace_method": trace.trace_method,
        "trace_outcome": trace.trace_outcome,
        "reason_for_default": trace.reason_for_default,
        "trace_date": trace.trace_date.isoformat(),
    }


@router.get("/defaulters/{patient_id}/history")
def defaulter_trace_history(patient_id: int, db: Session = Depends(get_db), session: dict = Depends(current_user)):
    traces = (
        db.query(DefaulterTrace)
        .filter(DefaulterTrace.patient_id == patient_id)
        .order_by(DefaulterTrace.trace_date.desc())
        .all()
    )
    return [
        {
            "id": t.id, "trace_date": t.trace_date.isoformat(), "trace_method": t.trace_method,
            "trace_outcome": t.trace_outcome, "reason_for_default": t.reason_for_default,
            "notes": t.notes, "logged_by": t.logged_by,
        }
        for t in traces
    ]
