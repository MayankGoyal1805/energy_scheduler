# Setup Notes

## Why We Configured `uv` First

Before writing backend code, we need a stable Python workflow for the project.

We are using `uv` because:

- it handles virtual environments, dependencies, and running commands in one tool
- it is fast
- it keeps the Python workflow simple for a small team project

## The Problem We Hit

When `uv` was first run in this workspace, it tried to create its cache under the default user cache
directory:

- `~/.cache/uv`

In this environment, that path was not writable, so `uv` failed before doing useful work.

That failure can look like a shell problem, but it is not really a `fish` vs `bash` issue. The real
issue is filesystem permissions for the cache path.

## The Fix

We added a local `uv.toml` file with:

```toml
cache-dir = ".uv-cache"
```

This tells `uv` to keep its cache inside the project directory, which is writable.

## Why This Matters

This is a good example of a common engineering rule:

- when a tool writes outside your project, that may fail in restricted environments
- if the tool supports project-local configuration, use it

By fixing this early, the rest of the project can use a predictable command flow:

```bash
uv venv
uv sync
uv run energy-scheduler
```

## What `uv venv` Does

`uv venv` creates a Python virtual environment, usually in `.venv/`.

That environment isolates:

- the Python interpreter used by the project
- installed dependencies
- scripts we run for the backend

This keeps the project reproducible and avoids depending on random packages from the system Python.

## What `uv sync` Does

`uv sync` reads the project metadata from `pyproject.toml`, resolves dependencies, and installs them
into the project environment.

Even if there are no extra dependencies yet, it is still the normal command to make sure the project
environment matches the declared configuration.

## Why We Are Writing This In `docs/`

You said you want to learn properly while building. So the project will keep a parallel set of docs
that explain:

- what we built
- why we built it that way
- what tradeoffs we made

This file is the first example of that approach.
