import hmac
import os
import time
from contextlib import asynccontextmanager
from typing import Literal

import anthropic
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, Field

from app import agent, db, simulator


def fire_cooldown_seconds():
    return float(os.environ.get("FIRE_COOLDOWN_SECONDS", 10))  # keeps a demo crowd from spamming paid model calls


def cors_origins():
    """Origins allowed to call this API, from CORS_ORIGINS (comma-separated). Empty if unset."""
    raw = os.environ.get("CORS_ORIGINS", "")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def write_api_key():
    return os.environ.get("WRITE_API_KEY")


def require_write_key(x_api_key: str | None = Header(default=None)):
    """Guards a write endpoint (ADR-0006): every Candidate can cost a paid model call.

    Deliberately not on /admin/fire or /admin/reset: those are demo controls the public
    dashboard calls straight from the browser (frontend/components/FireControl.tsx), so a
    key there would have to be visible to anyone anyway.
    """
    if not x_api_key or not hmac.compare_digest(x_api_key, write_api_key() or ""):
        raise HTTPException(401, "Missing or invalid API key")


@asynccontextmanager
async def lifespan(app: FastAPI):
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    if not write_api_key():
        raise RuntimeError("WRITE_API_KEY is not set")  # fail closed: never run with writes open (ADR-0006)
    with ConnectionPool(url, open=True) as pool:
        pool.wait()  # fail at startup if the database is down
        db.apply_schema(pool)
        app.state.pool = pool
        app.state.client = anthropic.Anthropic(max_retries=0)  # no retries: a slow model escalates instead
        app.state.fire_cooldown_until = 0.0
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


def _ingest_and_triage(request: Request, background_tasks: BackgroundTasks, appliance_id, watts):
    """Store a Reading and queue triage for any Candidate it raises. Returns the reading id, or
    None for an unknown appliance."""
    stored = db.insert_reading(request.app.state.pool, appliance_id, watts)
    if stored is None:
        return None
    reading_id, candidate_ids = stored
    for candidate_id in candidate_ids:  # runs after the response has gone out
        background_tasks.add_task(agent.triage, request.app.state.pool, request.app.state.client, candidate_id)
    return reading_id


@app.post("/readings", status_code=202, dependencies=[Depends(require_write_key)])
def post_reading(reading: ReadingIn, request: Request, background_tasks: BackgroundTasks):
    reading_id = _ingest_and_triage(request, background_tasks, reading.appliance_id, reading.watts)
    if reading_id is None:
        raise HTTPException(422, f"Unknown appliance '{reading.appliance_id}'")
    return {"id": reading_id}


@app.get("/decisions")
def list_decisions(
    request: Request,
    outcome: Literal["escalated", "resolved", "pending"] | None = None,
    limit: int = 20,
):
    return db.list_decisions(request.app.state.pool, outcome, limit)


@app.post("/admin/fire/{scenario}", status_code=202)
def fire_scenario(scenario: str, request: Request, background_tasks: BackgroundTasks):
    """Demo control (not a general write API): inject one of the simulator's three fixed
    scenarios so a career-fair visitor can watch the agent investigate something they caused.
    """
    if scenario not in simulator.SCENARIOS:
        raise HTTPException(404, f"Unknown scenario '{scenario}'")
    now = time.monotonic()
    if now < request.app.state.fire_cooldown_until:
        raise HTTPException(409, "Already investigating — try again in a moment.")
    # ponytail: time-based only, doesn't track whether the triage actually finished;
    # a real spend cap (#16) is the intended replacement, this is just a stopgap.
    request.app.state.fire_cooldown_until = now + fire_cooldown_seconds()
    for appliance_id, watts in simulator.fire_readings(scenario):
        _ingest_and_triage(request, background_tasks, appliance_id, watts)  # a fixed scenario table is always known
    return {"scenario": scenario}


@app.post("/admin/reset")
def reset_demo(request: Request):
    """Demo control (not a general write API): wipe the log a career-fair visitor left behind
    and replant baseline history, so the rack isn't empty while ambient traffic catches back up.
    """
    db.reset(request.app.state.pool)
    simulator.seed(request.app.state.pool)
    request.app.state.fire_cooldown_until = 0.0
    return {"status": "reset"}


@app.post("/admin/rollup", dependencies=[Depends(require_write_key)])
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
