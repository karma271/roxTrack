"""Export compact viewer-ready JSON artifacts."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ViewerExportResult:
    """Paths and counts for viewer export output."""

    course_path: Path
    trajectories_path: Path
    athlete_count: int
    point_count: int


def _polyline_for_segment(segment: dict) -> list[list[float]]:
    points = segment.get("points") or []
    if points:
        return [[float(point[0]), float(point[1])] for point in points]
    start = segment["start"]
    end = segment["end"]
    return [[float(start[0]), float(start[1])], [float(end[0]), float(end[1])]]


def _load_compact_course(course_path: Path) -> dict:
    raw = json.loads(course_path.read_text(encoding="utf-8"))
    segments = []
    for segment in raw.get("segments", []):
        segments.append(
            {
                "id": segment["segment_id"],
                "kind": segment["kind"],
                "points": _polyline_for_segment(segment),
            }
        )
    return {
        "course_id": raw["course_id"],
        "name": raw["name"],
        "segments": segments,
    }


def _load_compact_trajectories(trajectories_csv: Path) -> tuple[list[dict], dict, int]:
    athletes: dict[str, list[list[float]]] = {}
    t_min: float | None = None
    t_max: float | None = None
    point_count = 0

    with trajectories_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"athlete_id", "t", "x", "y"}
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise ValueError(f"Trajectories CSV missing required columns: {', '.join(missing)}")

        for row in reader:
            athlete_id = str(row["athlete_id"])
            t = float(row["t"])
            x = float(row["x"])
            y = float(row["y"])
            athletes.setdefault(athlete_id, []).append([t, x, y])
            t_min = t if t_min is None else min(t_min, t)
            t_max = t if t_max is None else max(t_max, t)
            point_count += 1

    payload = []
    for athlete_id in sorted(athletes):
        points = sorted(athletes[athlete_id], key=lambda item: item[0])
        payload.append({"athlete_id": athlete_id, "points": points})

    meta = {
        "athlete_count": len(payload),
        "point_count": point_count,
        "t_start": 0.0 if t_min is None else t_min,
        "t_end": 0.0 if t_max is None else t_max,
    }
    return payload, meta, point_count


def export_viewer_files(
    course_path: Path,
    trajectories_csv: Path,
    out_dir: Path = Path("data/viewer"),
) -> ViewerExportResult:
    """Export compact viewer JSON files from existing artifacts."""

    compact_course = _load_compact_course(course_path)
    compact_trajectories, meta, point_count = _load_compact_trajectories(trajectories_csv)

    out_dir.mkdir(parents=True, exist_ok=True)
    export_course_path = out_dir / "course.json"
    export_trajectories_path = out_dir / "trajectories.json"

    export_course_path.write_text(json.dumps(compact_course, indent=2), encoding="utf-8")
    trajectories_payload = {"meta": meta, "athletes": compact_trajectories}
    export_trajectories_path.write_text(
        json.dumps(trajectories_payload, indent=2),
        encoding="utf-8",
    )

    return ViewerExportResult(
        course_path=export_course_path,
        trajectories_path=export_trajectories_path,
        athlete_count=len(compact_trajectories),
        point_count=point_count,
    )

