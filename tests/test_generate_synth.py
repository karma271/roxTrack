import json
from pathlib import Path

from hyroxanim.synth.generate import generate_synthetic_dataset


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_generate_is_seed_reproducible(tmp_path: Path) -> None:
    out_dir_1 = tmp_path / "run1"
    out_dir_2 = tmp_path / "run2"

    generate_synthetic_dataset(num_athletes=3, seed=99, out_dir=out_dir_1)
    generate_synthetic_dataset(num_athletes=3, seed=99, out_dir=out_dir_2)

    payload_1 = _read_json(out_dir_1 / "athlete_splits.json")
    payload_2 = _read_json(out_dir_2 / "athlete_splits.json")

    assert payload_1 == payload_2


def test_generate_required_split_fields(tmp_path: Path) -> None:
    out_dir = tmp_path / "raw"
    generate_synthetic_dataset(num_athletes=1, seed=7, out_dir=out_dir)

    payload = _read_json(out_dir / "athlete_splits.json")
    split = payload["athletes"][0]["splits"][0]

    assert {"athlete_id", "sensor_type", "timestamp", "round"} <= set(split.keys())


def test_generate_n_athletes_count(tmp_path: Path) -> None:
    out_dir = tmp_path / "raw"
    generate_synthetic_dataset(num_athletes=4, seed=5, out_dir=out_dir)

    payload = _read_json(out_dir / "athlete_splits.json")
    assert len(payload["athletes"]) == 4


def test_generate_course_has_shifted_station_segments(tmp_path: Path) -> None:
    out_dir = tmp_path / "raw"
    generate_synthetic_dataset(num_athletes=1, seed=5, out_dir=out_dir)

    course = _read_json(out_dir / "course.json")
    segment_ids = {item["segment_id"] for item in course["segments"]}

    assert "seg_main_out_to_main_in" in segment_ids
    for round_num in range(1, 9):
        assert f"seg_main_in_to_station_in_r{round_num}" in segment_ids
        assert f"seg_station_in_to_station_out_r{round_num}" in segment_ids
        assert f"seg_station_out_to_main_out_r{round_num}" in segment_ids
