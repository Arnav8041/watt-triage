"""All SQL lives here as literal strings. No ORM (ADR-0002)."""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app import detector

SCHEMA = (Path(__file__).parent / "schema.sql").read_text()


def apply_schema(pool):
    with pool.connection() as conn:
        conn.execute(SCHEMA)


def insert_reading(pool, appliance_id, watts):
    """Store a Reading. Returns its id, or None if the Appliance doesn't exist.

    If watts is over the Appliance's rated_watts, it also records a rated_breach Candidate.
    One statement, so both rows save or neither does. Postgres runs an INSERT inside WITH
    even if nothing reads it, which is why `c` is never used.
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
            "  WHERE r.watts > a.rated_watts"
            ") SELECT id FROM r",
            (watts, appliance_id),
        ).fetchone()
    if row is None:
        return None
    # separate transaction, so a bug in the statistical part can't lose the reading or a breach
    with pool.connection() as conn:
        _raise_statistical_candidate(conn, appliance_id)
    return row[0]


def _raise_statistical_candidate(conn, appliance_id):
    """Raise a statistical Candidate if the newest Readings look abnormal (see detector.py).

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
        return
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
        conn.execute(
            "INSERT INTO anomaly_candidate "
            "(appliance_id, watts, trigger, z_score, baseline_size, baseline_mean, baseline_stddev) "
            "VALUES (%s, %s, 'statistical', %s, %s, %s, %s)",
            (appliance_id, watts[0], z, size, mean, stddev),
        )


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
