from sqlalchemy import Column, Integer, String, Date, Text, ForeignKey, Float
from sqlalchemy.orm import relationship
from database import Base


# ── Users & Auth ──────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"
    id            = Column(Integer, primary_key=True, index=True)
    username      = Column(String(100), unique=True, nullable=False)
    full_name     = Column(String(200), nullable=False)
    password_hash = Column(String(64), nullable=False)   # sha256 hex
    role          = Column(String(30), default="PHARMACIST")  # ADMIN | PHARMACIST | CLINICIAN | VIEWER
    facility_id   = Column(Integer, ForeignKey("facilities.id"))
    scan_pin_hash = Column(String(64))   # 4-digit PIN for QR scanner security
    is_active     = Column(Integer, default=1)
    facility      = relationship("Facility")


# ── Facility ──────────────────────────────────────────────────────
class Facility(Base):
    __tablename__ = "facilities"
    id              = Column(Integer, primary_key=True, index=True)
    name            = Column(String(300), nullable=False)
    dhis2_code      = Column(String(20), unique=True)
    facility_type   = Column(String(50), default="Clinic")
    address         = Column(String(300))
    district        = Column(String(100))
    district_code   = Column(String(10))
    province        = Column(String(100))
    province_code   = Column(String(10))
    lat             = Column(Float)
    lng             = Column(Float)
    contact_name    = Column(String(200))
    contact_phone   = Column(String(30))
    is_current      = Column(Integer, default=0)

    outgoing_transfers    = relationship("StockTransfer", foreign_keys="StockTransfer.donor_facility_id",        back_populates="donor")
    incoming_transfers    = relationship("StockTransfer", foreign_keys="StockTransfer.receiver_facility_id",     back_populates="receiver")
    sent_requests         = relationship("StockTransfer", foreign_keys="StockTransfer.requested_by_facility_id", back_populates="requester")


# ── Drug & Inventory ──────────────────────────────────────────────
class Drug(Base):
    __tablename__ = "drugs"
    id       = Column(Integer, primary_key=True, index=True)
    name     = Column(String(300), nullable=False)
    strength = Column(String(100))
    form     = Column(String(100), default="Tablet")
    category = Column(String(100), default="ART")
    batches  = relationship("Batch", back_populates="drug")


class Batch(Base):
    __tablename__ = "batches"
    id                = Column(Integer, primary_key=True, index=True)
    drug_id           = Column(Integer, ForeignKey("drugs.id"), nullable=False)
    batch_number      = Column(String(100), nullable=False)
    expiry_date       = Column(Date, nullable=False)
    quantity_received = Column(Integer, nullable=False, default=0)
    quantity_remaining= Column(Integer, nullable=False, default=0)
    received_date     = Column(Date, nullable=False)
    supplier          = Column(String(200), default="NatPharm Zimbabwe")
    gtin              = Column(String(50))
    received_by_user_id = Column(Integer, ForeignKey("users.id"))
    scan_logged       = Column(Integer, default=0)  # 1 = received via QR scan

    drug     = relationship("Drug", back_populates="batches")
    dispenses= relationship("DispenseRecord", back_populates="batch")
    losses   = relationship("ExpiryLoss", back_populates="batch")


# ── Patient (Recipient of Care) ───────────────────────────────────
TREATMENT_COMBOS = [
    "AZT + NVP", "TDF + 3TC + EFV", "TDF + 3TC + NVP",
    "AZT + NVP + 3TC + EFV", "AZT + NVP + 3TC", "ABC",
    "2nd Line", "3HP", "INH", "TDF + 3TC + DTG (TLD)", "TLE600"
]

PROGRESS_STATUSES = [
    "ACTIVE", "LTFU", "RTT", "TRANSFERRED_OUT",
    "DECEASED", "STOPPED", "TREATMENT_FAILURE", "NEW_INITIATION"
]

STOCK_STATUSES = ["IN", "OUT", "REQUESTED", "LOAN_OUT", "GRANTED"]


