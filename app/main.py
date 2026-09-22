import os
from contextlib import asynccontextmanager
from typing import Literal

import anthropic
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, Field

from app import agent, db


def cors_origins():
    """Origins allowed to call this API, from CORS_ORIGINS (comma-separated). Empty if unset."""
    raw = os.environ.get("CORS_ORIGINS", "")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    with ConnectionPool(url, open=True) as pool:
        pool.wait()  # fail at startup if the database is down
        db.apply_schema(pool)
        app.state.pool = pool
        app.state.client = anthropic.Anthropic(max_retries=0)  # no retries: a slow model escalates instead
        yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=cors_origins(), allow_methods=["GET", "POST"], allow_headers=["*"]
)


@app.exception_handler(RequestValidationError)
async def reject_bad_input(request: Request, exc: RequestValidationError):
    # The default 422 echoes the bad value back, and inf/nan can't be encoded.
    errors = [{"loc": e["loc"], "msg": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


class ReadingIn(BaseModel):
    appliance_id: str
    watts: float = Field(ge=0, allow_inf_nan=False)  # negative or infinite: 422


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/appliances")
def list_appliances(request: Request):
    return db.list_appliances(request.app.state.pool)


@app.get("/appliances/{appliance_id}/readings")
def appliance_readings(appliance_id: str, request: Request, minutes: int = Query(30, ge=1)):
    if db.get_appliance(request.app.state.pool, appliance_id) is None:
        raise HTTPException(404, f"Unknown appliance '{appliance_id}'")
    return db.get_readings_since(request.app.state.pool, appliance_id, minutes)


@app.post("/readings", status_code=202)
def post_reading(reading: ReadingIn, request: Request, background_tasks: BackgroundTasks):
    stored = db.insert_reading(request.app.state.pool, reading.appliance_id, reading.watts)
    if stored is None:
        raise HTTPException(422, f"Unknown appliance '{reading.appliance_id}'")
    reading_id, candidate_ids = stored
    for candidate_id in candidate_ids:  # runs after the 202 has gone out
        background_tasks.add_task(agent.triage, request.app.state.pool, request.app.state.client, candidate_id)
    return {"id": reading_id}


@app.get("/decisions")
def list_decisions(
    request: Request,
    outcome: Literal["escalated", "resolved", "pending"] | None = None,
    limit: int = 20,
):
    return db.list_decisions(request.app.state.pool, outcome, limit)


@app.post("/admin/rollup")
def rollup(request: Request):
    # No scheduler in v1 (ADR-0006): call this by hand, or from cron.
    rows_written, deleted = db.rollup_old_readings(request.app.state.pool, db.configured_retention_hours())
    return {"rollup_rows": rows_written, "readings_deleted": deleted}


@app.post("/decisions/{decision_id}/acknowledge")
def acknowledge(decision_id: int, request: Request):
    found = db.acknowledge_decision(request.app.state.pool, decision_id)
    if found is None:
        raise HTTPException(404, f"No decision {decision_id}")
    outcome, acknowledged_at = found
    if outcome != "escalated":
        raise HTTPException(409, "Only an Escalation can be acknowledged, not a Quiet Resolution")
    return {"id": decision_id, "acknowledged_at": acknowledged_at}
