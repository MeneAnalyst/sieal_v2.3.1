import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, SQLALCHEMY_DATABASE_URL
import models

# ── Startup visibility for the exact bug class that's easiest to ship
# silently: DATABASE_URL not reaching the process, so the app quietly
# runs against local SQLite instead of the real Postgres/Supabase DB.
# This turns that into a 5-second glance at the deploy log instead of a
# forensic debugging session. Printed BEFORE create_all() below, so it's
# visible even if the actual connection attempt then fails/hangs.
_is_sqlite = SQLALCHEMY_DATABASE_URL.startswith("sqlite")
_db_kind = "SQLite (local file)" if _is_sqlite else "Postgres (remote)"
# Mask credentials before logging — never print a connection string with
# a password in it, even to your own log output.
_db_display = SQLALCHEMY_DATABASE_URL if _is_sqlite else SQLALCHEMY_DATABASE_URL.split("@")[-1]
print(f"[SIEAL] Database: {_db_kind} — {_db_display}", file=sys.stderr)
if os.environ.get("RENDER") and _is_sqlite:
    print(
        "[SIEAL] WARNING: running on Render but connected to local SQLite — "
        "DATABASE_URL is probably not set correctly in the Render dashboard. "
        "Data will NOT persist across restarts and will NOT match Supabase.",
        file=sys.stderr,
    )

models.Base.metadata.create_all(bind=engine)

from routers import (drugs, stock, clients, appointments, dispense, exports,
                     forecast, dashboard, network, auth, patients, ehr, reports, ai_agent, kpi,
                     analytics, warehouse_admin, notices)

app = FastAPI(
    title="SIEAL — Strategic Intelligence Evaluation Accelerate Learning",
    description="Cimas Healthathon 3.0 | Tapfi Technologies",
    version="2.0.0",
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(auth.router,        prefix="/api/auth",         tags=["Auth"])
app.include_router(drugs.router,       prefix="/api/drugs",        tags=["Drugs"])
app.include_router(stock.router,       prefix="/api/stock",        tags=["Stock"])
app.include_router(clients.router,     prefix="/api/clients",      tags=["Clients (legacy)"])
app.include_router(patients.router,    prefix="/api/patients",     tags=["Patients"])
app.include_router(appointments.router,prefix="/api/appointments", tags=["Appointments"])
app.include_router(dispense.router,    prefix="/api/dispense",     tags=["Dispense"])
app.include_router(exports.router,     prefix="/api/export",       tags=["Export"])
app.include_router(kpi.router,         prefix="/api/kpi",          tags=["KPI Engine"])
app.include_router(analytics.router,   prefix="/api/analytics",    tags=["Population Analytics (Warehouse)"])
app.include_router(warehouse_admin.router, prefix="/api/warehouse", tags=["Warehouse Admin"])
app.include_router(forecast.router,    prefix="/api/forecast",     tags=["Forecast"])
app.include_router(dashboard.router,   prefix="/api/dashboard",    tags=["Dashboard"])
app.include_router(network.router,     prefix="/api/network",      tags=["Network"])
app.include_router(ehr.router,         prefix="/api/ehr",          tags=["EHR Import"])
app.include_router(reports.router,     prefix="/api/reports",      tags=["Reports & Export"])
app.include_router(notices.router,     prefix="/api/notices",       tags=["Notice Board"])
app.include_router(ai_agent.router,    prefix="/api/ai",           tags=["AI Agent"])
# Section 3: the React frontend's proxy calls live under /api/ai_agent/chat —
# same router, mounted a second time so both the legacy and new UI work.
app.include_router(ai_agent.router,    prefix="/api/ai_agent",     tags=["AI Agent (RESILIENCE-ART)"])

@app.get("/", tags=["Health"])
def root():
    return {"app": "SIEAL v2.0", "status": "running", "docs": "/docs"}
