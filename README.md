# WattTriage

**Live demo:** _add the deployed URL here once it's up — see [Deploying](#deploying) below._

WattTriage watches electrical power draw from five monitored home appliances and decides,
per suspicious reading, whether it can be closed quietly or must be put in front of the
homeowner — with the reasoning recorded either way.

![The WattTriage dashboard: five appliance cards, a decision log, and one Escalation expanded
to show its reasoning, gate rule, and tool-call trace.](docs/images/dashboard.png)

*The dashboard, the gate, and the data pipeline above are all real and running live — the
watts, the outcomes, and which gate rule fired are exactly what a real run produces for these
scenarios. Only the reasoning prose shown was scripted rather than a live model call, so the
screenshot is reproducible instead of depending on what the model happens to write that day.*

## Architecture, in one paragraph

A deterministic statistical **Detector** watches every incoming Reading and raises an
**Anomaly Candidate** when something looks statistically off, or immediately when a Reading
is above the appliance's **Rated Wattage** — its manufacturer-stated maximum safe draw — which
is a **Rated Breach**. A small hand-written
tool-calling agent then investigates the Candidate — it can look up the appliance's profile,
its recent trace, its hourly history, and past decisions, then recommends resolve-or-escalate
with a confidence — but the agent never decides on its own. A deterministic **gate**
(`app/gate.py`) turns that recommendation into the real **Triage Decision**: a Rated Breach
always escalates before the agent is even consulted, and quiet resolution only happens when
the agent says `certain` *and* every other safety check passes. Any Rated Breach, any
timeout, any API error, any malformed output, and now the hourly agent-run budget (below) —
all of it escalates. The agent can only ever *permit* silence; it can never *force* it. See
`docs/adr/` for the reasoning behind each of these decisions.

## Setup

