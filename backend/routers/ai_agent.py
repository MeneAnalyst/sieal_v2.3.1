"""
AI Agent router — "Strategic Intelligence" for RESILIENCE-ART.

HYBRID ARCHITECTURE (by explicit product decision):
Every endpoint here computes a complete, correct, real-data-driven answer
using narrative_templates.py FIRST — no API call involved. If
ANTHROPIC_API_KEY is configured, Claude is then asked to *refine the prose*
of that exact template (never to add new facts), and its output replaces
the template only on success. Any API failure — bad key, wrong model
string, network outage, rate limit — falls back to the template silently
from the user's point of view; the response body says which mode produced
it (`"source": "template" | "claude"`) so the frontend can show that
distinction without it ever being a hard error state.

This is a direct response to a real incident in this project: an invalid
model string caused every AI call to 400, and the entire Strategic
Intelligence page produced no output. That can no longer happen —
templates compute the exact same facts with zero dependency on the API.
"""
import os, json, csv, io, urllib.request, urllib.error, pathlib

# Auto-load .env if present (no python-dotenv dependency needed)
_env = pathlib.Path(__file__).parent.parent / 'ak.env'
if _env.exists():
    for _line in _env.read_text().splitlines():
        if '=' in _line and not _line.strip().startswith('#'):
            _k, _v = _line.split('=', 1)
            os.environ.setdefault(_k.strip(), _v.strip())

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta

from database import get_db
from models import ARTClient, Batch, DispenseRecord
from routers.auth import current_user
import narrative_templates as nt

router = APIRouter()

# Section 6 — this exact string is the mandated system prompt for the
# grounded chat/report endpoints below. Do not edit.
SYSTEM_PROMPT = (
    "You are the RESILIENCE-ART analyst for SIEAL. You strictly use Zimbabwe ART guidelines. "
    "Treatment failure is defined as VL >= 1000. Inventory safety buffer is 4 months (120 days). "
    "When suggesting donations, strictly apply the formula: Donatable = Current - (ADC * 120). "
    "If a patient has CD4 < 200 and is new, flag as ECI (Early Case Identification). "
    "Provide responses using available JSON context from the API."
)

STRATEGIC_DIRECTOR_PROMPT = SYSTEM_PROMPT + (
    " For this task specifically, act as the facility's Strategic Director: don't just answer, "
    "proactively rank the structured alerts you're given by clinical/operational severity and give "
    "one concrete, prescriptive next action per alert. Be concise — one short paragraph per alert."
)


# ══════════════════════════════════════════════════════════════════
# Raw Claude call — used only by generate_narrative() below
# ══════════════════════════════════════════════════════════════════

def _call_claude_raw(prompt: str, system: str) -> str:
    """Raises on any failure — caller (generate_narrative) decides the
    fallback. Never called directly by an endpoint."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")

    payload = json.dumps({
        "model": "claude-sonnet-5",
        "max_tokens": 1500,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
        return data["content"][0]["text"]


def generate_narrative(template_text: str, task_instruction: str, system: str = SYSTEM_PROMPT) -> dict:
    """
    The hybrid orchestrator. template_text is already a complete, correct
    answer computed from real numbers — this function's only job is to
    decide whether Claude gets a chance to improve its *phrasing*, and to
    guarantee the template is what ships if anything about that goes wrong.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"narrative": template_text, "source": "template"}

    prompt = (
        f"{task_instruction}\n\n"
        f"Here is a deterministically-computed draft based on real system data:\n"
        f"---\n{template_text}\n---\n\n"
        "Rewrite this in clearer, more natural prose for a pharmacist audience. "
        "Do NOT invent, change, or add any numbers, names, or facts not already present in the draft above."
    )
    try:
        text = _call_claude_raw(prompt, system)
        return {"narrative": text, "source": "claude"}
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8", errors="replace"))
            detail = body.get("error", {}).get("message", str(body))
        except Exception:
            detail = str(e)
        return {
            "narrative": template_text, "source": "template",
            "note": f"AI enhancement unavailable ({e.code}: {detail}) — showing the computed narrative instead.",
        }
    except Exception as e:
        return {
            "narrative": template_text, "source": "template",
            "note": f"AI enhancement unavailable ({e}) — showing the computed narrative instead.",
        }


