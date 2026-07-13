from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

from warehouse_database import warehouse_configured
from routers.auth import current_user

router = APIRouter()


@router.post("/refresh")
def refresh_warehouse(background_tasks: BackgroundTasks, session: dict = Depends(current_user)):
    """
    Triggers etl/build_warehouse.py's run() in the background. A nice-to-have
    per the architecture doc, so a refresh doesn't require shelling into the
    server to run the CLI script.
    """
    if not warehouse_configured():
        raise HTTPException(503, "WAREHOUSE_DATABASE_URL not set — nothing to refresh.")
    from etl.build_warehouse import run as run_etl
    background_tasks.add_task(run_etl)
    return {"message": "Warehouse refresh started in the background. Poll /api/analytics/* shortly for updated data."}


@router.get("/status")
def warehouse_status(session: dict = Depends(current_user)):
    return {"configured": warehouse_configured()}