The backend requires only **PostgreSQL** and **Python 3.12+** with
[uv](https://docs.astral.sh/uv/) — no container runtime (see [Why no Docker](#why-no-docker)
below). Seeing it in the browser needs one more thing, Node.js, for the dashboard — see
[Dashboard](#dashboard-needs-nodejs) below. Run every command below, in order, from the repo
root.

```bash
# 1. Create the role and the two databases (main + a separate one the test suite can wipe freely)
sudo -u postgres createuser --pwprompt watt
sudo -u postgres createdb --owner=watt watt
sudo -u postgres createdb --owner=watt watt_test

# 2. Copy the env template and fill in the two CHANGE_ME placeholders
cp .env.example .env
# edit .env: set the password you just chose in DATABASE_URL and TEST_DATABASE_URL,
# set ANTHROPIC_API_KEY, and set WRITE_API_KEY to any random string
# Everything else in .env.example (agent budget, detector thresholds, timeouts, ...) is
# commented out with its default already shown — only uncomment one to override it.

# 3. Install Python dependencies
uv sync

# 4. Start the API (applies the schema automatically, seeds the five appliances)
set -a; . ./.env; set +a
uv run uvicorn app.main:app --reload
```

The API is now running at `http://localhost:8000` — check `curl http://localhost:8000/health`.

```bash
# 5. In a second terminal: seed ~2 hours of realistic history so the dashboard has something to show
set -a; . ./.env; set +a
uv run python -m app.simulator seed

# optional: keep posting live traffic while you look around
uv run python -m app.simulator ambient
```

### Dashboard (needs Node.js)

The five backend steps above are the whole product — everything else is the browser view of
it. The dashboard is a separate Next.js app and is the one place this project needs anything
beyond Postgres and Python:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000/dashboard`. Set `CORS_ORIGINS=http://localhost:3000` in `.env`
(and restart the API) so the browser is allowed to call it. The frontend itself defaults to
calling `http://localhost:8000`; only set `NEXT_PUBLIC_API_URL` (in `frontend/`) if the API
runs somewhere else.

*These setup steps were run once from a clean shell, start to finish, to confirm nothing is
missing — with one caveat: the two `createuser`/`createdb` commands in step 1 need Postgres
superuser access, which the environment this README was written in doesn't have. Everything
from step 2 onward (env file, `uv sync`, schema application, seeding, the API, the dashboard)
was verified end to end against a real, freshly-emptied database.*

### Why no Docker

PostgreSQL was already available locally, and a container would have bought nothing except a
tool the author would have to justify.

## Deploying

The backend deploys to [Render](https://render.com) and the dashboard to
[Vercel](https://vercel.com) — chosen because Render bundles a managed Postgres database with
the web service in one place, and Vercel is built by the same team as Next.js with a
first-class free tier. See [ADR-0009](docs/adr/0009-render-and-vercel-for-deployment.md) for
the reasoning, including why the production agent budget is lower than the code default.

**Backend (Render):**

1. Push this repo to GitHub, then in Render choose **New → Blueprint** and point it at the
   repo. Render reads [`render.yaml`](render.yaml) — a file that describes the whole backend
   deploy (the web service, the free Postgres database, and every environment variable) as
   code, so the dashboard click-through is short and repeatable instead of freehand.
2. When prompted, paste in a real `ANTHROPIC_API_KEY` (from
   [console.anthropic.com](https://console.anthropic.com)) — this is the one secret Render
   can't generate for you. `WRITE_API_KEY` is generated automatically; you won't need to know
   its value for anything in these steps.
3. Once it's live, note the service's URL (`https://<something>.onrender.com`) — the
   dashboard needs it next.
4. Open the deployed service's **Shell** tab in Render and run
   `uv run python -m app.simulator seed` once, to plant ~2 hours of baseline history so the
   appliance cards aren't empty on first load.

**Dashboard (Vercel):**

1. Import the same GitHub repo into Vercel. Set **Root Directory** to `frontend` — this repo
   holds both the API and the dashboard, and Vercel only needs to build the latter.
2. Set the environment variable `NEXT_PUBLIC_API_URL` to the Render URL from step 3 above,
   then deploy.
3. Note the resulting Vercel URL (`https://<something>.vercel.app`).

**Wire them together:** back in Render, set `CORS_ORIGINS` to the Vercel URL from the step
above and save — **CORS** (Cross-Origin Resource Sharing) is the browser's own rule that a
page can't call an API on a different domain unless that API explicitly allows it, so without
this step the deployed dashboard would load but every request would be silently blocked by
the browser. Render redeploys automatically on an environment variable change.

*This deployment path is written from the current [Render Blueprint
spec](https://render.com/docs/blueprint-spec), and every command in it exists elsewhere in
this repo and was run for real in [Setup](#setup) above — but the cloud deploy itself
couldn't be executed or watched end to end from the environment this was written in (no
browser, no cloud accounts). Treat it as a precise, reviewable plan rather than a verified
one, and expect to debug the first real run.*

## The data is synthetic

Every Reading in this project is generated by `app/simulator.py`, not recorded from a real
house. That's deliberate, not a shortcut: a recording of a working house contains no Rated
Breach — nobody's appliance actually exceeds its rated wattage during normal life — so the
project's single most important scenario would have had to be injected into real data
anyway. Real appliance-level datasets (UK-DALE, REDD) were considered and rejected for
exactly this reason; see [ADR-0006](docs/adr/0006-v1-scope-boundary.md).

## Known weaknesses

- **A purely linear drift is undetectable, by design.** A slow, steady ramp inflates the
  baseline's mean and its spread by the same factor, so the z-score stays roughly constant
  and never crosses the threshold — this isn't a tuning problem, it needs a second detector
  working against the hourly Rollups. See [ADR-0008](docs/adr/0008-detector-limits-are-structural.md).
- **Detection has a deliberate lag.** The detector waits for `DETECTOR_PERSISTENCE`
  (default 3) consecutive abnormal readings before raising a Candidate, so one noisy reading
  can't trigger a paid investigation on its own — at the default 5-second reading interval,
  that's roughly a 15-second delay between a real fault starting and it being flagged.
- **Confidence is self-reported, not calibrated.** The agent says `certain`, `likely`, or
  `unsure` — never a float — because an LLM's self-reported 0.87 isn't a calibrated
  probability with labelled outcomes behind it; claiming that precision would be dishonest.
  See [ADR-0003](docs/adr/0003-ordinal-confidence-not-a-float.md).
- **A process restart strands `pending` Candidates.** The agent runs as a FastAPI background
  task, not a separate worker with a durable queue, so a crash or redeploy mid-investigation
  leaves a Candidate `pending` in the database — visible and re-runnable by hand, but not
  automatically retried. See [ADR-0006](docs/adr/0006-v1-scope-boundary.md).

## Architecture Decision Records

Every non-obvious design choice in this project is written down as it was made, including
the options considered and rejected, in [`docs/adr/`](docs/adr/):

- [0001 — Rated Breach bypasses agent judgement](docs/adr/0001-rated-breach-bypasses-agent-judgement.md)
- [0002 — Postgres with hand-written SQL](docs/adr/0002-postgres-with-hand-written-sql.md)
- [0003 — Ordinal confidence, not a float](docs/adr/0003-ordinal-confidence-not-a-float.md)
- [0004 — Decisions snapshot their own evidence](docs/adr/0004-decisions-snapshot-their-evidence.md)
- [0005 — Hand-written agent loop with read-only tools](docs/adr/0005-hand-written-agent-loop-with-read-only-tools.md)
- [0006 — v1 scope boundary](docs/adr/0006-v1-scope-boundary.md)
- [0007 — Cooldown veto counts unacknowledged Escalations only](docs/adr/0007-cooldown-veto-counts-unacknowledged-escalations-only.md)
- [0008 — Detector limits are structural](docs/adr/0008-detector-limits-are-structural.md)
- [0009 — Render and Vercel for deployment](docs/adr/0009-render-and-vercel-for-deployment.md)

The single test worth reading first is
[`test_breach_escalates_despite_agent`](tests/test_agent.py) in `tests/test_agent.py` — it
scripts a fake model that is *confidently wrong* about a genuine Rated Breach, and asserts
the system escalates anyway. That's the project's central safety claim in one test: the
agent can recommend, but it can never override a real safety condition.
