# SIEAL v2.0 — Strategic Intelligence Evaluation Accelerate Learning
### Cimas Healthathon 3.0  ·  Tapfi Technologies  ·  Demo Day: 28 August 2026

---

## Quick Start (3 commands)

```bash
cd pharmacy-module/backend
pip install -r requirements.txt
python seed_data.py
uvicorn main:app --reload
```

Open `frontend/index.html` in your browser. No npm, no build step.

**Demo logins**

| Username     | Password   | Role        |
|--------------|------------|-------------|
| pharmacist   | pharm123   | Pharmacist  |
| admin        | admin123   | Admin       |
| clinician    | clin123    | Clinician   |

Default QR scan PIN: **1234**

---

## Adding the Anthropic API Key (for live AI)

**Mac / Linux**
```bash
export ANTHROPIC_API_KEY=sk-ant-your-key-here
uvicorn main:app --reload
```

**Windows Command Prompt**
```cmd
set ANTHROPIC_API_KEY=sk-ant-your-key-here
uvicorn main:app --reload
```

**Permanent — create `backend/.env`** (copy from `.env.example`)
```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```
The server reads this file automatically on startup. Demo mode works without any key.

---

## What's Built

### Dashboard
- Editorial greeting with time-of-day awareness
- 6 animated KPI cards with sparklines
- 7-day dispense bar chart
- Patient status donut chart
- Mini appointment calendar (28-day, with appointment dots)
- Capacity stats progress bars
- Radial gauge charts (VL suppression, adherence, stock health)
- Live activity feed
- **Early Case Investigation tab** — AI-flagged patients

### Recipients of Care (Patients)
- ART number format: `09-0A-06-2025-A-00001`
- TB number format: `231084` (23 = year 2023)
- All treatment combinations: TLD, TLE600, AZT+NVP, TDF+3TC+EFV, AZT+NVP+3TC, ABC, 2nd Line, 3HP, INH
- CD4, VL, suppression status, adherence score
- Stock status: IN / OUT / REQUESTED / LOAN_OUT / GRANTED
- ECI auto-flagging per MOHCC guidelines

### Early Case Investigation (ECI)
1. New initiations with CD4 < 200
2. Return to Treatment (RTT) with CD4 < 200
3. Classified under Treatment Failure (VL ≥ 1000 on active ART)

### Stock Register
- FEFO batch management with RAG expiry alerts
- QR/GS1 barcode scanning — requires PIN (default 1234)
- 5-minute secure scan session with full audit log
- Expiry loss register with reason codes

### Forecast & Kanban
- Days of Stock Remaining (DSR) per drug line
- **Kanban board**: CRITICAL / LOW / MODERATE / ADEQUATE columns
- 30/60/90-day cohort demand projections
- Procurement quantity recommendations
- Each kanban card shows: DSR, stock qty, ADC, action button

### Stock Sharing Network
- 22 Bulawayo facilities pre-registered with DHIS2 codes
- Smart Finder: `safe_to_donate = stock − (90d demand + 30d buffer)`
- Transfer lifecycle: REQUESTED → APPROVED → COMPLETED → REPAID
- Repayment obligation tracking

### AI Agent
- Monthly summary, ECI analysis, stock intelligence, adherence narrative, anomaly detection
- Free-text query interface
- Requires `ANTHROPIC_API_KEY` env var — see above
- Demo responses included (no key needed)

### EHR Import
Supported datasets (CSV and XLSX/XLS):
- **Viral Load Results**: `art_number, sample_date, result_date, vl_result`
- **HTS Records**: `art_number, test_date, result, cd4_count`
- **ART Appointments**: `art_number, last_visit, next_appointment, visit_type, progress_status`

### Reports & Export
Five formats for each dataset:

| Format | Notes |
|--------|-------|
| CSV    | Universal, opens in Excel |
| XLSX   | Styled spreadsheet with teal header |
| DOCX   | Word document with table |
| PDF    | Opens print dialog — use Save as PDF |
| TXT    | Plain text, readable anywhere |

Plus AI-generated reports (5 types) and scheduled email reporting (configure SMTP env vars).

---

## All 22 Bulawayo Facilities

Cowdray Park (100348), Dr. Shennan (100418), E.F. Watson (100429),
Emakhandeni (100443), Entumbane (100449), Ingutsheni (100638),
Khami (100733), Luveve (100786), Magwegwe (100824), Maqhawe (100893),
Mpilo (101041), Mzilikazi (101202), Njube (101273), Nketa (101276),
Nkulumane (101278), Northern Suburbs (101290), Pelandaba (101412),
Princess Margaret (101429), Pumula (101432), Pumula South (101434),
Tshabalala (101710), United Bulawayo Hospital (101723)

---

## Backend API

| Router | Prefix | Key Endpoints |
|--------|--------|---------------|
| Auth | /api/auth | /login, /logout, /verify-pin, /facilities, /provinces, /districts |
| Patients | /api/patients | /, /{id}, /eci, /refresh-eci |
| Stock | /api/stock | /receive, /, /alerts, /fefo/{id}, /loss |
| Dispense | /api/dispense | /, /history/{id}, /recent |
| Appointments | /api/appointments | /upcoming, /ltfu, /calendar, /mark-attended/{id} |
| Forecast | /api/forecast | /dsr, /demand, /procurement, /cohort-demand |
| Network | /api/network | /facilities, /can-share, /request, /approve, /complete, /repay |
| EHR | /api/ehr | /vl-import, /hts-import, /art-appointments-import |
| Export | /api/export | /csv/*, /xlsx/*, /docx/*, /pdf/*, /txt/*, /json/* |
| AI | /api/ai | /analyze, /generate-report, /detect-anomalies |
| Dashboard | /api/dashboard | /summary |

Full docs: **http://localhost:8000/docs**

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+ · FastAPI · SQLAlchemy · SQLite |
| Frontend | Tailwind CSS (CDN) · Lucide Icons (CDN) · Vanilla JS |
| QR | html5-qrcode — GS1 pharmaceutical standard |
| AI | Anthropic Claude API (claude-sonnet-5) |
| Export | openpyxl (XLSX) · python-docx (DOCX) · stdlib (CSV/TXT) |
| Auth | SHA-256 · In-memory JWT sessions |

## Production Checklist

- [ ] Switch SQLite → PostgreSQL
- [ ] Add HTTPS (nginx + Let's Encrypt)
- [ ] Set `ANTHROPIC_API_KEY` in environment
- [ ] Configure SMTP for scheduled reports
- [ ] Set up nightly DB backups
- [ ] Add DHIS2/eLMIS export integration

---

*Cimas Healthathon 3.0  ·  Bulawayo, Zimbabwe  ·  info@tapfi.co.zw*
