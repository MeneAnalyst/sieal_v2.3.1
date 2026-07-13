from pydantic import BaseModel
from datetime import date
from typing import Optional

class Cfg:
    orm_mode = True

class DrugBase(BaseModel):
    name: str; strength: Optional[str]=None; form: Optional[str]="Tablet"; category: Optional[str]="ART"
class DrugCreate(DrugBase): pass
class DrugResponse(DrugBase):
    id: int
    class Config(Cfg): pass

class BatchCreate(BaseModel):
    drug_id: int; batch_number: str; expiry_date: date; quantity_received: int
    supplier: Optional[str]="NatPharm Zimbabwe"; gtin: Optional[str]=None
class BatchResponse(BaseModel):
    id: int; drug_id: int; drug_name: Optional[str]=None; batch_number: str
    expiry_date: date; quantity_received: int; quantity_remaining: int
    received_date: Optional[date]=None; supplier: Optional[str]=None
    alert_status: Optional[str]=None; days_to_expiry: Optional[int]=None
    class Config(Cfg): pass

class ClientCreate(BaseModel):
    art_number: str; full_name: str; regime: str; visit_type: str="PHARMACY"
    enrollment_date: date; phone: Optional[str]=None; gender: Optional[str]=None
    date_of_birth: Optional[date]=None
class ClientResponse(BaseModel):
    id: int; art_number: str; full_name: str; regime: str; visit_type: str
    enrollment_date: date; phone: Optional[str]=None; gender: Optional[str]=None
    last_visit: Optional[date]=None; next_appointment: Optional[date]=None; is_active: int=1
    class Config(Cfg): pass

class DispenseCreate(BaseModel):
    client_id: int; batch_id: int; quantity: int
    dispensed_by: Optional[str]="Pharmacist"; notes: Optional[str]=None

class ExpiryLossCreate(BaseModel):
    batch_id: int; quantity_lost: int; reason_code: str; notes: Optional[str]=None
