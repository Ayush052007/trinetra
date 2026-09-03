# Deploying TRINETRA to Vercel

This works, and the configuration is committed. Read the trade-offs first —
Vercel is built for static sites and serverless functions, and TRINETRA is a
stateful backend, so some things genuinely degrade.

**If you just want a public URL with nothing degraded, use Render instead**
(`docs/DEPLOYMENT.md`, ~10 minutes, already configured).

---

## What changes on Vercel

| Feature | On a normal server | On Vercel |
|---|---|---|
| Live alert feed | WebSocket, instant | **WebSocket unavailable.** The client falls back to polling every 8s automatically |
| Cross-user live updates | Broadcast to everyone | **Unreliable** — the event buffer is per-instance, and each request may hit a different instance |
| Analytics pages | Warmed at startup, instant | Rebuilt on each cold start, **~5s** |
| Database | SQLite file, zero setup | **External PostgreSQL required** |
| First-boot auto-seed | Works | **Must be seeded manually** — seeding takes ~60s and would exceed the request limit |
| File uploads | Written to disk | Held in memory only |

Nothing is broken; live updates are just slower and less reliable, and cold
requests are slower. Sign-in, the graph, search, cases, reports, the Women
Safety module and RBAC all work normally.

---

## 1. Create a PostgreSQL database

Vercel's filesystem is read-only, so SQLite cannot be used.

In the Vercel dashboard: **Storage → Create Database → Postgres** (Neon-backed,
free tier). Or use [neon.tech](https://neon.tech) / [supabase.com](https://supabase.com)
directly — any PostgreSQL works.

Copy the connection string. It looks like:

```
postgresql://user:password@host.neon.tech/dbname?sslmode=require
```

Change the prefix to `postgresql+psycopg://` so SQLAlchemy uses psycopg 3:

```
postgresql+psycopg://user:password@host.neon.tech/dbname?sslmode=require
```

## 2. Seed that database from your own machine

The seed takes about a minute — far past any serverless request limit — so run
it locally against the remote database. From the project folder:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://user:password@host.neon.tech/dbname?sslmode=require"
$env:SEED_PASSWORD = "TrinetraDemo#2026"
.\.venv\Scripts\python.exe backend\app\db\seed_bulk.py
```

This creates the schema, both demo cases, the background corpus and the six
accounts — all sharing the password you set. Run it **once**.

## 3. Import the repository into Vercel

1. Go to [vercel.com/new](https://vercel.com/new)
2. **Continue with GitHub**, authorise it if asked
3. Find **`Ayush052007/trinetra`** → **Import**
4. Leave the framework preset as **Other** — `vercel.json` handles the build
5. Expand **Environment Variables** and add:

| Name | Value |
|---|---|
| `DATABASE_URL` | your `postgresql+psycopg://...` string |
| `SECRET_KEY` | generate one — see below |
| `ENVIRONMENT` | `production` |
| `SERVERLESS` | `true` |
| `PYTHONPATH` | `backend:database:ai:graph` |
| `AUTO_SEED` | `false` |

Generate the key:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

6. **Deploy**

You get `https://trinetra.vercel.app` (or whatever you name the project).

## 4. Sign in

Service ID plus the `SEED_PASSWORD` from step 2:

- `IO-114` — Investigating Officer
- `WSO-052` — Women Safety Officer
- `ADM-001` — NCRB Administrator

---

## How the configuration works

**`api/index.py`** — Vercel's Python runtime looks for an ASGI app under
`api/`. This adds the project's packages to the path, sets `SERVERLESS=true`,
and re-exports the same FastAPI application. There is no separate codebase.

**`vercel.json`** — routes every path to that function and raises the limit to
60s with 1GB of memory, which the analytics endpoints need on a cold start.

**`SERVERLESS=true`** — makes the application skip its startup warm-up thread,
which cannot outlive a serverless invocation and would only burn the request's
time budget. The graph is built lazily on first use instead.

---

## If something goes wrong

**Sign-in succeeds then every request 401s** — `ENVIRONMENT` is not
`production`, so the session cookie is not marked `Secure` and the browser
rejects it over HTTPS. Set it and redeploy.

**"Invalid Service ID or password"** — the database was never seeded, or
`DATABASE_URL` points somewhere different from what you seeded in step 2.

**502 or a timeout on analytics pages** — the cold start exceeded the limit.
Confirm `maxDuration` is 60 in `vercel.json`, and that you are not on a plan
capped lower.

**`ModuleNotFoundError: app`** — `PYTHONPATH` is missing from the environment
variables.

**Live alerts do not appear across browsers** — expected. Serverless instances
do not share the in-memory event buffer. Making this work would need Redis or
a database-backed queue. Render does not have this limitation.
