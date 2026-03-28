"""Convert flat real-race CSV rows into canonical athlete-splits JSON."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

_HH_MM_SS_PATTERN = re.compile(r"^(?P<h>\d+):(?P<m>[0-5]?\d):(?P<s>[0-5]?\d(?:\.\d+)?)$")
_NONE_LIKE = {"", "none", "null", "na", "n/a"}


@dataclass(slots=True)
class ConvertCsvResult:
    """Summary of CSV-to-JSON conversion output."""

    out_path: Path
    athlete_count: int
    split_count: int
    normalized_start: bool


def _parse_timestamp(raw: str) -> float:
    value = raw.strip()
    if not value:
        raise ValueError("timestamp is required")

    try:
        return float(value)
    except ValueError:
        match = _HH_MM_SS_PATTERN.match(value)
        if not match:
            raise ValueError(
                f"timestamp '{raw}' must be numeric seconds or HH:MM:SS(.sss)"
            ) from None
        hours = int(match.group("h"))
        minutes = int(match.group("m"))
        seconds = float(match.group("s"))
        return hours * 3600 + minutes * 60 + seconds


def _parse_round(raw: str) -> int | None:
    value = raw.strip().lower()
    if value in _NONE_LIKE:
        return None
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"round '{raw}' must be an integer or empty") from None


def _normalize_splits(splits: list[dict], normalize_start: bool) -> list[dict]:
    ordered = sorted(splits, key=lambda item: item["timestamp"])
    if not normalize_start or not ordered:
        return ordered

    base_time = ordered[0]["timestamp"]
    normalized: list[dict] = []
    for split in ordered:
        normalized.append(
            {
                "athlete_id": split["athlete_id"],
                "sensor_type": split["sensor_type"],
                "timestamp": round(split["timestamp"] - base_time, 6),
                "round": split["round"],
            }
        )
    return normalized


def convert_real_csv_to_json(
    csv_path: Path,
    out_path: Path,
    *,
    normalize_start: bool = True,
) -> ConvertCsvResult:
    """Convert flat split rows into canonical JSON grouped by athlete."""

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])

        required = {"athlete_id", "sensor_type", "timestamp", "round"}
        missing = sorted(required - fieldnames)
        if missing:
            raise ValueError(f"CSV missing required columns: {', '.join(missing)}")

        grouped: dict[str, list[dict]] = {}
        total_rows = 0
        for row_num, row in enumerate(reader, start=2):
            athlete_id = (row.get("athlete_id") or "").strip()
            sensor_type = (row.get("sensor_type") or "").strip()
            timestamp_raw = row.get("timestamp") or ""
            round_raw = row.get("round") or ""

            if not athlete_id:
                raise ValueError(f"row {row_num}: athlete_id is required")
            if not sensor_type:
                raise ValueError(f"row {row_num}: sensor_type is required")

            timestamp = _parse_timestamp(timestamp_raw)
            round_num = _parse_round(round_raw)
            grouped.setdefault(athlete_id, []).append(
                {
                    "athlete_id": athlete_id,
                    "sensor_type": sensor_type,
                    "timestamp": timestamp,
                    "round": round_num,
                }
            )
            total_rows += 1

    athletes_payload = []
    for athlete_id, splits in grouped.items():
        athletes_payload.append(
            {
                "athlete_id": athlete_id,
                "splits": _normalize_splits(splits, normalize_start=normalize_start),
            }
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"athletes": athletes_payload}
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return ConvertCsvResult(
        out_path=out_path,
        athlete_count=len(athletes_payload),
        split_count=total_rows,
        normalized_start=normalize_start,
    )

