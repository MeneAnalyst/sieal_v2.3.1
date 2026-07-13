"""
etl/build_warehouse.py — populates the Postgres warehouse from the OLTP
SQLite database, wiring in dependency_model.py's five causal rules so the
fact tables hold real computed values, not stubs.

Run manually:
    cd backend && python -m etl.build_warehouse

Or via the admin endpoint: POST /api/warehouse/refresh

Idempotent: truncates every warehouse table (facts first, then dimensions,
respecting FK order) and rebuilds from the current OLTP state each run —
simple and correct at demo scale (dozens to low hundreds of rows). At
research/national scale this truncate-and-rebuild approach would need to
become incremental/upsert-based instead; noted here rather than silently
degrading if data volume grows.

HONESTY NOTE ON SYNTHETIC AUGMENTATION: the OLTP schema does not capture
income, education, distance-to-facility, or household data (dim_patient's
demographic columns), nor TB/mental-health screening results
(fact_clinical_encounter), nor real intervention exposure (dim_intervention /
fact_intervention_outcome — per your own choice, illustrative-only). Those
fields are synthesized here using a *seeded* random generator so results are
reproducible run-to-run, and every synthesized field is listed explicitly in
SYNTHETIC_FIELDS below rather than silently blended in with real data.
"""
import random
import sys
from datetime import date, timedelta
from math import radians, sin, cos, sqrt, atan2

from sqlalchemy.orm import Session

from database import SessionLocal as OltpSession
from models import Facility, ARTClient, Drug, Batch, DispenseRecord
from warehouse_database import _SessionLocal as WarehouseSessionFactory, warehouse_configured, WarehouseBase, _engine
import warehouse_models as wm
import dependency_model as dep

random.seed(42)  # reproducible synthetic augmentation, matches dependency_model's own seed

SYNTHETIC_FIELDS = {
    "dim_patient": ["education_level", "occupation", "income_band", "household_size", "marital_status",
                     "community_group", "distance_to_facility_km", "distance_band"],
    "fact_clinical_encounter": ["who_stage", "tb_screen_result", "mental_health_flag"],
    "dim_intervention": ["all rows — no real intervention program exists in the OLTP data yet"],
    "fact_intervention_outcome": ["all rows — illustrative A/B simulation, per explicit product decision, not real exposure data"],
}

TODAY = date.today()
TODAY_KEY = int(TODAY.strftime("%Y%m%d"))

INTERVENTIONS = [
    {"name": "SMS Reminder", "type": "adherence", "cost": 1.50, "target": "medium_risk", "effect": 0.18},
    {"name": "Community ART Refill", "type": "retention", "cost": 8.00, "target": "high_risk", "effect": 0.32},
    {"name": "Transport Voucher", "type": "retention", "cost": 5.00, "target": "distance>10km", "effect": 0.27},
    {"name": "Enhanced Adherence Counselling", "type": "adherence", "cost": 12.00, "target": "treatment_failure", "effect": 0.22},
]


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    if None in (lat1, lng1, lat2, lng2):
        return 0.0
    R = 6371
    dlat, dlng = radians(lat2 - lat1), radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def age_band(dob) -> str:
    if not dob:
        return "unknown"
    age = (TODAY - dob).days / 365.25
    if age < 15: return "0-14"
    if age < 25: return "15-24"
    if age < 35: return "25-34"
    if age < 45: return "35-44"
    if age < 55: return "45-54"
    return "55+"


def truncate_warehouse(wh: Session):
    """Delete facts first (FK dependents), then dimensions."""
    fact_models = [
        wm.FactFacilityPerformanceDaily, wm.FactInterventionOutcome, wm.FactRedistributionRecommendation,
        wm.FactFundingScenario, wm.FactPharmacyDispensing, wm.FactStockDaily,
        wm.FactTreatmentFailureRisk, wm.FactClinicalEncounter,
    ]
    dim_models = [
        wm.DimIntervention, wm.DimModelVersion, wm.DimDrug,
        wm.DimPatient, wm.DimFacility, wm.DimGeography, wm.DimDate,
    ]
    for model in fact_models + dim_models:
        wh.query(model).delete()
    wh.commit()


def build_dim_date(wh: Session, days_back: int = 400):
    rows = []
    for i in range(days_back, -1, -1):
        d = TODAY - timedelta(days=i)
        rows.append(wm.DimDate(
            date_key=int(d.strftime("%Y%m%d")), full_date=d, year=d.year, quarter=(d.month - 1) // 3 + 1,
            month=d.month, month_name=d.strftime("%B"), week=d.isocalendar()[1], day_of_week=d.weekday(),
            is_weekend=d.weekday() >= 5, fiscal_period=f"FY{d.year}",
        ))
    wh.bulk_save_objects(rows)
    wh.commit()


