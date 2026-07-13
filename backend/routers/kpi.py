from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import Drug
import kpi_engine as kpi
from network_impact import network_transfer_impact_score

router = APIRouter()


@router.get("/dashboard")
def kpi_dashboard(db: Session = Depends(get_db)):
    """Single aggregated payload for the frontend — Layer 1 + Layer 2 +
    the Layer 3 KPIs that don't need a specific drug/patient/transfer
    argument. Per-drug and per-patient KPIs are separate endpoints below."""
    drugs = db.query(Drug).all()

    layer1_per_drug = [kpi.days_of_stock_remaining(d.id, db) for d in drugs]
    for row, d in zip(layer1_per_drug, drugs):
        row["drug_name"] = d.name
        row["safe_to_donate"] = kpi.safe_to_donate(d.id, db)
        row["fill_rate"] = kpi.inventory_fill_rate(d.id, db)

    return {
        "layer1_operational": {
            "per_drug": layer1_per_drug,
            "fefo_compliance": kpi.fefo_compliance_rate(db),
            "expiry_loss": kpi.expiry_loss_rate(db),
            "network_equity": kpi.network_equity_score(db),
        },
        "layer2_clinical": {
            "eci_rate": kpi.eci_rate(db),
            "treatment_failure_rate": kpi.treatment_failure_rate(db),
            "vl_suppression_rate": kpi.vl_suppression_rate(db),
            "ltfu_rate": kpi.ltfu_rate(db),
            **kpi.not_available_kpis(),
        },
        "layer3_strategic": {
            "programmatic_health_index": kpi.programmatic_health_index(db),
        },
    }


@router.get("/retention-curve")
def retention_curve(db: Session = Depends(get_db)):
    return kpi.retention_curve(db)


@router.get("/stockout-probability/{drug_id}")
def stockout_probability(drug_id: int, horizon_days: int = 28, db: Session = Depends(get_db)):
    return kpi.stockout_probability(drug_id, db, horizon_days=horizon_days)


@router.get("/reorder-point/{drug_id}")
def reorder_point(drug_id: int, lead_time_days: int = 14, db: Session = Depends(get_db)):
    return kpi.optimal_reorder_point(drug_id, db, lead_time_days=lead_time_days)


@router.get("/root-cause")
def root_cause(outcome: str = Query("ltfu", pattern="^(ltfu|treatment_failure)$"), db: Session = Depends(get_db)):
    return kpi.root_cause_attribution(db, outcome=outcome)


@router.get("/confidence/{patient_id}")
def confidence(patient_id: int, db: Session = Depends(get_db)):
    return kpi.bayesian_confidence(db, patient_id)


@router.post("/network-transfer-impact")
def transfer_impact(payload: dict, db: Session = Depends(get_db)):
    return network_transfer_impact_score(
        db,
        drug_id=payload["drug_id"],
        donor_facility_id=payload["donor_facility_id"],
        receiver_facility_id=payload["receiver_facility_id"],
        quantity=payload["quantity"],
    )