class ARTClient(Base):
    __tablename__ = "art_clients"

    id          = Column(Integer, primary_key=True, index=True)
    facility_id = Column(Integer, ForeignKey("facilities.id"))

    # --- Identifiers ---
    art_number      = Column(String(50), unique=True, nullable=False, index=True)
    # Format: [province_code]-0A-[district_code]-[year]-A-[number]  e.g. 09-0A-06-2015-A-00250
    tb_number       = Column(String(50))   # Format: YYXXXX  e.g. 231084 (2023)
    oi_number       = Column(String(50))

    # --- Personal ---
    full_name       = Column(String(200), nullable=False)
    date_of_birth   = Column(Date)
    gender          = Column(String(10))
    phone           = Column(String(20))

    # --- Treatment ---
    treatment_combination = Column(String(100))   # from TREATMENT_COMBOS
    regime                = Column(String(200))   # free-text full regime
    visit_type            = Column(String(20), default="PHARMACY")  # PHARMACY=6m, CLINICAL=3m
    initiation_date       = Column(Date)
    enrollment_date       = Column(Date)

    # --- Clinical ---
    cd4_count   = Column(Integer)
    cd4_date    = Column(Date)
    vl_result   = Column(Float)   # copies/mL
    vl_date     = Column(Date)
    vl_suppressed = Column(Integer, default=0)  # 1 if VL < 1000

    # --- Status ---
    progress_status = Column(String(30), default="ACTIVE")
    adherence_score = Column(Float)          # 0–100 calculated
    stock_status    = Column(String(20), default="IN")   # IN | OUT | REQUESTED | LOAN_OUT | GRANTED

    # --- Visits ---
    last_visit       = Column(Date)
    next_appointment = Column(Date)
    is_active        = Column(Integer, default=1)

    # --- ECI Flag (Early Case Investigation) ---
    is_eci_flag  = Column(Integer, default=0)
    eci_reason   = Column(Text)
    eci_flagged_date = Column(Date)

    facility    = relationship("Facility")
    dispenses   = relationship("DispenseRecord", back_populates="client")
    vl_history  = relationship("VLResult", back_populates="patient")


class VLResult(Base):
    __tablename__ = "vl_results"
    id          = Column(Integer, primary_key=True, index=True)
    patient_id  = Column(Integer, ForeignKey("art_clients.id"), nullable=False)
    result      = Column(Float, nullable=False)   # copies/mL
    sample_date = Column(Date, nullable=False)
    result_date = Column(Date)
    suppressed  = Column(Integer, default=0)   # <1000 copies/mL
    source      = Column(String(50), default="MANUAL")  # MANUAL | EHR_IMPORT | LAB_IMPORT
    patient     = relationship("ARTClient", back_populates="vl_history")


class HTSRecord(Base):
    __tablename__ = "hts_records"
    id          = Column(Integer, primary_key=True, index=True)
    patient_id  = Column(Integer, ForeignKey("art_clients.id"), nullable=False)
    test_date   = Column(Date, nullable=False)
    result      = Column(String(20))    # POSITIVE | NEGATIVE | INDETERMINATE
    cd4_count   = Column(Integer)
    linked_to_art = Column(Integer, default=0)
    source      = Column(String(50), default="MANUAL")
    patient     = relationship("ARTClient")


# ── Dispense ──────────────────────────────────────────────────────
class DispenseRecord(Base):
    __tablename__ = "dispense_records"
    id            = Column(Integer, primary_key=True, index=True)
    client_id     = Column(Integer, ForeignKey("art_clients.id"), nullable=False)
    batch_id      = Column(Integer, ForeignKey("batches.id"), nullable=False)
    quantity      = Column(Integer, nullable=False)
    dispense_date = Column(Date, nullable=False)
    dispensed_by  = Column(String(100), default="Pharmacist")
    notes         = Column(Text)
    client        = relationship("ARTClient", back_populates="dispenses")
    batch         = relationship("Batch", back_populates="dispenses")


class ExpiryLoss(Base):
    __tablename__ = "expiry_losses"
    id            = Column(Integer, primary_key=True, index=True)
    batch_id      = Column(Integer, ForeignKey("batches.id"), nullable=False)
    quantity_lost = Column(Integer, nullable=False)
    loss_date     = Column(Date, nullable=False)
    reason_code   = Column(String(50))
    notes         = Column(Text)
    batch         = relationship("Batch", back_populates="losses")


