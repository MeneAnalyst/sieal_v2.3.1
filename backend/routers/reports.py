"""Export and reporting router."""
import csv, io, json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta

from database import get_db
from models import ARTClient, Batch, DispenseRecord, Drug
from routers.auth import current_user

router = APIRouter()


@router.get("/export/patients")
def export_patients(db: Session = Depends(get_db), session: dict = Depends(current_user)):
    fid = session.get("facility_id")
    q = db.query(ARTClient).filter(ARTClient.is_active==1)
    if fid:
        q = q.filter(ARTClient.facility_id == fid)
    clients = q.all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["ART Number","TB Number","Full Name","DOB","Gender","Regime","Treatment Combination",
                "Visit Type","Initiation Date","Progress Status","CD4 Count","CD4 Date",
                "VL Result","VL Date","VL Suppressed","Adherence Score","Stock Status",
                "Last Visit","Next Appointment","ECI Flag","ECI Reason"])
    for c in clients:
        w.writerow([c.art_number, c.tb_number, c.full_name, c.date_of_birth, c.gender,
                    c.regime, c.treatment_combination, c.visit_type, c.initiation_date,
                    c.progress_status, c.cd4_count, c.cd4_date, c.vl_result, c.vl_date,
                    "Yes" if c.vl_suppressed else "No", c.adherence_score, c.stock_status,
                    c.last_visit, c.next_appointment,
                    "Yes" if c.is_eci_flag else "No", c.eci_reason])
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=patients_export.csv"})


@router.get("/export/stock")
def export_stock(db: Session = Depends(get_db), session: dict = Depends(current_user)):
    batches = db.query(Batch).filter(Batch.quantity_remaining > 0)\
                .order_by(Batch.expiry_date.asc()).all()
    today = date.today()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Drug Name","Batch Number","Expiry Date","Days to Expiry",
                "Qty Received","Qty Remaining","Supplier","Alert Status"])
    for b in batches:
        days = (b.expiry_date - today).days
        status = "RED" if days<=30 else "AMBER" if days<=90 else "GREEN"
        w.writerow([b.drug.name if b.drug else "", b.batch_number, b.expiry_date,
                    days, b.quantity_received, b.quantity_remaining, b.supplier, status])
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=stock_export.csv"})


@router.get("/export/dispenses")
def export_dispenses(db: Session = Depends(get_db), session: dict = Depends(current_user)):
    records = db.query(DispenseRecord).order_by(DispenseRecord.dispense_date.desc()).limit(5000).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Date","Client Name","ART Number","Drug","Batch","Quantity","Dispensed By"])
    for r in records:
        w.writerow([r.dispense_date,
                    r.client.full_name if r.client else "",
                    r.client.art_number if r.client else "",
                    r.batch.drug.name if r.batch and r.batch.drug else "",
                    r.batch.batch_number if r.batch else "",
                    r.quantity, r.dispensed_by])
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dispenses_export.csv"})


@router.get("/summary-json")
def summary_json(db: Session = Depends(get_db), session: dict = Depends(current_user)):
    fid = session.get("facility_id")
    today = date.today()
    q = db.query(ARTClient).filter(ARTClient.is_active==1)
    if fid: q = q.filter(ARTClient.facility_id == fid)
    total = q.count()
    active = q.filter(ARTClient.progress_status=="ACTIVE").count()
    ltfu = q.filter(ARTClient.progress_status=="LTFU").count()
    tf = q.filter(ARTClient.progress_status=="TREATMENT_FAILURE").count()
    eci = q.filter(ARTClient.is_eci_flag==1).count()
    suppressed = q.filter(ARTClient.vl_suppressed==1).count()
    unsuppressed = q.filter(ARTClient.vl_suppressed==0, ARTClient.vl_result != None).count()
    due_30 = q.filter(ARTClient.next_appointment >= today, ARTClient.next_appointment <= today+timedelta(days=30)).count()
    return {
        "generated": today.isoformat(),
        "patients": {"total": total, "active": active, "ltfu": ltfu, "treatment_failure": tf, "eci_flagged": eci},
        "viral_load": {"suppressed": suppressed, "unsuppressed": unsuppressed,
                       "suppression_rate": round(suppressed/(suppressed+unsuppressed)*100, 1) if (suppressed+unsuppressed) > 0 else 0},
        "appointments": {"due_next_30_days": due_30},
    }
