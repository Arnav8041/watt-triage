# Fleet Sentinel — Project Standards

## Code style — ponytail by default

Invoke the `ponytail` skill by default for any coding task in this project — writing, adding, refactoring, fixing, or reviewing code, and choosing libraries/dependencies. Push for the simplest, shortest, most minimal solution: question whether the task needs to exist at all (YAGNI), reach for the standard library / framework built-ins before custom code or a new dependency, and prefer one clear line over an abstraction built for hypothetical future needs. Applies across the stack — FastAPI backend, database layer, and the agentic AI code — not just frontend.

## Frontend Standards

## Stack
- Framework: Next.js / React
- Styling: Tailwind CSS
- Motion: Framer Motion (`motion-framer` skill) for component/state-driven animation, GSAP + ScrollTrigger (`gsap-scrolltrigger` skill) for scroll-driven timelines

## Mandatory skill invocation for frontend work

Any frontend decision — writing or reviewing UI/component code, choosing typography/color/layout, or implementing animation/transitions/scroll effects — MUST invoke all four of these skills together, not just the one that seems most relevant:

- `frontend-design` — anti-slop rules: typography pairing, restrained color palettes, no default Inter/Roboto, no repetitive hover effects, deliberate layout rhythm
- `motion-framer` — Framer Motion: spring physics (`stiffness: 400, damping: 30`), variants, gestures, layout animations, AnimatePresence
- `gsap-scrolltrigger` — GSAP + ScrollTrigger: scroll-driven timelines, pinning, scrubbing, parallax
- `motion` — Motion (Framer Motion) library specifics: bundle size, complex transitions, spring physics edge cases

These four plugins are installed at **project scope only** (declared in `.claude/settings.json`, not the user's global config) — they apply to Fleet Sentinel and are not carried into other projects.

Do not implement a UI surface using only one of these skills in isolation — design (frontend-design), interaction motion (motion-framer / motion), and scroll motion (gsap-scrolltrigger) are meant to compose on every non-trivial frontend task.

## Secrets and `.env` — never print it

`.env` holds real secrets (including `ANTHROPIC_API_KEY`). Never `cat`, `head`, `Read`, `sed` or otherwise
display the file, and never echo a secret's value. To see which variables exist, list names only with
`bash scripts/env-names.sh`. Do NOT run `grep ... .env` yourself: the `Read(./.env)` deny rule blocks any
command that names the file, so it fails. Don't paste a connection string with its password into output either.

## Running things

- Load env for one command without printing it: `set -a; . ./.env; set +a`.
- Tests: `set -a; . ./.env; set +a; uv run pytest -q` (needs `TEST_DATABASE_URL`; local Postgres on 5432 must be up).
- Typecheck: `uv run pyright app tests` (pyright is a dev dependency).
- Ad-hoc scripts outside the repo need `PYTHONPATH=.` so `import app` works.
