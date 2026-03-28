"""Real-race ingest and lightweight validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from hyroxanim.models import AthleteSplits, Course, Split, TrajectoryPoint, split_from_dict
from hyroxanim.process.transform import (
    _load_course,
    transform_athlete_to_trajectory,
    write_processed_output,
)

_KNOWN_SENSORS = {
    "start_tunnel_sensor",
    "main_in_sensor",
    "station_in_sensor",
    "station_out_sensor",
    "main_out_sensor",
    "finish_line_sensor",
}
_EXPECTED_ROUNDS = range(1, 9)
_LEGACY_SEGMENTS = {
    "seg_main_in_to_station_zone",
    "seg_station_zone_to_main_out",
    "seg_station_out_to_main_out",
}
_ALLOWED_UNUSED_SEGMENTS = {
    # Round 8 terminal flow goes station_in -> finish, so these can exist but stay unused.
    "seg_station_in_to_station_out_r8",
    "seg_station_out_to_main_out_r8",
}


@dataclass(slots=True)
class ValidationIssue:
    """Issue found while validating real ingest data."""

    severity: str
    code: str
    message: str
    athlete_id: str | None = None
    round: int | None = None
    segment_id: str | None = None


@dataclass(slots=True)
class RealIngestResult:
    """Normalized athlete splits with validation issues."""

    athletes: list[AthleteSplits]
    warnings: list[ValidationIssue]
    errors: list[ValidationIssue]


@dataclass(slots=True)
class ProcessRealResult:
    """Processed real-race output details."""

    output_paths: dict[str, Path]
    warnings: list[ValidationIssue]
    errors: list[ValidationIssue]
    processed_athletes: int
    skipped_athletes: list[str]
    total_athletes: int


def _issue_text(issue: ValidationIssue) -> str:
    fields: list[str] = [f"{issue.severity.upper()} {issue.code}: {issue.message}"]
    if issue.athlete_id is not None:
        fields.append(f"athlete={issue.athlete_id}")
    if issue.round is not None:
        fields.append(f"round={issue.round}")
    if issue.segment_id is not None:
        fields.append(f"segment={issue.segment_id}")
    return " | ".join(fields)


def _format_issues(issues: list[ValidationIssue]) -> str:
    return "\n".join(_issue_text(issue) for issue in issues)


def _split_issues_by_athlete(
    issues: list[ValidationIssue],
) -> tuple[dict[str, list[ValidationIssue]], list[ValidationIssue]]:
    by_athlete: dict[str, list[ValidationIssue]] = {}
    global_issues: list[ValidationIssue] = []
    for issue in issues:
        if issue.athlete_id is None:
            global_issues.append(issue)
            continue
        by_athlete.setdefault(issue.athlete_id, []).append(issue)
    return by_athlete, global_issues


def _required_segment_ids() -> set[str]:
    required = {
        "seg_start_to_main_in",
        "seg_main_out_to_main_in",
        "seg_station_in_to_finish",
    }
    for round_num in _EXPECTED_ROUNDS:
        required.add(f"seg_main_in_to_station_in_r{round_num}")
        if round_num < 8:
            required.add(f"seg_station_in_to_station_out_r{round_num}")
            required.add(f"seg_station_out_to_main_out_r{round_num}")
    return required


def validate_course_segments(course: Course) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
    """Validate expected and unknown segment IDs for the fixed HYROX map."""

    warnings: list[ValidationIssue] = []
    errors: list[ValidationIssue] = []
    known_ids = {segment.segment_id for segment in course.segments}
    required = _required_segment_ids()

    for segment_id in sorted(required):
        if segment_id not in known_ids and segment_id not in _LEGACY_SEGMENTS:
            errors.append(
                ValidationIssue(
                    severity="error",
                    code="missing_segment",
                    message="Required course segment is missing",
                    segment_id=segment_id,
                )
            )

    allowed = required | _LEGACY_SEGMENTS | _ALLOWED_UNUSED_SEGMENTS
    for segment_id in sorted(known_ids):
        if segment_id not in allowed:
            warnings.append(
                ValidationIssue(
                    severity="warning",
                    code="unknown_segment",
                    message="Segment is not used by current transition mapping",
                    segment_id=segment_id,
                )
            )

    return warnings, errors


def _dedupe_by_transition(
    athlete_id: str,
    splits: list[Split],
) -> tuple[list[Split], list[ValidationIssue]]:
    warnings: list[ValidationIssue] = []
    deduped: dict[tuple[str, int | None], Split] = {}
    for split in sorted(splits, key=lambda item: item.timestamp):
        key = (split.sensor_type, split.round)
        if key in deduped:
            warnings.append(
                ValidationIssue(
                    severity="warning",
                    code="duplicate_split",
                    message="Duplicate split found; keeping earliest timestamped entry",
                    athlete_id=athlete_id,
                    round=split.round,
                )
            )
            continue
        deduped[key] = split
    return list(deduped.values()), warnings


def _validate_athlete(
    athlete: AthleteSplits,
) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
    warnings: list[ValidationIssue] = []
    errors: list[ValidationIssue] = []
    event = {(split.sensor_type, split.round): split for split in athlete.splits}

    required_keys: list[tuple[str, int | None]] = [("start_tunnel_sensor", None)]
    for round_num in _EXPECTED_ROUNDS:
        required_keys.append(("main_in_sensor", round_num))
        required_keys.append(("station_in_sensor", round_num))
        if round_num < 8:
            required_keys.append(("station_out_sensor", round_num))
            required_keys.append(("main_out_sensor", round_num))
    required_keys.append(("finish_line_sensor", None))

    for sensor_type, round_num in required_keys:
        if (sensor_type, round_num) not in event:
            errors.append(
                ValidationIssue(
                    severity="error",
                    code="missing_split",
                    message=f"Required split is missing: {sensor_type}",
                    athlete_id=athlete.athlete_id,
                    round=round_num,
                )
            )

    ordered_keys: list[tuple[str, int | None]] = [("start_tunnel_sensor", None)]
    for round_num in _EXPECTED_ROUNDS:
        ordered_keys.append(("main_in_sensor", round_num))
        ordered_keys.append(("station_in_sensor", round_num))
        if round_num < 8:
            ordered_keys.append(("station_out_sensor", round_num))
            ordered_keys.append(("main_out_sensor", round_num))
    ordered_keys.append(("finish_line_sensor", None))

    for idx in range(len(ordered_keys) - 1):
        left_key = ordered_keys[idx]
        right_key = ordered_keys[idx + 1]
        left = event.get(left_key)
        right = event.get(right_key)
        if left is None or right is None:
            continue
        delta = right.timestamp - left.timestamp
        if delta <= 0:
            errors.append(
                ValidationIssue(
                    severity="error",
                    code="non_positive_time_delta",
                    message=f"Non-positive elapsed time from {left_key[0]} to {right_key[0]}",
                    athlete_id=athlete.athlete_id,
                    round=right_key[1],
                )
            )

    return warnings, errors


def _normalize_athlete(
    item: dict,
) -> tuple[AthleteSplits, list[ValidationIssue], list[ValidationIssue]]:
    athlete_id = str(item["athlete_id"])
    raw_splits = item.get("splits", [])
    if not isinstance(raw_splits, list):
        raise ValueError(f"splits must be a list for athlete {athlete_id}")

    warnings: list[ValidationIssue] = []
    errors: list[ValidationIssue] = []
    parsed: list[Split] = []

    for row in raw_splits:
        try:
            split = split_from_dict(row)
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(
                ValidationIssue(
                    severity="error",
                    code="invalid_split_payload",
                    message=f"Invalid split payload: {exc}",
                    athlete_id=athlete_id,
                )
            )
            continue

        if split.athlete_id != athlete_id:
            warnings.append(
                ValidationIssue(
                    severity="warning",
                    code="athlete_id_mismatch",
                    message="Split athlete_id mismatched parent athlete; normalizing to parent id",
                    athlete_id=athlete_id,
                )
            )
            split = Split(
                athlete_id=athlete_id,
                sensor_type=split.sensor_type,
                timestamp=split.timestamp,
                round=split.round,
            )

        if split.sensor_type not in _KNOWN_SENSORS:
            warnings.append(
                ValidationIssue(
                    severity="warning",
                    code="unknown_sensor",
                    message=f"Ignoring unknown sensor type: {split.sensor_type}",
                    athlete_id=athlete_id,
                )
            )
            continue

        if (
            split.sensor_type in {"start_tunnel_sensor", "finish_line_sensor"}
            and split.round is not None
        ):
            warnings.append(
                ValidationIssue(
                    severity="warning",
                    code="unexpected_round",
                    message=f"{split.sensor_type} should not include round; coercing to None",
                    athlete_id=athlete_id,
                    round=split.round,
                )
            )
            split = Split(
                athlete_id=split.athlete_id,
                sensor_type=split.sensor_type,
                timestamp=split.timestamp,
                round=None,
            )

        if (
            split.sensor_type not in {"start_tunnel_sensor", "finish_line_sensor"}
            and split.round is None
        ):
            errors.append(
                ValidationIssue(
                    severity="error",
                    code="missing_round",
                    message=f"{split.sensor_type} requires round value",
                    athlete_id=athlete_id,
                )
            )
            continue

        parsed.append(split)

    ordered = list(parsed)
    if ordered != sorted(parsed, key=lambda item: item.timestamp):
        warnings.append(
            ValidationIssue(
                severity="warning",
                code="out_of_order_splits",
                message="Splits are not time-ordered; sorting by timestamp",
                athlete_id=athlete_id,
            )
        )
    ordered = sorted(parsed, key=lambda item: item.timestamp)

    deduped, dedupe_warnings = _dedupe_by_transition(athlete_id, ordered)
    warnings.extend(dedupe_warnings)
    athlete = AthleteSplits(athlete_id=athlete_id, splits=deduped)

    athlete_warnings, athlete_errors = _validate_athlete(athlete)
    warnings.extend(athlete_warnings)
    errors.extend(athlete_errors)
    return athlete, warnings, errors


def ingest_real_splits(splits_path: Path) -> RealIngestResult:
    """Load and normalize a real race splits file."""

    payload = json.loads(splits_path.read_text(encoding="utf-8"))
    athletes_payload = payload.get("athletes")
    if not isinstance(athletes_payload, list):
        raise ValueError("Expected payload with top-level 'athletes' list")

    athletes: list[AthleteSplits] = []
    warnings: list[ValidationIssue] = []
    errors: list[ValidationIssue] = []

    for athlete_item in athletes_payload:
        athlete, athlete_warnings, athlete_errors = _normalize_athlete(athlete_item)
        athletes.append(athlete)
        warnings.extend(athlete_warnings)
        errors.extend(athlete_errors)

    return RealIngestResult(athletes=athletes, warnings=warnings, errors=errors)


def process_real_files(
    course_path: Path,
    splits_path: Path,
    out_dir: Path,
    dt: float = 1.0,
    strict: bool = False,
) -> ProcessRealResult:
    """Process real-race files into trajectories with validation."""

    course = _load_course(course_path)
    ingest_result = ingest_real_splits(splits_path)
    course_warnings, course_errors = validate_course_segments(course)

    warnings = ingest_result.warnings + course_warnings
    ingest_errors = ingest_result.errors
    error_map, global_errors = _split_issues_by_athlete(ingest_errors)
    fatal_errors = [*course_errors, *global_errors]
    if fatal_errors:
        raise ValueError(_format_issues(fatal_errors))
    if strict and ingest_errors:
        raise ValueError(_format_issues(ingest_errors))

    trajectories: dict[str, list[TrajectoryPoint]] = {}
    all_errors: list[ValidationIssue] = [*ingest_errors]
    skipped: set[str] = set()
    for athlete in ingest_result.athletes:
        athlete_errors = error_map.get(athlete.athlete_id, [])
        if athlete_errors:
            skipped.add(athlete.athlete_id)
            continue
        try:
            trajectories[athlete.athlete_id] = transform_athlete_to_trajectory(
                athlete_splits=athlete,
                course=course,
                dt=dt,
            )
        except (KeyError, ValueError) as exc:
            skipped.add(athlete.athlete_id)
            transform_issue = ValidationIssue(
                severity="error",
                code="transform_failed",
                message=str(exc),
                athlete_id=athlete.athlete_id,
            )
            all_errors.append(transform_issue)
            if strict:
                raise ValueError(_format_issues([transform_issue])) from exc

    if not trajectories:
        raise ValueError(_format_issues(all_errors))

    output_paths = write_processed_output(trajectories=trajectories, out_dir=out_dir)
    return ProcessRealResult(
        output_paths=output_paths,
        warnings=warnings,
        errors=all_errors,
        processed_athletes=len(trajectories),
        skipped_athletes=sorted(skipped),
        total_athletes=len(ingest_result.athletes),
    )
