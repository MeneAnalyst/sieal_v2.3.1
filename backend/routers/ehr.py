"""
EHR Import router — VL results, HTS, ART appointments, pharmacy register.

Every import accepts EITHER our own clean CSV templates OR real MOHCC/
OpenMRS report exports (XLSX-format, messy metadata header, report-
specific column names) — see ehr_parsing.py for how both are normalized
into plain dict rows before this file's mapping logic runs.

DESIGN NOTE ON PATIENT AUTO-CREATION — read before changing this file:
Whether an import is allowed to create a NEW patient record (vs only
update an existing one) depends entirely on whether the source data
actually contains enough real fields to safely do so:
  - ART Appointments List (MOHCC format) has first/last name, sex, phone,
    ART initiation date — enough for a real patient record. Auto-create
    is safe and implemented below.
  - HTS Register has NO art_number at all (clinically correct — most
    people tested were never ART patients) and no reliable unique
    identifier to match an existing patient against. Auto-linking by
    name alone risks attaching an HIV test result to the WRONG patient
    record on a name collision — a real clinical-safety issue, not just
    a data-quality one. This import deliberately does NOT auto-link or
    auto-create; positive results are surfaced in the response for a
    human to review and manually link via the patient's own record.
  - VL results and Pharmacy Register both assume the patient already
    exists (a lab result or a dispense event doesn't carry enough
    demographic data to safely register someone new either).
"""
from datetime import date, timedelta
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models import ARTClient, VLResult, HTSRecord, Drug, Batch, DispenseRecord
from routers.auth import current_user
from routers.patients import _auto_eci
from ehr_parsing import load_rows, clean_str

router = APIRouter()

VISIT_INTERVALS = {"PHARMACY": 180, "CLINICAL": 90}


def _find_patient(db: Session, art_number: str):
    """Case- and whitespace-tolerant ART number lookup — see prior fix."""
    art = clean_str(art_number)
    if not art:
        return None
    return db.query(ARTClient).filter(func.upper(ARTClient.art_number) == art.upper()).first()


def _parse_date(v):
    """Accepts an ISO string, a pandas Timestamp already cast to str, or a date."""
    if v is None or v == "":
        return None
    if isinstance(v, date):
        return v
    s = clean_str(v)
    if not s:
        return None
    return date.fromisoformat(s.split(" ")[0])  # pandas sometimes hands back "2024-04-16 00:00:00"


# ══════════════════════════════════════════════════════════════════════
# VL RESULTS — our template only; a lab result alone can't safely create
# a new patient record, so this always requires an existing match.
# ══════════════════════════════════════════════════════════════════════
@router.post("/vl-import")
async def import_vl(file: UploadFile = File(...), db: Session = Depends(get_db), session: dict = Depends(current_user)):
    """CSV or XLSX: art_number, sample_date, result_date, vl_result"""
    content = await file.read()
    rows = load_rows(file.filename, content)
    imported, skipped, errors, skipped_art_numbers = 0, 0, [], []
    for i, row in enumerate(rows, 1):
        art = clean_str(row.get("art_number"))
        try:
            result = float(clean_str(row.get("vl_result", "0")).replace(",", ""))
            sample = _parse_date(row.get("sample_date"))
            patient = _find_patient(db, art)
            if not patient:
                skipped += 1
                skipped_art_numbers.append(art or f"(row {i}: blank art_number)")
                continue
            vl = VLResult(patient_id=patient.id, result=result, sample_date=sample,
                          suppressed=1 if result < 1000 else 0, source="EHR_IMPORT")
            db.add(vl)
            patient.vl_result = result; patient.vl_date = sample
            patient.vl_suppressed = 1 if result < 1000 else 0
            _auto_eci(patient); imported += 1
        except Exception as e:
            errors.append(f"Row {i} (art_number={art}): {e}")
    db.commit()
    return {"imported": imported, "skipped": skipped, "errors": errors[:10], "skipped_art_numbers": skipped_art_numbers[:20]}


# ══════════════════════════════════════════════════════════════════════
# HTS REGISTER — MOHCC format has no art_number at all. No auto-linking.
# ══════════════════════════════════════════════════════════════════════
_HTS_MOHCC_COLUMNS = {"Seriel #", "Name", "Gender", "Final Result"}


