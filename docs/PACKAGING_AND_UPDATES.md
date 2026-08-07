# Packaging & Auto-Update (Windows MVP)

> Goal: install the app once, open it like a normal program, and have new versions apply
> themselves on the next restart — no manual reinstall. Scope chosen: **your machine only**
> (uses the Python already on your PATH; bundling Python for other machines is deferred).
> Update feed: **GitHub Releases**.

## What is already wired (code, done)

- `package.json`
  - scripts: `pack` (build an unpacked app to test locally), `dist` (build the .exe
    installer), `release` (build + publish to GitHub Releases).
  - `electron-updater` dependency (installed).
  - `build.win` = NSIS installer; `build.nsis` = per-user install (no admin),
    user can choose the folder.
  - `build.publish` = GitHub provider (owner/repo are placeholders you must set).
- `electron/main.js`
  - `setupAutoUpdater()` runs on launch **only in a packaged build**: checks GitHub
    Releases, downloads in the background, and installs on the next quit
    (`autoInstallOnAppQuit`). It emits `app-update` events to the UI (checking/available/
    downloading/ready) and there is an `install-update-now` IPC handler if you want a
    "restart to update" button later.
- `ipc_sidecar.py` — provider keys now load from the **stable user-data dir**
  (`COWORK_USER_DATA_DIR`, i.e. `%APPDATA%/AI Dev Co-worker`) instead of the app folder.
  This is critical: the app folder is REPLACED on every update, so keys kept there would be
  wiped each time. Now keys survive updates. (In dev, with no `COWORK_USER_DATA_DIR`, it
  still falls back to the project dir, so your current setup keeps working.)

## What you must do manually (needs your GitHub account / a token)

### 1. Put the code on GitHub
The `.git` here is empty. Create a repo and push. `.gitignore` already excludes
`credentials.txt` / `key.txt` / `.env` / `release/` / `build/`, so **no secrets get
committed** — verify with `git status` before the first push.

```bash
git init
git add .
git status            # confirm credentials.txt / key.txt are NOT listed
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<you>/AI_DEV_COWORKER.git
git push -u origin main
```

**Public vs private:** a **public** repo is by far the simplest for auto-update — the app
checks for updates without any token embedded in it. A **private** repo would require
shipping a GitHub token inside the app (not recommended). Since the code carries no secrets
(they're gitignored), a public repo is the practical choice. Your call.

### 2. Point the publish config at your repo
In `package.json` → `build.publish`, replace `YOUR_GITHUB_USERNAME` with your GitHub
username (and the repo name if you changed it).

### 3. A GitHub token for publishing (publish step only — not needed by end users)
Create a token with `repo` scope at github.com/settings/tokens, then set it in the shell
you build from (PowerShell):
```powershell
$env:GH_TOKEN = "ghp_your_token"
```
This is only used when YOU publish a release. The installed app never sees it.

## Building & releasing

- **Test the pipeline locally (no publish):**
  ```bash
  npm run pack
  ```
  Produces an unpacked app under `release/win-unpacked/` — double-click the .exe to confirm
  it launches and the sidecar starts.
- **Build the installer (no publish):**
  ```bash
  npm run dist
  ```
  Produces `release/AI Dev Co-worker Setup <version>.exe`.
- **Cut a release (build + upload to GitHub Releases):**
  ```bash
  npm run release
  ```
  This uploads the installer + the `latest.yml` feed that auto-update reads.

**The version rule that makes auto-update work:** bump `version` in `package.json` for every
release (e.g. 0.1.0 → 0.1.1). electron-updater compares the running version to the newest
GitHub Release; if they match, it sees no update. No bump = no update detected.

## How updates reach you (the end-user experience)

1. Install once from the Setup .exe (Windows SmartScreen will warn on first run because the
   app is unsigned — "More info → Run anyway"; this is expected without code signing).
2. On each launch the app quietly checks GitHub Releases and downloads a newer version in
   the background.
3. The update applies automatically the next time you quit and reopen — no reinstall, no
   overwriting by hand.

## First-run setup for the INSTALLED app (one time)

The installed app reads credentials from `%APPDATA%\AI Dev Co-worker\`, not the project
folder. So place your key file there once:
- Create `credentials.txt` in `%APPDATA%\AI Dev Co-worker\` with your provider keys
  (one per line), and set `COWORK_SEARCH_API_KEY` as a user env var (you already did).
- Everything else (memory, connectors, artifacts, logs) already lives in that same folder
  and survives updates.

## Known limitations (MVP scope — deferred on purpose)

- **Python is still required on the machine.** The installed app spawns `python` from PATH
  and needs the pip deps (`openai`, optional `mcp`/`fastembed`). Fine on your machine.
  Bundling a frozen Python (PyInstaller) so it runs on a machine with no Python is the
  next step if you ever distribute to others.
- **No code signing.** Unsigned installers trigger SmartScreen warnings and some AV noise.
  A code-signing certificate removes this (costs money) — skip for personal use.
- **`build/` folder** is leftover from an old Python `bdist` and is now gitignored; safe to
  delete.

## Recommended sequence

1. `npm run pack` → confirm the unpacked app launches locally.
2. Set up the GitHub repo + publish config (steps 1–2 above).
3. `npm run dist` → install the Setup .exe on your machine; confirm it runs and finds your
   keys in `%APPDATA%`.
4. Bump version, `npm run release` → confirm a second install auto-updates on restart.
5. (Later, only to share with others) bundle Python via PyInstaller.