# ══════════════════════════════════════════════════════════════════
# Context builder — the single source of real numbers every
# template and every Claude prompt in this file is grounded in
# ══════════════════════════════════════════════════════════════════

def _build_full_context(db: Session, facility_id: int) -> dict:
    from routers.forecast import get_adc, get_total_stock, donatable_surplus, kanban_status
    from models import Drug

    today = date.today()
    q = db.query(ARTClient).filter(ARTClient.is_active == 1)
    if facility_id:
        q = q.filter(ARTClient.facility_id == facility_id)

    total = q.count()
    eci_count = q.filter(ARTClient.is_eci_flag == 1).count()
    ltfu_count = q.filter(ARTClient.progress_status == "LTFU").count()
    tf_count = q.filter(ARTClient.progress_status == "TREATMENT_FAILURE").count()

    vl_supp = q.filter(ARTClient.vl_suppressed == 1).count()
    vl_total = q.filter(ARTClient.vl_result.isnot(None)).count()
    vl_suppression_pct = round(vl_supp / vl_total * 100, 1) if vl_total else None

    avg_adherence = db.query(func.avg(ARTClient.adherence_score)).filter(
        ARTClient.is_active == 1, ARTClient.adherence_score.isnot(None)
    ).scalar()
    avg_adherence = round(avg_adherence, 1) if avg_adherence is not None else None

    red_alerts = db.query(Batch).filter(Batch.quantity_remaining > 0, Batch.expiry_date <= today + timedelta(days=30)).count()
    amber_alerts = db.query(Batch).filter(
        Batch.quantity_remaining > 0, Batch.expiry_date > today + timedelta(days=30),
        Batch.expiry_date <= today + timedelta(days=90),
    ).count()
    dispensed_month = db.query(func.sum(DispenseRecord.quantity)).filter(
        DispenseRecord.dispense_date >= today.replace(day=1)
    ).scalar() or 0

    eci_patients = [
        {"art_number": p.art_number, "cd4": p.cd4_count, "vl": p.vl_result, "reason": p.eci_reason}
        for p in q.filter(ARTClient.is_eci_flag == 1).limit(15).all()
    ]

    critical_drugs, donatable_drugs, dsr_snapshot = [], [], []
    for drug in db.query(Drug).all():
        adc = get_adc(drug.id, db)
        total_stock = get_total_stock(drug.id, db)
        dsr = round(total_stock / adc, 1) if adc > 0 else 999.0
        status = kanban_status(dsr)
        dsr_snapshot.append({"drug": drug.name, "dsr_days": dsr, "status": status})
        if status == "CRITICAL":
            critical_drugs.append({"drug": drug.name, "dsr_days": dsr})
        surplus = donatable_surplus(total_stock, adc) if adc > 0 else 0
        if status == "ADEQUATE" and surplus > 0:
            donatable_drugs.append({"drug": drug.name, "donatable_surplus": surplus})

    return {
        "facility_id": facility_id, "facility_name": f"Facility #{facility_id}" if facility_id else "All Facilities",
        "period": today.strftime("%B %Y"), "date": today.isoformat(),
        "total_patients": total, "eci_count": eci_count, "ltfu_count": ltfu_count, "tf_count": tf_count,
        "vl_suppression_pct": vl_suppression_pct, "avg_adherence": avg_adherence,
        "red_alerts": red_alerts, "amber_alerts": amber_alerts, "dispensed_month": int(dispensed_month),
        "eci_patients": eci_patients, "critical_drugs": critical_drugs, "donatable_drugs": donatable_drugs,
        "stock_dsr_snapshot": dsr_snapshot,
    }


# ══════════════════════════════════════════════════════════════════
# Endpoints
# ══════════════════════════════════════════════════════════════════

