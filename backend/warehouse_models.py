"""
warehouse_models.py — SQLAlchemy ORM translation of 01_warehouse_schema.sql.

Because the target is a real, separate Postgres warehouse (not SQLite),
this is a direct translation — UUID and ARRAY columns are used natively via
sqlalchemy.dialects.postgresql, no type substitutions were needed. If this
project ever needs to fall back to SQLite for the warehouse too, TEXT[]
columns (top_risk_drivers) would need to become JSON-encoded TEXT and UUID
columns would need to become CHAR(36) — noted here rather than silently
handled, per the instruction not to guess at schema changes.
"""
from sqlalchemy import (
    Column, Integer, BigInteger, String, Date, Boolean, Numeric, Float, Text,
    ForeignKey, Index,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship

from warehouse_database import WarehouseBase as Base


# ══════════════════════════════════════════════════════════════════
# 1. CONFORMED DIMENSIONS
# ══════════════════════════════════════════════════════════════════

class DimDate(Base):
    __tablename__ = "dim_date"
    date_key      = Column(Integer, primary_key=True)  # YYYYMMDD
    full_date     = Column(Date, nullable=False)
    year          = Column(Integer)
    quarter       = Column(Integer)
    month         = Column(Integer)
    month_name    = Column(String(20))
    week          = Column(Integer)
    day_of_week   = Column(Integer)
    is_weekend    = Column(Boolean)
    fiscal_period = Column(String(20))


class DimGeography(Base):
    __tablename__ = "dim_geography"
    geo_key        = Column(Integer, primary_key=True, autoincrement=True)
    province       = Column(String(50), default="Bulawayo")
    district       = Column(String(50))
    ward           = Column(String(50))
    catchment_zone = Column(String(50))
    urban_rural    = Column(String(20))


class DimFacility(Base):
    __tablename__ = "dim_facility"
    facility_key          = Column(Integer, primary_key=True, autoincrement=True)
    facility_id            = Column(String(50))  # natural key -> OLTP facilities.id
    facility_name           = Column(String(150))
    facility_type            = Column(String(50))
    geo_key                   = Column(Integer, ForeignKey("dim_geography.geo_key"))
    latitude                   = Column(Float)
    longitude                   = Column(Float)
    catchment_population         = Column(Integer)
    has_lab                       = Column(Boolean)
    has_pharmacy                   = Column(Boolean)
    has_electricity                 = Column(Boolean)
    has_internet                     = Column(Boolean)
    staff_doctors                     = Column(Integer)
    staff_nurses                       = Column(Integer)
    staff_pharmacists                   = Column(Integer)
    capacity_patients                    = Column(Integer)
    is_current                            = Column(Boolean, default=True)
    effective_date                         = Column(Date)
    end_date                                = Column(Date)


class DimPatient(Base):
    __tablename__ = "dim_patient"
    patient_key              = Column(Integer, primary_key=True, autoincrement=True)
    patient_id                = Column(String(50))  # natural key -> OLTP art_clients.id
    sex                         = Column(String(10))
    birth_year                   = Column(Integer)
    age_band                      = Column(String(20))
    education_level                 = Column(String(50))
    occupation                       = Column(String(100))
    income_band                       = Column(String(50))
    household_size                     = Column(Integer)
    marital_status                       = Column(String(50))
    community_group                       = Column(String(100))
    home_geo_key                           = Column(Integer, ForeignKey("dim_geography.geo_key"))
    home_facility_key                       = Column(Integer, ForeignKey("dim_facility.facility_key"))
    distance_to_facility_km                  = Column(Float)
    distance_band                             = Column(String(20))
    registration_date                          = Column(Date)
    is_current                                  = Column(Boolean, default=True)
    effective_date                               = Column(Date)
    end_date                                      = Column(Date)


class DimDrug(Base):
    __tablename__ = "dim_drug"
    drug_key      = Column(Integer, primary_key=True, autoincrement=True)
    drug_name     = Column(String(100))
    drug_class    = Column(String(50))
    regimen_line  = Column(String(20))
    is_critical   = Column(Boolean)


class DimIntervention(Base):
    __tablename__ = "dim_intervention"
    intervention_key    = Column(Integer, primary_key=True, autoincrement=True)
    intervention_name     = Column(String(150))
    intervention_type       = Column(String(50))
    cost_per_patient          = Column(Numeric(10, 2))
    target_risk_group          = Column(String(100))


class DimModelVersion(Base):
    __tablename__ = "dim_model_version"
    model_version_key = Column(Integer, primary_key=True, autoincrement=True)
    model_name          = Column(String(100))
    trained_date          = Column(Date)
    algorithm               = Column(String(50))
    notes                     = Column(Text)


# ══════════════════════════════════════════════════════════════════
# 2. FACT TABLES
# ══════════════════════════════════════════════════════════════════

class FactClinicalEncounter(Base):
    __tablename__ = "fact_clinical_encounter"
    encounter_key             = Column(BigInteger, primary_key=True, autoincrement=True)
    patient_key                 = Column(Integer, ForeignKey("dim_patient.patient_key"))
    facility_key                  = Column(Integer, ForeignKey("dim_facility.facility_key"))
    date_key                        = Column(Integer, ForeignKey("dim_date.date_key"))
    who_stage                         = Column(Integer)
    cd4_count                           = Column(Integer)
    viral_load_value                     = Column(Integer)
    suppressed_flag                        = Column(Boolean)
    adherence_pct                            = Column(Numeric(5, 2))
    days_since_last_visit                      = Column(Integer)
    missed_appointment_flag                      = Column(Boolean)
    tb_screen_result                               = Column(String(50))
    mental_health_flag                               = Column(Boolean)
    turnaround_days_last_lab                           = Column(Integer)


class FactTreatmentFailureRisk(Base):
    __tablename__ = "fact_treatment_failure_risk"
    risk_key                = Column(BigInteger, primary_key=True, autoincrement=True)
    patient_key                = Column(Integer, ForeignKey("dim_patient.patient_key"))
    facility_key                 = Column(Integer, ForeignKey("dim_facility.facility_key"))
    date_key                       = Column(Integer, ForeignKey("dim_date.date_key"))
    model_version_key                = Column(Integer, ForeignKey("dim_model_version.model_version_key"))
    risk_score_6mo                     = Column(Numeric(5, 4))
    risk_band                            = Column(String(20))
    top_risk_drivers                       = Column(ARRAY(String))
    predicted_failure_date                   = Column(Date)


class FactStockDaily(Base):
    __tablename__ = "fact_stock_daily"
    stock_key                = Column(BigInteger, primary_key=True, autoincrement=True)
    facility_key                = Column(Integer, ForeignKey("dim_facility.facility_key"))
    drug_key                      = Column(Integer, ForeignKey("dim_drug.drug_key"))
    date_key                        = Column(Integer, ForeignKey("dim_date.date_key"))
    opening_balance                    = Column(Integer)
    received                             = Column(Integer)
    dispensed                              = Column(Integer)
    expired                                  = Column(Integer)
    closing_balance                            = Column(Integer)
    avg_daily_consumption_7d                     = Column(Numeric(8, 2))
    stock_days_remaining                           = Column(Numeric(6, 1))
    stockout_flag                                    = Column(Boolean)
    predicted_stockout_date                            = Column(Date)


class FactPharmacyDispensing(Base):
    __tablename__ = "fact_pharmacy_dispensing"
    dispensing_key           = Column(BigInteger, primary_key=True, autoincrement=True)
    patient_key                 = Column(Integer, ForeignKey("dim_patient.patient_key"))
    facility_key                  = Column(Integer, ForeignKey("dim_facility.facility_key"))
    drug_key                        = Column(Integer, ForeignKey("dim_drug.drug_key"))
    date_key                          = Column(Integer, ForeignKey("dim_date.date_key"))
    quantity                            = Column(Integer)
    days_supplied                         = Column(Integer)
    missed_pickup_flag                      = Column(Boolean)
    days_late                                 = Column(Integer)


class FactFundingScenario(Base):
    __tablename__ = "fact_funding_scenario"
    scenario_key                = Column(BigInteger, primary_key=True, autoincrement=True)
    scenario_name                  = Column(String(100))
    facility_key                     = Column(Integer, ForeignKey("dim_facility.facility_key"))
    date_key                           = Column(Integer, ForeignKey("dim_date.date_key"))
    funding_delta_pct                    = Column(Numeric(5, 2))
    projected_stockout_rate                = Column(Numeric(5, 4))
    projected_default_rate                   = Column(Numeric(5, 4))
    projected_suppression_rate                 = Column(Numeric(5, 4))
    projected_staff_attrition_pct                = Column(Numeric(5, 4))
    projected_patients_at_risk                     = Column(Integer)
    run_date                                         = Column(Date)


class FactRedistributionRecommendation(Base):
    __tablename__ = "fact_redistribution_recommendation"
    recommendation_key         = Column(BigInteger, primary_key=True, autoincrement=True)
    date_key                      = Column(Integer, ForeignKey("dim_date.date_key"))
    source_facility_key             = Column(Integer, ForeignKey("dim_facility.facility_key"))
    target_facility_key               = Column(Integer, ForeignKey("dim_facility.facility_key"))
    drug_key                            = Column(Integer, ForeignKey("dim_drug.drug_key"))
    recommended_qty                       = Column(Integer)
    source_surplus_days                     = Column(Numeric(6, 1))
    target_days_remaining                     = Column(Numeric(6, 1))
    urgency_score                               = Column(Numeric(5, 2))
    estimated_transport_cost                      = Column(Numeric(10, 2))
    status                                          = Column(String(20))


class FactInterventionOutcome(Base):
    __tablename__ = "fact_intervention_outcome"
    outcome_key              = Column(BigInteger, primary_key=True, autoincrement=True)
    patient_key                 = Column(Integer, ForeignKey("dim_patient.patient_key"))
    intervention_key               = Column(Integer, ForeignKey("dim_intervention.intervention_key"))
    facility_key                     = Column(Integer, ForeignKey("dim_facility.facility_key"))
    date_key                           = Column(Integer, ForeignKey("dim_date.date_key"))
    pre_default_rate_90d                 = Column(Numeric(5, 4))
    post_default_rate_90d                  = Column(Numeric(5, 4))
    effect_size                              = Column(Numeric(6, 4))
    cost_per_default_averted                   = Column(Numeric(10, 2))


class FactFacilityPerformanceDaily(Base):
    __tablename__ = "fact_facility_performance_daily"
    perf_key                 = Column(BigInteger, primary_key=True, autoincrement=True)
    facility_key                 = Column(Integer, ForeignKey("dim_facility.facility_key"))
    date_key                       = Column(Integer, ForeignKey("dim_date.date_key"))
    active_patient_load               = Column(Integer)
    staff_workload_ratio                = Column(Numeric(6, 2))
    avg_turnaround_days                   = Column(Numeric(6, 2))
    vl_suppression_rate                     = Column(Numeric(5, 4))
    tb_case_rate                              = Column(Numeric(5, 4))
    default_rate_90d                            = Column(Numeric(5, 4))
    facility_overload_flag                        = Column(Boolean)


# Indexes — mirrors 01_warehouse_schema.sql section 3
Index("idx_fce_patient_date", FactClinicalEncounter.patient_key, FactClinicalEncounter.date_key)
Index("idx_ftr_riskband_date", FactTreatmentFailureRisk.risk_band, FactTreatmentFailureRisk.date_key)
Index("idx_fsd_facility_drug_date", FactStockDaily.facility_key, FactStockDaily.drug_key, FactStockDaily.date_key)
Index("idx_fsd_stockout", FactStockDaily.stockout_flag, FactStockDaily.predicted_stockout_date)
Index("idx_ffs_scenario", FactFundingScenario.scenario_name, FactFundingScenario.facility_key)
Index("idx_frr_status_urgency", FactRedistributionRecommendation.status, FactRedistributionRecommendation.urgency_score)
Index("idx_fio_intervention", FactInterventionOutcome.intervention_key, FactInterventionOutcome.effect_size)
Index("idx_ffp_facility_date", FactFacilityPerformanceDaily.facility_key, FactFacilityPerformanceDaily.date_key)
