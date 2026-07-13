from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import date, timedelta

from database import get_db
from models import ARTClient, VLResult, HTSRecord, Facility
from routers.auth import current_user

router = APIRouter()

VISIT_INTERVALS = {"PHARMACY": 180, "CLINICAL": 90}


def calc_adherence(client: ARTClient, db: Session) -> float:
    """Simple adherence: ratio of on-time dispenses in last 180 days."""
    from models import DispenseRecord
    since = date.today() - timedelta(days=180)
    total = db.query(DispenseRecord).filter(
        DispenseRecord.client_id == client.id,
        DispenseRecord.dispense_date >= since,
    ).count()
    interval = VISIT_INTERVALS.get(client.visit_type, 180)
    expected = 180 / interval
    return min(100.0, round((total / max(expected, 1)) * 100, 1))


def patient_dict(c: ARTClient, include_vl: bool = False, db: Session = None) -> dict:
    d = {
        "id": c.id,
        "art_number": c.art_number,
        "tb_number": c.tb_number,
        "oi_number": c.oi_number,
        "full_name": c.full_name,
        "date_of_birth": c.date_of_birth.isoformat() if c.date_of_birth else None,
        "gender": c.gender,
        "phone": c.phone,
        "treatment_combination": c.treatment_combination,
        "regime": c.regime,
        "visit_type": c.visit_type,
        "initiation_date": c.initiation_date.isoformat() if c.initiation_date else None,
        "enrollment_date": c.enrollment_date.isoformat() if c.enrollment_date else None,
        "cd4_count": c.cd4_count,
        "cd4_date": c.cd4_date.isoformat() if c.cd4_date else None,
        "vl_result": c.vl_result,
        "vl_date": c.vl_date.isoformat() if c.vl_date else None,
        "vl_suppressed": bool(c.vl_suppressed),
        "progress_status": c.progress_status,
        "adherence_score": c.adherence_score,
        "stock_status": c.stock_status or "IN",
        "last_visit": c.last_visit.isoformat() if c.last_visit else None,
        "next_appointment": c.next_appointment.isoformat() if c.next_appointment else None,
        "is_active": c.is_active,
        "is_eci_flag": bool(c.is_eci_flag),
        "eci_reason": c.eci_reason,
        "eci_flagged_date": c.eci_flagged_date.isoformat() if c.eci_flagged_date else None,
        "facility_id": c.facility_id,
        "facility_name": c.facility.name if c.facility else "",
    }
    if include_vl and db:
        history = db.query(VLResult).filter(VLResult.patient_id == c.id)\
                    .order_by(VLResult.sample_date.desc()).limit(6).all()
        d["vl_history"] = [
            {"result": v.result, "date": v.sample_date.isoformat(), "suppressed": bool(v.suppressed)}
            for v in history
        ]
    return d


@router.get("/")
def list_patients(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    eci_only: bool = Query(False),
    facility_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    session: dict = Depends(current_user),
):
    q = db.query(ARTClient).filter(ARTClient.is_active == 1)
    fid = facility_id or session.get("facility_id")
    if fid:
        q = q.filter(ARTClient.facility_id == fid)
    if search:
        t = f"%{search}%"
        q = q.filter((ARTClient.art_number.ilike(t)) | (ARTClient.full_name.ilike(t)))
    if status:
        q = q.filter(ARTClient.progress_status == status.upper())
    if eci_only:
        q = q.filter(ARTClient.is_eci_flag == 1)
    clients = q.order_by(ARTClient.next_appointment.asc()).all()
    return [patient_dict(c) for c in clients]


@router.post("/", status_code=201)
def create_patient(payload: dict, db: Session = Depends(get_db), session: dict = Depends(current_user)):
    existing = db.query(ARTClient).filter(ARTClient.art_number == payload["art_number"]).first()
    if existing:
        raise HTTPException(400, "ART number already registered")

    enroll = date.fromisoformat(payload["enrollment_date"]) if payload.get("enrollment_date") else date.today()
    interval = 180 if payload.get("visit_type", "PHARMACY") == "PHARMACY" else 90
    vl = payload.get("vl_result")

    c = ARTClient(
        facility_id           = payload.get("facility_id") or session.get("facility_id"),
        art_number            = payload["art_number"],
        tb_number             = payload.get("tb_number"),
        oi_number             = payload.get("oi_number"),
        full_name             = payload["full_name"],
        date_of_birth         = date.fromisoformat(payload["date_of_birth"]) if payload.get("date_of_birth") else None,
        gender                = payload.get("gender"),
        phone                 = payload.get("phone"),
        treatment_combination = payload.get("treatment_combination"),
        regime                = payload.get("regime"),
        visit_type            = payload.get("visit_type", "PHARMACY"),
        initiation_date       = date.fromisoformat(payload["initiation_date"]) if payload.get("initiation_date") else None,
        enrollment_date       = enroll,
        cd4_count             = payload.get("cd4_count"),
        cd4_date              = date.fromisoformat(payload["cd4_date"]) if payload.get("cd4_date") else None,
        vl_result             = vl,
        vl_date               = date.fromisoformat(payload["vl_date"]) if payload.get("vl_date") else None,
        vl_suppressed         = 1 if vl and float(vl) < 1000 else 0,
        progress_status       = payload.get("progress_status", "ACTIVE"),
        stock_status          = payload.get("stock_status", "IN"),
        last_visit            = enroll,
        next_appointment      = enroll + timedelta(days=interval),
        is_active             = 1,
    )
    # Auto-ECI flag
    _auto_eci(c)
    db.add(c)
    db.commit()
    db.refresh(c)
    return patient_dict(c)


