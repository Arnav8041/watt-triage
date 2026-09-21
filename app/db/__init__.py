"""All SQL lives here as literal strings. No ORM (ADR-0002)."""
from pathlib import Path

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
    return row[0] if row else None
