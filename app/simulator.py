"""Demo data generator for a career-fair table, not the API (ADR-0006). Four commands.

reset and seed talk to the database directly. ambient and fire go over HTTP instead, so a
Reading runs through the real detector and agent, exactly like a real appliance would.
"""
import argparse
import os
import random
import time

from psycopg_pool import ConnectionPool

from app import db, detector

SEED_HOURS = 2
SEED_INTERVAL_SECONDS = 5
AMBIENT_INTERVAL_SECONDS = 5
FRIDGE_RUNNING_WATTS = 150
FRIDGE_CYCLE_TICKS = 12  # ~1 minute running, ~1 minute idle, at the ambient interval

# mean, stddev per Appliance: everyday noise around a normal draw
BASELINE = {
    "fridge": (40, 4),
    "water_heater": (30, 4),
    "space_heater": (1450, 20),
    "washer": (480, 22),
    "ac_unit": (900, 31),
}

# appliance_id, peak watts, trigger it should raise. Numbers checked against detector.py and gate.py.
SCENARIOS = {
    "heater-breach": ("space_heater", 3180, "rated_breach"),
    "washer-spin": ("washer", 850, "statistical"),
    "ac-surge": ("ac_unit", 2900, "statistical"),
}


def seed(pool):
    """Write ~2h of realistic per-Appliance history, directly via SQL. Fixed seed: same numbers every run."""
    rng = random.Random(0)
    count = SEED_HOURS * 3600 // SEED_INTERVAL_SECONDS
    for appliance_id, (mean, stddev) in BASELINE.items():
        watts = [max(0.0, rng.gauss(mean, stddev)) for _ in range(count)]
        db.seed_readings(pool, appliance_id, watts, interval_seconds=SEED_INTERVAL_SECONDS)


def fire_readings(scenario):
    """The Readings to post for a scenario, oldest first. A rated_breach needs one; a statistical
    Candidate needs `detector.persistence()` in a row, all abnormal."""
    appliance_id, watts, trigger = SCENARIOS[scenario]
    times = 1 if trigger == "rated_breach" else detector.persistence()
    return [(appliance_id, watts)] * times


def fire(base_url, scenario):
    for appliance_id, watts in fire_readings(scenario):
        _post(base_url, appliance_id, watts)


def ambient_tick(tick, rng):
    """The Readings to post for one ambient tick: one per Appliance. Every FRIDGE_CYCLE_TICKS
    ticks the fridge flips between idle and running, its normal compressor cycle."""
    fridge_running = (tick // FRIDGE_CYCLE_TICKS) % 2 == 1
    readings = []
    for appliance_id, (mean, stddev) in BASELINE.items():
        if appliance_id == "fridge" and fridge_running:
            mean = FRIDGE_RUNNING_WATTS
        readings.append((appliance_id, max(0.0, rng.gauss(mean, stddev))))
    return readings


def ambient(base_url, ticks=None, interval=AMBIENT_INTERVAL_SECONDS):
    """Post ~one Reading per Appliance every `interval` seconds, forever unless `ticks` is given."""
    rng = random.Random()  # real randomness: this is traffic, not a fixture
    tick = 0
    while ticks is None or tick < ticks:
        for appliance_id, watts in ambient_tick(tick, rng):
            _post(base_url, appliance_id, watts)
        tick += 1
        if ticks is None or tick < ticks:
            time.sleep(interval)


def _post(base_url, appliance_id, watts):
    import httpx2  # dev-only dependency; only the standalone CLI paths (fire, ambient) need it

    response = httpx2.post(
        f"{base_url}/readings",
        json={"appliance_id": appliance_id, "watts": watts},
        headers={"X-API-Key": os.environ["WRITE_API_KEY"]},
    )
    response.raise_for_status()


def main():
    parser = argparse.ArgumentParser(description="WattTriage demo data generator")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("reset", help="wipe Readings, Candidates and Decisions")
    sub.add_parser("seed", help="write ~2h of baseline history for every Appliance")
    ambient_cmd = sub.add_parser("ambient", help="post normal traffic forever, over HTTP")
    ambient_cmd.add_argument("--ticks", type=int, default=None, help="stop after N ticks instead of forever")
    fire_cmd = sub.add_parser("fire", help="inject a named fault, over HTTP")
    fire_cmd.add_argument("scenario", choices=sorted(SCENARIOS))
    args = parser.parse_args()

    if args.command in ("reset", "seed"):
        with ConnectionPool(os.environ["DATABASE_URL"], open=True) as pool:
            pool.wait()
            db.apply_schema(pool)  # safe to run twice, and makes this usable standalone
            if args.command == "reset":
                db.reset(pool)
            else:
                seed(pool)
    else:
        base_url = os.environ.get("SIMULATOR_API_URL", "http://localhost:8000")
        if args.command == "ambient":
            ambient(base_url, ticks=args.ticks)
        else:
            fire(base_url, args.scenario)


if __name__ == "__main__":
    main()
