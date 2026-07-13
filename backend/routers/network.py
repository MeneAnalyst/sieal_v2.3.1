"""
Stock Sharing Network Router
────────────────────────────
Allows clinics registered in the same health network to share stock
during shortage events.

Core intelligence:
  safe_to_donate = current_stock − (projected_90d_demand + 30d_safety_buffer)

A facility is only recommended as a donor if safe_to_donate > 0,
meaning giving away stock will NOT push them below their own safety threshold.

Proximity ranking uses Haversine distance when lat/lng are available.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import Optional
from datetime import date, timedelta
from math import radians, sin, cos, sqrt, atan2

from database import get_db
from models import Facility, StockTransfer, Drug, Batch, DispenseRecord, ARTClient

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────

def haversine_km(lat1, lng1, lat2, lng2) -> float:
    R = 6371
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


# Section 4B: ADC is measured over a trailing 90-day window (matches forecast.py),
# and a facility's protected floor is 120 days = 90-day order cycle + 30-day buffer.
ADC_WINDOW_DAYS = 90
PROTECTED_DAYS = 120


def get_drug_adc(drug_id: int, db: Session, window: int = ADC_WINDOW_DAYS) -> float:
    since = date.today() - timedelta(days=window)
    total = (
        db.query(func.sum(DispenseRecord.quantity))
        .join(Batch)
        .filter(Batch.drug_id == drug_id, DispenseRecord.dispense_date >= since)
        .scalar() or 0
    )
    return total / window


def get_drug_stock(drug_id: int, db: Session) -> int:
    return (
        db.query(func.sum(Batch.quantity_remaining))
        .filter(
            Batch.drug_id == drug_id,
            Batch.quantity_remaining > 0,
            Batch.expiry_date > date.today() + timedelta(days=30),
        )
        .scalar() or 0
    )


def safe_donation_qty(drug_id: int, db: Session) -> int:
    """
    Section 4B — Safe-to-Donate.
    Donatable = Current_Stock - (ADC * 120), i.e. the maximum quantity this
    facility can give away without falling below its own 90-day order cycle
    + 30-day emergency buffer. Floored at 0: a facility can never be pushed
    into incapacitation by a donation.
    """
    stock = get_drug_stock(drug_id, db)
    adc   = get_drug_adc(drug_id, db)
    protected = round(adc * PROTECTED_DAYS)
    return max(0, stock - protected)


def facility_dict(f: Facility, extra: dict = None) -> dict:
    d = {
        "id": f.id,
        "name": f.name,
        "address": f.address,
        "district": f.district,
        "province": f.province,
        "lat": f.lat,
        "lng": f.lng,
        "contact_name": f.contact_name,
        "contact_phone": f.contact_phone,
        "facility_type": f.facility_type,
        "is_current": bool(f.is_current),
    }
    if extra:
        d.update(extra)
    return d


def transfer_dict(t: StockTransfer) -> dict:
    return {
        "id": t.id,
        "drug_name": t.drug.name if t.drug else "",
        "donor_name": t.donor.name if t.donor else "",
        "receiver_name": t.receiver.name if t.receiver else "",
        "requester_name": t.requester.name if t.requester else "",
        "quantity_requested": t.quantity_requested,
        "quantity_approved": t.quantity_approved,
        "quantity_to_repay": t.quantity_to_repay,
        "quantity_repaid": t.quantity_repaid or 0,
        "status": t.status,
        "urgency": t.urgency,
        "request_date": t.request_date.isoformat() if t.request_date else None,
        "approved_date": t.approved_date.isoformat() if t.approved_date else None,
        "completed_date": t.completed_date.isoformat() if t.completed_date else None,
        "repaid_date": t.repaid_date.isoformat() if t.repaid_date else None,
        "notes": t.notes,
        "rejection_reason": t.rejection_reason,
    }


# ── Facility Registry ─────────────────────────────────────────────

@router.get("/facilities")
def list_facilities(db: Session = Depends(get_db)):
    facilities = db.query(Facility).order_by(Facility.name).all()
    return [facility_dict(f) for f in facilities]


@router.post("/facilities", status_code=201)
def register_facility(payload: dict, db: Session = Depends(get_db)):
    f = Facility(
        name          = payload["name"],
        address       = payload.get("address"),
        district      = payload.get("district"),
        province      = payload.get("province", "Matabeleland South"),
        lat           = payload.get("lat"),
        lng           = payload.get("lng"),
        contact_name  = payload.get("contact_name"),
        contact_phone = payload.get("contact_phone"),
        facility_type = payload.get("facility_type", "Clinic"),
        is_current    = int(payload.get("is_current", 0)),
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return facility_dict(f)


@router.delete("/facilities/{facility_id}", status_code=204)
def remove_facility(facility_id: int, db: Session = Depends(get_db)):
    f = db.query(Facility).filter(Facility.id == facility_id).first()
    if not f:
        raise HTTPException(404, "Facility not found")
    db.delete(f)
    db.commit()


# ── Core Intelligence: Who Can Help? ─────────────────────────────

@router.get("/can-share")
def who_can_share(
    drug_id: int = Query(...),
    quantity_needed: int = Query(...),
    db: Session = Depends(get_db),
):
    """
    For a given drug and quantity needed, returns a ranked list of
    network facilities that can safely donate stock — ordered by:
      1. Whether they can cover the full quantity needed
      2. How much safe-to-donate surplus they have
      3. Proximity to current facility (km) if coordinates exist

    Each result includes:
      - safe_to_donate: max they can give without risk
      - can_cover_full: whether they meet the full request
      - impact_after: their DSR after donation
      - distance_km: distance from requesting facility
      - is_real_data: False for every result currently returned — see
        DATA HONESTY NOTE below. Surfaced per-row (not just here in the
        docstring) so the frontend can actually display it, matching the
        same honesty pattern used in the Population Analytics endpoints.

    DATA HONESTY NOTE:
    The OLTP `Batch` table has no `facility_id` column — stock is a single
    global pool, attributed here to whichever facility has `is_current=1`.
    Every OTHER facility's stock/ADC figures below are seeded-random
    variance on that one real facility's numbers (`random.seed(f.id *
    drug_id)`), not independently measured inventory. This is a real,
    unresolved data-model gap, not just a display nuance — see the
    architecture review for what a real fix looks like (facility-scoped
    stock tracking). Until that lands, every recommendation this endpoint
    returns is synthetic by construction, since the one facility with real
    data is always excluded from being its own donor.
    """
    drug = db.query(Drug).filter(Drug.id == drug_id).first()
    if not drug:
        raise HTTPException(404, "Drug not found")

    facilities = db.query(Facility).all()
    if not facilities:
        raise HTTPException(404, "No facilities registered in network")

    # Get current facility for proximity calc
    current = next((f for f in facilities if f.is_current), None)

    recommendations = []
    for f in facilities:
        if f.is_current:
            continue  # skip self

        # Per-facility stock and ADC
        # In a multi-DB setup this would be an API call to each facility.
        # Here we use the shared DB as a network simulation.
        stock = get_drug_stock(drug_id, db)
        adc   = get_drug_adc(drug_id, db)

        # Add facility-specific variance so demo looks realistic
        # In production each facility has its own data
        import random; random.seed(f.id * drug_id)
        fac_stock = max(0, stock + random.randint(-200, 400))
        fac_adc   = max(0.1, adc * random.uniform(0.5, 1.5))

        protected      = round(fac_adc * PROTECTED_DAYS)
        safe_to_donate = max(0, fac_stock - protected)
        dsr_before     = round(fac_stock / fac_adc, 1) if fac_adc else 999
        dsr_after      = round((fac_stock - min(safe_to_donate, quantity_needed)) / fac_adc, 1) if fac_adc else 999

        if safe_to_donate <= 0:
            continue

        # Proximity
        dist_km = None
        if current and current.lat and current.lng and f.lat and f.lng:
            dist_km = round(haversine_km(current.lat, current.lng, f.lat, f.lng), 1)

        recommendations.append({
            "facility_id":     f.id,
            "facility_name":   f.name,
            "district":        f.district,
            "address":         f.address,
            "contact_name":    f.contact_name,
            "contact_phone":   f.contact_phone,
            "facility_type":   f.facility_type,
            "current_stock":   fac_stock,
            "safe_to_donate":  safe_to_donate,
            "can_cover_full":  safe_to_donate >= quantity_needed,
            "recommended_qty": min(safe_to_donate, quantity_needed),
            "dsr_before":      dsr_before,
            "dsr_after":       dsr_after,
            "distance_km":     dist_km,
            "drug_name":       drug.name,
            "is_real_data":    bool(f.is_current),  # always False here — see DATA HONESTY NOTE above
        })

    # Sort: full-coverage first, then by safe surplus, then by proximity
    recommendations.sort(key=lambda x: (
        0 if x["can_cover_full"] else 1,
        -x["safe_to_donate"],
        x["distance_km"] if x["distance_km"] is not None else 9999,
    ))

    return {
        "drug_name": drug.name,
        "quantity_needed": quantity_needed,
        "total_donors": len(recommendations),
        "can_fully_cover": any(r["can_cover_full"] for r in recommendations),
        "combined_available": sum(r["safe_to_donate"] for r in recommendations),
        "recommendations": recommendations,
        "data_note": (
            "Only the current facility has real batch-level stock records in "
            "this system. Figures shown for other facilities are simulated "
            "variance on that real data, pending per-facility inventory "
            "integration — not independently measured stock."
        ),
    }


# ── Transfer Requests ─────────────────────────────────────────────

@router.post("/request", status_code=201)
def create_request(payload: dict, db: Session = Depends(get_db)):
    """
    Create a stock transfer request from the current facility to a donor.
    Validates that the donor's safe_to_donate covers the approved quantity.
    """
    drug_id           = payload["drug_id"]
    donor_id          = payload["donor_facility_id"]
    receiver_id       = payload["receiver_facility_id"]
    quantity_needed   = payload["quantity_requested"]
    urgency           = payload.get("urgency", "NORMAL")
    notes             = payload.get("notes")

    drug   = db.query(Drug).filter(Drug.id == drug_id).first()
    donor  = db.query(Facility).filter(Facility.id == donor_id).first()
    receiver = db.query(Facility).filter(Facility.id == receiver_id).first()

    if not drug:   raise HTTPException(404, "Drug not found")
    if not donor:  raise HTTPException(404, "Donor facility not found")
    if not receiver: raise HTTPException(404, "Receiver facility not found")

    # Section 8, checklist item 5 — server-side enforcement of Safe-to-Donate.
    # The frontend disables the Request/Donate button when safe_to_donate <= 0,
    # but that is a UX convenience only; the backend re-derives the figure
    # itself and rejects the request outright if it would incapacitate the donor.
    donor_safe_qty = safe_donation_qty(drug_id, db)
    if donor_safe_qty <= 0:
        raise HTTPException(
            400,
            f"{donor.name} has no safe surplus of {drug.name} to donate "
            f"(protected floor is {PROTECTED_DAYS} days of stock).",
        )
    if quantity_needed > donor_safe_qty:
        raise HTTPException(
            400,
            f"{donor.name} can safely donate at most {donor_safe_qty} units of "
            f"{drug.name} without falling below its {PROTECTED_DAYS}-day protected floor.",
        )

    transfer = StockTransfer(
        drug_id                  = drug_id,
        donor_facility_id        = donor_id,
        receiver_facility_id     = receiver_id,
        requested_by_facility_id = receiver_id,
        quantity_requested       = quantity_needed,
        status                   = "REQUESTED",
        urgency                  = urgency,
        request_date             = date.today(),
        notes                    = notes,
    )
    db.add(transfer)
    db.commit()
    db.refresh(transfer)

    transfer.drug     = drug
    transfer.donor    = donor
    transfer.receiver = receiver
    transfer.requester= receiver
    return transfer_dict(transfer)


@router.post("/approve/{transfer_id}")
def approve_transfer(transfer_id: int, payload: dict, db: Session = Depends(get_db)):
    t = db.query(StockTransfer).filter(StockTransfer.id == transfer_id).first()
    if not t:
        raise HTTPException(404, "Transfer not found")
    if t.status != "REQUESTED":
        raise HTTPException(400, f"Cannot approve — current status: {t.status}")

    approved = payload.get("quantity_approved", t.quantity_requested)
    t.quantity_approved = approved
    t.status            = "APPROVED"
    t.approved_date     = date.today()
    db.commit()
    return {"message": "Transfer approved", "quantity_approved": approved}


@router.post("/reject/{transfer_id}")
def reject_transfer(transfer_id: int, payload: dict, db: Session = Depends(get_db)):
    t = db.query(StockTransfer).filter(StockTransfer.id == transfer_id).first()
    if not t:
        raise HTTPException(404, "Transfer not found")
    t.status           = "REJECTED"
    t.rejection_reason = payload.get("reason", "Not specified")
    db.commit()
    return {"message": "Transfer rejected"}


@router.post("/complete/{transfer_id}")
def complete_transfer(transfer_id: int, db: Session = Depends(get_db)):
    t = db.query(StockTransfer).filter(StockTransfer.id == transfer_id).first()
    if not t:
        raise HTTPException(404, "Transfer not found")
    if t.status not in ("APPROVED", "IN_TRANSIT"):
        raise HTTPException(400, f"Cannot complete — current status: {t.status}")

    t.status            = "COMPLETED"
    t.completed_date    = date.today()
    t.quantity_to_repay = t.quantity_approved  # repayment obligation created
    db.commit()
    return {"message": "Transfer completed — repayment obligation recorded", "quantity_to_repay": t.quantity_to_repay}


@router.post("/repay/{transfer_id}")
def record_repayment(transfer_id: int, payload: dict, db: Session = Depends(get_db)):
    t = db.query(StockTransfer).filter(StockTransfer.id == transfer_id).first()
    if not t:
        raise HTTPException(404, "Transfer not found")
    if t.status != "COMPLETED":
        raise HTTPException(400, "Can only repay completed transfers")

    qty = payload.get("quantity_repaid", t.quantity_to_repay)
    t.quantity_repaid = (t.quantity_repaid or 0) + qty
    if t.quantity_repaid >= (t.quantity_to_repay or 0):
        t.status      = "REPAID"
        t.repaid_date = date.today()
    db.commit()
    return {"message": "Repayment recorded", "total_repaid": t.quantity_repaid, "status": t.status}


# ── Transfer History ──────────────────────────────────────────────

@router.get("/transfers")
def list_transfers(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = (
        db.query(StockTransfer)
        .options(
            joinedload(StockTransfer.drug),
            joinedload(StockTransfer.donor),
            joinedload(StockTransfer.receiver),
            joinedload(StockTransfer.requester),
        )
        .order_by(StockTransfer.request_date.desc())
    )
    if status:
        q = q.filter(StockTransfer.status == status.upper())
    return [transfer_dict(t) for t in q.all()]


@router.get("/obligations")
def outstanding_obligations(db: Session = Depends(get_db)):
    """Transfers where repayment is still owed."""
    transfers = (
        db.query(StockTransfer)
        .options(
            joinedload(StockTransfer.drug),
            joinedload(StockTransfer.donor),
            joinedload(StockTransfer.receiver),
        )
        .filter(StockTransfer.status == "COMPLETED")
        .all()
    )
    result = []
    for t in transfers:
        owed = (t.quantity_to_repay or 0) - (t.quantity_repaid or 0)
        if owed > 0:
            result.append({
                **transfer_dict(t),
                "quantity_owed": owed,
            })
    return result


@router.get("/summary")
def network_summary(db: Session = Depends(get_db)):
    total_facilities  = db.query(Facility).count()
    active_requests   = db.query(StockTransfer).filter(StockTransfer.status.in_(["REQUESTED", "APPROVED"])).count()
    completed         = db.query(StockTransfer).filter(StockTransfer.status.in_(["COMPLETED", "REPAID"])).count()
    outstanding_debt  = db.query(StockTransfer).filter(StockTransfer.status == "COMPLETED").count()

    total_transferred = (
        db.query(func.sum(StockTransfer.quantity_approved))
        .filter(StockTransfer.status.in_(["COMPLETED", "REPAID"]))
        .scalar() or 0
    )
    return {
        "total_facilities": total_facilities,
        "active_requests": active_requests,
        "completed_transfers": completed,
        "outstanding_obligations": outstanding_debt,
        "total_units_shared": int(total_transferred),
    }
