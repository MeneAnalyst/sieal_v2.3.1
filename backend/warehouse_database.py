"""
warehouse_database.py — connection layer for the analytical data warehouse.

Deliberately separate from database.py (the OLTP SQLite connection). The
warehouse is a different database, on a different engine (Postgres), reached
over the network rather than a local file — mixing that into database.py
would make the OLTP path silently depend on warehouse availability, which
is exactly the coupling the ETL-based design in the architecture doc is
meant to avoid.

Set WAREHOUSE_DATABASE_URL in backend/.env, e.g. a Supabase/Neon/RDS
connection string:
    WAREHOUSE_DATABASE_URL=postgresql://user:password@host:5432/resilience_art_warehouse

If it isn't set, warehouse-dependent endpoints return a clear 503 rather
than silently falling back to something that looks like real data.
"""
import os
import pathlib
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError

_env = pathlib.Path(__file__).parent / "ak.env"
if _env.exists():
    for _line in _env.read_text().splitlines():
        if "=" in _line and not _line.strip().startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

WAREHOUSE_DATABASE_URL: Optional[str] = os.environ.get("WAREHOUSE_DATABASE_URL")

WarehouseBase = declarative_base()

_engine = None
_SessionLocal = None

if WAREHOUSE_DATABASE_URL:
    _engine = create_engine(WAREHOUSE_DATABASE_URL, pool_pre_ping=True)
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def warehouse_configured() -> bool:
    return _engine is not None


def get_warehouse_db():
    """
    FastAPI dependency. Raises a clear, honest error rather than falling
    back to SQLite or returning empty-but-200 responses — a warehouse
    endpoint that silently has no data is worse than one that says so.
    """
    from fastapi import HTTPException

    if _SessionLocal is None:
        raise HTTPException(
            503,
            "Warehouse not configured. Set WAREHOUSE_DATABASE_URL in backend/.env "
            "to a Postgres connection string (Supabase/Neon/RDS), then run "
            "`python -m etl.build_warehouse` to populate it.",
        )
    db = _SessionLocal()
    try:
        yield db
    except OperationalError as e:
        raise HTTPException(503, f"Could not reach the warehouse database: {e}")
    finally:
        db.close()