@router.post("/hts-import")
async def import_hts(file: UploadFile = File(...), db: Session = Depends(get_db), session: dict = Depends(current_user)):
    """
    Accepts either our simple template (art_number, test_date, result,
    cd4_count — updates a matched patient, same as before) or a real
    MOHCC "HTS Register" export (no art_number column at all). For the
    MOHCC format, nothing is written automatically — every POSITIVE
    result is returned for a human to manually cross-reference and link.
    Deliberate safety choice, not a missing feature — see module docstring.
    """
    content = await file.read()
    rows = load_rows(file.filename, content)
    if not rows:
        return {"imported": 0, "skipped": 0, "errors": [], "skipped_art_numbers": [], "positive_results_for_review": []}

    is_mohcc_format = bool(_HTS_MOHCC_COLUMNS & set(rows[0].keys()))

    if is_mohcc_format:
        positive_results = []
        for i, row in enumerate(rows, 1):
            result = clean_str(row.get("Final Result") or row.get("Result"))
            if result.upper() != "POSITIVE":
                continue
            positive_results.append({
                "row": i,
                "name": clean_str(row.get("Name")),
                "test_date": clean_str(row.get("Date")),
                "gender": clean_str(row.get("Gender")),
                "address": clean_str(row.get("Address")),
                "entry_point": clean_str(row.get("Entry Point")),
            })
        return {
            "imported": 0, "skipped": 0, "errors": [], "skipped_art_numbers": [],
            "positive_results_for_review": positive_results,
            "data_note": (
                f"This is a MOHCC HTS Register export — it has no ART number column "
                f"(most people tested were never ART patients). {len(positive_results)} "
                f"positive result(s) found out of {len(rows)} rows tested. None were "
                f"auto-linked to a patient record — matching by name alone risks attaching "
                f"a result to the wrong person. Review the list below and link each "
                f"manually via that patient's record."
            ),
        }

    imported, skipped, errors, skipped_art_numbers = 0, 0, [], []
    for i, row in enumerate(rows, 1):
        art = clean_str(row.get("art_number"))
        try:
            patient = _find_patient(db, art)
            if not patient:
                skipped += 1
                skipped_art_numbers.append(art or f"(row {i}: blank art_number)")
                continue
            cd4 = row.get("cd4_count")
            hts = HTSRecord(
                patient_id=patient.id,
                test_date=_parse_date(row.get("test_date")),
                result=clean_str(row.get("result")).upper(),
                cd4_count=int(cd4) if cd4 not in (None, "") else None,
                source="EHR_IMPORT",
            )
            db.add(hts)
            if cd4 not in (None, ""):
                patient.cd4_count = int(cd4); patient.cd4_date = hts.test_date
                _auto_eci(patient)
            imported += 1
        except Exception as e:
            errors.append(f"Row {i} (art_number={art}): {e}")
    db.commit()
    return {"imported": imported, "skipped": skipped, "errors": errors[:10], "skipped_art_numbers": skipped_art_numbers[:20]}


# ══════════════════════════════════════════════════════════════════════
# ART APPOINTMENTS LIST — MOHCC format has enough real fields to safely
# auto-create a new patient when the ART number isn't already registered.
# ══════════════════════════════════════════════════════════════════════
_APPT_MOHCC_COLUMN_MAP = {
    "art_number": "2) OI/ART Number",
    "first_name": "3)  First Name of Index",
    "surname": "4) Surname of Index",
    "sex": "5)Sex",
    "phone": "7) Phone Number",
    "initiation_date": "10) ART initiation date (mm/dd/yy)",
    "next_appointment": "12. Date client eligible for follow-up",
    "reason": "13. Reason for Follow-up",
}
_REASON_TO_VISIT_TYPE = {"drug pickup": "PHARMACY", "clinical visit": "CLINICAL", "routine viral load": "CLINICAL"}


def _mohcc_get(row: dict, key: str) -> str:
    """MOHCC column names carry inconsistent internal spacing across
    exports (' 2) OI/ART Number' vs '2) OI/ART Number') — match by
    normalized comparison (strip + collapse whitespace + lowercase)
    rather than an exact key lookup."""
    target = " ".join(_APPT_MOHCC_COLUMN_MAP[key].split()).lower()
    for k, v in row.items():
        if " ".join(str(k).split()).lower() == target:
            return clean_str(v)
    return ""


