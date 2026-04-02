"""Transform raw sensor reads into time-indexed trajectories."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from hyroxanim.models import AthleteSplits, Course, Segment, Split, TrajectoryPoint, split_from_dict
from hyroxanim.process.interpolate import interpolate_point_at_fraction

Point = tuple[float, float]


def _segment_lookup(course: Course) -> dict[str, list[Point]]:
    lookup: dict[str, list[Point]] = {}
    for segment in course.segments:
        if segment.points:
            lookup[segment.segment_id] = list(segment.points)
        else:
            lookup[segment.segment_id] = [segment.start, segment.end]
    return lookup


def _resolve_leg_segment_id(
    seg: dict[str, list[Point]],
    start_event: Split,
    end_event: Split,
) -> str:
    start_sensor = start_event.sensor_type
    end_sensor = end_event.sensor_type
    round_num = start_event.round

    if start_sensor == "start_tunnel_sensor" and end_sensor == "main_in_sensor":
        return "seg_start_to_main_in"
    if start_sensor == "main_out_sensor" and end_sensor == "main_in_sensor":
        return "seg_main_out_to_main_in"
    if start_sensor == "station_in_sensor" and end_sensor == "finish_line_sensor":
        return "seg_station_in_to_finish"

    if round_num is None:
        raise KeyError(f"Round missing for transition {start_sensor} -> {end_sensor}")

    if start_sensor == "main_in_sensor" and end_sensor == "station_in_sensor":
        round_id = f"seg_main_in_to_station_in_r{round_num}"
        legacy_id = "seg_main_in_to_station_zone"
    elif start_sensor == "station_in_sensor" and end_sensor == "station_out_sensor":
        round_id = f"seg_station_in_to_station_out_r{round_num}"
        legacy_id = "seg_station_zone_to_main_out"
    elif start_sensor == "station_out_sensor" and end_sensor == "main_out_sensor":
        round_id = f"seg_station_out_to_main_out_r{round_num}"
        legacy_id = "seg_station_out_to_main_out"
    else:
        raise KeyError(f"Unsupported transition {start_sensor} -> {end_sensor}")

    if round_id in seg:
        return round_id
    if legacy_id in seg:
        return legacy_id
    raise KeyError(
        f"Missing segment for transition {start_sensor} -> {end_sensor} round {round_num}"
    )


def _index_events(splits: list[Split]) -> dict[tuple[str, int | None], Split]:
    indexed: dict[tuple[str, int | None], Split] = {}
    for split in splits:
        indexed[(split.sensor_type, split.round)] = split
    return indexed


def compute_elapsed_intervals(athlete_splits: AthleteSplits) -> dict[str, float]:
    """Compute elapsed intervals according to the agreed sensor formulas."""

    splits = sorted(athlete_splits.splits, key=lambda item: item.timestamp)
    event = _index_events(splits)
    elapsed: dict[str, float] = {}

    start = event[("start_tunnel_sensor", None)]
    main_in_1 = event[("main_in_sensor", 1)]
    elapsed["R1"] = main_in_1.timestamp - start.timestamp

    for round_num in range(1, 9):
        main_in = event[("main_in_sensor", round_num)]
        station_in = event[("station_in_sensor", round_num)]
        elapsed[f"Rox In {round_num}"] = station_in.timestamp - main_in.timestamp

        if round_num < 8:
            station_out = event[("station_out_sensor", round_num)]
            main_out = event[("main_out_sensor", round_num)]
            elapsed[f"S{round_num}"] = station_out.timestamp - station_in.timestamp
            elapsed[f"Rox Out {round_num}"] = main_out.timestamp - station_out.timestamp
            next_main_in = event[("main_in_sensor", round_num + 1)]
            elapsed[f"R{round_num + 1}"] = next_main_in.timestamp - main_out.timestamp
        else:
            finish = event[("finish_line_sensor", None)]
            elapsed["S8"] = finish.timestamp - station_in.timestamp

    return elapsed


def _sample_leg(
    athlete_id: str,
    start_t: float,
    end_t: float,
    polyline: list[Point],
    dt: float,
) -> list[TrajectoryPoint]:
    if end_t <= start_t:
        return []

    points: list[TrajectoryPoint] = []
    t = start_t
    duration = end_t - start_t

    while t < end_t:
        fraction = (t - start_t) / duration
        x, y = interpolate_point_at_fraction(polyline, fraction)
        points.append(TrajectoryPoint(athlete_id=athlete_id, t=round(t, 6), x=x, y=y))
        t += dt

    x_end, y_end = interpolate_point_at_fraction(polyline, 1.0)
    points.append(TrajectoryPoint(athlete_id=athlete_id, t=round(end_t, 6), x=x_end, y=y_end))
    return points


def transform_athlete_to_trajectory(
    athlete_splits: AthleteSplits,
    course: Course,
    dt: float = 1.0,
) -> list[TrajectoryPoint]:
    """Convert one athlete's sensor reads into sampled trajectory points."""

    if dt <= 0:
        raise ValueError("dt must be greater than zero")

    seg = _segment_lookup(course)
    event = _index_events(athlete_splits.splits)
    athlete_id = athlete_splits.athlete_id

    legs: list[tuple[Split, Split]] = []
    legs.append((event[("start_tunnel_sensor", None)], event[("main_in_sensor", 1)]))

    for round_num in range(1, 9):
        legs.append((event[("main_in_sensor", round_num)], event[("station_in_sensor", round_num)]))
        if round_num < 8:
            legs.append(
                (event[("station_in_sensor", round_num)], event[("station_out_sensor", round_num)])
            )
            legs.append(
                (event[("station_out_sensor", round_num)], event[("main_out_sensor", round_num)])
            )
            legs.append(
                (event[("main_out_sensor", round_num)], event[("main_in_sensor", round_num + 1)])
            )
        else:
            legs.append(
                (event[("station_in_sensor", round_num)], event[("finish_line_sensor", None)])
            )

    trajectory: list[TrajectoryPoint] = []
    for index, (start_event, end_event) in enumerate(legs):
        segment_id = _resolve_leg_segment_id(seg, start_event, end_event)
        polyline = seg[segment_id]
        sampled = _sample_leg(
            athlete_id=athlete_id,
            start_t=start_event.timestamp,
            end_t=end_event.timestamp,
            polyline=polyline,
            dt=dt,
        )
        if index > 0 and sampled:
            sampled = sampled[1:]
        trajectory.extend(sampled)

    return trajectory


