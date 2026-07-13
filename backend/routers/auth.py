"""
Authentication router — simple sha256 + in-memory token store.
No Rust-compiled dependencies required.
"""
import hashlib, secrets, json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from models import User, Facility

router = APIRouter()

# In-memory token store  { token: {user_id, facility_id, expires, username, role, full_name} }
_sessions: dict = {}


def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


def make_token(user: User) -> str:
    tok = secrets.token_urlsafe(32)
    _sessions[tok] = {
        "user_id":     user.id,
        "facility_id": user.facility_id,
        "username":    user.username,
        "full_name":   user.full_name,
        "role":        user.role,
        "expires":     (datetime.utcnow() + timedelta(hours=10)).isoformat(),
    }
    return tok


def get_session(token: str) -> Optional[dict]:
    s = _sessions.get(token)
    if not s:
        return None
    if datetime.utcnow() > datetime.fromisoformat(s["expires"]):
        del _sessions[token]
        return None
    return s


def current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    token = authorization.split(" ", 1)[1]
    s = get_session(token)
    if not s:
        raise HTTPException(401, "Session expired or invalid")
    return s


# ── Endpoints ─────────────────────────────────────────────────────

@router.post("/login")
def login(payload: dict, db: Session = Depends(get_db)):
    username = payload.get("username", "").strip().lower()
    password = payload.get("password", "")
    facility_id = payload.get("facility_id")

    user = db.query(User).filter(User.username == username, User.is_active == 1).first()
    if not user or user.password_hash != hash_pw(password):
        raise HTTPException(401, "Invalid username or password")

    # If facility provided at login, update session facility
    if facility_id:
        user.facility_id = int(facility_id)
        db.commit()

    token = make_token(user)
    facility = db.query(Facility).filter(Facility.id == user.facility_id).first()
    return {
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role,
            "facility_id": user.facility_id,
            "facility_name": facility.name if facility else "",
            "facility_dhis2": facility.dhis2_code if facility else "",
        }
    }


@router.post("/logout")
def logout(authorization: Optional[str] = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        tok = authorization.split(" ", 1)[1]
        _sessions.pop(tok, None)
    return {"message": "Logged out"}


@router.get("/me")
def me(session: dict = Depends(current_user), db: Session = Depends(get_db)):
    facility = db.query(Facility).filter(Facility.id == session["facility_id"]).first()
    return {**session, "facility_name": facility.name if facility else ""}


@router.post("/verify-pin")
def verify_pin(payload: dict, session: dict = Depends(current_user), db: Session = Depends(get_db)):
    pin = payload.get("pin", "")
    user = db.query(User).filter(User.id == session["user_id"]).first()
    if not user or not user.scan_pin_hash:
        raise HTTPException(400, "No scan PIN set. Configure in Settings.")
    if user.scan_pin_hash != hash_pw(pin):
        raise HTTPException(401, "Incorrect PIN")
    return {"verified": True, "session_minutes": 5}


@router.get("/facilities")
def list_facilities(
    province_code: str = None,
    district_code: str = None,
    db: Session = Depends(get_db)
):
    """Public endpoint — used during login facility selection."""
    q = db.query(Facility)
    if province_code:
        q = q.filter(Facility.province_code == province_code)
    if district_code:
        q = q.filter(Facility.district_code == district_code)
    return [
        {
            "id": f.id, "name": f.name, "dhis2_code": f.dhis2_code,
            "facility_type": f.facility_type, "district": f.district,
            "district_code": f.district_code, "province": f.province,
            "province_code": f.province_code,
        }
        for f in q.order_by(Facility.name).all()
    ]


@router.get("/provinces")
def list_provinces(db: Session = Depends(get_db)):
    rows = db.query(Facility.province, Facility.province_code).distinct().all()
    return [{"name": r[0], "code": r[1]} for r in rows if r[0]]


@router.get("/districts")
def list_districts(province_code: str = None, db: Session = Depends(get_db)):
    q = db.query(Facility.district, Facility.district_code).distinct()
    if province_code:
        q = q.filter(Facility.province_code == province_code)
    rows = q.all()
    return [{"name": r[0], "code": r[1]} for r in rows if r[0]]