@router.post("/analyze")
def analyze(payload: dict, db: Session = Depends(get_db), session: dict = Depends(current_user)):
    ctx = _build_full_context(db, session.get("facility_id", 0))
    template = nt.chat_response_template(payload.get("query", ""), ctx)
    result = generate_narrative(template, f"User asked: {payload.get('query', 'Provide a facility summary.')}")
    return {"response": result["narrative"], "source": result["source"], "note": result.get("note")}


@router.post("/chat")
def chat(payload: dict, db: Session = Depends(get_db), session: dict = Depends(current_user)):
    """Section 3 — the frontend AI chat panel calls this endpoint exclusively;
    the Anthropic key never leaves this backend process."""
    ctx = _build_full_context(db, session.get("facility_id", 0))
    query = payload.get("query", "Provide a facility summary.")
    template = nt.chat_response_template(query, ctx)
    result = generate_narrative(
        template,
        f"User asked: {query}\nFull JSON context:\n{json.dumps(ctx, default=str)}",
    )
    return {"response": result["narrative"], "source": result["source"], "note": result.get("note")}


@router.post("/generate-report")
def generate_report(payload: dict, db: Session = Depends(get_db), session: dict = Depends(current_user)):
    ctx = _build_full_context(db, session.get("facility_id", 0))
    rtype = payload.get("report_type", "monthly_summary")
    template_fn = nt.REPORT_TEMPLATES.get(rtype, nt.REPORT_TEMPLATES["monthly_summary"])
    template = template_fn(ctx)

    instructions = {
        "monthly_summary": "Generate a comprehensive monthly pharmacy operations report for this ART clinic.",
        "eci_analysis": "Analyse patients flagged for Early Case Identification and provide clinical recommendations.",
        "stock_intelligence": "Generate a stock intelligence report with procurement and network transfer recommendations.",
        "adherence_narrative": "Generate a patient adherence analysis narrative with intervention recommendations.",
        "anomaly_detection": "Perform anomaly detection on the clinical and stock data.",
    }
    result = generate_narrative(template, instructions.get(rtype, instructions["monthly_summary"]))
    return {
        "report_type": rtype, "content": result["narrative"], "source": result["source"],
        "note": result.get("note"), "generated_at": date.today().isoformat(),
    }


@router.post("/detect-anomalies")
def detect_anomalies(db: Session = Depends(get_db), session: dict = Depends(current_user)):
    ctx = _build_full_context(db, session.get("facility_id", 0))
    template = nt.anomaly_detection_template(ctx)
    result = generate_narrative(template, "Perform anomaly detection on this facility's clinical and stock data.")
    return {"anomalies": result["narrative"], "source": result["source"], "note": result.get("note")}


# ══════════════════════════════════════════════════════════════════
# Strategic Intelligence — proactive briefing
# ══════════════════════════════════════════════════════════════════

def _build_alerts(db: Session, facility_id: int) -> list:
    """Structured, locally-computed alerts — no AI call involved in
    producing these; see strategic_brief_narrative() for how they're
    turned into prose."""
    from routers.forecast import get_adc, get_total_stock, donatable_surplus, kanban_status
    from models import Drug

    alerts = []
    patients_q = db.query(ARTClient).filter(ARTClient.is_active == 1)
    if facility_id:
        patients_q = patients_q.filter(ARTClient.facility_id == facility_id)

    eci_count = patients_q.filter(ARTClient.is_eci_flag == 1).count()
    if eci_count > 0:
        alerts.append({
            "severity": "high", "category": "clinical", "title": f"{eci_count} patient(s) flagged for ECI",
            "detail": "New/RTT patients with CD4 < 200, or active patients with VL >= 1000.",
        })

    ltfu_count = patients_q.filter(ARTClient.progress_status == "LTFU").count()
    if ltfu_count > 3:
        alerts.append({
            "severity": "medium", "category": "clinical", "title": f"{ltfu_count} patients Lost to Follow-Up",
            "detail": "Elevated LTFU count — consider a community tracing push.",
        })

    critical_drugs, donatable_drugs = [], []
    for drug in db.query(Drug).all():
        adc = get_adc(drug.id, db)
        total = get_total_stock(drug.id, db)
        dsr = round(total / adc, 1) if adc > 0 else 999.0
        status = kanban_status(dsr)
        if status == "CRITICAL":
            import kpi_engine
            sim = kpi_engine.stockout_probability(drug.id, db, horizon_days=28)
            critical_drugs.append({"drug": drug.name, "dsr_days": dsr, "stockout_probability_28d": sim.get("probability")})
        surplus = donatable_surplus(total, adc) if adc > 0 else 0
        if status == "ADEQUATE" and surplus > 0:
            donatable_drugs.append({"drug": drug.name, "donatable_surplus": surplus})

    if critical_drugs:
        alerts.append({
            "severity": "critical", "category": "stock",
            "title": f"{len(critical_drugs)} drug line(s) at CRITICAL stock (< 30 days)",
            "detail": ", ".join(
                f"{d['drug'].split('(')[0].strip()} ({d['dsr_days']}d, {d['stockout_probability_28d']}% chance of stockout in 28d)"
                for d in critical_drugs[:5]
            ),
        })
    if donatable_drugs:
        alerts.append({
            "severity": "info", "category": "network",
            "title": f"{len(donatable_drugs)} drug line(s) have donatable surplus",
            "detail": ", ".join(f"{d['drug'].split('(')[0].strip()} (+{d['donatable_surplus']})" for d in donatable_drugs[:5]),
        })
    return alerts