@router.get("/eci")
def eci_list(db: Session = Depends(get_db), session: dict = Depends(current_user)):
    """Patients shortlisted for Early Case Investigation."""
    fid = session.get("facility_id")
    q = db.query(ARTClient).filter(ARTClient.is_active == 1, ARTClient.is_eci_flag == 1)
    if fid:
        q = q.filter(ARTClient.facility_id == fid)
    clients = q.order_by(ARTClient.cd4_count.asc()).all()
    return [patient_dict(c) for c in clients]


@router.post("/refresh-eci")
def refresh_eci(db: Session = Depends(get_db), session: dict = Depends(current_user)):
    """Re-evaluate all patients for ECI flags based on clinical rules."""
    fid = session.get("facility_id")
    q = db.query(ARTClient).filter(ARTClient.is_active == 1)
    if fid:
        q = q.filter(ARTClient.facility_id == fid)
    clients = q.all()
    flagged = 0
    for c in clients:
        before = c.is_eci_flag
        _auto_eci(c)
        if c.is_eci_flag and not before:
            c.eci_flagged_date = date.today()
            flagged += 1
    db.commit()
    return {"message": f"ECI refresh complete", "newly_flagged": flagged}


def _auto_eci(c: ARTClient):
    """Business rules for Early Case Investigation flagging."""
    reasons = []
    if c.cd4_count and c.cd4_count < 200:
        if c.progress_status in ("NEW_INITIATION", "ACTIVE") and c.initiation_date and \
           (date.today() - c.initiation_date).days <= 90:
            reasons.append("New initiation with CD4 < 200")
        if c.progress_status == "RTT":
            reasons.append("Return to Treatment (RTT) with CD4 < 200")
    if c.progress_status == "TREATMENT_FAILURE":
        reasons.append("Classified under Treatment Failure (VL ≥ 1000 on 2nd+ test)")
    if c.vl_result and c.vl_result >= 1000 and c.progress_status == "ACTIVE":
        reasons.append(f"Unsuppressed VL ({int(c.vl_result):,} copies/mL) on active treatment")

    if reasons:
        c.is_eci_flag = 1
        c.eci_reason = "; ".join(reasons)
    else:
        c.is_eci_flag = 0
        c.eci_reason = None


