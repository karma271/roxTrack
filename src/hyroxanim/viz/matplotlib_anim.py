"""Matplotlib animation proof-of-life for processed trajectories."""

from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path

import matplotlib.animation as animation
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from hyroxanim.models import TrajectoryPoint

Point = tuple[float, float]
CANVAS_MAX_X = 3.0
CANVAS_MAX_Y = 3.0
TARGET_CANVAS_COVERAGE = 0.85
# Fit comfortably on a 16-inch laptop screen during interactive preview.
FIGURE_WIDTH_IN = 14.0
FIGURE_HEIGHT_IN = 8.0
FIGURE_DPI = 100
COURSE_LINE_WIDTH = 2.0
ATHLETE_DOT_SIZE = 50.0
FINISH_PARKING_X_NUDGE = 0.06
STATION_EXIT_TURN_Y_NUDGE = 0.15
ATHLETE_LABEL_OFFSET = 0.01
START_BOX_WIDTH = 0.3
START_BOX_HEIGHT = 0.18
FINISH_BOX_WIDTH = 0.16
FINISH_BOX_MIN_HEIGHT = 0.6
FINISH_BOX_EXTRA_HEIGHT = 0.1
FINISH_BOX_X_OFFSET = 0.12
BOX_LINE_WIDTH = 1.8
DECORATION_TEXT_SIZE = 9
MAIN_LABEL_Y_OFFSET = 0.04
FIGURE_NOTE_TEXT = "NOTE: Space-time not drawn to scale"
FIGURE_NOTE_SIZE = 8
FIGURE_NOTE_COLOR = "#9CA3AF"
PASTEL_COLORS = [
    "#F4A7B9",
    "#A8D8EA",
    "#B8E0A5",
    "#F9D29D",
    "#CDB4DB",
    "#FFD6E0",
    "#BDE0FE",
    "#D9ED92",
]


def load_course_polylines(course_path: Path) -> list[list[Point]]:
    """Load course segment polylines from course JSON."""

    payload = json.loads(course_path.read_text(encoding="utf-8"))
    polylines: list[list[Point]] = []
    for segment in payload["segments"]:
        points_raw = segment.get("points")
        if points_raw:
            points = [(float(point[0]), float(point[1])) for point in points_raw]
            polylines.append(points)
        else:
            start = (float(segment["start"][0]), float(segment["start"][1]))
            end = (float(segment["end"][0]), float(segment["end"][1]))
            polylines.append([start, end])
    return polylines


def _load_station_parking_layout(course_path: Path) -> dict[int, tuple[Point, float]]:
    """Load station parking midpoint and station length keyed by round."""

    payload = json.loads(course_path.read_text(encoding="utf-8"))
    parking: dict[int, tuple[Point, float]] = {}
    for segment in payload["segments"]:
        segment_id = str(segment.get("segment_id", ""))
        match = re.fullmatch(r"seg_station_in_to_station_out_r(\d+)", segment_id)
        if not match:
            continue
        round_num = int(match.group(1))
        start = (float(segment["start"][0]), float(segment["start"][1]))
        end = (float(segment["end"][0]), float(segment["end"][1]))
        midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
        length = abs(end[1] - start[1])
        parking[round_num] = (midpoint, length)
    return parking


def _load_finish_anchor(course_path: Path) -> Point:
    """Load finish-line point from course JSON."""

    payload = json.loads(course_path.read_text(encoding="utf-8"))
    for segment in payload["segments"]:
        if segment.get("segment_id") != "seg_station_in_to_finish":
            continue
        points_raw = segment.get("points")
        if points_raw:
            end = points_raw[-1]
            return (float(end[0]), float(end[1]))
        end_raw = segment["end"]
        return (float(end_raw[0]), float(end_raw[1]))
    raise ValueError("Finish segment seg_station_in_to_finish not found in course")


def _load_start_anchor(course_path: Path) -> Point:
    """Load start-tunnel point from course JSON."""

    payload = json.loads(course_path.read_text(encoding="utf-8"))
    for segment in payload["segments"]:
        if segment.get("segment_id") != "seg_start_to_main_in":
            continue
        points_raw = segment.get("points")
        if points_raw:
            start = points_raw[0]
            return (float(start[0]), float(start[1]))
        start_raw = segment["start"]
        return (float(start_raw[0]), float(start_raw[1]))
    raise ValueError("Start segment seg_start_to_main_in not found in course")


