"""Canonical data models for HYROX animation processing."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class Segment:
    """A course segment represented as a 2D line from start to end."""

    segment_id: str
    name: str
    kind: str
    start: tuple[float, float]
    end: tuple[float, float]
    points: list[tuple[float, float]] | None = None


@dataclass(slots=True)
class Course:
    """A full course made of ordered segments."""

    course_id: str
    name: str
    segments: list[Segment]


@dataclass(slots=True)
class Split:
    """One raw sensor read for an athlete."""

    athlete_id: str
    sensor_type: str
    timestamp: float
    round: int | None = None


@dataclass(slots=True)
class AthleteSplits:
    """All sensor reads for one athlete."""

    athlete_id: str
    splits: list[Split]


@dataclass(slots=True)
class TrajectoryPoint:
    """A time-indexed 2D point used by animation."""

    athlete_id: str
    t: float
    x: float
    y: float


def to_dict(obj: Segment | Course | Split | AthleteSplits | TrajectoryPoint) -> dict:
    """Serialize a dataclass model into a plain dictionary."""

    return asdict(obj)


def split_from_dict(payload: dict) -> Split:
    """Create a Split model from a dictionary payload."""

    return Split(
        athlete_id=str(payload["athlete_id"]),
        sensor_type=str(payload["sensor_type"]),
        timestamp=float(payload["timestamp"]),
        round=int(payload["round"]) if payload.get("round") is not None else None,
    )
