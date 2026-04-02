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

## Real Data CSV Workflow (M2)

Use this workflow when your source data is a flat CSV.

### CSV Input Contract

- File is row-per-split with required columns:
  - `athlete_id`
  - `sensor_type`
  - `timestamp`
  - `round`
- `timestamp` can be either numeric seconds (`2430.5`) or clock format (`HH:MM:SS` / `HH:MM:SS.sss`).
- `round` should be blank for `start_tunnel_sensor` and `finish_line_sensor`, and `1..8` for other sensors.

Sample input file is provided at `data/real/raw/athlete_splits.csv`.
For Option B testing (separate real-style sample with 3 athletes and HH:MM:SS timestamps), use `data/real/raw/athlete_splits_real.csv`.

### Convert CSV -> Canonical JSON

Default conversion normalizes each athlete's first event to `0.0` seconds.

```bash
hyroxanim convert-real-csv \
  --csv-path data/real/raw/athlete_splits.csv \
  --out-path data/real/raw/athlete_splits.json
```

Disable normalization if you want to keep source timestamps as-is:

```bash
hyroxanim convert-real-csv \
  --csv-path data/real/raw/athlete_splits.csv \
  --out-path data/real/raw/athlete_splits.json \
  --no-normalize-start
```

### Process Real JSON

```bash
hyroxanim process-real \
  --course-path data/synth/raw/course.json \
  --splits-path data/real/raw/athlete_splits.json \
  --out-dir data/real/processed
```

## Viewer Export (M3 Part 1)

Export compact viewer-ready JSON from an existing course + processed trajectories CSV.

```bash
hyroxanim export-viewer \
  --course-path data/synth/raw/course.json \
  --trajectories-csv data/real/processed/trajectories.csv \
  --out-dir data/viewer
```

This writes:
- `data/viewer/course.json`
- `data/viewer/trajectories.json`

### Minimal Static Viewer (M3 Part 2)

The minimal browser viewer is available at:
- `viewer/index.html`
- `viewer/app.js`

Serve the repo root and open the viewer in your browser:

```bash
python -m http.server 8000
```

Then open:
- `http://localhost:8000/viewer/index.html`

Viewer controls (M3 Part 3):
- Play/Pause button
- Seek slider
- Playback speed selector

### Run Example Viewer (End-to-End)

From repo root:

```bash
# 1) Export compact viewer JSON from existing artifacts
hyroxanim export-viewer \
  --course-path data/synth/raw/course.json \
  --trajectories-csv data/real/processed/trajectories.csv \
  --out-dir data/viewer

# 2) Serve repository files
python -m http.server 8000
```

Then open:
- `http://localhost:8000/viewer/index.html`
