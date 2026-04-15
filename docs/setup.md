environment matches the declared configuration.
# Setup Notes

## Python Environment and Project Setup

This project uses [`uv`](https://github.com/astral-sh/uv) for Python environment and dependency management. All commands and backend logic assume you are using the project-local `.venv` created by `uv`.

### Why `uv`?
- Handles venv, dependencies, and running commands in one tool
- Fast and simple for small team projects
- Project-local config avoids permission issues in restricted environments

### Common Setup Steps
```bash
uv venv
uv sync
uv run energy-scheduler doctor
uv run energy-scheduler workloads
```

### uv Cache Directory
If you see errors about cache permissions, it is because `uv` by default tries to use `~/.cache/uv`, which may not be writable. This project sets a local cache in `uv.toml`:

```toml
cache-dir = ".uv-cache"
```

This ensures all `uv` operations work regardless of shell or user home directory restrictions.

---

## Backend and Dashboard UI

- The backend provides all benchmarking, caching, and API logic (see [docs/architecture.md](architecture.md)).
- The dashboard UI is a modern, responsive local webapp that consumes the backend API and visualizes results (see [README.md](../README.md)).
- All results are cached—identical parameter runs are never repeated.

---

## Reproducibility and Energy Measurement

- For stable results, set your CPU governor to `performance` and minimize background load.
- If RAPL energy readings are not available (permission denied), see [docs/ops-checklist.md](ops-checklist.md) for host-side fixes.

---

## Why We Document Decisions

This project keeps parallel docs explaining:
- what was built
- why it was built that way
- what tradeoffs were made

This file is the first example of that approach.