def _load_main_loop_anchors(course_path: Path) -> tuple[Point, Point]:
    """Load main-out and main-in anchor points."""

    payload = json.loads(course_path.read_text(encoding="utf-8"))
    for segment in payload["segments"]:
        if segment.get("segment_id") != "seg_main_out_to_main_in":
            continue
        points_raw = segment.get("points")
        if points_raw:
            main_out = points_raw[0]
            main_in = points_raw[-1]
            return (
                (float(main_out[0]), float(main_out[1])),
                (float(main_in[0]), float(main_in[1])),
            )
        start_raw = segment["start"]
        end_raw = segment["end"]
        return (
            (float(start_raw[0]), float(start_raw[1])),
            (float(end_raw[0]), float(end_raw[1])),
        )
    raise ValueError("Main loop segment seg_main_out_to_main_in not found in course")


def _load_station_out_points(course_path: Path) -> dict[int, Point]:
    """Load station-out anchors keyed by round number."""

    payload = json.loads(course_path.read_text(encoding="utf-8"))
    station_out: dict[int, Point] = {}
    for segment in payload["segments"]:
        segment_id = str(segment.get("segment_id", ""))
        match = re.fullmatch(r"seg_station_in_to_station_out_r(\d+)", segment_id)
        if not match:
            continue
        round_num = int(match.group(1))
        end = (float(segment["end"][0]), float(segment["end"][1]))
        station_out[round_num] = end
    return station_out


def _load_station_windows(
    splits_path: Path,
) -> tuple[dict[str, dict[int, tuple[float, float]]], dict[int, dict[str, int]]]:
    """Load station windows and station-in arrival order by round."""

    payload = json.loads(splits_path.read_text(encoding="utf-8"))
    windows: dict[str, dict[int, tuple[float, float]]] = {}
    arrivals_by_round: dict[int, list[tuple[str, float]]] = {}
    for athlete_payload in payload["athletes"]:
        athlete_id = str(athlete_payload["athlete_id"])
        station_in_for_athlete: dict[int, float] = {}
        station_out_by_round: dict[int, float] = {}

        for split in athlete_payload["splits"]:
            sensor_type = str(split["sensor_type"])
            round_num = split.get("round")
            if round_num is None:
                continue
            round_idx = int(round_num)
            timestamp = float(split["timestamp"])
            if sensor_type == "station_in_sensor":
                station_in_for_athlete[round_idx] = timestamp
                arrivals_by_round.setdefault(round_idx, []).append((athlete_id, timestamp))
            elif sensor_type == "station_out_sensor":
                station_out_by_round[round_idx] = timestamp

        windows[athlete_id] = {}
        for round_idx, start_t in station_in_for_athlete.items():
            end_t = station_out_by_round.get(round_idx)
            if end_t is not None and end_t >= start_t:
                windows[athlete_id][round_idx] = (start_t, end_t)

    arrival_order_by_round: dict[int, dict[str, int]] = {}
    for round_idx, arrivals in arrivals_by_round.items():
        ranked = sorted(arrivals, key=lambda item: item[1])
        arrival_order_by_round[round_idx] = {
            athlete_id: rank for rank, (athlete_id, _) in enumerate(ranked)
        }
    return windows, arrival_order_by_round


def _parking_offset(slot_idx: int, slot_count: int, station_length_canvas: float) -> Point:
    """Return vertical parking offsets spread over 90% station length."""

    usable = max(station_length_canvas * 0.9, 0.06)
    spacing = usable / max(slot_count, 1)
    start = -usable / 2.0 + spacing / 2.0
    return (0.0, start + spacing * slot_idx)


def _rank_by_race_position(
    athlete_ids: list[str],
    trajectories: dict[str, list[TrajectoryPoint]],
    frame_idx: int,
) -> dict[str, int]:
    """Return 1-based race ranks using progress fraction at this frame."""

    progress: list[tuple[str, float]] = []
    for athlete_id in athlete_ids:
        points = trajectories[athlete_id]
        point_idx = min(frame_idx, len(points) - 1)
        denominator = max(len(points) - 1, 1)
        fraction = point_idx / denominator
        progress.append((athlete_id, fraction))

    ranked = sorted(progress, key=lambda item: item[1], reverse=True)
    return {athlete_id: rank + 1 for rank, (athlete_id, _) in enumerate(ranked)}


def _display_athlete_id(athlete_id: str) -> str:
    """Return compact athlete label (e.g., athlete_001 -> A1)."""

    match = re.fullmatch(r"athlete_(\d+)", athlete_id)
    if not match:
        return athlete_id
    return f"A{int(match.group(1))}"


