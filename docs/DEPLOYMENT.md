# Deploying TRINETRA to a permanent URL

The goal: a public HTTPS address anyone can open on any device, with no setup
on their side and nothing running on your laptop.

**Render is the recommended host** — free tier, managed PostgreSQL, HTTPS
included, and a `render.yaml` in this repository that configures everything.

---

## Render (recommended)

### 1. Push the repository to GitHub

```powershell
cd TriNetra
git init
git add .
git commit -m "TRINETRA - AI-Powered Criminal Network Intelligence Platform"
git branch -M main
git remote add origin https://github.com/<you>/trinetra.git
git push -u origin main
```

`.gitignore` already excludes `.env`, `CREDENTIALS.md`, the database and local
tooling config, so **nothing secret is committed**. Worth confirming once:

```powershell
git status --ignored --short | Select-String "CREDENTIALS|\.env"
```

### 2. Create the blueprint

1. Sign in at [render.com](https://render.com) (GitHub login is fine)
2. **New → Blueprint**
3. Pick your repository — Render reads `render.yaml` and proposes a web service
   plus a PostgreSQL database
4. It will ask for **`SEED_PASSWORD`**. Set a password you will actually use to
   sign in: 12+ characters with an uppercase letter, a lowercase letter, a digit
   and a symbol. For example `TrinetraDemo#2026`.
5. **Apply**

First deploy takes about 5–10 minutes. When it finishes you have a permanent URL:

```
https://trinetra.onrender.com
```

### 3. Sign in

The instance seeds itself on first boot — no shell needed. While that runs the
login page says *"Setting up for the first time"* and updates itself when ready.
It takes about a minute.

Then sign in with any Service ID and the `SEED_PASSWORD` you chose:

| Service ID | Role |
|---|---|
| `IO-114` | Investigating Officer |
| `WSO-052` | Women Safety Officer |
| `SI-207` | Supervisory Officer |
| `AN-331` | Intelligence Analyst |
| `ADM-001` | NCRB Administrator |

---

## Two things to know about the free tier

**It sleeps after 15 minutes of inactivity.** The next visitor waits roughly
50 seconds for it to wake. That is fine for a link someone opens once, and
annoying if a judge hits it cold during evaluation.

Two ways to handle it:
- **Warm it up** a few minutes before anyone opens the link, by visiting it
  yourself.
- **Upgrade to Starter (about $7/month)** for the evaluation period, which
  removes sleeping entirely. Worth it for a judged demo.

**The free PostgreSQL database expires after 90 days.** Fine for a hackathon;
note it if you keep the project running afterwards.

---

## About `SEED_PASSWORD`

This makes every seeded account share one password.

Normally the seed generates a separate strong password per account and writes
them to `CREDENTIALS.md`. On a cloud host that file lands on an ephemeral disk
and disappears on the next restart — so you would have no way to sign in.

`SEED_PASSWORD` solves that, and it is a real weakening: anyone who knows it can
sign in as any role, so role separation stops being a security boundary and
becomes only a demonstration of the feature. The application logs a warning
saying exactly this on boot.

**It is acceptable here because the deployment holds only synthetic data.** It
would not be acceptable for a deployment holding real case data — that needs
per-user accounts, individually issued credentials and MFA. See
`docs/SECURITY.md`.

---

## Other hosts

The repository also carries a `Dockerfile` and a `Procfile`, so the same code
deploys elsewhere without changes.

**Fly.io**
```powershell
fly launch --no-deploy
fly postgres create --name trinetra-db
fly postgres attach trinetra-db
fly secrets set ENVIRONMENT=production `
                SECRET_KEY=(python -c "import secrets;print(secrets.token_urlsafe(48))") `
                AUTO_SEED=true SEED_PASSWORD='TrinetraDemo#2026'
fly deploy
```

**Railway** — connect the repo, add a PostgreSQL plugin, set the same
environment variables. The `Procfile` supplies the start command.

**Any container host** (Cloud Run, Koyeb, Azure Container Apps) — build the
`Dockerfile` and set the same variables.

---

## Required environment variables

| Variable | Value | Why |
|---|---|---|
| `ENVIRONMENT` | `production` | Enables Secure cookies and enforces `SECRET_KEY` |
| `SECRET_KEY` | a long random string | Signs session tokens. **The app refuses to start without it in production.** |
| `DATABASE_URL` | the host's PostgreSQL URL | See the warning below |
| `AUTO_SEED` | `true` | Populates an empty database on first boot |
| `SEED_PASSWORD` | your chosen password | So you can sign in — see above |
| `PYTHONPATH` | `backend:database:ai:graph` | Local packages (colon-separated on Linux) |

Generate a key with:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Optional:

| Variable | Default | Effect |
|---|---|---|
| `SEED_WITH_CORPUS` | `true` | `false` seeds only the two named cases — much faster boot, but analytics have little to rank against |
| `MAP_TILE_URL` | empty | Set to an XYZ template to overlay real map tiles |
| `GRAPH_BACKEND` | `embedded` | `neo4j` with `NEO4J_*` set |

---

## Use PostgreSQL, not SQLite

Most hosts give containers an **ephemeral filesystem**: it is wiped on every
restart and every redeploy. With SQLite you would lose the entire database —
including any case work done through the UI — without warning, and the app would
silently reseed itself as if nothing had happened.

`render.yaml` wires PostgreSQL automatically. On other hosts, set `DATABASE_URL`
to a managed PostgreSQL instance. The driver is already in `requirements.txt`;
no code changes are needed.

---

## The gotcha that catches people

`ENVIRONMENT=production` marks the session cookie **Secure**, which browsers
only send over HTTPS.

- **Cloud deploy** — always HTTPS, so use `production`. Correct.
- **Local or LAN over plain HTTP** — keep `development`. In production mode the
  browser silently discards the cookie: sign-in appears to succeed, then every
  request comes back unauthenticated. See `docs/SHARING.md`.

---

## After deploying

1. Open the URL and wait for first-boot setup to finish.
2. Sign in as `IO-114`, confirm the dashboard populates.
3. Sign in as `WSO-052` and open the Women Safety module.
4. Confirm the **SYNTHETIC DATA** banner is visible — it must never be off on a
   public instance.
5. Share the URL. Tell people to sign in with a **Service ID**, not an email.
