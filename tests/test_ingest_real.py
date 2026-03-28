import json
import random
from pathlib import Path

import pytest

from hyroxanim.ingest.real import ingest_real_splits, process_real_files, validate_course_segments
from hyroxanim.models import Segment, to_dict
from hyroxanim.synth.generate import build_default_course, generate_athlete_splits


def _write_course(path: Path) -> Path:
    course = build_default_course()
    path.write_text(json.dumps(to_dict(course), indent=2), encoding="utf-8")
    return path


def _write_real_splits(
    path: Path,
    *,
    shuffled: bool = False,
    include_unknown_sensor: bool = False,
) -> Path:
    athlete = generate_athlete_splits("athlete_001", random.Random(7))
    splits = [to_dict(split) for split in athlete.splits]
    if include_unknown_sensor:
        splits.append(
            {
                "athlete_id": "athlete_001",
                "sensor_type": "mystery_sensor",
                "timestamp": splits[-1]["timestamp"] + 1.0,
                "round": None,
            }
        )
    if shuffled:
        splits[1], splits[2] = splits[2], splits[1]

    payload = {"athletes": [{"athlete_id": "athlete_001", "splits": splits}]}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_ingest_real_splits_warns_on_out_of_order_and_unknown_sensor(tmp_path: Path) -> None:
    splits_path = _write_real_splits(
        tmp_path / "real_splits.json",
        shuffled=True,
        include_unknown_sensor=True,
    )

    result = ingest_real_splits(splits_path)

    assert not result.errors
    warning_codes = {warning.code for warning in result.warnings}
    assert "out_of_order_splits" in warning_codes
    assert "unknown_sensor" in warning_codes
    assert len(result.athletes) == 1


def test_process_real_files_writes_outputs_for_valid_input(tmp_path: Path) -> None:
    course_path = _write_course(tmp_path / "course.json")
    splits_path = _write_real_splits(tmp_path / "real_splits.json")

    result = process_real_files(
        course_path=course_path,
        splits_path=splits_path,
        out_dir=tmp_path / "processed",
        dt=1.0,
    )

    assert result.output_paths["csv_path"].exists()
    assert result.output_paths["json_path"].exists()
    assert result.processed_athletes == 1


def test_process_real_files_raises_for_non_positive_time_delta(tmp_path: Path) -> None:
    course_path = _write_course(tmp_path / "course.json")
    splits_path = _write_real_splits(tmp_path / "real_splits.json")
    payload = json.loads(splits_path.read_text(encoding="utf-8"))
    athlete_splits = payload["athletes"][0]["splits"]

    main_in_r1 = next(
        split
        for split in athlete_splits
        if split["sensor_type"] == "main_in_sensor" and split["round"] == 1
    )
    station_in_r1 = next(
        split
        for split in athlete_splits
        if split["sensor_type"] == "station_in_sensor" and split["round"] == 1
    )
    station_in_r1["timestamp"] = main_in_r1["timestamp"]
    splits_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="non_positive_time_delta"):
        process_real_files(
            course_path=course_path,
            splits_path=splits_path,
            out_dir=tmp_path / "processed",
            dt=1.0,
        )


def test_validate_course_segments_reports_unknown_segment() -> None:
    course = build_default_course()
    course.segments.append(
        Segment(
            segment_id="seg_unused_demo",
            name="Unused test segment",
            kind="run",
            start=(0.0, 0.0),
            end=(1.0, 1.0),
            points=[(0.0, 0.0), (1.0, 1.0)],
        )
    )
    warnings, errors = validate_course_segments(course)
    assert not errors
    assert any(item.code == "unknown_segment" for item in warnings)


def test_validate_course_segments_allows_round_8_unused_segments() -> None:
    course = build_default_course()
    warnings, errors = validate_course_segments(course)
    assert not errors
    warning_segments = {item.segment_id for item in warnings}
    assert "seg_station_in_to_station_out_r8" not in warning_segments
    assert "seg_station_out_to_main_out_r8" not in warning_segments


def test_process_real_files_skips_invalid_athlete_and_continues(tmp_path: Path) -> None:
    course_path = _write_course(tmp_path / "course.json")
    good = generate_athlete_splits("athlete_good", random.Random(17))
    bad = generate_athlete_splits("athlete_bad", random.Random(23))

    bad_splits = [to_dict(split) for split in bad.splits]
    bad_splits = [
        split
        for split in bad_splits
        if not (split["sensor_type"] == "station_out_sensor" and split["round"] == 2)
    ]

    payload = {
        "athletes": [
            {"athlete_id": "athlete_good", "splits": [to_dict(split) for split in good.splits]},
            {"athlete_id": "athlete_bad", "splits": bad_splits},
        ]
    }
    splits_path = tmp_path / "real_splits.json"
    splits_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = process_real_files(
        course_path=course_path,
        splits_path=splits_path,
        out_dir=tmp_path / "processed",
        dt=1.0,
    )

    assert result.output_paths["csv_path"].exists()
    assert result.processed_athletes == 1
    assert result.total_athletes == 2
    assert result.skipped_athletes == ["athlete_bad"]
    assert any(issue.code == "missing_split" for issue in result.errors)


def test_process_real_files_strict_raises_on_athlete_errors(tmp_path: Path) -> None:
    course_path = _write_course(tmp_path / "course.json")
    good = generate_athlete_splits("athlete_good", random.Random(17))
    bad = generate_athlete_splits("athlete_bad", random.Random(23))

    bad_splits = [to_dict(split) for split in bad.splits]
    bad_splits = [
        split
        for split in bad_splits
        if not (split["sensor_type"] == "station_out_sensor" and split["round"] == 2)
    ]

    payload = {
        "athletes": [
            {"athlete_id": "athlete_good", "splits": [to_dict(split) for split in good.splits]},
            {"athlete_id": "athlete_bad", "splits": bad_splits},
        ]
    }
    splits_path = tmp_path / "real_splits.json"
    splits_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="missing_split"):
        process_real_files(
            course_path=course_path,
            splits_path=splits_path,
            out_dir=tmp_path / "processed",
            dt=1.0,
            strict=True,
        )
