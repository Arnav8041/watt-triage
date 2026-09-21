"""All SQL lives here as literal strings. No ORM (ADR-0002)."""
from pathlib import Path

SCHEMA = (Path(__file__).parent / "schema.sql").read_text()


def apply_schema(pool):
    with pool.connection() as conn:
        conn.execute(SCHEMA)


def insert_reading(pool, appliance_id, watts):
    """Store a Reading. Returns its id, or None if the Appliance doesn't exist."""
    with pool.connection() as conn:
        row = conn.execute(
            "INSERT INTO reading (appliance_id, watts) "
            "SELECT id, %s FROM appliance WHERE id = %s "
            "RETURNING id",
            (watts, appliance_id),
        ).fetchone()
    return row[0] if row else None