def transform_all_athletes(
    course: Course,
    athletes: list[AthleteSplits],
    dt: float = 1.0,
) -> dict[str, list[TrajectoryPoint]]:
    """Transform all athletes into trajectories keyed by athlete_id."""

    return {
        athlete.athlete_id: transform_athlete_to_trajectory(athlete, course, dt=dt)
        for athlete in athletes
    }


def get_position(trajectory: list[TrajectoryPoint], t: float) -> tuple[float, float]:
    """Return position of an athlete at time t from a sampled trajectory."""

    if not trajectory:
        raise ValueError("trajectory is empty")

    if t <= trajectory[0].t:
        return (trajectory[0].x, trajectory[0].y)
    if t >= trajectory[-1].t:
        return (trajectory[-1].x, trajectory[-1].y)

    left = trajectory[0]
    for right in trajectory[1:]:
        if right.t >= t:
            span = right.t - left.t
            if span <= 0:
                return (right.x, right.y)
            ratio = (t - left.t) / span
            x = left.x + (right.x - left.x) * ratio
            y = left.y + (right.y - left.y) * ratio
            return (x, y)
        left = right

    return (trajectory[-1].x, trajectory[-1].y)


def _load_course(path: Path) -> Course:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return Course(
        course_id=payload["course_id"],
        name=payload["name"],
        segments=[
            Segment(
                segment_id=item["segment_id"],
                name=item["name"],
                kind=item["kind"],
                start=(float(item["start"][0]), float(item["start"][1])),
                end=(float(item["end"][0]), float(item["end"][1])),
                points=[
                    (float(point[0]), float(point[1]))
                    for point in item.get("points", [])
                ]
                or None,
            )
            for item in payload["segments"]
        ],
    )


def _load_athletes(path: Path) -> list[AthleteSplits]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    athletes: list[AthleteSplits] = []
    for item in payload["athletes"]:
        splits = [split_from_dict(split_item) for split_item in item["splits"]]
        athletes.append(AthleteSplits(athlete_id=item["athlete_id"], splits=splits))
    return athletes


def write_processed_output(
    trajectories: dict[str, list[TrajectoryPoint]],
    out_dir: Path,
) -> dict[str, Path]:
    """Write processed trajectories to CSV + JSON."""

    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "trajectories.csv"
    json_path = out_dir / "trajectories.json"

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["athlete_id", "t", "x", "y"])
        writer.writeheader()
        for athlete_points in trajectories.values():
            for point in athlete_points:
                writer.writerow(asdict(point))

    json_payload = {
        athlete_id: [asdict(point) for point in athlete_points]
        for athlete_id, athlete_points in trajectories.items()
    }
    json_path.write_text(json.dumps(json_payload, indent=2), encoding="utf-8")
    return {"csv_path": csv_path, "json_path": json_path}


def transform_raw_files(
    course_path: Path = Path("data/synth/raw/course.json"),
    splits_path: Path = Path("data/synth/raw/athlete_splits.json"),
    out_dir: Path = Path("data/synth/processed"),
    dt: float = 1.0,
) -> dict[str, Path]:
    """Load raw files, transform to trajectories, and write processed outputs."""

    course = _load_course(course_path)
    athletes = _load_athletes(splits_path)
    trajectories = transform_all_athletes(course=course, athletes=athletes, dt=dt)
    return write_processed_output(trajectories, out_dir)
