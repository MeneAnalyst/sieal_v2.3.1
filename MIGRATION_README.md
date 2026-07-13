# SIEAL v2.0 — React Migration + Population Analytics Warehouse

## What's in this package

**smartpharm-frontend/** — React 19 + Vite + TS + Shadcn/TanStack app. All
12 original pages migrated, plus:
- **Strategic Intelligence** (formerly "AI Agent") — proactive Briefing
  Feed + Deep Dive chat with CSV data import.
- **Defaulter Management** — primary component on the Appointments page,
  scikit-learn logistic-regression risk scoring (the one Tier-3 library
  wired in, deliberately scoped — see backend/defaulter_risk.py).
- **Dashboard** — Operational/Clinical tabs; Clinical tab has a
  Programmatic Health Index gauge, Kaplan-Meier retention curve, Layer 2
  rate cards, and honest "Not yet available" cards for Renal/TB/IRIS/
  Post-Transition-Adherence.
- **Population Analytics** (new) — 5 tabs (Clinical/Operational/Strategic/
  Optimization/Policy) reading from the separate Postgres warehouse below.

**backend/** — FastAPI. Existing OLTP routers unchanged in shape, plus:
- `kpi_engine.py`, `network_impact.py`, `routers/kpi.py` — Layer 1/2/3 KPI
  matrix (numpy/pandas/scipy + PuLP + lifelines — Tier 1 + selective
  Tier 2, no xgboost/SHAP/PyMC/OR-Tools; see kpi_engine.py's own docstrings
  for why).
- `defaulter_risk.py` — logistic regression defaulter risk (the one Tier-3
  library), with an honest small-sample caveat surfaced in every response.
- `warehouse_database.py`, `warehouse_models.py`, `dependency_model.py`,
  `etl/build_warehouse.py`, `routers/analytics.py`,
  `routers/warehouse_admin.py` — the new Population Analytics warehouse.

## Population Analytics warehouse — setup

This is a **separate Postgres database**, not the SQLite pharmacy.db. It
does not exist until you connect one and run the ETL:

```bash
cd backend
pip install -r requirements.txt        # now includes psycopg2-binary
# In backend/.env, add:
#   WAREHOUSE_DATABASE_URL=postgresql://user:pass@host:5432/resilience_art_warehouse
python -m etl.build_warehouse           # builds the star schema + populates it
uvicorn main:app --reload
```

Without `WAREHOUSE_DATABASE_URL` set, `/api/analytics/*` and
`/api/warehouse/*` return a clear 503 (not fake data), and the Population
Analytics page shows a "Warehouse not connected" state with these same
instructions — I could not provision or test against a live Postgres
instance in the environment I built this in (no network access), so this
is real, complete code that I could not run end-to-end. Please test the
ETL against your actual Supabase/Neon/RDS instance and tell me what
breaks — the highest-risk spots are:
- Column/type mismatches SQLAlchemy surfaces only against a real Postgres
  server (SQLite never validates foreign key types the same way).
- The synthetic augmentation in `etl/build_warehouse.py` (distance,
  income, education, TB screening, mental health flag) — every synthesized
  field is listed in `SYNTHETIC_FIELDS` at the top of that file. Real
  values should replace these as soon as that data exists in the OLTP side.
- `build_intervention_outcomes()` is explicitly illustrative — per your
  own decision, there's no real A/B program yet. The Policy tab says so
  in its `method` field, and the frontend surfaces that note directly.

## Honest scope notes

- This targets **demo scale** (extends the current ~45 seed patients),
  not the research/national scale mentioned as an open question in your
  README — say the word if you want the ETL's synthetic volume bumped up.
- The funding scenario ("what if funding drops 20%?") uses a **stated
  assumption** (proportional procurement cut → higher stockout/default
  rate, lower suppression) via a fixed multiplier, not a measured
  historical elasticity. This is disclosed in the API response's
  `assumption_note` and shown in the UI, not hidden in a tooltip.
- Redistribution recommendations use a **greedy heuristic** (rank-and-pair
  by days-of-stock-remaining), not an LP solve — `network_impact.py`
  already has the PuLP feasibility check for transfer-request-time; this
  is the standing "who should we look at today" list, and a heuristic is
  the right tool for that per your own `kpi_fix.txt` reasoning.

## Running everything

```bash
# OLTP backend (unchanged flow)
cd backend
pip install -r requirements.txt
cp .env.example .env   # ANTHROPIC_API_KEY + optional WAREHOUSE_DATABASE_URL
python seed_data.py
uvicorn main:app --reload

# Frontend
cd smartpharm-frontend
npm install
cp .env.example .env
npm run dev
```

Demo logins: `pharmacist / pharm123`, `admin / admin123`. Demo scan PIN: `1234`.

## Hybrid template/Claude architecture for AI Agent endpoints (latest)

By explicit product decision: every AI Agent endpoint now computes a
complete, correct answer from `narrative_templates.py` FIRST — zero API
calls, zero cost, zero network dependency. If `ANTHROPIC_API_KEY` is
configured and reachable, Claude is asked only to *refine the prose* of
that exact template (never to add new facts); on any failure it silently
falls back to the template. Every response includes `"source": "template"
| "claude"` so the frontend can show which mode produced it — see the
"Computed" / "AI-enhanced" badge on the Strategic Intelligence page and
Reports page.

This exists because of a real incident earlier in this project: an
invalid model string caused every AI call to fail with a 400, and the
whole Strategic Intelligence page went dark. That can no longer happen —
the fix wasn't just correcting the model name, it was removing the
single point of failure entirely. `backend/narrative_templates.py` has
the full rationale and every template function; `backend/routers/
ai_agent.py`'s `generate_narrative()` is the orchestrator.

Free-text chat (`/chat`) is the one place a template can't fully replace
an LLM — it does keyword-based intent matching to the same templates
(ECI, stock, adherence, anomalies, monthly summary) rather than true
open-ended reasoning, with an honest message when a question falls
outside what it can answer without AI configured.
