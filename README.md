# roxTrack

> HYROX athlete race animation tracker

Animate HYROX athletes moving through a course over time. The project starts with a simple Python prototype (synthetic data first), then expands later.

## Current Scope

Active work stops at **Milestone 1D** (synthetic data pipeline + Python animation proof-of-life).

## Document Ownership

- `README.md`: product context, boundaries, and engineering conventions.
- `task.md`: execution checklist, milestone tracking, and acceptance status.
- `plan.md`: archived draft notes (superseded by `task.md`).

## Goals

- Ingest athlete splits and course definition.
- Produce animation-ready trajectories: `t -> (x, y)` per athlete.
- Prototype animation in Python first (`matplotlib` is enough for now).
- Keep architecture simple and easy to iterate.

## Non-goals (for now)

- No backend, auth, or deployment.
- No advanced biomechanics modeling (linear interpolation is fine).
- No extra frameworks before they are required.

## Engineering Conventions

- Use `uv` for environment and dependency management.
- Use `ruff` for linting and formatting.
- Use `pytest` for tests.
- Prefer dataclasses, pure functions, and modular code.
- Use modern Python type hints.
- Add docstrings for non-trivial functions.

## Data Contract

Canonical data models will live in `src/hyroxanim/models.py` (`Segment`, `Course`, `Split`, `AthleteSplits`, `TrajectoryPoint`). Keep the schema stable; if it changes, update generator, transformer, and tests together.

## Sensor Event Semantics (M1)

- Canonical event order per round: `main_in_sensor -> station_in_sensor -> station_out_sensor -> main_out_sensor`.
- Race starts with `start_tunnel_sensor` and ends with `finish_line_sensor`.
- Round 8 terminal interval follows your sheet: `finish_line_sensor - station_in_sensor`.
- M1 uses a normalized loop path (not physically measured distances yet).

## Quickstart

Python: target a modern 3.12+ runtime.

```bash
uv sync
ruff check .
pytest
```
