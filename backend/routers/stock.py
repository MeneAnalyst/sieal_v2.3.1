from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List
from datetime import date, timedelta

from database import get_db
from models import Drug, Batch, ExpiryLoss, DispenseRecord
from schemas import BatchCreate, BatchResponse, ExpiryLossCreate

router = APIRouter()


def expiry_status(expiry_date: date) -> str:
    days = (expiry_date - date.today()).days
    if days <= 30:
        return "RED"
    elif days <= 90:
        return "AMBER"
    return "GREEN"


def enrich_batch(b: Batch) -> dict:
    days = (b.expiry_date - date.today()).days
    return {
        "id": b.id,
        "drug_id": b.drug_id,
        "drug_name": b.drug.name if b.drug else "",
        "drug_strength": b.drug.strength if b.drug else "",
        "batch_number": b.batch_number,
        "expiry_date": b.expiry_date.isoformat(),
        "quantity_received": b.quantity_received,
        "quantity_remaining": b.quantity_remaining,
        "received_date": b.received_date.isoformat() if b.received_date else None,
        "supplier": b.supplier,
        "gtin": b.gtin,
        "alert_status": expiry_status(b.expiry_date),
        "days_to_expiry": days,
    }


# ── Receive stock ─────────────────────────────────────────────────
@router.post("/receive")
def receive_stock(payload: BatchCreate, db: Session = Depends(get_db)):
    drug = db.query(Drug).filter(Drug.id == payload.drug_id).first()
    if not drug:
        raise HTTPException(status_code=404, detail="Drug not found")

    batch = Batch(
        drug_id=payload.drug_id,
        batch_number=payload.batch_number,
        expiry_date=payload.expiry_date,
        quantity_received=payload.quantity_received,
        quantity_remaining=payload.quantity_received,
        received_date=date.today(),
        supplier=payload.supplier,
        gtin=payload.gtin,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    batch.drug = drug
    return enrich_batch(batch)


# ── All active inventory (FEFO sorted) ───────────────────────────
@router.get("/")
def list_stock(db: Session = Depends(get_db)):
    batches = (
        db.query(Batch)
        .options(joinedload(Batch.drug))
        .filter(Batch.quantity_remaining > 0)
        .order_by(Batch.expiry_date.asc())
        .all()
    )
    return [enrich_batch(b) for b in batches]


# ── FEFO batch for a specific drug ───────────────────────────────
@router.get("/fefo/{drug_id}")
def get_fefo_batch(drug_id: int, db: Session = Depends(get_db)):
    batch = (
        db.query(Batch)
        .options(joinedload(Batch.drug))
        .filter(
            Batch.drug_id == drug_id,
            Batch.quantity_remaining > 0,
            Batch.expiry_date > date.today(),
        )
        .order_by(Batch.expiry_date.asc())
        .first()
    )
    if not batch:
        raise HTTPException(status_code=404, detail="No available stock for this drug")
    return enrich_batch(batch)


# ── Expiry alerts (RED + AMBER) ───────────────────────────────────
@router.get("/alerts")
def get_expiry_alerts(db: Session = Depends(get_db)):
    cutoff = date.today() + timedelta(days=90)
    batches = (
        db.query(Batch)
        .options(joinedload(Batch.drug))
        .filter(
            Batch.quantity_remaining > 0,
            Batch.expiry_date <= cutoff,
            Batch.expiry_date >= date.today(),
        )
        .order_by(Batch.expiry_date.asc())
        .all()
    )
    return [enrich_batch(b) for b in batches]


# ── All stock including zero-quantity (full history) ─────────────
@router.get("/all")
def list_all_stock(db: Session = Depends(get_db)):
    batches = (
        db.query(Batch)
        .options(joinedload(Batch.drug))
        .order_by(Batch.expiry_date.asc())
        .all()
    )
    return [enrich_batch(b) for b in batches]


# ── Record expiry loss ────────────────────────────────────────────
@router.post("/loss")
def record_expiry_loss(payload: ExpiryLossCreate, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.id == payload.batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    if payload.quantity_lost > batch.quantity_remaining:
        raise HTTPException(status_code=400, detail="Loss quantity exceeds remaining stock")

    batch.quantity_remaining -= payload.quantity_lost
    loss = ExpiryLoss(
        batch_id=payload.batch_id,
        quantity_lost=payload.quantity_lost,
        loss_date=date.today(),
        reason_code=payload.reason_code,
        notes=payload.notes,
    )
    db.add(loss)
    db.commit()
    return {"message": "Expiry loss recorded", "quantity_lost": payload.quantity_lost}


# ── Loss register ─────────────────────────────────────────────────
@router.get("/losses")
def get_loss_register(db: Session = Depends(get_db)):
    losses = (
        db.query(ExpiryLoss)
        .options(joinedload(ExpiryLoss.batch).joinedload(Batch.drug))
        .order_by(ExpiryLoss.loss_date.desc())
        .all()
    )
    return [
        {
            "id": l.id,
            "drug_name": l.batch.drug.name if l.batch and l.batch.drug else "",
            "batch_number": l.batch.batch_number if l.batch else "",
            "quantity_lost": l.quantity_lost,
            "loss_date": l.loss_date.isoformat(),
            "reason_code": l.reason_code,
            "notes": l.notes,
        }
        for l in losses
    ]


# ── Edit batch details ────────────────────────────────────────────
@router.put("/{batch_id}")
def update_batch(batch_id: int, payload: dict, db: Session = Depends(get_db)):
    """
    Only corrects data-entry fields — batch number, expiry date, supplier,
    GTIN. Quantities (received/remaining) are deliberately NOT editable
    here: they're derived from receive/dispense/loss events, and editing
    them directly would silently break the stock ledger's arithmetic
    (remaining = received − dispensed − lost). Use Receive Stock or
    Record Loss for quantity changes instead.
    """
    b = db.query(Batch).options(joinedload(Batch.drug)).filter(Batch.id == batch_id).first()
    if not b:
        raise HTTPException(404, "Batch not found")
    if "batch_number" in payload:
        b.batch_number = payload["batch_number"]
    if "expiry_date" in payload and payload["expiry_date"]:
        b.expiry_date = date.fromisoformat(payload["expiry_date"])
    if "supplier" in payload:
        b.supplier = payload["supplier"]
    if "gtin" in payload:
        b.gtin = payload["gtin"]
    db.commit()
    db.refresh(b)
    return enrich_batch(b)


# ── Delete a batch ─────────────────────────────────────────────────
@router.delete("/{batch_id}", status_code=204)
def delete_batch(batch_id: int, db: Session = Depends(get_db)):
    """
    Hard delete — but only permitted if the batch has zero dispense or
    loss records against it. A batch with real history must be kept for
    the audit trail; this endpoint is meant for correcting a genuine
    data-entry mistake (wrong batch created, never actually distributed),
    not for removing stock that's already been used.
    """
    b = db.query(Batch).filter(Batch.id == batch_id).first()
    if not b:
        raise HTTPException(404, "Batch not found")
    has_dispenses = db.query(DispenseRecord).filter(DispenseRecord.batch_id == batch_id).count() > 0
    has_losses = db.query(ExpiryLoss).filter(ExpiryLoss.batch_id == batch_id).count() > 0
    if has_dispenses or has_losses:
        raise HTTPException(
            400,
            "This batch has dispense or loss history and can't be deleted — "
            "it's kept for the audit trail. If stock was miscounted, use "
            "Record Loss to correct the remaining quantity instead."
        )
    db.delete(b)
    db.commit()
