# Contributing to MIA-ScreenCapture

Thanks for your interest in contributing! This guide covers the essentials
needed to get a PR merged smoothly.

## Setup

```bash
uv sync                      # install all dependencies, including dev
uv run pre-commit install    # enable ruff + mypy checks on every commit
```

Windows 10/11 is required (the project depends on the Windows Graphics
Capture API). FFmpeg must be available on `PATH`.

## Before opening a PR

Run the full check suite locally — it mirrors what CI runs:

```bash
uv run pytest                # full test suite
uv run ruff check .          # lint
uv run ruff format --check . # formatting
uv run mypy .                # type-check
```

`pre-commit` (installed above) runs ruff and a curated mypy subset
automatically on every `git commit`, so most of this happens for you —
but running the full suite once before pushing catches anything the
pre-commit subset doesn't cover.

## Code style

The codebase follows the conventions documented in
[`AGENTS.md`](AGENTS.md) — written for AI coding agents, but equally
useful as a human style guide: PEP 8, 79-character lines, type hints on
all functions, docstrings, and the project's architectural patterns (MVC
in `gui/`, the event bus in `core/`, etc.).

Code comments, docstrings, and commit messages in this repo are
conventionally written in Russian (the original author's language). If
you're not comfortable writing Russian, English is fine — a maintainer
can adjust wording during review.

## Pull request expectations

- New logic should come with unit tests. See `tests/unit/` for existing
  patterns and `tests/conftest.py` for the PyQt6 mocking setup used to
  test GUI code headlessly.
- CI (ruff, mypy, pytest) must be green.
- Keep PRs focused — one issue/feature per PR.
- Reference the issue you're fixing (e.g. `Fixes #123`) in the PR
  description.

`good first issue` labels are a good starting point if you're new to the
codebase.