# ── Stock Transfer Network ────────────────────────────────────────
class StockTransfer(Base):
    __tablename__ = "stock_transfers"
    id                         = Column(Integer, primary_key=True, index=True)
    drug_id                    = Column(Integer, ForeignKey("drugs.id"), nullable=False)
    donor_facility_id          = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    receiver_facility_id       = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    requested_by_facility_id   = Column(Integer, ForeignKey("facilities.id"), nullable=False)
    quantity_requested         = Column(Integer, nullable=False)
    quantity_approved          = Column(Integer)
    quantity_to_repay          = Column(Integer)
    quantity_repaid            = Column(Integer, default=0)
    status                     = Column(String(30), default="REQUESTED")
    urgency                    = Column(String(20), default="NORMAL")
    request_date               = Column(Date, nullable=False)
    approved_date              = Column(Date)
    completed_date             = Column(Date)
    repaid_date                = Column(Date)
    notes                      = Column(Text)
    rejection_reason           = Column(Text)
    drug     = relationship("Drug")
    donor    = relationship("Facility", foreign_keys=[donor_facility_id],    back_populates="outgoing_transfers")
    receiver = relationship("Facility", foreign_keys=[receiver_facility_id], back_populates="incoming_transfers")
    requester= relationship("Facility", foreign_keys=[requested_by_facility_id], back_populates="sent_requests")


# ── Scan Audit Log ────────────────────────────────────────────────
class ScanAuditLog(Base):
    __tablename__ = "scan_audit_logs"
    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    batch_id    = Column(Integer, ForeignKey("batches.id"))
    scanned_at  = Column(String(50))   # ISO datetime string
    raw_data    = Column(Text)
    action      = Column(String(50), default="RECEIVE")
    ip_address  = Column(String(50))
    user        = relationship("User")


# ── Defaulter Management ───────────────────────────────────────────
TRACE_METHODS = ["PHONE_CALL", "SMS", "HOME_VISIT", "COMMUNITY_HEALTH_WORKER"]
TRACE_OUTCOMES = ["RETURNED", "PROMISED_TO_RETURN", "UNREACHABLE", "TRANSFERRED_OUT", "DECEASED", "REFUSED"]
DEFAULT_REASONS = ["TRAVEL_DISTANCE", "SIDE_EFFECTS", "STIGMA", "CLINIC_WAIT_TIME", "FINANCIAL_CONSTRAINTS", "FORGOT", "OTHER"]

class DefaulterTrace(Base):
    __tablename__ = "defaulter_traces"
    id                 = Column(Integer, primary_key=True, index=True)
    patient_id         = Column(Integer, ForeignKey("art_clients.id"), nullable=False)
    trace_date         = Column(Date, nullable=False)
    trace_method       = Column(String(30))    # PHONE_CALL | SMS | HOME_VISIT | COMMUNITY_HEALTH_WORKER
    trace_outcome      = Column(String(30))    # RETURNED | PROMISED_TO_RETURN | UNREACHABLE | ...
    reason_for_default = Column(String(30))    # TRAVEL_DISTANCE | SIDE_EFFECTS | STIGMA | ...
    notes              = Column(Text)
    logged_by          = Column(String(100))
    patient            = relationship("ARTClient")


# ── Notice Board ──────────────────────────────────────────────────
NOTICE_PRIORITIES = ["INFO", "WARNING", "URGENT"]

class Notice(Base):
    __tablename__ = "notices"
    id          = Column(Integer, primary_key=True, index=True)
    title       = Column(String(200), nullable=False)
    message     = Column(Text, nullable=False)
    priority    = Column(String(20), default="INFO")   # INFO | WARNING | URGENT
    facility_id = Column(Integer, ForeignKey("facilities.id"))  # null = visible to all facilities
    created_by  = Column(String(100))
    created_at  = Column(Date, nullable=False)
    expires_at  = Column(Date)   # null = doesn't expire
    is_active   = Column(Integer, default=1)
    facility    = relationship("Facility")