@router.post("/art-appointments-import")
async def import_appointments(file: UploadFile = File(...), db: Session = Depends(get_db), session: dict = Depends(current_user)):
    """
    Accepts either our simple template (art_number, last_visit,
    next_appointment, visit_type, progress_status) or a real MOHCC
    "Art Appointments List" export. For the MOHCC format specifically,
    an unmatched ART number triggers auto-creation of a new patient
    record — this export carries first/last name, sex, phone, and ART
    initiation date, enough to do that safely (unlike HTS — see
    module docstring).
    """
    content = await file.read()
    rows = load_rows(file.filename, content)
    if not rows:
        return {"imported": 0, "created": 0, "skipped": 0, "errors": [], "skipped_art_numbers": []}

    is_mohcc_format = any(
        " ".join(str(k).split()).lower() == " ".join(_APPT_MOHCC_COLUMN_MAP["art_number"].split()).lower()
        for k in rows[0].keys()
    )

    imported, created, skipped, errors, skipped_art_numbers = 0, 0, 0, [], []

    for i, row in enumerate(rows, 1):
        try:
            if is_mohcc_format:
                art = _mohcc_get(row, "art_number")
                if not art:
                    skipped += 1; continue
                patient = _find_patient(db, art)
                if not patient:
                    first = _mohcc_get(row, "first_name")
                    surname = _mohcc_get(row, "surname")
                    sex_raw = _mohcc_get(row, "sex").upper()
                    init_date = _parse_date(_mohcc_get(row, "initiation_date")) or date.today()
                    if not (first and surname):
                        skipped += 1
                        skipped_art_numbers.append(f"{art} (row {i}: missing name, can't auto-create)")
                        continue
                    reason = _mohcc_get(row, "reason").strip().lower()
                    visit_type = _REASON_TO_VISIT_TYPE.get(reason, "PHARMACY")
                    interval = VISIT_INTERVALS[visit_type]
                    patient = ARTClient(
                        facility_id=session.get("facility_id"),
                        art_number=art,
                        full_name=f"{first} {surname}".strip(),
                        gender="F" if sex_raw.startswith("F") else ("M" if sex_raw.startswith("M") else None),
                        phone=_mohcc_get(row, "phone") or None,
                        visit_type=visit_type,
                        initiation_date=init_date,
                        enrollment_date=init_date,  # not separately captured in this export — initiation date is the closest real field
                        progress_status="ACTIVE",
                        last_visit=init_date,
                        next_appointment=_parse_date(_mohcc_get(row, "next_appointment")) or (init_date + timedelta(days=interval)),
                        is_active=1,
                    )
                    db.add(patient)
                    db.flush()
                    created += 1
                else:
                    next_appt = _parse_date(_mohcc_get(row, "next_appointment"))
                    if next_appt:
                        patient.next_appointment = next_appt
                        patient.last_visit = date.today()
                    reason = _mohcc_get(row, "reason").strip().lower()
                    if reason in _REASON_TO_VISIT_TYPE:
                        patient.visit_type = _REASON_TO_VISIT_TYPE[reason]
                _auto_eci(patient)
                imported += 1
            else:
                art = clean_str(row.get("art_number"))
                patient = _find_patient(db, art)
                if not patient:
                    skipped += 1
                    skipped_art_numbers.append(art or f"(row {i}: blank art_number)")
                    continue
                if row.get("last_visit"):
                    patient.last_visit = _parse_date(row["last_visit"])
                if row.get("next_appointment"):
                    patient.next_appointment = _parse_date(row["next_appointment"])
                if row.get("visit_type"):
                    patient.visit_type = clean_str(row["visit_type"]).upper()
                if row.get("progress_status"):
                    patient.progress_status = clean_str(row["progress_status"]).upper()
                _auto_eci(patient)
                imported += 1
        except Exception as e:
            errors.append(f"Row {i}: {e}")

    db.commit()
    return {
        "imported": imported, "created": created, "skipped": skipped,
        "errors": errors[:10], "skipped_art_numbers": skipped_art_numbers[:20],
        "format_detected": "MOHCC Art Appointments List" if is_mohcc_format else "simple template",
    }


