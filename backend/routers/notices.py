"""Notice Board — dashboard announcements. Facility-scoped or global (facility_id=null),
with optional expiry. Same auth/error patterns as the rest of the app."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date

from database import get_db
from models import Notice
from routers.auth import current_user

router = APIRouter()


def notice_dict(n: Notice) -> dict:
    return {
        "id": n.id,
        "title": n.title,
        "message": n.message,
        "priority": n.priority,
        "facility_id": n.facility_id,
        "facility_name": n.facility.name if n.facility else "All Facilities",
        "created_by": n.created_by,
        "created_at": n.created_at.isoformat() if n.created_at else None,
        "expires_at": n.expires_at.isoformat() if n.expires_at else None,
    }


@router.get("/")
def list_notices(db: Session = Depends(get_db), session: dict = Depends(current_user)):
    """Active, non-expired notices visible to the current user's facility
    (global notices with facility_id=null are visible everywhere)."""
    today = date.today()
    fid = session.get("facility_id")
    q = db.query(Notice).filter(Notice.is_active == 1)
    q = q.filter((Notice.facility_id == None) | (Notice.facility_id == fid))  # noqa: E711
    q = q.filter((Notice.expires_at == None) | (Notice.expires_at >= today))  # noqa: E711
    notices = q.order_by(Notice.created_at.desc()).all()
    return [notice_dict(n) for n in notices]


@router.post("/", status_code=201)
def create_notice(payload: dict, db: Session = Depends(get_db), session: dict = Depends(current_user)):
    title = (payload.get("title") or "").strip()
    message = (payload.get("message") or "").strip()
    if not title or not message:
        raise HTTPException(400, "Title and message are required")
    n = Notice(
        title=title,
        message=message,
        priority=(payload.get("priority") or "INFO").upper(),
        facility_id=payload.get("facility_id") if payload.get("scope") == "facility" else None,
        created_by=session.get("full_name") or session.get("username"),
        created_at=date.today(),
        expires_at=date.fromisoformat(payload["expires_at"]) if payload.get("expires_at") else None,
        is_active=1,
    )
    if n.facility_id is None and payload.get("scope") == "facility":
        n.facility_id = session.get("facility_id")
    db.add(n)
    db.commit()
    db.refresh(n)
    return notice_dict(n)


@router.delete("/{notice_id}", status_code=204)
def delete_notice(notice_id: int, db: Session = Depends(get_db), session: dict = Depends(current_user)):
    n = db.query(Notice).filter(Notice.id == notice_id).first()
    if not n:
        raise HTTPException(404, "Notice not found")
    db.delete(n)
    db.commit()
