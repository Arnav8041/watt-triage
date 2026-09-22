-- Applied on every startup, so everything here must be safe to run twice.
-- No migration tool in v1 (ADR-0006): this file is the whole schema.

CREATE TABLE IF NOT EXISTS appliance (
    id          text PRIMARY KEY,
    name        text NOT NULL,
    location    text NOT NULL,
    rated_watts integer NOT NULL CHECK (rated_watts > 0)
);

INSERT INTO appliance (id, name, location, rated_watts) VALUES
    ('fridge',       'Fridge',       'Kitchen',     250),
    ('water_heater', 'Water heater', 'Utility',    4500),
    ('space_heater', 'Space heater', 'Bedroom',    1500),
    ('washer',       'Washer',       'Laundry',    1200),
    ('ac_unit',      'AC unit',      'Living room', 3500)
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS reading (
    id           bigserial PRIMARY KEY,
    appliance_id text NOT NULL REFERENCES appliance (id),
    watts        double precision NOT NULL CHECK (watts >= 0),
    recorded_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS reading_appliance_time_idx
    ON reading (appliance_id, recorded_at DESC);

CREATE TABLE IF NOT EXISTS anomaly_candidate (
    id              bigserial PRIMARY KEY,
    appliance_id    text NOT NULL REFERENCES appliance (id),
    watts           double precision NOT NULL,
    trigger         text NOT NULL CHECK (trigger IN ('rated_breach', 'statistical')),
    z_score         double precision,          -- null for a pure Rated Breach
    baseline_size   integer NOT NULL DEFAULT 0,
    baseline_mean   double precision,
    baseline_stddev double precision,
    status          text NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'decided', 'failed')),
    detected_at     timestamptz NOT NULL DEFAULT now()
);

-- No foreign key to reading: retention deletes Readings, the audit record must survive (ADR-0004).
-- An Escalation is just a decision with outcome 'escalated'; acknowledgement lives here too.
CREATE TABLE IF NOT EXISTS triage_decision (
    id              bigserial PRIMARY KEY,
    candidate_id    bigint NOT NULL UNIQUE REFERENCES anomaly_candidate (id),
    outcome         text NOT NULL CHECK (outcome IN ('escalated', 'resolved')),
    confidence      text CHECK (confidence IN ('certain', 'likely', 'unsure')),
    gate_reason     text NOT NULL,
    reasoning       text,
    evidence        jsonb NOT NULL,
    tool_trace      jsonb NOT NULL,
    model           text,
    latency_ms      integer,
    acknowledged_at timestamptz,
    decided_at      timestamptz NOT NULL DEFAULT now()
);

-- One row per real model call attempted (ticket #16's hourly budget). Written atomically with
-- the budget check itself (pg_advisory_xact_lock in app/db/__init__.py:reserve_agent_run), so
-- concurrent triage() runs can't all read the same stale count before any of them is recorded.
CREATE TABLE IF NOT EXISTS agent_run (
    id     bigserial PRIMARY KEY,
    ran_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rollup (
    appliance_id text NOT NULL REFERENCES appliance (id),
    hour         timestamptz NOT NULL,
    min_watts    double precision NOT NULL,
    max_watts    double precision NOT NULL,
    avg_watts    double precision NOT NULL,
    sample_count integer NOT NULL,
    PRIMARY KEY (appliance_id, hour)
);
