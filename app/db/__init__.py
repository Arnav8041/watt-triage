"""All SQL lives here as literal strings. No ORM (ADR-0002)."""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app import detector

SCHEMA = (Path(__file__).parent / "schema.sql").read_text()


def apply_schema(pool):
    with pool.connection() as conn:
        conn.execute(SCHEMA)


def insert_reading(pool, appliance_id, watts):
    """Store a Reading. Returns (reading_id, new Candidate ids), or None for an unknown Appliance.

    Over rated_watts it also records a rated_breach Candidate, in the same statement.
    """
    with pool.connection() as conn:
        row = conn.execute(
            "WITH r AS ("
            "  INSERT INTO reading (appliance_id, watts) "
            "  SELECT id, %s FROM appliance WHERE id = %s "
            "  RETURNING id, appliance_id, watts"
            "), c AS ("
            "  INSERT INTO anomaly_candidate (appliance_id, watts, trigger) "
            "  SELECT r.appliance_id, r.watts, 'rated_breach' "
            "  FROM r JOIN appliance a ON a.id = r.appliance_id "
            "  WHERE r.watts > a.rated_watts "
            "  RETURNING id"
            ") SELECT r.id, c.id FROM r LEFT JOIN c ON true",
            (watts, appliance_id),
        ).fetchone()
    if row is None:
        return None
    reading_id, breach_id = row
    # separate transaction, so a bug in the statistical part can't lose the reading or a breach
    with pool.connection() as conn:
        statistical_id = _raise_statistical_candidate(conn, appliance_id)
    return reading_id, [i for i in (breach_id, statistical_id) if i is not None]


def _raise_statistical_candidate(conn, appliance_id):
    """Raise a statistical Candidate if the newest Readings look abnormal (detector.py). Returns its id.

    Skips if one is already pending, unless it's older than twice the agent timeout.
    """
    # lock per appliance so two readings at once can't both raise
    conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (appliance_id,))
    stale_after = 2 * float(os.environ.get("AGENT_TIMEOUT_SECONDS", 30))
    if conn.execute(
        "SELECT 1 FROM anomaly_candidate "
        "WHERE appliance_id = %s AND trigger = 'statistical' AND status = 'pending' "
        "AND detected_at > now() - make_interval(secs => %s)",
        (appliance_id, stale_after),
    ).fetchone():
        return None
    watts = [
        r[0]
        for r in conn.execute(
            "SELECT watts FROM reading WHERE appliance_id = %s "
            "ORDER BY recorded_at DESC, id DESC LIMIT %s",
            (appliance_id, detector.window() + detector.persistence()),
        )
    ]
    flagged = detector.check(watts)
    if flagged:
        z, mean, stddev, size = flagged
        return conn.execute(
            "INSERT INTO anomaly_candidate "
            "(appliance_id, watts, trigger, z_score, baseline_size, baseline_mean, baseline_stddev) "
            "VALUES (%s, %s, 'statistical', %s, %s, %s, %s) RETURNING id",
            (appliance_id, watts[0], z, size, mean, stddev),
        ).fetchone()[0]


def seed_readings(pool, appliance_id, watts, interval_seconds=5):
    """Plant past readings for one Appliance. Oldest first, ending one interval ago. Skips the detector."""
    now = datetime.now(timezone.utc)
    rows = [
        (appliance_id, w, now - timedelta(seconds=interval_seconds * (len(watts) - i)))
        for i, w in enumerate(watts)
    ]
    with pool.connection() as conn:
        conn.cursor().executemany(
            "INSERT INTO reading (appliance_id, watts, recorded_at) VALUES (%s, %s, %s)", rows
        )


def get_candidate(pool, candidate_id):
    """One Candidate as a dict, or None. detected_at is text so it fits in JSON."""
    with pool.connection() as conn:
        return conn.cursor(row_factory=dict_row).execute(
            "SELECT id, appliance_id, watts, trigger, z_score, baseline_size, baseline_mean, "
            "baseline_stddev, detected_at::text AS detected_at FROM anomaly_candidate WHERE id = %s",
            (candidate_id,),
        ).fetchone()


def get_appliance(pool, appliance_id):
    """An Appliance as a dict, or None."""
    with pool.connection() as conn:
        return conn.cursor(row_factory=dict_row).execute(
            "SELECT id, name, location, rated_watts FROM appliance WHERE id = %s", (appliance_id,)
        ).fetchone()


def insert_decision(pool, candidate_id, outcome, confidence, gate_reason, reasoning, evidence, tool_trace, model, latency_ms):
    """Save the Triage Decision and mark the Candidate decided, in one transaction."""
    with pool.connection() as conn:
        conn.execute(
            "INSERT INTO triage_decision (candidate_id, outcome, confidence, gate_reason, reasoning, "
            "evidence, tool_trace, model, latency_ms) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (candidate_id, outcome, confidence, gate_reason, reasoning, Jsonb(evidence), Jsonb(tool_trace), model, latency_ms),
        )
        conn.execute("UPDATE anomaly_candidate SET status = 'decided' WHERE id = %s", (candidate_id,))
