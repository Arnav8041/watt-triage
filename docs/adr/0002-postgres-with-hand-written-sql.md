# PostgreSQL accessed through hand-written SQL, not an ORM

Readings arrive at roughly one row per second (~2.6M rows/month), which is far below the
point where a time-series database earns its dependency, and the deployment story only
needs a single `DATABASE_URL`. We use managed PostgreSQL via psycopg3 with a connection
pool, and every query is a literal SQL string in a small `db/` module.

## Considered Options

- **SQLite.** Zero setup and no server. Rejected on two counts: it has no built-in
  `stddev` aggregate, which sits on the detector's hot path, and free PaaS filesystems are
  ephemeral so the data would not survive a redeploy.
- **TimescaleDB.** Hypertables and continuous aggregates would replace the retention job
  outright. Rejected as overkill at this volume, and it narrows which hosts can run the app.
- **DuckDB.** Wrong workload shape — columnar and analytical, not concurrent single-row
  appends.
- **SQLAlchemy Core / ORM.** Rejected deliberately: this codebase must be defensible line
  by line under technical questioning, and generated SQL is SQL the author did not write.

## Consequences

Inserts, migrations and the rollup are all written by hand. This is the point, not a
regression — do not "modernise" `db/` into an ORM.
