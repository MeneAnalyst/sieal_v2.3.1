from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from datetime import date, timedelta

from database import get_db
from models import Batch, ARTClient, DispenseRecord

router = APIRouter()


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    today = date.today()

    total_clients = db.query(ARTClient).filter(ARTClient.is_active == 1).count()

    due_today = db.query(ARTClient).filter(
        ARTClient.is_active == 1, ARTClient.next_appointment == today
    ).count()

    due_week = db.query(ARTClient).filter(
        ARTClient.is_active == 1,
        ARTClient.next_appointment >= today,
        ARTClient.next_appointment <= today + timedelta(days=7),
    ).count()

    ltfu = db.query(ARTClient).filter(
        ARTClient.is_active == 1,
        ARTClient.next_appointment < today - timedelta(days=14),
    ).count()

    red_alerts = db.query(Batch).filter(
        Batch.quantity_remaining > 0,
        Batch.expiry_date >= today,
        Batch.expiry_date <= today + timedelta(days=30),
    ).count()

    amber_alerts = db.query(Batch).filter(
        Batch.quantity_remaining > 0,
        Batch.expiry_date > today + timedelta(days=30),
        Batch.expiry_date <= today + timedelta(days=90),
    ).count()

    total_batches = db.query(Batch).filter(Batch.quantity_remaining > 0).count()

    dispensed_today = (
        db.query(func.sum(DispenseRecord.quantity))
        .filter(DispenseRecord.dispense_date == today)
        .scalar() or 0
    )

    dispensed_month = (
        db.query(func.sum(DispenseRecord.quantity))
        .filter(DispenseRecord.dispense_date >= today.replace(day=1))
        .scalar() or 0
    )

    # Recent 7-day trend (for mini sparkline)
    daily_trend = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        qty = (
            db.query(func.sum(DispenseRecord.quantity))
            .filter(DispenseRecord.dispense_date == d)
            .scalar() or 0
        )
        daily_trend.append({"date": d.isoformat(), "qty": qty})

    # ── Relevant clinical KPIs ──────────────────────────────────────
    active_q = db.query(ARTClient).filter(ARTClient.is_active == 1)

    eci_flagged = active_q.filter(ARTClient.is_eci_flag == 1).count()
    treatment_failure_count = active_q.filter(ARTClient.progress_status == "TREATMENT_FAILURE").count()

    vl_suppressed = active_q.filter(ARTClient.vl_suppressed == 1).count()
    vl_unsuppressed = active_q.filter(ARTClient.vl_suppressed == 0, ARTClient.vl_result.isnot(None)).count()
    vl_total = vl_suppressed + vl_unsuppressed
    vl_suppression_pct = round(vl_suppressed / vl_total * 100, 1) if vl_total else None

    avg_adherence = db.query(func.avg(ARTClient.adherence_score)).filter(
        ARTClient.is_active == 1, ARTClient.adherence_score.isnot(None)
    ).scalar()
    avg_adherence = round(avg_adherence, 1) if avg_adherence is not None else None

    # ── Relevant network KPI: how many drug lines currently have surplus
    # available to donate (Section 4B formula), reused from forecast.py so
    # the Dashboard and Network page never disagree on the number.
    from routers.forecast import get_adc, get_total_stock, donatable_surplus
    from models import Drug
    donatable_drug_count = 0
    for drug in db.query(Drug).all():
        adc = get_adc(drug.id, db)
        if adc <= 0:
            continue
        total = get_total_stock(drug.id, db)
        if donatable_surplus(total, adc) > 0:
            donatable_drug_count += 1

    return {
        "date": today.isoformat(),
        "total_clients": total_clients,
        "due_today": due_today,
        "due_this_week": due_week,
        "ltfu_count": ltfu,
        "red_alerts": red_alerts,
        "amber_alerts": amber_alerts,
        "total_active_batches": total_batches,
        "dispensed_today": int(dispensed_today),
        "dispensed_this_month": int(dispensed_month),
        "daily_trend": daily_trend,
        "eci_flagged": eci_flagged,
        "treatment_failure_count": treatment_failure_count,
        "vl_suppression_pct": vl_suppression_pct,
        "avg_adherence": avg_adherence,
        "donatable_drug_count": donatable_drug_count,
    }


@router.get("/activity-feed")
def activity_feed(limit: int = 15, db: Session = Depends(get_db)):
    """
    Latest Activities — recent dispense events, each joined with the
    patient's current ECI status. Scoped to dispenses specifically (not
    a generic "recent registrations" feed) because DispenseRecord is the
    only table in this schema with a real system event timestamp;
    ARTClient.enrollment_date is a clinical date, not an audit timestamp
    — using it to mean "recently added to this system" would be
    misleading for patients imported from real historical EHR records.
    """
    records = (
        db.query(DispenseRecord)
        .options(joinedload(DispenseRecord.client), joinedload(DispenseRecord.batch).joinedload(Batch.drug))
        .order_by(DispenseRecord.dispense_date.desc(), DispenseRecord.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "client_id": r.client.id if r.client else None,
            "client_name": r.client.full_name if r.client else "",
            "art_number": r.client.art_number if r.client else "",
            "drug_name": r.batch.drug.name if r.batch and r.batch.drug else "",
            "quantity": r.quantity,
            "dispense_date": r.dispense_date.isoformat(),
            "dispensed_by": r.dispensed_by,
            "is_eci_flag": bool(r.client.is_eci_flag) if r.client else False,
            "eci_reason": r.client.eci_reason if r.client else None,
        }
        for r in records
    ]
