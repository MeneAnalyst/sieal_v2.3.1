"""
Seed script — Zimbabwe ART clinic demo data.
  python seed_data.py
"""
import hashlib, random
from datetime import date, timedelta
from database import SessionLocal, engine
from models import Base, Drug, Batch, ARTClient, DispenseRecord, Facility, User, VLResult

random.seed(99)
TODAY = date.today()

def hp(s): return hashlib.sha256(s.encode()).hexdigest()

FACILITIES = [
    ("Cowdray Park",        "100348","Clinic"),
    ("Dr. Shennan",         "100418","Clinic"),
    ("E.F. Watson",         "100429","Clinic"),
    ("Emakhandeni",         "100443","Clinic"),
    ("Entumbane",           "100449","Clinic"),
    ("Ingutsheni",          "100638","Central Hospital"),
    ("Khami",               "100733","Clinic"),
    ("Luveve",              "100786","Clinic"),
    ("Magwegwe",            "100824","Clinic"),
    ("Maqhawe",             "100893","Clinic"),
    ("Mpilo",               "101041","Central Hospital"),
    ("Mzilikazi",           "101202","Clinic"),
    ("Njube",               "101273","Clinic"),
    ("Nketa",               "101276","Clinic"),
    ("Nkulumane",           "101278","Clinic"),
    ("Northern Suburbs",    "101290","Clinic"),
    ("Pelandaba",           "101412","Clinic"),
    ("Princess Margaret",   "101429","Clinic"),
    ("Pumula",              "101432","Clinic"),
    ("Pumula South",        "101434","Clinic"),
    ("Tshabalala",          "101710","Clinic"),
    ("United Bulawayo Hospital","101723","Central Hospital"),
]

COORDS = {
    "100348":(-20.2100,28.6050),"100418":(-20.1490,28.5840),"100429":(-20.1520,28.5900),
    "100443":(-20.1800,28.6200),"100449":(-20.2050,28.5530),"100638":(-20.1630,28.5590),
    "100733":(-20.1350,28.5100),"100786":(-20.2200,28.5650),"100824":(-20.1550,28.5750),
    "100893":(-20.2300,28.6100),"101041":(-20.1558,28.5680),"101202":(-20.1600,28.5820),
    "101273":(-20.1700,28.5950),"101276":(-20.1450,28.5960),"101278":(-20.1250,28.5420),
    "101290":(-20.1300,28.5900),"101412":(-20.1650,28.5700),"101429":(-20.1580,28.5780),
    "101432":(-20.1980,28.5860),"101434":(-20.2050,28.5780),"101710":(-20.1900,28.5600),
    "101723":(-20.1490,28.5840),
}

TREATMENTS = [
    "TDF + 3TC + DTG (TLD)","TDF + 3TC + EFV","AZT + NVP","AZT + NVP + 3TC",
    "TDF + 3TC + NVP","AZT + NVP + 3TC + EFV","ABC","2nd Line","3HP","INH",
]

NAMES = [
    "Tendai Moyo","Chipo Ndlovu","Farai Sibanda","Rudo Ncube","Blessing Dube",
    "Tariro Mpofu","Kudakwashe Nkomo","Siphiwe Moyo","Patience Ncube","Trust Dube",
    "Lindiwe Sibanda","Memory Ndlovu","Talent Mpofu","Mavis Nkomo","Faith Dlodlo",
    "Sibongile Moyo","Tafadzwa Zulu","Nomathemba Dube","Charles Ncube","Agnes Ndlovu",
    "Joseph Mhlanga","Grace Nyathi","Samuel Ndlovu","Mary Sibanda","Peter Moyo",
    "Ruth Nkomo","David Mpofu","Esther Ncube","John Dube","Sarah Sibanda",
    "Nomalanga Moyo","Aleck Chirwa","Chiedza Mutasa","Takudzwa Banda","Ropafadzai Gumbo",
    "Munesu Shumba","Tinarwo Chidhakwa","Prisca Matemba","Garikai Mpofu","Netsai Dube",
    "Rumbidzai Ncube","Simba Mhlanga","Tatenda Nkomo","Vongai Moyo","Wadzanai Sibanda",
]

