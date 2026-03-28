from hyroxanim.models import AthleteSplits, Course, Segment, Split, TrajectoryPoint


def test_model_creation_defaults() -> None:
    segment = Segment(
        segment_id="seg_1",
        name="Segment 1",
        kind="run",
        start=(0.0, 0.0),
        end=(1.0, 0.0),
    )
    course = Course(course_id="course_1", name="Course 1", segments=[segment])
    split = Split(athlete_id="athlete_001", sensor_type="main_in_sensor", timestamp=10.0)
    athlete_splits = AthleteSplits(athlete_id="athlete_001", splits=[split])
    trajectory = TrajectoryPoint(athlete_id="athlete_001", t=0.0, x=0.0, y=0.0)

    assert course.segments[0].segment_id == "seg_1"
    assert split.round is None
    assert athlete_splits.splits[0].sensor_type == "main_in_sensor"
    assert trajectory.t == 0.0


def test_split_schema_fields() -> None:
    split = Split(
        athlete_id="athlete_002",
        sensor_type="station_in_sensor",
        timestamp=123.4,
        round=2,
    )

    assert split.athlete_id == "athlete_002"
    assert split.sensor_type == "station_in_sensor"
    assert split.timestamp == 123.4
    assert split.round == 2
