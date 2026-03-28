"""Synthetic course and sensor-read generation."""

from __future__ import annotations

import json
import random
from pathlib import Path

from hyroxanim.models import AthleteSplits, Course, Segment, Split, to_dict


def build_default_course() -> Course:
    """Return default course with fixed run loop and shifted station detours."""

    start_tunnel = (-0.08, 0.18)
    main_in = (0.30, 0.18)
    main_out = (0.64, 0.18)
    finish_line = (0.92, 0.50)
    station_x_start = 0.18
    station_x_step = 0.08

    segments: list[Segment] = [
        Segment(
            "seg_start_to_main_in",
            "Start tunnel to main in run loop (3 laps)",
            "run",
            start_tunnel,
            main_in,
            points=[
                start_tunnel,
                (0.0, 0.18),
                (main_out[0], 0.18),
                (0.92, 0.18),
                (0.92, 0.82),
                (0.08, 0.82),
                (0.08, 0.18),
                main_out,
                (0.92, 0.18),
                (0.92, 0.82),
                (0.08, 0.82),
                (0.08, 0.18),
                main_out,
                (0.92, 0.18),
                (0.92, 0.82),
                (0.08, 0.82),
                (0.08, 0.18),
                main_in,
            ],
        )
    ]

    for round_num in range(1, 9):
        station_x = station_x_start + (round_num - 1) * station_x_step
        station_in = (station_x, 0.34)
        station_out = (station_x, 0.72)

        segments.append(
            Segment(
                f"seg_main_in_to_station_in_r{round_num}",
                f"Round {round_num} main in to station in",
                "run",
                main_in,
                station_in,
                points=[main_in, (main_in[0], 0.22), (station_x, 0.22), station_in],
            )
        )
        segments.append(
            Segment(
                f"seg_station_in_to_station_out_r{round_num}",
                f"Round {round_num} station in to station out",
                "run",
                station_in,
                station_out,
                points=[station_in, station_out],
            )
        )
        segments.append(
            Segment(
                f"seg_station_out_to_main_out_r{round_num}",
                f"Round {round_num} station out to main out",
                "run",
                station_out,
                main_out,
                points=[station_out, (station_x, 0.22), (main_out[0], 0.22), main_out],
            )
        )

    segments.append(
        Segment(
            "seg_main_out_to_main_in",
            "Main out to main in run loop (3 laps)",
            "run",
            main_out,
            main_in,
            points=[
                main_out,
                (0.92, 0.18),
                (0.92, 0.82),
                (0.08, 0.82),
                (0.08, 0.18),
                main_out,
                (0.92, 0.18),
                (0.92, 0.82),
                (0.08, 0.82),
                (0.08, 0.18),
                main_out,
                (0.92, 0.18),
                (0.92, 0.82),
                (0.08, 0.82),
                (0.08, 0.18),
                main_in,
            ],
        )
    )

    station_8_x = station_x_start + 7 * station_x_step
    station_8_mid = (station_8_x, 0.53)
    finish_line = (0.92, 0.53)
    segments.append(
        Segment(
            "seg_station_in_to_finish",
            "Round 8 station in to finish line",
            "run",
            station_8_mid,
            finish_line,
            points=[station_8_mid, finish_line],
        )
    )

    return Course(
        course_id="hyrox_shifted_station_paths_v2",
        name="HYROX repeated run loop with shifted station detours",
        segments=segments,
    )


def generate_athlete_splits(athlete_id: str, rng: random.Random) -> AthleteSplits:
    """Generate one athlete's raw sensor reads for 8 rounds."""

    splits: list[Split] = []
    timestamp = 0.0

    # Start tunnel event has no round association.
    splits.append(
        Split(
            athlete_id=athlete_id,
            sensor_type="start_tunnel_sensor",
            timestamp=timestamp,
        )
    )

    pace_factor = rng.uniform(0.9, 1.2)
    station_factor = rng.uniform(0.85, 1.15)

    timestamp += rng.uniform(12.0, 18.0) * pace_factor

    for round_num in range(1, 9):
        splits.append(
            Split(
                athlete_id=athlete_id,
                sensor_type="main_in_sensor",
                timestamp=timestamp,
                round=round_num,
            )
        )

        timestamp += rng.uniform(45.0, 85.0) * pace_factor
        splits.append(
            Split(
                athlete_id=athlete_id,
                sensor_type="station_in_sensor",
                timestamp=timestamp,
                round=round_num,
            )
        )

        if round_num < 8:
            timestamp += rng.uniform(90.0, 220.0) * station_factor
            splits.append(
                Split(
                    athlete_id=athlete_id,
                    sensor_type="station_out_sensor",
                    timestamp=timestamp,
                    round=round_num,
                )
            )

            timestamp += rng.uniform(50.0, 95.0) * pace_factor
            splits.append(
                Split(
                    athlete_id=athlete_id,
                    sensor_type="main_out_sensor",
                    timestamp=timestamp,
                    round=round_num,
                )
            )
            timestamp += rng.uniform(45.0, 85.0) * pace_factor
        else:
            # Final interval follows the agreed rule:
            # finish_line_sensor - station_in_sensor
            timestamp += rng.uniform(20.0, 55.0) * pace_factor
            splits.append(
                Split(
                    athlete_id=athlete_id,
                    sensor_type="finish_line_sensor",
                    timestamp=timestamp,
                )
            )

    return AthleteSplits(athlete_id=athlete_id, splits=splits)


def generate_synthetic_dataset(
    num_athletes: int,
    seed: int = 42,
    out_dir: Path = Path("data/synth/raw"),
) -> dict[str, Path]:
    """Generate synthetic course + athlete raw splits and write JSON files."""

    if num_athletes <= 0:
        raise ValueError("num_athletes must be greater than zero")

    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)

    course = build_default_course()
    athletes = [
        generate_athlete_splits(f"athlete_{idx + 1:03d}", rng) for idx in range(num_athletes)
    ]

    course_path = out_dir / "course.json"
    splits_path = out_dir / "athlete_splits.json"

    course_payload = to_dict(course)
    splits_payload = {"athletes": [to_dict(athlete) for athlete in athletes]}

    course_path.write_text(json.dumps(course_payload, indent=2), encoding="utf-8")
    splits_path.write_text(json.dumps(splits_payload, indent=2), encoding="utf-8")

    return {"course_path": course_path, "splits_path": splits_path}