STATUSES = ["ACTIVE","ACTIVE","ACTIVE","ACTIVE","LTFU","RTT","TREATMENT_FAILURE","NEW_INITIATION"]

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    if db.query(Facility).count() > 0:
        print("Already seeded."); db.close(); return

    # ── Facilities ────────────────────────────────────────────────
    fac_map = {}
    for name, code, ftype in FACILITIES:
        lat, lng = COORDS.get(code, (-20.15, 28.57))
        is_cur = 1 if code == "101041" else 0   # Mpilo is "current"
        f = Facility(name=name, dhis2_code=code, facility_type=ftype,
                     district="Bulawayo", district_code="06",
                     province="Bulawayo Metropolitan", province_code="09",
                     lat=lat, lng=lng, contact_phone=f"+26377{random.randint(1000000,9999999)}",
                     is_current=is_cur)
        db.add(f); db.flush(); fac_map[code] = f.id
    db.commit(); print(f"[OK] {len(FACILITIES)} facilities")

    mpilo_id = fac_map["101041"]

    # ── Users ─────────────────────────────────────────────────────
    users = [
        ("admin",      "System Administrator", "admin123",  "ADMIN",      "101041"),
        ("pharmacist", "Sr. T. Moyo",          "pharm123",  "PHARMACIST", "101041"),
        ("clinician",  "Dr. K. Sibanda",       "clin123",   "CLINICIAN",  "101041"),
        ("viewer",     "Data Officer",         "view123",   "VIEWER",     "100786"),
    ]
    for uname, fname, pw, role, fcode in users:
        db.add(User(username=uname, full_name=fname, password_hash=hp(pw),
                    role=role, facility_id=fac_map[fcode], scan_pin_hash=hp("1234"), is_active=1))
    db.commit(); print("[OK] 4 users (admin/admin123, pharmacist/pharm123, clinician/clin123)")

    # ── Drugs ─────────────────────────────────────────────────────
    drugs_data = [
        ("Tenofovir/Lamivudine/Dolutegravir (TLD)","300/300/50mg","Tablet","ART"),
        ("Tenofovir/Lamivudine/Efavirenz (TLE600)","300/300/600mg","Tablet","ART"),
        ("Zidovudine/Lamivudine/Nevirapine (AZT/3TC/NVP)","300/150/200mg","Tablet","ART"),
        ("Abacavir/Lamivudine (ABC/3TC)","600/300mg","Tablet","ART"),
        ("Lopinavir/Ritonavir (LPV/r)","200/50mg","Tablet","ART"),
        ("Dolutegravir (DTG)","50mg","Tablet","ART"),
        ("Cotrimoxazole (CTX)","960mg","Tablet","Prophylaxis"),
        ("Fluconazole","200mg","Capsule","OI Treatment"),
    ]
    drugs = []
    for n,s,f,c in drugs_data:
        d = Drug(name=n,strength=s,form=f,category=c); db.add(d); db.flush(); drugs.append(d)
    db.commit(); print(f"[OK] {len(drugs)} drugs")

    # ── Batches ───────────────────────────────────────────────────
    batches_raw = [
        (0,"TLD-ZW-24-001",TODAY+timedelta(14),500,45),
        (0,"TLD-ZW-24-002",TODAY+timedelta(65),1000,820),
        (0,"TLD-ZW-24-003",TODAY+timedelta(190),1200,1200),
        (1,"TLE-ZW-24-001",TODAY+timedelta(22),300,110),
        (1,"TLE-ZW-24-002",TODAY+timedelta(130),600,580),
        (2,"AZT-ZW-24-001",TODAY+timedelta(78),400,280),
        (2,"AZT-ZW-24-002",TODAY+timedelta(210),800,800),
        (3,"ABC-ZW-24-001",TODAY+timedelta(50),200,90),
        (4,"LPV-ZW-24-001",TODAY+timedelta(88),150,130),
        (4,"LPV-ZW-24-002",TODAY+timedelta(370),300,300),
        (5,"DTG-ZW-24-001",TODAY+timedelta(18),100,55),
        (5,"DTG-ZW-24-002",TODAY+timedelta(250),500,500),
        (6,"CTX-ZW-24-001",TODAY+timedelta(160),2000,1800),
        (6,"CTX-ZW-24-002",TODAY+timedelta(310),3000,3000),
        (7,"FLU-ZW-24-001",TODAY+timedelta(82),200,150),
    ]
    batches = []
    for di,bno,exp,qr,qrem in batches_raw:
        b = Batch(drug_id=drugs[di].id,batch_number=bno,expiry_date=exp,
                  quantity_received=qr,quantity_remaining=qrem,
                  received_date=TODAY-timedelta(random.randint(10,90)),
                  supplier="NatPharm Zimbabwe")
        db.add(b); db.flush(); batches.append(b)
    db.commit(); print(f"[OK] {len(batches)} batches")

    # ── ART Clients ───────────────────────────────────────────────
    drug_name_map = {d.name: i for i,d in enumerate(drugs)}
    clients = []
    tcs = ["TDF + 3TC + DTG (TLD)","TDF + 3TC + DTG (TLD)","TDF + 3TC + DTG (TLD)",
           "TDF + 3TC + EFV","AZT + NVP + 3TC","TDF + 3TC + DTG (TLD)","2nd Line","3HP"]

    for i, name in enumerate(NAMES):
        tc       = tcs[i % len(tcs)]
        vtype    = "PHARMACY" if i % 3 != 0 else "CLINICAL"
        gender   = "F" if i % 2 == 0 else "M"
        status   = STATUSES[i % len(STATUSES)]
        dob      = TODAY - timedelta(days=random.randint(18*365, 55*365))
        enroll   = TODAY - timedelta(days=random.randint(200,1200))
        initdate = enroll + timedelta(days=random.randint(1,30))
        last_v   = TODAY - timedelta(days=random.randint(1,175))
        interval = 180 if vtype=="PHARMACY" else 90
        next_a   = last_v + timedelta(days=interval)
        cd4      = random.choice([85,120,145,180,210,350,450,600,None])
        vl       = random.choice([20,50,200,400,800,1200,5000,50000,None])
        yr       = enroll.year % 100
        art_no   = f"09-0A-06-{enroll.year}-A-{str(i+1).zfill(5)}"
        tb_no    = f"{str(yr).zfill(2)}{random.randint(1000,9999)}" if i%4==0 else None
        adh      = round(random.uniform(55, 100), 1)
        fac_id   = mpilo_id if i < 30 else list(fac_map.values())[i % len(fac_map)]

        c = ARTClient(
            facility_id=fac_id, art_number=art_no, tb_number=tb_no,
            full_name=name, date_of_birth=dob, gender=gender,
            phone=f"+26377{random.randint(1000000,9999999)}",
            treatment_combination=tc, regime=tc, visit_type=vtype,
            initiation_date=initdate, enrollment_date=enroll,
            cd4_count=cd4, cd4_date=TODAY-timedelta(random.randint(30,180)) if cd4 else None,
            vl_result=vl, vl_date=TODAY-timedelta(random.randint(14,90)) if vl else None,
            vl_suppressed=1 if vl and vl<1000 else 0,
            progress_status=status, adherence_score=adh,
            stock_status=random.choice(["IN","IN","IN","OUT","REQUESTED"]),
            last_visit=last_v, next_appointment=next_a, is_active=1,
        )
        from routers.patients import _auto_eci
        _auto_eci(c)
        db.add(c); db.flush(); clients.append(c)
    db.commit(); print(f"[OK] {len(clients)} patients")

    # ── VL History ────────────────────────────────────────────────
    for c in clients[:20]:
        if c.vl_result:
            for j in range(random.randint(1,3)):
                res = random.choice([50,200,500,1100,5000])
                db.add(VLResult(patient_id=c.id, result=res,
                                sample_date=TODAY-timedelta(days=90*(j+1)),
                                suppressed=1 if res<1000 else 0, source="EHR_IMPORT"))
    db.commit(); print("[OK] VL history records")

    # ── Dispense History ─────────────────────────────────────────
    for _ in range(300):
        c = random.choice(clients)
        b = random.choice(batches[:8])
        db.add(DispenseRecord(client_id=c.id, batch_id=b.id,
                              quantity=random.choice([30,60,90,180]),
                              dispense_date=TODAY-timedelta(random.randint(1,90)),
                              dispensed_by="Demo Pharmacist"))
    db.commit(); print("[OK] 300 dispense records")
    db.close()
    print("\n[DONE] Seeded! Login: pharmacist / pharm123 | admin / admin123")

if __name__ == "__main__":
    seed()