def _scale_point_xy(point: Point, render_scale_x: float, render_scale_y: float) -> Point:
    """Scale a 2D point with independent x/y scales."""

    return (point[0] * render_scale_x, point[1] * render_scale_y)


def _interpolate_two_segment_path(start: Point, turn: Point, end: Point, fraction: float) -> Point:
    """Interpolate across start->turn->end with arc-length weighting."""

    f = max(0.0, min(1.0, fraction))
    len_a = math.dist(start, turn)
    len_b = math.dist(turn, end)
    total = len_a + len_b
    if total <= 0:
        return end

    pivot = len_a / total
    if f <= pivot and len_a > 0:
        local = f / pivot if pivot > 0 else 1.0
        return (
            start[0] + (turn[0] - start[0]) * local,
            start[1] + (turn[1] - start[1]) * local,
        )

    if len_b <= 0:
        return end

    local = (f - pivot) / (1.0 - pivot) if pivot < 1.0 else 1.0
    return (
        turn[0] + (end[0] - turn[0]) * local,
        turn[1] + (end[1] - turn[1]) * local,
    )


def load_trajectories_from_csv(csv_path: Path) -> dict[str, list[TrajectoryPoint]]:
    """Load trajectory rows from processed CSV grouped by athlete."""

    grouped: dict[str, list[TrajectoryPoint]] = {}
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            athlete_id = str(row["athlete_id"])
            grouped.setdefault(athlete_id, []).append(
                TrajectoryPoint(
                    athlete_id=athlete_id,
                    t=float(row["t"]),
                    x=float(row["x"]),
                    y=float(row["y"]),
                )
            )

    for athlete_id in grouped:
        grouped[athlete_id].sort(key=lambda item: item.t)
    return grouped