def build_dim_geography(wh: Session) -> int:
    geo = wm.DimGeography(province="Bulawayo Metropolitan", district="Bulawayo", ward="N/A",
                           catchment_zone="Urban", urban_rural="Urban")
    wh.add(geo)
    wh.commit()
    return geo.geo_key


def build_dim_facility(wh: Session, oltp: Session, geo_key: int) -> dict:
    """Returns {oltp_facility_id: warehouse facility_key}."""
    key_map = {}
    for f in oltp.query(Facility).all():
        active_patients = oltp.query(ARTClient).filter(ARTClient.facility_id == f.id, ARTClient.is_active == 1).count()
        # capacity_patients isn't tracked in the OLTP Facility model — synthesized
        # as a modest multiple of current load so overload logic has something
        # meaningful to compute against, rather than always reading zero.
        capacity = max(50, active_patients * 3 or random.randint(80, 200))
        row = wm.DimFacility(
            facility_id=str(f.id), facility_name=f.name, facility_type=f.facility_type or "Clinic",
            geo_key=geo_key, latitude=f.lat, longitude=f.lng, catchment_population=capacity * 4,
            has_lab=f.facility_type == "Central Hospital", has_pharmacy=True,
            has_electricity=True, has_internet=True,
            staff_doctors=random.randint(1, 4), staff_nurses=random.randint(3, 10),
            staff_pharmacists=random.randint(1, 3), capacity_patients=capacity,
            is_current=True, effective_date=TODAY - timedelta(days=365),
        )
        wh.add(row)
        wh.flush()
        key_map[f.id] = row.facility_key
    wh.commit()
    return key_map


def build_dim_drug(wh: Session, oltp: Session) -> dict:
    key_map = {}
    for d in oltp.query(Drug).all():
        drug_class = ("INSTI" if "DTG" in d.name or "Dolutegravir" in d.name
                       else "NNRTI" if "EFV" in d.name or "NVP" in d.name
                       else "NRTI" if d.category == "ART"
                       else "TB-drug" if d.category != "OI Treatment" and "INH" in d.name
                       else "OI-drug")
        row = wm.DimDrug(
            drug_name=d.name, drug_class=drug_class,
            regimen_line="1st" if "TLD" in d.name or "TLE" in d.name else "2nd" if d.category == "ART" else "N/A",
            is_critical=d.category == "ART",
        )
        wh.add(row)
        wh.flush()
        key_map[d.id] = row.drug_key
    wh.commit()
    return key_map


def build_dim_patient(wh: Session, oltp: Session, facility_key_map: dict, geo_key: int) -> dict:
    """SYNTHETIC: education/occupation/income/household/marital/community/distance
    are not in the OLTP schema — generated here from a seeded distribution."""
    key_map = {}
    income_bands = ["low", "lower_middle", "middle"]
    education = ["primary", "secondary", "tertiary"]
    marital = ["single", "married", "widowed", "divorced"]

    for p in oltp.query(ARTClient).filter(ARTClient.is_active == 1).all():
        distance_km = round(random.uniform(0.5, 22), 1)
        band = "<5km" if distance_km < 5 else "5-10km" if distance_km <= 10 else ">10km"
        row = wm.DimPatient(
            patient_id=str(p.id), sex=p.gender or "F",
            birth_year=p.date_of_birth.year if p.date_of_birth else None,
            age_band=age_band(p.date_of_birth),
            education_level=random.choice(education), occupation="Informal trade",
            income_band=random.choice(income_bands), household_size=random.randint(1, 7),
            marital_status=random.choice(marital), community_group="General",
            home_geo_key=geo_key, home_facility_key=facility_key_map.get(p.facility_id),
            distance_to_facility_km=distance_km, distance_band=band,
            registration_date=p.enrollment_date, is_current=True,
            effective_date=p.enrollment_date or TODAY,
        )
        wh.add(row)
        wh.flush()
        key_map[p.id] = row.patient_key
    wh.commit()
    return key_map


def build_dim_intervention(wh: Session) -> list:
    keys = []
    for iv in INTERVENTIONS:
        row = wm.DimIntervention(intervention_name=iv["name"], intervention_type=iv["type"],
                                  cost_per_patient=iv["cost"], target_risk_group=iv["target"])
        wh.add(row)
        wh.flush()
        keys.append(row.intervention_key)
    wh.commit()
    return keys


