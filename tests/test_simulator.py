import random

import pytest

from app import agent, db, detector, simulator
from app.agent import triage as real_triage
from app.main import app
from tests.fakes import ScriptedClient, submit
from tests.test_acknowledge import make_decision


def counts():
    with app.state.pool.connection() as conn:
        return {
            table: conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("reading", "anomaly_candidate", "triage_decision", "appliance")
        }


def readings_for(appliance_id):
    with app.state.pool.connection() as conn:
        return [
            watts
            for (watts,) in conn.execute(
                "SELECT watts FROM reading WHERE appliance_id = %s ORDER BY recorded_at, id", (appliance_id,)
            )
        ]


def candidates_for(appliance_id):
    with app.state.pool.connection() as conn:
        return conn.execute(
            "SELECT trigger FROM anomaly_candidate WHERE appliance_id = %s", (appliance_id,)
        ).fetchall()


def decision_for(appliance_id):
    with app.state.pool.connection() as conn:
        return conn.execute(
            "SELECT outcome, gate_reason FROM triage_decision d "
            "JOIN anomaly_candidate c ON c.id = d.candidate_id "
            "WHERE c.appliance_id = %s ORDER BY d.id DESC LIMIT 1",
            (appliance_id,),
        ).fetchone()


def fire_through(client, scenario):
    for appliance_id, watts in simulator.fire_readings(scenario):
        response = client.post("/readings", json={"appliance_id": appliance_id, "watts": watts})
        assert response.status_code == 202


def test_reset_clears_readings_candidates_and_decisions_but_not_appliances(client):
    make_decision()  # a Decision, which also plants a Candidate
    db.seed_readings(app.state.pool, "fridge", [100, 110])

    db.reset(app.state.pool)

    assert counts() == {"reading": 0, "anomaly_candidate": 0, "triage_decision": 0, "appliance": 5}


def test_seed_writes_roughly_two_hours_for_every_appliance(client):
    simulator.seed(app.state.pool)

    expected = simulator.SEED_HOURS * 3600 // simulator.SEED_INTERVAL_SECONDS
    for appliance_id in simulator.BASELINE:
        assert len(readings_for(appliance_id)) == expected


def test_seed_clears_the_minimum_baseline_veto(client):
    simulator.seed(app.state.pool)

    for appliance_id in simulator.BASELINE:
        assert len(readings_for(appliance_id)) >= detector.window() + detector.persistence()


def test_seed_is_deterministic(client):
    simulator.seed(app.state.pool)
    first_run = readings_for("washer")

    db.reset(app.state.pool)
    simulator.seed(app.state.pool)

    assert readings_for("washer") == first_run


@pytest.mark.parametrize(
    "scenario, appliance_id, watts, times",
    [
        ("heater-breach", "space_heater", 3180, 1),
        ("washer-spin", "washer", 850, detector.persistence()),
        ("ac-surge", "ac_unit", 2900, detector.persistence()),
    ],
)
def test_fire_readings_matches_the_scenario_table(scenario, appliance_id, watts, times):
    assert simulator.fire_readings(scenario) == [(appliance_id, watts)] * times


def test_ambient_tick_keeps_non_fridge_appliances_close_to_their_baseline():
    rng = random.Random(1)
    for tick in range(30):
        readings = dict(simulator.ambient_tick(tick, rng))
        for appliance_id, (mean, stddev) in simulator.BASELINE.items():
            if appliance_id != "fridge":
                assert abs(readings[appliance_id] - mean) < 6 * stddev  # no wild outliers


def test_ambient_tick_cycles_the_fridge_between_idle_and_running():
    rng = random.Random(1)
    idle_mean, _ = simulator.BASELINE["fridge"]

    idle = dict(simulator.ambient_tick(0, rng))["fridge"]
    running = dict(simulator.ambient_tick(simulator.FRIDGE_CYCLE_TICKS, rng))["fridge"]

    assert abs(idle - idle_mean) < 20
    assert abs(running - simulator.FRIDGE_RUNNING_WATTS) < 20


def test_ambient_raises_no_candidates_except_the_fridges_duty_cycle(client):
    simulator.seed(app.state.pool)
    rng = random.Random(1)
    ticks = simulator.FRIDGE_CYCLE_TICKS * 2 + detector.persistence()  # a full idle-run-idle cycle, plus margin

    for tick in range(ticks):
        for appliance_id, watts in simulator.ambient_tick(tick, rng):
            response = client.post("/readings", json={"appliance_id": appliance_id, "watts": watts})
            assert response.status_code == 202

    for appliance_id in simulator.BASELINE:
        if appliance_id != "fridge":
            assert candidates_for(appliance_id) == []
    fridge_candidates = candidates_for("fridge")
    assert fridge_candidates  # the compressor starting up did raise something
    assert all(trigger == "statistical" for (trigger,) in fridge_candidates)


# the three fixed scenarios, end to end through the real gate (ADR-0006)

def test_heater_breach_escalates_no_matter_what_the_agent_says(client, monkeypatch):
    monkeypatch.setattr(agent, "triage", real_triage)
    simulator.seed(app.state.pool)
    app.state.client = ScriptedClient([submit("resolve_quietly", "certain", "Just warming up.")])

    fire_through(client, "heater-breach")

    outcome, gate_reason = decision_for("space_heater")
    assert outcome == "escalated"
    assert "rated breach" in gate_reason


def test_washer_spin_resolves_quietly_when_every_veto_passes(client, monkeypatch):
    monkeypatch.setattr(agent, "triage", real_triage)
    simulator.seed(app.state.pool)
    app.state.client = ScriptedClient([submit("resolve_quietly", "certain")])

    fire_through(client, "washer-spin")

    assert decision_for("washer") == ("resolved", "all checks passed")


def test_ac_surge_escalates_via_the_headroom_veto_even_with_a_confident_agent(client, monkeypatch):
    monkeypatch.setattr(agent, "triage", real_triage)
    simulator.seed(app.state.pool)
    app.state.client = ScriptedClient([submit("resolve_quietly", "certain")])

    fire_through(client, "ac-surge")

    outcome, gate_reason = decision_for("ac_unit")
    assert outcome == "escalated"
    assert "is at or above" in gate_reason  # the headroom wording; "is above" alone would also match the breach one


@pytest.mark.parametrize(
    "scenario, appliance_id, expected_outcome",
    [
        ("heater-breach", "space_heater", "escalated"),
        ("washer-spin", "washer", "resolved"),
        ("ac-surge", "ac_unit", "escalated"),
    ],
)
def test_running_the_same_scenario_twice_after_reset_gives_the_same_outcome(
    client, monkeypatch, scenario, appliance_id, expected_outcome
):
    monkeypatch.setattr(agent, "triage", real_triage)

    for _ in range(2):
        db.reset(app.state.pool)
        simulator.seed(app.state.pool)
        app.state.client = ScriptedClient([submit("resolve_quietly", "certain")])
        fire_through(client, scenario)
        assert decision_for(appliance_id)[0] == expected_outcome
