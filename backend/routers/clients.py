from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, timedelta

from database import get_db
from models import ARTClient
from schemas import ClientCreate, ClientResponse

router = APIRouter()

VISIT_INTERVALS = {"PHARMACY": 180, "CLINICAL": 90}


def calc_next_appointment(last_visit: date, visit_type: str) -> date:
    interval = VISIT_INTERVALS.get(visit_type, 180)
    return last_visit + timedelta(days=interval)


@router.get("/", response_model=List[ClientResponse])
def list_clients(
    search: Optional[str] = Query(None),
    visit_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(ARTClient).filter(ARTClient.is_active == 1)
    if search:
        term = f"%{search}%"
        q = q.filter(
            (ARTClient.art_number.ilike(term)) | (ARTClient.full_name.ilike(term))
        )
    if visit_type:
        q = q.filter(ARTClient.visit_type == visit_type)
    return q.order_by(ARTClient.next_appointment.asc()).all()


@router.post("/", response_model=ClientResponse, status_code=201)
def create_client(client: ClientCreate, db: Session = Depends(get_db)):
    existing = db.query(ARTClient).filter(ARTClient.art_number == client.art_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="ART number already registered")

    next_apt = calc_next_appointment(client.enrollment_date, client.visit_type)
    db_client = ARTClient(
        **client.dict(),
        last_visit=client.enrollment_date,
        next_appointment=next_apt,
    )
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client


@router.get("/art/{art_number}", response_model=ClientResponse)
def get_by_art_number(art_number: str, db: Session = Depends(get_db)):
    client = db.query(ARTClient).filter(ARTClient.art_number == art_number).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.get("/{client_id}", response_model=ClientResponse)
def get_client(client_id: int, db: Session = Depends(get_db)):
    client = db.query(ARTClient).filter(ARTClient.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.put("/{client_id}", response_model=ClientResponse)
def update_client(client_id: int, updates: ClientCreate, db: Session = Depends(get_db)):
    client = db.query(ARTClient).filter(ARTClient.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    for k, v in updates.dict(exclude_unset=True).items():
        setattr(client, k, v)
    # Recalculate next appointment
    if client.last_visit:
        client.next_appointment = calc_next_appointment(client.last_visit, client.visit_type)
    db.commit()
    db.refresh(client)
    return client


@router.delete("/{client_id}", status_code=204)
def deactivate_client(client_id: int, db: Session = Depends(get_db)):
    client = db.query(ARTClient).filter(ARTClient.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    client.is_active = 0
    db.commit()
