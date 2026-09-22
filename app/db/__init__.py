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


def reset(pool):
    """Wipe Readings, Candidates and Decisions for the simulator. Appliances are left alone."""
    with pool.connection() as conn:
        conn.execute("TRUNCATE reading, anomaly_candidate, rollup CASCADE")  # cascades to triage_decision


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


def configured_retention_hours():
    """Hours of raw Readings to keep, from RETENTION_HOURS."""
    hours = float(os.environ.get("RETENTION_HOURS", 24))
    if not 0 <= hours < float("inf"):  # a negative value would delete the current hour; nan fails this too
        raise ValueError("RETENTION_HOURS must be 0 or more")
    return hours


def rollup_old_readings(pool, retention_hours):
    """Turn old Readings into hourly Rollup rows and delete them. Returns (rows written, Readings deleted).

    One statement, so it's all or nothing, and the DELETE feeds the summary, so nothing is deleted uncounted.
    Decisions keep their own evidence (ADR-0004), so the DELETE needs no exceptions.
    """
    with pool.connection() as conn:
        summaries = conn.execute(
            # Cutoff rounds down to a whole UTC hour, so only full hours get summarised.
            "WITH old AS ("
            "  DELETE FROM reading WHERE recorded_at < date_trunc('hour', now() - %s * interval '1 hour', 'UTC') "
            "  RETURNING appliance_id, watts, recorded_at"
            ") "
            "INSERT INTO rollup (appliance_id, hour, min_watts, max_watts, avg_watts, sample_count) "
            "SELECT appliance_id, date_trunc('hour', recorded_at, 'UTC'), min(watts), max(watts), avg(watts), count(*) "
            "FROM old GROUP BY appliance_id, date_trunc('hour', recorded_at, 'UTC') "
            # ponytail: overwrites, so a late Reading for a summarised hour would replace its numbers. Merge counts then.
            "ON CONFLICT (appliance_id, hour) DO UPDATE SET min_watts = EXCLUDED.min_watts, "
            "max_watts = EXCLUDED.max_watts, avg_watts = EXCLUDED.avg_watts, sample_count = EXCLUDED.sample_count "
            "RETURNING sample_count",
            (retention_hours,),
        ).fetchall()
    return len(summaries), sum(count for (count,) in summaries)


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


def get_recent_readings(pool, appliance_id, minutes, around):
    """Readings up to `minutes` (max 60) either side of `around`, oldest first. Empty list if none.

    Pass the Candidate's detected_at as `around`, so a late triage still sees the event.
    """
    minutes = min(minutes, 60)  # the model chooses this, so cap it
    with pool.connection() as conn:
        return conn.cursor(row_factory=dict_row).execute(
            "SELECT watts, recorded_at::text AS recorded_at FROM reading "
            "WHERE appliance_id = %s "
            "AND recorded_at BETWEEN %s::timestamptz - make_interval(mins => %s) "
            "AND %s::timestamptz + make_interval(mins => %s) "
            "ORDER BY recorded_at, id",
            (appliance_id, around, minutes, around, minutes),
        ).fetchall()


def get_hourly_history(pool, appliance_id, hours, around):
    """Rollup rows for the `hours` (max 168) up to `around`, oldest first. Empty list if none.

    Pass the Candidate's detected_at as `around`, same as get_recent_readings.
    """
    hours = min(hours, 168)  # the model chooses this, so cap it at a week
    with pool.connection() as conn:
        return conn.cursor(row_factory=dict_row).execute(
            "SELECT hour::text AS hour, min_watts, max_watts, avg_watts, sample_count FROM rollup "
            "WHERE appliance_id = %s "
            "AND hour BETWEEN %s::timestamptz - make_interval(hours => %s) AND %s::timestamptz "
            "ORDER BY hour",
            (appliance_id, around, hours, around),
        ).fetchall()


def get_recent_decisions(pool, appliance_id, limit):
    """The last few (max 10) Triage Decisions for an Appliance, newest first."""
    limit = max(1, min(limit, 10))  # model-chosen too, and Postgres errors on a negative LIMIT
    with pool.connection() as conn:
        return conn.cursor(row_factory=dict_row).execute(
            "SELECT d.outcome, d.confidence, d.reasoning, d.gate_reason, c.trigger, c.watts, "
            "d.decided_at::text AS decided_at "
            "FROM triage_decision d JOIN anomaly_candidate c ON c.id = d.candidate_id "
            "WHERE c.appliance_id = %s ORDER BY d.decided_at DESC, d.id DESC LIMIT %s",
            (appliance_id, limit),
        ).fetchall()


def has_unacknowledged_escalation(pool, appliance_id, within_hours):
    """True if this Appliance has an unacknowledged Escalation from the last `within_hours`."""
    with pool.connection() as conn:
        return conn.execute(
            "SELECT EXISTS (SELECT 1 FROM triage_decision d JOIN anomaly_candidate c ON c.id = d.candidate_id "
            "WHERE c.appliance_id = %s AND d.outcome = 'escalated' AND d.acknowledged_at IS NULL "
            "AND d.decided_at > now() - %s * interval '1 hour')",
            (appliance_id, within_hours),
        ).fetchone()[0]


def acknowledge_decision(pool, decision_id):
    """Mark an Escalation acknowledged. Returns (outcome, acknowledged_at), or None if there's no such decision.

    A second call keeps the first time. A Quiet Resolution is left alone.
    """
    with pool.connection() as conn:
        row = conn.execute(
            "UPDATE triage_decision SET acknowledged_at = COALESCE(acknowledged_at, now()) "
            "WHERE id = %s AND outcome = 'escalated' RETURNING outcome, acknowledged_at",
            (decision_id,),
        ).fetchone()
        if row:
            return row
        return conn.execute(  # not updated: missing, or not an Escalation
            "SELECT outcome, acknowledged_at FROM triage_decision WHERE id = %s", (decision_id,)
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
