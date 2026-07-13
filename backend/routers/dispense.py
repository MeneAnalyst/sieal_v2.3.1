from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from datetime import date, timedelta

from database import get_db
from models import ARTClient, Batch, DispenseRecord
from schemas import DispenseCreate

router = APIRouter()

VISIT_INTERVALS = {"PHARMACY": 180, "CLINICAL": 90}


@router.post("/")
def dispense(payload: DispenseCreate, db: Session = Depends(get_db)):
    client = db.query(ARTClient).filter(ARTClient.id == payload.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    batch = db.query(Batch).options(joinedload(Batch.drug)).filter(
        Batch.id == payload.batch_id
    ).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    if batch.quantity_remaining < payload.quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient stock. Available: {batch.quantity_remaining}",
        )

    # Decrement stock
    batch.quantity_remaining -= payload.quantity

    # Advance client's visit record
    interval = VISIT_INTERVALS.get(client.visit_type, 180)
    client.last_visit = date.today()
    client.next_appointment = date.today() + timedelta(days=interval)

    record = DispenseRecord(
        client_id=payload.client_id,
        batch_id=payload.batch_id,
        quantity=payload.quantity,
        dispense_date=date.today(),
        dispensed_by=payload.dispensed_by or "Pharmacist",
        notes=payload.notes,
    )
    db.add(record)
    db.commit()

    return {
        "message": "Dispensed successfully",
        "client": client.full_name,
        "drug": batch.drug.name if batch.drug else "",
        "batch_number": batch.batch_number,
        "quantity_dispensed": payload.quantity,
        "stock_remaining": batch.quantity_remaining,
        "next_appointment": client.next_appointment.isoformat(),
    }


@router.get("/history/{client_id}")
def dispense_history(client_id: int, db: Session = Depends(get_db)):
    records = (
        db.query(DispenseRecord)
        .options(joinedload(DispenseRecord.batch).joinedload(Batch.drug))
        .filter(DispenseRecord.client_id == client_id)
        .order_by(DispenseRecord.dispense_date.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "drug_name": r.batch.drug.name if r.batch and r.batch.drug else "",
            "batch_number": r.batch.batch_number if r.batch else "",
            "expiry_date": r.batch.expiry_date.isoformat() if r.batch else "",
            "quantity": r.quantity,
            "dispense_date": r.dispense_date.isoformat(),
            "dispensed_by": r.dispensed_by,
            "notes": r.notes,
        }
        for r in records
    ]


@router.get("/recent")
def recent_dispenses(limit: int = 20, db: Session = Depends(get_db)):
    records = (
        db.query(DispenseRecord)
        .options(
            joinedload(DispenseRecord.client),
            joinedload(DispenseRecord.batch).joinedload(Batch.drug),
        )
        .order_by(DispenseRecord.dispense_date.desc(), DispenseRecord.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "client_name": r.client.full_name if r.client else "",
            "art_number": r.client.art_number if r.client else "",
            "drug_name": r.batch.drug.name if r.batch and r.batch.drug else "",
            "quantity": r.quantity,
            "dispense_date": r.dispense_date.isoformat(),
            "dispensed_by": r.dispensed_by,
        }
        for r in records
    ]
