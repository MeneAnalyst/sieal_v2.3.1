"""
network_impact.py — Network Transfer Impact Score
────────────────────────────────────────────────
Simulates the change in Network Equity Score if a proposed transfer
(X units of drug from facility A to facility B) were executed, using
PuLP for the underlying feasibility/allocation check.

Uses the same seeded-random peer-facility simulation as
routers/network.py and kpi_engine.network_equity_score — see caveat
there. This is a demo-consistent simulation, not live multi-facility
data, and the response says so explicitly.
"""
import random
from datetime import date, timedelta

import pulp
from sqlalchemy import func
from sqlalchemy.orm import Session

from models import Facility, Drug, Batch, DispenseRecord
from kpi_engine import adc, current_stock, TODAY


def _facility_dsr(facility: Facility, drug: Drug, db: Session, stock_delta: int = 0) -> float:
    a = adc(drug.id, db)
    stock = current_stock(drug.id, db)
    if not facility.is_current:
        rnd = random.Random(facility.id * drug.id)
        stock = max(0, stock + rnd.randint(-200, 400))
        a = max(0.1, a * rnd.uniform(0.5, 1.5))
    stock = max(0, stock + stock_delta)
    return stock / a if a > 0 else 999


def network_transfer_impact_score(
    db: Session, drug_id: int, donor_facility_id: int, receiver_facility_id: int, quantity: int
) -> dict:
    drug = db.query(Drug).filter(Drug.id == drug_id).first()
    facilities = db.query(Facility).all()
    donor = next((f for f in facilities if f.id == donor_facility_id), None)
    receiver = next((f for f in facilities if f.id == receiver_facility_id), None)
    if not (drug and donor and receiver):
        return {"error": "drug or facility not found"}

    # Feasibility check via PuLP: a trivial single-constraint LP, but this
    # is the same formulation that scales to multi-drug/multi-facility
    # allocation if the network grows real per-facility stock data later.
    prob = pulp.LpProblem("transfer_feasibility", pulp.LpMinimize)
    x = pulp.LpVariable("transfer_qty", lowBound=0, upBound=quantity, cat="Integer")
    donor_stock = current_stock(drug_id, db) if donor.is_current else max(
        0, current_stock(drug_id, db) + random.Random(donor.id * drug.id).randint(-200, 400)
    )
    prob += x  # minimize (feasibility only; not cost-optimizing yet)
    prob += x <= donor_stock
    prob += x == quantity
    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    feasible = pulp.LpStatus[prob.status] == "Optimal"

    def equity_across(stock_deltas: dict) -> float:
        adequate = 0
        for f in facilities:
            delta = stock_deltas.get(f.id, 0)
            dsr = _facility_dsr(f, drug, db, stock_delta=delta)
            if dsr >= 90:
                adequate += 1
        return adequate / len(facilities) * 100 if facilities else 0

    equity_before = equity_across({})
    equity_after = equity_across({donor_facility_id: -quantity, receiver_facility_id: quantity})

    return {
        "feasible": feasible,
        "drug": drug.name,
        "donor": donor.name,
        "receiver": receiver.name,
        "quantity": quantity,
        "network_equity_before": round(equity_before, 1),
        "network_equity_after": round(equity_after, 1),
        "impact_score": round(equity_after - equity_before, 1),
        "recommendation": "PROCEED" if equity_after >= equity_before else "AVOID",
        "simulated": True,
    }
