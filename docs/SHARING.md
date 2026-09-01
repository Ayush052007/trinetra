# Sharing TRINETRA with other people

By default the server binds to `127.0.0.1`, which only your own machine can
reach. Below are four ways to let other people in, from easiest to most
permanent. Pick by who needs access and for how long.

| Option | Who can reach it | Setup | Best for |
|---|---|---|---|
| 1. Local network | Anyone on the same Wi-Fi | 1 command | **SIH demo, judging table, teammates in the room** |
| 2. Temporary public link | Anyone with the link | Install a tunnel tool | Remote mentor, quick review call |
| 3. Share the code | Anyone, on their own machine | They run the setup | Judges who want to inspect it |
| 4. Cloud deploy | Anyone, permanently | ~30 min | A lasting URL for the submission |

---

## Option 1 — Local network (recommended for the demo)

Everyone on the same Wi-Fi reaches your machine directly. Nothing leaves the
network, and it needs no accounts or installs.

```powershell
.\share.ps1
```

The script prints two URLs:

```
On this machine :  http://localhost:8000
On this network :  http://10.3.168.191:8000     <- share this one
```

Hand out the second URL. It works on phones and tablets on the same Wi-Fi too —
the interface is responsive.

**Firewall.** The first run usually raises a Windows Firewall prompt. Allow it
on **Private** networks. If no prompt appears and nobody can connect, run this
once in an **Administrator** PowerShell:

```powershell
New-NetFirewallRule -DisplayName "TRINETRA 8000" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow -Profile Private
```

**Your IP can change.** It is assigned by the Wi-Fi router, so it may differ on
a different network. Re-run `share.ps1` — it always prints the current one.

**Caveats.** Your machine must stay on and awake, and everyone must be on the
same network. Venue Wi-Fi sometimes uses *client isolation*, which blocks
device-to-device traffic; if the URL works on your machine but not on a
teammate's phone, that is the cause — use a phone hotspot instead.

---

## Option 2 — Temporary public link

For someone not on your network. A tunnel gives a public URL that forwards to
your machine.

**Cloudflare Tunnel** (no account needed for a quick link):

```powershell
winget install --id Cloudflare.cloudflared
cloudflared tunnel --url http://localhost:8000
```

It prints a `https://something-random.trycloudflare.com` URL. Start TRINETRA
normally in another terminal first.

**ngrok** is an alternative and needs a free account:

```powershell
winget install ngrok.ngrok
ngrok config add-authtoken <your token>
ngrok http 8000
```

**Before you do this, understand what it means.** The link is public — anyone
who has it can reach your machine's server, and search engines have been known
to find tunnel URLs. It is acceptable here because the platform holds only
synthetic data and requires a sign-in, but:

- Set a strong `SECRET_KEY` in `.env` first.
- Do not leave the tunnel running unattended.
- Never tunnel a deployment holding real case data.

Tunnels also serve over HTTPS, so if you go this route you can safely set
`ENVIRONMENT=production` — but see the warning in the next section about doing
that over plain HTTP.

---

## Option 3 — Share the code

The most useful option for judges who want to look inside, and the only one
that does not depend on your laptop staying on.

Zip the project, excluding the generated and secret files:

```powershell
Compress-Archive -Path backend,frontend,ai,graph,database,tests,docs,requirements.txt,README.md,.env.example,docker-compose.yml,run.ps1,share.ps1,pytest.ini,.gitignore -DestinationPath TRINETRA.zip
```

Or push to GitHub — `.gitignore` already excludes `.env`, `CREDENTIALS.md` and
the database, so **no secret is committed**:

```powershell
git init
git add .
git commit -m "TRINETRA - AI-Powered Criminal Network Intelligence Platform"
git branch -M main
git remote add origin https://github.com/<you>/trinetra.git
git push -u origin main
```

Whoever receives it runs the four commands in the README. The seed generates a
**fresh set of passwords on their machine**, written to their own
`CREDENTIALS.md` — yours are never shared, which is the correct behaviour.

---

## Option 4 — Deploy to a cloud host

For a permanent URL on the submission. TRINETRA is a single Python service with
no external dependencies by default, so most platforms take it as-is.

**Render / Railway / Fly.io** — all work. The shape is the same:

- Build: `pip install -r requirements.txt`
- Pre-deploy (once): `python backend/app/db/seed_bulk.py`
- Start: `uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $PORT`

Environment variables to set:

```
ENVIRONMENT=production
SECRET_KEY=<generate a fresh one>
DATABASE_URL=<the host's PostgreSQL URL>
CORS_ORIGINS=https://your-app.onrender.com
```

Generate the key with:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

**Use PostgreSQL, not SQLite,** on a cloud host. Most have ephemeral disks, so
a SQLite file is wiped on every restart and you would lose the database. Add
`psycopg[binary]` to `requirements.txt` and point `DATABASE_URL` at the managed
database.

**Read the seed output.** The generated passwords are printed once and written
to `CREDENTIALS.md` on the server's disk. Capture them during the deploy, or
you will not be able to sign in.

---

## One important gotcha

`ENVIRONMENT=production` marks the session cookie **Secure**, which browsers
only accept over HTTPS.

- Options 1 and 2 over plain `http://` — keep `ENVIRONMENT=development`.
  Setting it to production will make sign-in appear to succeed and then
  immediately fail, because the browser silently discards the cookie.
- Option 2 over the tunnel's `https://` URL, and option 4 — use
  `ENVIRONMENT=production`, and set `SECRET_KEY`, which is mandatory there.

---

## What to tell people you share it with

- The URL, and that they need a **Service ID** (not an email) to sign in.
- Which account to use — `IO-114` for the investigation workflow, `WSO-052` for
  the Women Safety module. Signing in as both is the clearest way to see that
  role permissions are enforced by the server.
- That **all data is synthetic**, which the banner says on every screen.
- That five wrong passwords locks an account for 15 minutes. If a judge fatigues
  an account, unlock it from the Administration screen as `ADM-001`.
