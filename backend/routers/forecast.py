from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta

from database import get_db
from models import Drug, Batch, DispenseRecord, ARTClient

router = APIRouter()

# ── OR constants (Sections 4B / 4C of the RESILIENCE-ART instruction set) ──
ADC_WINDOW_DAYS = 90        # ADC = Average Daily Consumption, trailing 90 days
ORDER_CYCLE_DAYS = 90       # routine re-order cycle
SAFETY_BUFFER_DAYS = 30     # emergency buffer on top of the order cycle
PROTECTED_DAYS = ORDER_CYCLE_DAYS + SAFETY_BUFFER_DAYS  # = 120

# Kanban thresholds — Section 4C, strict mapping
CRITICAL_MAX_DAYS = 30
LOW_MAX_DAYS = 90
MODERATE_MAX_DAYS = 180


def get_adc(drug_id: int, db: Session, window_days: int = ADC_WINDOW_DAYS) -> float:
    """Average Daily Consumption over the past `window_days` (default 90)."""
    since = date.today() - timedelta(days=window_days)
    total = (
        db.query(func.sum(DispenseRecord.quantity))
        .join(Batch)
        .filter(Batch.drug_id == drug_id, DispenseRecord.dispense_date >= since)
        .scalar()
        or 0
    )
    return total / window_days


def get_total_stock(drug_id: int, db: Session) -> int:
    return (
        db.query(func.sum(Batch.quantity_remaining))
        .filter(Batch.drug_id == drug_id, Batch.quantity_remaining > 0)
        .scalar()
        or 0
    )


def get_usable_stock(drug_id: int, db: Session) -> int:
    """Total remaining stock excluding batches expiring within 30 days."""
    safe_cutoff = date.today() + timedelta(days=30)
    return (
        db.query(func.sum(Batch.quantity_remaining))
        .filter(
            Batch.drug_id == drug_id,
            Batch.quantity_remaining > 0,
            Batch.expiry_date > safe_cutoff,
        )
        .scalar()
        or 0
    )


def kanban_status(dsr: float) -> str:
    """Section 4C strict mapping."""
    if dsr < CRITICAL_MAX_DAYS:
        return "CRITICAL"
    if dsr < LOW_MAX_DAYS:
        return "LOW"
    if dsr < MODERATE_MAX_DAYS:
        return "MODERATE"
    return "ADEQUATE"


def donatable_surplus(total_stock: int, adc: float) -> int:
    """
    Section 4B — Safe-to-Donate.
    Donatable = Current_Stock - (ADC*90 + ADC*30) = Current_Stock - ADC*120.
    Never floored at zero here; callers check > 0 for eligibility so a
    negative "deficit" value is still visible/informative in the UI.
    """
    protected = round(adc * PROTECTED_DAYS)
    return total_stock - protected


@router.get("/dsr")
def days_of_stock_remaining(db: Session = Depends(get_db)):
    """Days of Stock Remaining per drug line, with Kanban band + donatable surplus."""
    drugs = db.query(Drug).order_by(Drug.name).all()
    result = []
    for drug in drugs:
        adc = get_adc(drug.id, db)
        total = get_total_stock(drug.id, db)
        dsr = round(total / adc, 1) if adc > 0 else 999.0
        monthly = round(adc * 30)
        status = kanban_status(dsr)
        surplus = donatable_surplus(total, adc) if adc > 0 else 0

        result.append(
            {
                "drug_id": drug.id,
                "drug_name": drug.name,
                "strength": drug.strength,
                "total_stock": total,
                "adc": round(adc, 2),
                "dsr": dsr,
                "status": status,
                "monthly_consumption": monthly,
                "donatable_surplus": surplus,
            }
        )
    return sorted(result, key=lambda x: x["dsr"])


@router.get("/demand")
def demand_forecast(db: Session = Depends(get_db)):
    """Projected consumption at 30, 60, and 90-day horizons."""
    drugs = db.query(Drug).order_by(Drug.name).all()
    result = []
    for drug in drugs:
        adc = get_adc(drug.id, db)
        if adc == 0:
            continue
        total = get_total_stock(drug.id, db)
        result.append(
            {
                "drug_name": drug.name,
                "adc": round(adc, 2),
                "current_stock": total,
                "projected_30": round(adc * 30),
                "projected_60": round(adc * 60),
                "projected_90": round(adc * 90),
                "surplus_30": total - round(adc * 30),
                "surplus_60": total - round(adc * 60),
                "surplus_90": total - round(adc * 90),
            }
        )
    return result


@router.get("/procurement")
def procurement_recommendations(db: Session = Depends(get_db)):
    """
    Recommended order quantities.
    Formula: order = max(0, projected_90 + safety_stock_30 - usable_stock)
    """
    drugs = db.query(Drug).order_by(Drug.name).all()
    recommendations = []
    for drug in drugs:
        adc = get_adc(drug.id, db)
        if adc == 0:
            continue
        usable = get_usable_stock(drug.id, db)
        total = get_total_stock(drug.id, db)
        dsr = round(total / adc, 1) if adc > 0 else 999.0
        safety = round(adc * SAFETY_BUFFER_DAYS)
        projected_90 = round(adc * ORDER_CYCLE_DAYS)
        order_qty = max(0, projected_90 + safety - usable)

        if order_qty > 0:
            urgency = "URGENT" if dsr < CRITICAL_MAX_DAYS else "SOON" if dsr < LOW_MAX_DAYS else "PLANNED"
            recommendations.append(
                {
                    "drug_name": drug.name,
                    "current_stock": total,
                    "usable_stock": usable,
                    "dsr": dsr,
                    "adc": round(adc, 2),
                    "order_quantity": order_qty,
                    "urgency": urgency,
                }
            )
    return sorted(recommendations, key=lambda x: x["dsr"])


@router.get("/cohort-demand")
def cohort_demand(db: Session = Depends(get_db)):
    """How many clients are due in the next 30/60/90 days by visit type."""
    today = date.today()
    result = {}
    for horizon in [30, 60, 90]:
        until = today + timedelta(days=horizon)
        pharmacy = db.query(ARTClient).filter(
            ARTClient.is_active == 1,
            ARTClient.visit_type == "PHARMACY",
            ARTClient.next_appointment >= today,
            ARTClient.next_appointment <= until,
        ).count()
        clinical = db.query(ARTClient).filter(
            ARTClient.is_active == 1,
            ARTClient.visit_type == "CLINICAL",
            ARTClient.next_appointment >= today,
            ARTClient.next_appointment <= until,
        ).count()
        result[f"d{horizon}"] = {"pharmacy": pharmacy, "clinical": clinical, "total": pharmacy + clinical}
    return result