@router.post("/brief")
def strategic_brief(db: Session = Depends(get_db), session: dict = Depends(current_user)):
    fid = session.get("facility_id", 0)
    alerts = _build_alerts(db, fid)
    template = nt.strategic_brief_narrative(alerts)
    if not alerts:
        return {"alerts": [], "narrative": template, "source": "template"}

    result = generate_narrative(
        template,
        f"Structured alerts (JSON):\n{json.dumps(alerts)}\n\nRank these by severity and give one action per alert.",
        system=STRATEGIC_DIRECTOR_PROMPT,
    )
    return {"alerts": alerts, "narrative": result["narrative"], "source": result["source"], "note": result.get("note")}


# ══════════════════════════════════════════════════════════════════
# Strategic Intelligence — import data directly into the chat
# ══════════════════════════════════════════════════════════════════

MAX_UPLOAD_ROWS = 500

def _summarize_csv(raw_text: str) -> dict:
    reader = csv.DictReader(io.StringIO(raw_text))
    rows = list(reader)
    if not rows:
        return {"row_count": 0, "columns": [], "sample": []}

    columns = reader.fieldnames or []
    numeric_summary = {}
    for col in columns:
        values = []
        for row in rows[:MAX_UPLOAD_ROWS]:
            raw = (row.get(col) or "").strip()
            try:
                values.append(float(raw))
            except ValueError:
                continue
        if len(values) >= max(3, len(rows) // 4):
            numeric_summary[col] = {"count": len(values), "mean": round(sum(values) / len(values), 2), "min": min(values), "max": max(values)}

    return {"row_count": len(rows), "columns": columns, "numeric_summary": numeric_summary, "sample": rows[:5]}


@router.post("/analyze-upload")
async def analyze_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    session: dict = Depends(current_user),
):
    if not file.filename.lower().endswith((".csv", ".txt")):
        raise HTTPException(400, "Only .csv or .txt files are supported for chat data import right now.")

    raw = (await file.read()).decode("utf-8-sig", errors="replace")
    profile = _summarize_csv(raw)
    if profile["row_count"] == 0:
        raise HTTPException(400, "No rows detected — check the file has a header row and at least one data row.")

    ctx = _build_full_context(db, session.get("facility_id", 0))
    template = nt.upload_analysis_template(profile, ctx)
    result = generate_narrative(
        template,
        f"An uploaded dataset was profiled as:\n{json.dumps(profile, default=str)}\n\n"
        f"Facility context:\n{json.dumps(ctx, default=str)}\n\n"
        "Analyse this in light of Zimbabwe ART guidelines and the facility's current state.",
    )
    return {
        "filename": file.filename, "profile": profile,
        "response": result["narrative"], "source": result["source"], "note": result.get("note"),
    }