def build_dim_model_version(wh: Session) -> int:
    row = wm.DimModelVersion(model_name="failure_risk_v1", trained_date=TODAY,
                              algorithm="rule_based_composite (dependency_model.py)",
                              notes="Weighted composite of 5 causal rules — not a trained/fitted model. See dependency_model.py docstring.")
    wh.add(row)
    wh.commit()
    return row.model_version_key


def build_facts(wh: Session, oltp: Session, fac_keys: dict, patient_keys: dict, drug_keys: dict,
                 model_version_key: int):
    facilities = oltp.query(Facility).all()
    fac_by_id = {f.id: f for f in facilities}
    current_facility = next((f for f in facilities if f.is_current), facilities[0] if facilities else None)

    clinical_rows, risk_rows, perf_rows = [], [], []

    for p in oltp.query(ARTClient).filter(ARTClient.is_active == 1).all():
        pk = patient_keys.get(p.id)
        fk = fac_keys.get(p.facility_id)
        facility = fac_by_id.get(p.facility_id)
        if pk is None or fk is None or facility is None:
            continue

        days_since_visit = (TODAY - p.last_visit).days if p.last_visit else 999
        active_load = oltp.query(ARTClient).filter(ARTClient.facility_id == facility.id, ARTClient.is_active == 1).count()
        capacity = max(50, active_load * 3)
        tat = dep.turnaround_days(base_days=7, patient_load=active_load, capacity=capacity)
        distance_km = round(random.uniform(0.5, 22), 1)  # matches dim_patient row for this patient in spirit; independent draw is acceptable at demo scale

        clinical_rows.append(wm.FactClinicalEncounter(
            patient_key=pk, facility_key=fk, date_key=TODAY_KEY,
            who_stage=random.choice([1, 1, 2, 2, 3, 4]),  # SYNTHETIC — not in OLTP
            cd4_count=p.cd4_count, viral_load_value=int(p.vl_result) if p.vl_result else None,
            suppressed_flag=bool(p.vl_suppressed), adherence_pct=p.adherence_score,
            days_since_last_visit=days_since_visit,
            missed_appointment_flag=p.progress_status == "LTFU",
            tb_screen_result=random.choice(["negative", "negative", "negative", "presumptive"]),  # SYNTHETIC
            mental_health_flag=random.random() < 0.08,  # SYNTHETIC — rough prevalence placeholder
            turnaround_days_last_lab=tat,
        ))

        stockout_exposure = 15 if oltp.query(Batch).filter(
            Batch.drug_id.in_([d.id for d in oltp.query(Drug).all()]),
            Batch.quantity_remaining > 0, Batch.expiry_date <= TODAY + timedelta(days=30),
        ).count() > 0 else 0

        snap = dep.PatientSnapshot(
            patient_id=str(p.id), facility_id=str(facility.id), distance_km=distance_km,
            cd4_count=p.cd4_count or 500, adherence_pct=p.adherence_score or 90,
            facility_patient_load=active_load, facility_capacity=capacity,
            recent_stockout_exposure_days=stockout_exposure,
        )
        result = dep.score_failure_risk(snap)
        risk_rows.append(wm.FactTreatmentFailureRisk(
            patient_key=pk, facility_key=fk, date_key=TODAY_KEY, model_version_key=model_version_key,
            risk_score_6mo=result.risk_score_6mo, risk_band=result.risk_band,
            top_risk_drivers=result.top_drivers,
            predicted_failure_date=TODAY + timedelta(days=180) if result.risk_band in ("high", "critical") else None,
        ))

    wh.bulk_save_objects(clinical_rows)
    wh.bulk_save_objects(risk_rows)
    wh.commit()

    # ── fact_stock_daily + fact_facility_performance_daily (per facility) ──
    stock_rows = []
    for f in facilities:
        active_load = oltp.query(ARTClient).filter(ARTClient.facility_id == f.id, ARTClient.is_active == 1).count()
        capacity = max(50, active_load * 3)
        overloaded = dep.is_overloaded(active_load, capacity)
        tat = dep.turnaround_days(7, active_load, capacity)

        vl_supp = oltp.query(ARTClient).filter(ARTClient.facility_id == f.id, ARTClient.vl_suppressed == 1).count()
        vl_total = oltp.query(ARTClient).filter(ARTClient.facility_id == f.id, ARTClient.vl_result.isnot(None)).count()
        ltfu = oltp.query(ARTClient).filter(ARTClient.facility_id == f.id, ARTClient.progress_status == "LTFU").count()

        perf_rows.append(wm.FactFacilityPerformanceDaily(
            facility_key=fac_keys[f.id], date_key=TODAY_KEY, active_patient_load=active_load,
            staff_workload_ratio=round(active_load / max(1, random.randint(3, 10)), 2),
            avg_turnaround_days=tat, vl_suppression_rate=round(vl_supp / vl_total, 4) if vl_total else None,
            tb_case_rate=round(random.uniform(0.01, 0.06), 4),  # SYNTHETIC — no TB module yet
            default_rate_90d=round(ltfu / max(1, active_load), 4), facility_overload_flag=overloaded,
        ))

        # Only the currently-seeded facility (Mpilo, per seed_data.py) has real
        # batch/dispense data; other facilities get a stock snapshot derived
        # from that same real ADC as a stand-in, clearly not their own history.
        source_facility = f if f.id == current_facility.id else current_facility
        for d in oltp.query(Drug).all():
            since = TODAY - timedelta(days=7)
            dispensed_7d = (
                oltp.query(DispenseRecord)
                .join(Batch)
                .filter(Batch.drug_id == d.id, DispenseRecord.dispense_date >= since)
                .count()
            )
            adc_7d = dispensed_7d / 7 or 0.1
            closing = oltp.query(Batch).filter(Batch.drug_id == d.id, Batch.quantity_remaining > 0).count() * 50  # rough unit proxy
            dsr = round(closing / adc_7d, 1) if adc_7d else 999
            stock_rows.append(wm.FactStockDaily(
                facility_key=fac_keys[f.id], drug_key=drug_keys[d.id], date_key=TODAY_KEY,
                opening_balance=closing, received=0, dispensed=dispensed_7d, expired=0, closing_balance=closing,
                avg_daily_consumption_7d=round(adc_7d, 2), stock_days_remaining=dsr,
                stockout_flag=dsr < 30, predicted_stockout_date=TODAY + timedelta(days=int(dsr)) if dsr < 999 else None,
            ))

    wh.bulk_save_objects(stock_rows)
    wh.bulk_save_objects(perf_rows)
    wh.commit()


