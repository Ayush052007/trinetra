# Running TRINETRA in GitHub Codespaces

A Codespace is a full Linux machine GitHub runs in the cloud from this
repository. It is the only way to run the platform "from GitHub" — GitHub
Pages cannot host it, because TRINETRA needs a Python server and a database.

## Start one

On the repository page: **Code → Codespaces → Create codespace on main**

The container then, on its own:

1. installs the dependencies
2. seeds the database (this prints the account passwords — **keep them**)
3. starts the server on port 8000 and opens it in a browser tab

First start takes about 3–4 minutes. Later starts are much quicker.

## Let other people in

A forwarded port is **private to you** by default. To share it:

1. Open the **Ports** panel (next to the terminal)
2. Right-click port **8000** → **Port Visibility → Public**
3. Copy the URL — it looks like
   `https://<something>-8000.app.github.dev`

Anyone with that URL can then open the platform, on any device.

## Sign in

The seed prints a credentials table in the terminal during setup, and writes
it to `CREDENTIALS.md` inside the Codespace. Sign in with a **Service ID**
(`IO-114`, `WSO-052`, `ADM-001`), not an email.

## Worth knowing

- Free accounts get roughly 60 hours of Codespace time per month. It stops
  automatically after 30 minutes idle, so it is not a permanent address.
- The URL changes each time you create a new Codespace.
- For a stable URL that does not consume your quota, deploy to Render
  instead — see `docs/DEPLOYMENT.md`.
