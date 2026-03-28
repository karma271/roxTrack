import random
from pathlib import Path

from hyroxanim.models import AthleteSplits, Split
from hyroxanim.process.transform import (
    compute_elapsed_intervals,
    get_position,
    transform_all_athletes,
    transform_raw_files,
)
from hyroxanim.synth.generate import (
    build_default_course,
    generate_athlete_splits,
    generate_synthetic_dataset,
)


def test_trajectory_time_is_monotonic() -> None:
    course = build_default_course()
    athlete = generate_athlete_splits("athlete_001", random.Random(42))
    trajectories = transform_all_athletes(course=course, athletes=[athlete], dt=1.0)
    points = trajectories["athlete_001"]
    assert all(points[idx].t <= points[idx + 1].t for idx in range(len(points) - 1))


def test_trajectory_start_and_end_positions() -> None:
    course = build_default_course()
    athlete = generate_athlete_splits("athlete_001", random.Random(7))
    trajectories = transform_all_athletes(course=course, athletes=[athlete], dt=2.0)
    points = trajectories["athlete_001"]
    assert (points[0].x, points[0].y) == (-0.08, 0.18)
    assert (round(points[-1].x, 6), round(points[-1].y, 6)) == (0.92, 0.53)


def test_get_position_lookup_is_direct() -> None:
    course = build_default_course()
    athlete = generate_athlete_splits("athlete_001", random.Random(9))
    trajectories = transform_all_athletes(course=course, athletes=[athlete], dt=1.0)
    points = trajectories["athlete_001"]
    mid_t = points[len(points) // 2].t
    x, y = get_position(points, mid_t)
    assert isinstance(x, float)
    assert isinstance(y, float)


def test_elapsed_time_formulas_include_round_8_rule() -> None:
    splits = [
        Split("athlete_001", "start_tunnel_sensor", 0.0),
        Split("athlete_001", "main_in_sensor", 10.0, 1),
        Split("athlete_001", "station_in_sensor", 20.0, 1),
        Split("athlete_001", "station_out_sensor", 50.0, 1),
        Split("athlete_001", "main_out_sensor", 60.0, 1),
        Split("athlete_001", "main_in_sensor", 70.0, 2),
        Split("athlete_001", "station_in_sensor", 90.0, 2),
        Split("athlete_001", "station_out_sensor", 120.0, 2),
        Split("athlete_001", "main_out_sensor", 130.0, 2),
        Split("athlete_001", "main_in_sensor", 140.0, 3),
        Split("athlete_001", "station_in_sensor", 160.0, 3),
        Split("athlete_001", "station_out_sensor", 190.0, 3),
        Split("athlete_001", "main_out_sensor", 200.0, 3),
        Split("athlete_001", "main_in_sensor", 210.0, 4),
        Split("athlete_001", "station_in_sensor", 230.0, 4),
        Split("athlete_001", "station_out_sensor", 260.0, 4),
        Split("athlete_001", "main_out_sensor", 270.0, 4),
        Split("athlete_001", "main_in_sensor", 280.0, 5),
        Split("athlete_001", "station_in_sensor", 300.0, 5),
        Split("athlete_001", "station_out_sensor", 330.0, 5),
        Split("athlete_001", "main_out_sensor", 340.0, 5),
        Split("athlete_001", "main_in_sensor", 350.0, 6),
        Split("athlete_001", "station_in_sensor", 370.0, 6),
        Split("athlete_001", "station_out_sensor", 400.0, 6),
        Split("athlete_001", "main_out_sensor", 410.0, 6),
        Split("athlete_001", "main_in_sensor", 420.0, 7),
        Split("athlete_001", "station_in_sensor", 440.0, 7),
        Split("athlete_001", "station_out_sensor", 470.0, 7),
        Split("athlete_001", "main_out_sensor", 480.0, 7),
        Split("athlete_001", "main_in_sensor", 490.0, 8),
        Split("athlete_001", "station_in_sensor", 510.0, 8),
        Split("athlete_001", "finish_line_sensor", 540.0),
    ]
    athlete = AthleteSplits(athlete_id="athlete_001", splits=splits)

    elapsed = compute_elapsed_intervals(athlete)
    assert elapsed["R1"] == 10.0
    assert elapsed["Rox In 1"] == 10.0
    assert elapsed["S1"] == 30.0
    assert elapsed["Rox Out 1"] == 10.0
    assert elapsed["R8"] == 10.0
    assert elapsed["S8"] == 30.0


def test_transform_raw_files_writes_outputs(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    paths = generate_synthetic_dataset(num_athletes=2, seed=11, out_dir=raw_dir)

    out = transform_raw_files(
        course_path=paths["course_path"],
        splits_path=paths["splits_path"],
        out_dir=processed_dir,
        dt=1.0,
    )
    assert out["csv_path"].exists()
    assert out["json_path"].exists()
