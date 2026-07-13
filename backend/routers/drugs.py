from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models import Drug
from schemas import DrugCreate, DrugResponse

router = APIRouter()


@router.get("/", response_model=List[DrugResponse])
def list_drugs(db: Session = Depends(get_db)):
    return db.query(Drug).order_by(Drug.name).all()


@router.post("/", response_model=DrugResponse, status_code=201)
def create_drug(drug: DrugCreate, db: Session = Depends(get_db)):
    existing = db.query(Drug).filter(Drug.name == drug.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Drug with this name already exists")
    db_drug = Drug(**drug.dict())
    db.add(db_drug)
    db.commit()
    db.refresh(db_drug)
    return db_drug


@router.get("/{drug_id}", response_model=DrugResponse)
def get_drug(drug_id: int, db: Session = Depends(get_db)):
    drug = db.query(Drug).filter(Drug.id == drug_id).first()
    if not drug:
        raise HTTPException(status_code=404, detail="Drug not found")
    return drug


@router.delete("/{drug_id}", status_code=204)
def delete_drug(drug_id: int, db: Session = Depends(get_db)):
    drug = db.query(Drug).filter(Drug.id == drug_id).first()
    if not drug:
        raise HTTPException(status_code=404, detail="Drug not found")
    db.delete(drug)
    db.commit()