# ══════════════════════════════════════════════════════════════════════
# PHARMACY REGISTER — new import type. Matches existing patients and
# drugs by name; FEFO-selects a batch and records a real dispense event,
# exactly like the manual Dispense screen would, so stock stays accurate.
# ══════════════════════════════════════════════════════════════════════
@router.post("/pharmacy-register-import")
async def import_pharmacy_register(file: UploadFile = File(...), db: Session = Depends(get_db), session: dict = Depends(current_user)):
    """
    CSV or XLSX: art_number, drug_name, quantity, dispense_date, batch_number (optional)

    A dispense event doesn't carry enough demographic data to safely
    register a new patient, so — like VL import — this only updates
    patients (and stock) that already exist; unmatched ART numbers or
    drug names are reported, not guessed at.

    NOTE: no real MOHCC pharmacy register sample has been provided/tested
    yet (unlike Appointments and HTS, which were built and verified
    against real exports). This generic template is a best-effort based
    on the DispenseRecord schema — if you have a real pharmacy register
    export, upload it and this gets the same exact-column-mapping
    treatment Appointments and HTS Register got.
    """
    content = await file.read()
    rows = load_rows(file.filename, content)
    imported, skipped, errors = 0, 0, []

    for i, row in enumerate(rows, 1):
        art = clean_str(row.get("art_number"))
        drug_name = clean_str(row.get("drug_name"))
        try:
            patient = _find_patient(db, art)
            if not patient:
                skipped += 1
                errors.append(f"Row {i}: ART number '{art}' not found — patient not registered")
                continue

            drug = db.query(Drug).filter(Drug.name.ilike(f"%{drug_name}%")).first()
            if not drug:
                skipped += 1
                errors.append(f"Row {i}: drug '{drug_name}' not found in drug registry")
                continue

            qty = int(float(clean_str(row.get("quantity", "0")) or "0"))
            if qty <= 0:
                skipped += 1
                errors.append(f"Row {i}: quantity must be positive")
                continue

            batch_number = clean_str(row.get("batch_number"))
            if batch_number:
                batch = db.query(Batch).filter(Batch.drug_id == drug.id, Batch.batch_number == batch_number).first()
            else:
                batch = (
                    db.query(Batch)
                    .filter(Batch.drug_id == drug.id, Batch.quantity_remaining > 0, Batch.expiry_date > date.today())
                    .order_by(Batch.expiry_date.asc())
                    .first()
                )
            if not batch:
                skipped += 1
                errors.append(f"Row {i}: no available batch for '{drug_name}'" + (f" (batch {batch_number})" if batch_number else ""))
                continue
            if batch.quantity_remaining < qty:
                skipped += 1
                errors.append(f"Row {i}: batch {batch.batch_number} only has {batch.quantity_remaining} remaining, row requests {qty}")
                continue

            dispense_date = _parse_date(row.get("dispense_date")) or date.today()
            batch.quantity_remaining -= qty
            db.add(DispenseRecord(
                client_id=patient.id, batch_id=batch.id, quantity=qty,
                dispense_date=dispense_date, dispensed_by="EHR Import", notes="Imported from pharmacy register",
            ))
            interval = VISIT_INTERVALS.get(patient.visit_type, 180)
            patient.last_visit = dispense_date
            patient.next_appointment = dispense_date + timedelta(days=interval)
            imported += 1
        except Exception as e:
            errors.append(f"Row {i} (art_number={art}): {e}")

    db.commit()
    return {"imported": imported, "skipped": skipped, "errors": errors[:15]}


@router.get("/templates")
def get_templates():
    return {
        "vl_csv": "art_number,sample_date,result_date,vl_result\n09-0A-06-2015-A-00250,2026-05-01,2026-05-10,450",
        "hts_csv": "art_number,test_date,result,cd4_count\n09-0A-06-2015-A-00250,2026-05-01,POSITIVE,180",
        "appointments_csv": "art_number,last_visit,next_appointment,visit_type,progress_status\n09-0A-06-2015-A-00250,2026-04-01,2026-10-01,PHARMACY,ACTIVE",
        "pharmacy_register_csv": "art_number,drug_name,quantity,dispense_date,batch_number\n09-0A-06-2015-A-00250,TLD,60,2026-05-01,",
    }
