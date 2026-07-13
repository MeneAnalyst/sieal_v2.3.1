# SIEAL — What Changed Before This Deploy

Applied every fix from the runbook (they'd reverted in this fresh export,
since it was built from an earlier snapshot) + the rename to SIEAL, then
verified both halves actually build and run — not just edited blind.

## Runbook fixes re-applied (see DEPLOYMENT_RUNBOOK.md for full context on each)

1. `smartpharm-frontend/package.json` — build script flipped to
   `"vite build && tsc -b"` (was reverted to the broken order)
2. `smartpharm-frontend/src/lib/api.ts` — `patientStats()` type updated to
   include `credible_interval_95` and `method`
3. `smartpharm-frontend/src/components/appointments/DefaulterManagement.tsx`
   — removed unused `CardHeader`, `CardTitle` imports (confirmed unused in
   this version too before removing — it's grown since the last check)
4. `smartpharm-frontend/src/vite-env.d.ts` — added (was missing)
5. `backend/.python-version` — added, pinned to `3.11.11`
6. `backend/database.py` — restored the `os.environ.get("DATABASE_URL", ...)`
   version (was reverted to hardcoded SQLite)

**Not touched — already correct in this version:**
- `main.py` CORS is `allow_origins=["*"]`, not the specific hardcoded list
  that caused the earlier "Disallowed CORS origin" bug. Since this app's
  `fetch()` calls don't use `credentials: 'include'` (confirmed by
  grepping `api.ts`), the wildcard-plus-credentials browser restriction
  doesn't apply here — `"*"` will work correctly as-is.
- `backend/warehouse_database.py` already reads `WAREHOUSE_DATABASE_URL`
  from env correctly and fails honest (503) when unset — no fix needed,
  this was built right the first time.

## Rebrand: SmartPharm → SIEAL

Every user-facing and doc occurrence renamed (verified zero `SmartPharm`
strings remain anywhere in `.py`/`.tsx`/`.ts`/`.html`/`.md`/`.json` files):

- Browser tab title, login screen, sidebar, header, help page
- FastAPI app title + `/` health check response
- All 7 export document headers (CSV/TXT/XLSX/DOCX/PDF)
- Both README files
- `package.json` name field → `sieal-frontend`

**Deliberately NOT renamed — flagging this as a decision for you:**
The physical folder names (`smartpharm-frontend/`, and the GitHub repo name
`siel-react` itself) are unchanged. Renaming those would require updating
your Render "Root Directory" and Vercel "Root Directory" settings to match,
and rewriting git history references — a bigger, riskier change than
renaming display text. If you want the actual folder/repo renamed too, say
so explicitly and I'll walk through it (including updating `render.yaml`/
`netlify.toml`'s `rootDir`/`base` paths to match) — safer to do that as a
deliberate separate step than bundle it into tonight's deploy.

## What's new in this version (from MIGRATION_README.md, for your awareness)

- **Strategic Intelligence** (renamed from "AI Agent") — now
  template-first: every response is computed from real data with zero API
  calls by default, Claude only refines prose if configured, with a
  visible "Computed" / "AI-enhanced" badge. Verified this works with no
  `ANTHROPIC_API_KEY` set — returns a real, correctly-computed report.
- **Defaulter Management** — logistic regression risk scoring, deliberately
  scoped (not xgboost/SHAP), with an honest small-sample caveat.
- **Population Analytics** — 5-tab warehouse view, needs a **separate**
  `WAREHOUSE_DATABASE_URL` (different from your existing Supabase
  `DATABASE_URL`). Verified it returns a clean 503 with setup instructions
  when unset, rather than fake data or a crash.

## Verified end-to-end before packaging

- Backend: installed deps, seeded fresh, started with uvicorn, logged in,
  hit `/api/dashboard/summary` (200), `/api/kpi/dashboard` (200),
  `/api/analytics/failure-risk` (correct 503, warehouse unconfigured),
  `/api/warehouse/refresh` (correct 503), `/api/ai/generate-report`
  (real computed template report, `"source": "template"`)
- Frontend: `npm install && npm run build` — clean, zero TypeScript errors,
  `dist/index.html` confirmed carrying the new SIEAL title

## Still on you before/after this deploy

- Decide whether `WAREHOUSE_DATABASE_URL` gets set this round (Population
  Analytics tab) or stays disabled for now — either is fine, it degrades
  honestly either way
- If deploying to the *same* Render/Vercel projects as before: update the
  `DATABASE_URL` and `ANTHROPIC_API_KEY` env vars are still correct there
  (they should carry over, but confirm)
- Same CORS note as always — if your frontend domain changes, update
  `allow_origins` in `main.py` (currently `["*"]`, which covers any domain
  automatically, so this is only relevant if you tighten it later)
