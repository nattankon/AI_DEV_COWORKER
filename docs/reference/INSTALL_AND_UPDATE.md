# Install And Update Notes

## Portable Runtime Rules

- Installed releases must not depend on any external application checkout or the development source directory.
- Electron resolves app files from the installed app folder or `process.resourcesPath`.
- Mutable runtime data must live under `COWORK_USER_DATA_DIR`, which the Electron shell sets to `app.getPath("userData")`.
- Session logs, audit logs, memory, settings, and update metadata should stay outside the install directory.

## Current Packaging Shape

- Python CLI metadata: `pyproject.toml`
- Installed command: `cowork`
- Renderer entry: `dist/index.html`
- Electron entry: `electron/main.js`
- Standalone npm dependency lockfile: `package-lock.json`
- Local dependency install path: `node_modules/`
- Future Electron IPC discovery order:
  1. `COWORK_PYTHON_ENTRY`
  2. `process.resourcesPath/cowork-sidecar/AI_DEV_COWORKER/ipc_sidecar.py`
  3. project-root `ipc_sidecar.py`

## CLI Install

- Development: `python -m pip install -e .`
- Future release: build a wheel from `pyproject.toml` and install it without the source checkout.
- The Python package has no runtime dependency on the legacy application.
- Electron packaging remains deferred because `ipc_sidecar.py` is not implemented.

## Future Update Target

The update flow should replace application files only. It must not delete or overwrite:

- `COWORK_USER_DATA_DIR/work_logs/`
- workspace memory files
- user model/provider settings
- local approval/audit records

This is the foundation for updating without losing user sessions after the app becomes a packaged `.exe`.

## Current Development Boundary

Use `C:\AI_DEV_COWORKER` as the active working directory. CLI development and verification must not require any other application checkout.
