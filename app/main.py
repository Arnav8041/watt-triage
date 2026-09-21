import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, Field

from app import db


@asynccontextmanager
async def lifespan(app: FastAPI):
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    with ConnectionPool(url, open=True) as pool:
        pool.wait()  # fail at startup if the database is down
        db.apply_schema(pool)
        app.state.pool = pool
        yield


app = FastAPI(lifespan=lifespan)


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


@app.post("/readings", status_code=202)
def post_reading(reading: ReadingIn, request: Request):
    reading_id = db.insert_reading(request.app.state.pool, reading.appliance_id, reading.watts)
    if reading_id is None:
        raise HTTPException(422, f"Unknown appliance '{reading.appliance_id}'")
    return {"id": reading_id}