@router.get("/{patient_id}/stats")
def patient_statistics(patient_id: int, db: Session = Depends(get_db), session: dict = Depends(current_user)):
    """
    Section 8 — Hypothesis Analysis Integration.

    Bayesian posterior probability of treatment failure is delegated to
    kpi_engine.bayesian_confidence(): a genuine Beta-Binomial conjugate
    update with a literature-sourced prior (WHO 3rd-95 target implies a
    ~5% population failure rate), returned with its 95% credible interval
    rather than a bare point estimate — a Statistical Engineer shows the
    uncertainty band alongside the number, not just the number. Only
    surfaced when the patient has 2+ consecutive unsuppressed readings
    (spec requirement) so a single noisy result never triggers a scary
    figure.

    CD4 slope: simple (last - first) / months across HTS-linked CD4
    readings in the last 180 days, used only to choose a Trending icon.
    """
    import kpi_engine

    patient = db.query(ARTClient).filter(ARTClient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "Patient not found")

    history = (
        db.query(VLResult)
        .filter(VLResult.patient_id == patient_id)
        .order_by(VLResult.sample_date.asc())
        .all()
    )
    readings = [{"result": v.result, "date": v.sample_date.isoformat(), "suppressed": bool(v.suppressed)} for v in history]
    if patient.vl_result is not None and patient.vl_date:
        readings.append({"result": patient.vl_result, "date": patient.vl_date.isoformat(), "suppressed": bool(patient.vl_suppressed)})
    readings.sort(key=lambda r: r["date"])

    last_two_failed = len(readings) >= 2 and readings[-1]["result"] >= 1000 and readings[-2]["result"] >= 1000

    bayesian = None
    if last_two_failed:
        conf = kpi_engine.bayesian_confidence(db, patient_id)
        bayesian = {
            "posterior_probability": conf["posterior_mean_failure_risk"],
            "credible_interval_95": conf["credible_interval_95"],
            "evidence_readings": conf["n_vl_results"],
            "consecutive_failures": True,
            "method": conf["method"],
        }

    cd4_history = (
        db.query(HTSRecord)
        .filter(HTSRecord.patient_id == patient_id, HTSRecord.cd4_count.isnot(None),
                HTSRecord.test_date >= date.today() - timedelta(days=180))
        .order_by(HTSRecord.test_date.asc())
        .all()
    )
    cd4_slope = None
    trend = "flat"
    if len(cd4_history) >= 2:
        first, last = cd4_history[0], cd4_history[-1]
        months = max(1, (last.test_date - first.test_date).days / 30)
        cd4_slope = round((last.cd4_count - first.cd4_count) / months, 1)
        trend = "up" if cd4_slope > 5 else "down" if cd4_slope < -5 else "flat"

    return {
        "patient_id": patient_id,
        "vl_history": readings,
        "treatment_failure_bayesian": bayesian,
        "cd4_slope_per_month": cd4_slope,
        "cd4_trend": trend,
    }


@router.get("/{patient_id}")
def get_patient(patient_id: int, db: Session = Depends(get_db), session: dict = Depends(current_user)):
    c = db.query(ARTClient).filter(ARTClient.id == patient_id).first()
    if not c:
        raise HTTPException(404, "Patient not found")
    return patient_dict(c, include_vl=True, db=db)


@router.put("/{patient_id}")
def update_patient(patient_id: int, payload: dict, db: Session = Depends(get_db), session: dict = Depends(current_user)):
    c = db.query(ARTClient).filter(ARTClient.id == patient_id).first()
    if not c:
        raise HTTPException(404, "Patient not found")
    fields = [
        "full_name","date_of_birth","gender","phone","treatment_combination",
        "regime","visit_type","initiation_date","cd4_count","cd4_date",
        "vl_result","vl_date","progress_status","stock_status","tb_number","oi_number",
    ]
    for f in fields:
        if f in payload:
            val = payload[f]
            if f in ("date_of_birth","initiation_date","cd4_date","vl_date") and val:
                val = date.fromisoformat(val)
            setattr(c, f, val)
    if c.vl_result:
        c.vl_suppressed = 1 if float(c.vl_result) < 1000 else 0
    c.adherence_score = calc_adherence(c, db)
    _auto_eci(c)
    db.commit()
    return patient_dict(c, include_vl=True, db=db)


@router.delete("/{patient_id}", status_code=204)
def deactivate_patient(patient_id: int, db: Session = Depends(get_db), session: dict = Depends(current_user)):
    """
    Soft-delete only — sets is_active=0, never removes the row. Medical
    records (dispense history, VL history, ECI history) must never be
    hard-deleted, both for audit-trail integrity and because the row is
    referenced by DispenseRecord.client_id (FK) elsewhere in the system.
    A deactivated patient simply stops appearing in the active patient
    list and dashboard counts.
    """
    c = db.query(ARTClient).filter(ARTClient.id == patient_id).first()
    if not c:
        raise HTTPException(404, "Patient not found")
    c.is_active = 0
    db.commit()


@router.post("/{patient_id}/vl")
def add_vl_result(patient_id: int, payload: dict, db: Session = Depends(get_db), session: dict = Depends(current_user)):
    c = db.query(ARTClient).filter(ARTClient.id == patient_id).first()
    if not c:
        raise HTTPException(404, "Patient not found")
    result = float(payload["result"])
    vl = VLResult(
        patient_id  = patient_id,
        result      = result,
        sample_date = date.fromisoformat(payload["sample_date"]),
        result_date = date.fromisoformat(payload["result_date"]) if payload.get("result_date") else None,
        suppressed  = 1 if result < 1000 else 0,
        source      = payload.get("source", "MANUAL"),
    )
    db.add(vl)
    # Update patient current VL
    c.vl_result = result
    c.vl_date   = vl.sample_date
    c.vl_suppressed = vl.suppressed
    _auto_eci(c)
    db.commit()
    return {"message": "VL result recorded", "suppressed": bool(vl.suppressed)}
