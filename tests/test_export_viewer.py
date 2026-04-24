import json
from pathlib import Path

from hyroxanim.export.viewer import export_viewer_files
from hyroxanim.process.transform import transform_raw_files
from hyroxanim.synth.generate import generate_synthetic_dataset


def test_export_viewer_files_writes_compact_json(tmp_path: Path) -> None:
    raw_paths = generate_synthetic_dataset(num_athletes=2, seed=5, out_dir=tmp_path / "raw")
    processed = transform_raw_files(
        course_path=raw_paths["course_path"],
        splits_path=raw_paths["splits_path"],
        out_dir=tmp_path / "processed",
        dt=1.0,
    )

    result = export_viewer_files(
        course_path=raw_paths["course_path"],
        trajectories_csv=processed["csv_path"],
        out_dir=tmp_path / "viewer",
    )

    assert result.course_path.exists()
    assert result.trajectories_path.exists()
    assert result.athlete_count == 2
    assert result.point_count > 0

    course_payload = json.loads(result.course_path.read_text(encoding="utf-8"))
    trajectories_payload = json.loads(result.trajectories_path.read_text(encoding="utf-8"))

    assert "segments" in course_payload
    assert "meta" in trajectories_payload
    assert "athletes" in trajectories_payload
    assert trajectories_payload["meta"]["athlete_count"] == 2
    first_athlete = trajectories_payload["athletes"][0]
    assert "points" in first_athlete
    assert len(first_athlete["points"][0]) == 3