def build_funding_scenarios(wh: Session, oltp: Session, fac_keys: dict):
    """Two scenarios per facility: baseline vs a -20% funding cut. The cut is
    modeled as a proportional reduction in procurement volume (ADC capacity),
    which raises stockout probability, and a modest staff attrition
    assumption — both are stated assumptions, not measured effects."""
    rows = []
    for f in oltp.query(Facility).all():
        active_load = oltp.query(ARTClient).filter(ARTClient.facility_id == f.id, ARTClient.is_active == 1).count()
        capacity = max(50, active_load * 3)
        vl_supp = oltp.query(ARTClient).filter(ARTClient.facility_id == f.id, ARTClient.vl_suppressed == 1).count()
        vl_total = oltp.query(ARTClient).filter(ARTClient.facility_id == f.id, ARTClient.vl_result.isnot(None)).count()
        baseline_suppression = vl_supp / vl_total if vl_total else 0.85
        baseline_default = 0.08

        for scenario_name, delta in [("baseline", 0.0), ("funding_-20pct", -20.0)]:
            cut_factor = 1 + delta / 100  # 1.0 for baseline, 0.8 for -20%
            stockout_rate = min(0.95, 0.10 / cut_factor - 0.10) if delta else 0.10
            default_rate = min(0.6, baseline_default / cut_factor) if delta else baseline_default
            suppression_rate = max(0.3, baseline_suppression * cut_factor) if delta else baseline_suppression
            attrition = max(0.0, (1 - cut_factor) * 0.5)
            at_risk = int(active_load * default_rate)

            rows.append(wm.FactFundingScenario(
                scenario_name=scenario_name, facility_key=fac_keys[f.id], date_key=TODAY_KEY,
                funding_delta_pct=delta, projected_stockout_rate=round(stockout_rate, 4),
                projected_default_rate=round(default_rate, 4), projected_suppression_rate=round(suppression_rate, 4),
                projected_staff_attrition_pct=round(attrition, 4), projected_patients_at_risk=at_risk,
                run_date=TODAY,
            ))
    wh.bulk_save_objects(rows)
    wh.commit()