def animate_processed_trajectories(
    course_path: Path = Path("data/synth/raw/course.json"),
    trajectories_csv: Path = Path("data/synth/processed/trajectories.csv"),
    splits_path: Path | None = None,
    interval_ms: int = 60,
    no_show: bool = False,
    max_frames: int | None = None,
    show_decorations: bool = True,
) -> None:
    """Plot course and animate athlete positions over time."""

    course_polylines = load_course_polylines(course_path)
    trajectories = load_trajectories_from_csv(trajectories_csv)
    if not trajectories:
        raise ValueError("No trajectories found to animate")
    station_parking_layout = _load_station_parking_layout(course_path)
    start_anchor = _load_start_anchor(course_path)
    main_out_anchor, main_in_anchor = _load_main_loop_anchors(course_path)
    finish_anchor = _load_finish_anchor(course_path)
    station_out_points = _load_station_out_points(course_path)
    if splits_path:
        station_windows, arrival_order_by_round = _load_station_windows(splits_path)
    else:
        station_windows = {}
        arrival_order_by_round = {}
    finish_order = {
        athlete_id: rank
        for rank, (athlete_id, _) in enumerate(
            sorted(
                ((athlete_id, points[-1].t) for athlete_id, points in trajectories.items()),
                key=lambda item: item[1],
            )
        )
    }
    athlete_ids = sorted(trajectories.keys())
    athlete_colors = [PASTEL_COLORS[idx % len(PASTEL_COLORS)] for idx in range(len(athlete_ids))]
    max_len = max(len(points) for points in trajectories.values())
    frame_count = min(max_len, max_frames) if max_frames is not None else max_len
    if frame_count <= 0:
        raise ValueError("No frames available for animation")

    fig, ax = plt.subplots(figsize=(FIGURE_WIDTH_IN, FIGURE_HEIGHT_IN), dpi=FIGURE_DPI)

    all_course_points = [point for polyline in course_polylines for point in polyline]
    all_trajectory_points = [
        (point.x, point.y) for points in trajectories.values() for point in points
    ]
    all_world_points = [*all_course_points, *all_trajectory_points]
    min_course_x = min(point[0] for point in all_course_points)
    max_course_x = max(point[0] for point in all_course_points)
    min_course_y = min(point[1] for point in all_course_points)
    max_course_y = max(point[1] for point in all_course_points)
    world_min_x = min(point[0] for point in all_world_points)
    world_max_x = max(point[0] for point in all_world_points)
    world_min_y = min(point[1] for point in all_world_points)
    world_max_y = max(point[1] for point in all_world_points)
    world_width = max(world_max_x - world_min_x, 1e-9)
    world_height = max(world_max_y - world_min_y, 1e-9)
    target_width = CANVAS_MAX_X * TARGET_CANVAS_COVERAGE
    target_height = CANVAS_MAX_Y * TARGET_CANVAS_COVERAGE
    render_scale_x = target_width / world_width
    render_scale_y = target_height / world_height
    course_center_x = (min_course_x + max_course_x) / 2.0
    course_center_y = (min_course_y + max_course_y) / 2.0
    render_center_x = CANVAS_MAX_X / 2.0
    render_center_y = CANVAS_MAX_Y / 2.0
    shift_x = render_center_x - (course_center_x * render_scale_x)
    shift_y = render_center_y - (course_center_y * render_scale_y)
    if station_parking_layout:
        finish_parking_length_canvas = (
            max(length for _, length in station_parking_layout.values()) * render_scale_y
        )
    else:
        finish_parking_length_canvas = 0.3

    def to_canvas(point: Point) -> Point:
        scaled_x, scaled_y = _scale_point_xy(point, render_scale_x, render_scale_y)
        return (scaled_x + shift_x, scaled_y + shift_y)

    for polyline in course_polylines:
        canvas_points = [to_canvas(point) for point in polyline]
        xs = [point[0] for point in canvas_points]
        ys = [point[1] for point in canvas_points]
        ax.plot(xs, ys, color="#4B5563", linewidth=COURSE_LINE_WIDTH)

    if show_decorations:
        start_x, start_y = to_canvas(start_anchor)
        start_box = Rectangle(
            (start_x - START_BOX_WIDTH, start_y - START_BOX_HEIGHT / 2.0),
            START_BOX_WIDTH,
            START_BOX_HEIGHT,
            fill=False,
            edgecolor="#7C2D12",
            linewidth=BOX_LINE_WIDTH,
            zorder=4,
        )
        ax.add_patch(start_box)
        ax.text(
            start_x - START_BOX_WIDTH / 2.0,
            start_y + START_BOX_HEIGHT / 2.0 + 0.03,
            "Start Tunnel",
            ha="center",
            va="bottom",
            fontsize=DECORATION_TEXT_SIZE,
            color="#7C2D12",
        )

        finish_x, finish_y = to_canvas(finish_anchor)
        finish_box_center_x = finish_x + FINISH_BOX_X_OFFSET
        finish_box_height = max(
            FINISH_BOX_MIN_HEIGHT,
            finish_parking_length_canvas + FINISH_BOX_EXTRA_HEIGHT,
        )
        finish_box = Rectangle(
            (
                finish_box_center_x - FINISH_BOX_WIDTH / 2.0,
                finish_y - finish_box_height / 2.0,
            ),
            FINISH_BOX_WIDTH,
            finish_box_height,
            fill=False,
            edgecolor="#065F46",
            linewidth=BOX_LINE_WIDTH,
            zorder=4,
        )
        ax.add_patch(finish_box)
        ax.text(
            finish_box_center_x,
            finish_y + finish_box_height / 2.0 + 0.03,
            "Finish Line",
            ha="center",
            va="bottom",
            fontsize=DECORATION_TEXT_SIZE,
            color="#065F46",
        )

        main_in_x, main_in_y = to_canvas(main_in_anchor)
        ax.text(
            main_in_x,
            main_in_y - MAIN_LABEL_Y_OFFSET,
            "Main In",
            ha="center",
            va="top",
            fontsize=DECORATION_TEXT_SIZE,
            color="#111827",
        )
        main_out_x, main_out_y = to_canvas(main_out_anchor)
        ax.text(
            main_out_x,
            main_out_y - MAIN_LABEL_Y_OFFSET,
            "Main Out",
            ha="center",
            va="top",
            fontsize=DECORATION_TEXT_SIZE,
            color="#111827",
        )

        for station_num in range(1, 9):
            layout = station_parking_layout.get(station_num)
            if layout is None:
                continue
            station_mid, station_length = layout
            station_x, station_y = to_canvas(station_mid)
            label_y = station_y + (station_length * render_scale_y / 2.0) + 0.04
            ax.text(
                station_x,
                label_y,
                f"Station {station_num}",
                ha="center",
                va="bottom",
                fontsize=DECORATION_TEXT_SIZE,
                color="#1F2937",
            )

    # Dots represent athlete positions at each animation frame.
    initial_offsets = [(0.0, 0.0) for _ in athlete_ids]
    dots = ax.scatter(
        [point[0] for point in initial_offsets],
        [point[1] for point in initial_offsets],
        s=ATHLETE_DOT_SIZE,
        c=athlete_colors,
        edgecolors="#374151",
        linewidths=0.5,
    )
    labels = [
        ax.text(
            0.0,
            0.0,
            athlete_id,
            fontsize=8,
            color="#111827",
            ha="left",
            va="bottom",
            clip_on=True,
        )
        for athlete_id in athlete_ids
    ]
    ax.set_title("HYROX Synthetic Animation")
    ax.set_aspect("auto")
    ax.set_axis_off()
    fig.subplots_adjust(left=0.01, right=0.99, bottom=0.01, top=0.95)
    ax.text(
        0.995,
        0.015,
        FIGURE_NOTE_TEXT,
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=FIGURE_NOTE_SIZE,
        color=FIGURE_NOTE_COLOR,
    )

    ax.set_xlim(0.0, CANVAS_MAX_X)
    ax.set_ylim(0.0, CANVAS_MAX_Y)

    def update(frame_idx: int):
        offsets: list[Point] = []
        race_rank = _rank_by_race_position(athlete_ids, trajectories, frame_idx)
        for label_idx, athlete_id in enumerate(athlete_ids):
            athlete_points = trajectories[athlete_id]
            point_idx = min(frame_idx, len(athlete_points) - 1)
            x, y = to_canvas((athlete_points[point_idx].x, athlete_points[point_idx].y))
            t = athlete_points[point_idx].t

            is_finished = point_idx == len(athlete_points) - 1
            if is_finished:
                base_x, base_y = to_canvas(finish_anchor)
                slot_idx = finish_order.get(athlete_id, label_idx)
                off_x, off_y = _parking_offset(
                    slot_idx,
                    len(athlete_ids),
                    finish_parking_length_canvas,
                )
                x = base_x + FINISH_PARKING_X_NUDGE + off_x
                y = base_y + off_y
            else:
                windows = station_windows.get(athlete_id, {})
                for round_num, (start_t, end_t) in windows.items():
                    if start_t <= t <= end_t and round_num in station_parking_layout:
                        station_mid, station_length = station_parking_layout[round_num]
                        base_x, base_y = to_canvas(station_mid)
                        round_ranks = arrival_order_by_round.get(round_num, {})
                        slot_idx = round_ranks.get(athlete_id, label_idx)
                        slot_count = len(round_ranks) if round_ranks else len(athlete_ids)
                        station_length_canvas = station_length * render_scale_y
                        off_x, off_y = _parking_offset(slot_idx, slot_count, station_length_canvas)
                        parked_x = base_x + off_x
                        parked_y = base_y + off_y

                        duration = end_t - start_t
                        if duration <= 0:
                            x = parked_x
                            y = parked_y
                            break

                        window_fraction = (t - start_t) / duration
                        if window_fraction <= 0.8:
                            x = parked_x
                            y = parked_y
                        else:
                            station_out_world = station_out_points.get(round_num)
                            if station_out_world is None:
                                x = parked_x
                                y = parked_y
                            else:
                                station_out_x, station_out_y = to_canvas(station_out_world)
                                turn_point = (parked_x, parked_y + STATION_EXIT_TURN_Y_NUDGE)
                                x, y = _interpolate_two_segment_path(
                                    (parked_x, parked_y),
                                    turn_point,
                                    (station_out_x, station_out_y),
                                    (window_fraction - 0.8) / 0.2,
                                )
                        break


            offsets.append((x, y))
            labels[label_idx].set_position((x + ATHLETE_LABEL_OFFSET, y + ATHLETE_LABEL_OFFSET))
            if 0.0 <= x <= CANVAS_MAX_X and 0.0 <= y <= CANVAS_MAX_Y:
                labels[label_idx].set_text(
                    f"{_display_athlete_id(athlete_id)} ({race_rank[athlete_id]})"
                )
            else:
                labels[label_idx].set_text("")
        dots.set_offsets(offsets)
        return (dots, *labels)

    anim = animation.FuncAnimation(
        fig=fig,
        func=update,
        frames=frame_count,
        interval=interval_ms,
        blit=False,
        repeat=False,
    )

    if no_show:
        preview_frames = min(frame_count, 10)
        for frame_idx in range(preview_frames):
            update(frame_idx)
            fig.canvas.draw()
        plt.close(fig)
        return

    _ = anim
    plt.show()
