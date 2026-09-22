# Deploying to Render and Vercel, with a tighter public budget

The backend (API + Postgres) deploys to Render, described as code in `render.yaml`. The
dashboard deploys to Vercel. Both were picked for the same reason the rest of this project
avoids infrastructure it can't explain: Render bundles a managed Postgres database with the
web service in one place, so there's one deploy target instead of two to reason about, and
Vercel is built by the same team as Next.js, with zero-config deploys and a genuinely
indefinite free tier (unlike Render's free Postgres, which expires after 90 days).

The production `AGENT_MAX_RUNS_PER_HOUR` is set to 50, half the code default of 100. The
default was sized for a demo table running for a few hours; a public URL on a resume is
reachable by anyone, indefinitely, so the budget is set more conservatively for the same
reason ticket #16 exists at all — a lower number is a smaller worst case if the cap is ever
the only thing standing between a visitor and real spend.

No background process posts ambient traffic to the deployed instance. Locally,
`app.simulator ambient` exists so the dashboard has something moving to look at during
development. In production that would mean a worker running, and paying for compute, forever,
whether or not anyone is looking — for a resume link, the far cheaper and more compelling
demo is the "fire a scenario" button already on the dashboard: a visitor triggers a real,
live agent investigation themselves, on demand, which is a better pitch than ambient noise
they didn't cause.

## Considered Options

- **Railway** for the backend. Similarly simple, but its free tier is now a one-time trial
  credit rather than an ongoing plan — likely to need a paid plan within weeks of deploying,
  which doesn't suit a link meant to outlive a single career fair.
- **Fly.io** for the backend. A reasonable alternative with a friendlier long-lived free
  allowance than Render's, but a CLI-driven (`flyctl`) deploy flow instead of a dashboard
  Blueprint — more setup friction for a one-person project deployed once.
- **A background worker running `ambient` continuously in production.** Rejected above:
  ongoing cost for a demo nobody's necessarily watching, when the fire button already
  demonstrates the real pipeline on demand.

## Consequences

Render's free Postgres database expires after 90 days; the link will need a paid database
plan (or a migration to a different free database) before then to keep working past that
window. The dashboard, being static-ish Vercel hosting, has no equivalent expiry.