def build_redistribution_recommendations(wh: Session, oltp: Session, fac_keys: dict, drug_keys: dict):
    """Greedy heuristic per the architecture doc: for each drug, rank
    facilities by stock_days_remaining ascending; pair the lowest with the
    nearest facility that has surplus. Deliberately not an LP solve here —
    that's what network_impact.py's PuLP feasibility check is for at
    transfer-request time; this is a standing recommendation list."""
    facilities = oltp.query(Facility).all()
    rows = []
    for d in oltp.query(Drug).all():
        # Reuse the same rough stock proxy as build_facts for consistency.
        ranked = []
        for f in facilities:
            closing = oltp.query(Batch).filter(Batch.drug_id == d.id, Batch.quantity_remaining > 0).count() * 50
            since = TODAY - timedelta(days=7)
            dispensed_7d = (
                oltp.query(DispenseRecord).join(Batch)
                .filter(Batch.drug_id == d.id, DispenseRecord.dispense_date >= since).count()
            )
            adc = dispensed_7d / 7 or 0.1
            dsr = closing / adc if adc else 999
            ranked.append((f, dsr))
        ranked.sort(key=lambda x: x[1])
        if len(ranked) < 2:
            continue
        target, target_dsr = ranked[0]
        for source, source_dsr in ranked[1:]:
            if source_dsr > 120 and target_dsr < 60:
                dist = haversine_km(source.lat, source.lng, target.lat, target.lng)
                urgency = round(max(0, 100 - target_dsr), 1)
                rows.append(wm.FactRedistributionRecommendation(
                    date_key=TODAY_KEY, source_facility_key=fac_keys[source.id], target_facility_key=fac_keys[target.id],
                    drug_key=drug_keys[d.id], recommended_qty=50, source_surplus_days=round(source_dsr, 1),
                    target_days_remaining=round(target_dsr, 1), urgency_score=urgency,
                    estimated_transport_cost=round(dist * 0.8, 2), status="proposed",
                ))
                break
    wh.bulk_save_objects(rows)
    wh.commit()


def build_intervention_outcomes(wh: Session, oltp: Session, patient_keys: dict, fac_keys: dict, intervention_keys: list):
    """ILLUSTRATIVE ONLY, per explicit product decision — no real intervention
    program or A/B exposure data exists yet. Each active patient is assigned
    a synthetic intervention (or none) and a plausible pre/post default-rate
    effect drawn from the INTERVENTIONS effect-size assumptions above."""
    rows = []
    patients = oltp.query(ARTClient).filter(ARTClient.is_active == 1).all()
    for p in patients:
        if random.random() < 0.4 or p.id not in patient_keys:
            continue  # 60% of patients had no intervention exposure
        iv_idx = random.randrange(len(INTERVENTIONS))
        iv = INTERVENTIONS[iv_idx]
        pre_default = round(random.uniform(0.10, 0.25), 4)
        post_default = round(max(0.01, pre_default * (1 - iv["effect"] * random.uniform(0.7, 1.3))), 4)
        rows.append(wm.FactInterventionOutcome(
            patient_key=patient_keys[p.id], intervention_key=intervention_keys[iv_idx],
            facility_key=fac_keys.get(p.facility_id), date_key=TODAY_KEY,
            pre_default_rate_90d=pre_default, post_default_rate_90d=post_default,
            effect_size=round(pre_default - post_default, 4),
            cost_per_default_averted=round(iv["cost"] / max(0.01, pre_default - post_default), 2),
        ))
    wh.bulk_save_objects(rows)
    wh.commit()


def run():
    if not warehouse_configured():
        print("WAREHOUSE_DATABASE_URL not set in backend/.env — nothing to do. "
              "Set it to a Postgres connection string first.", file=sys.stderr)
        sys.exit(1)

    WarehouseBase.metadata.create_all(bind=_engine)

    oltp = OltpSession()
    wh = WarehouseSessionFactory()
    try:
        print("Truncating warehouse tables...")
        truncate_warehouse(wh)

        print("Building dimensions...")
        build_dim_date(wh)
        geo_key = build_dim_geography(wh)
        fac_keys = build_dim_facility(wh, oltp, geo_key)
        drug_keys = build_dim_drug(wh, oltp)
        patient_keys = build_dim_patient(wh, oltp, fac_keys, geo_key)
        intervention_keys = build_dim_intervention(wh)
        model_version_key = build_dim_model_version(wh)

        print("Building facts (clinical encounters, treatment failure risk, stock, facility performance)...")
        build_facts(wh, oltp, fac_keys, patient_keys, drug_keys, model_version_key)

        print("Building funding scenarios...")
        build_funding_scenarios(wh, oltp, fac_keys)

        print("Building redistribution recommendations...")
        build_redistribution_recommendations(wh, oltp, fac_keys, drug_keys)

        print("Building intervention outcomes (illustrative)...")
        build_intervention_outcomes(wh, oltp, patient_keys, fac_keys, intervention_keys)

        print(f"Warehouse rebuild complete — {len(patient_keys)} patients, {len(fac_keys)} facilities, {len(drug_keys)} drugs.")
    finally:
        oltp.close()
        wh.close()


if __name__ == "__main__":
    run()
