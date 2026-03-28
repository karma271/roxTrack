from hyroxanim.process.interpolate import (
    interpolate_point_at_distance,
    interpolate_point_at_fraction,
    polyline_length,
)


def test_polyline_length_simple() -> None:
    polyline = [(0.0, 0.0), (3.0, 0.0), (3.0, 4.0)]
    assert polyline_length(polyline) == 7.0


def test_interpolate_point_on_polyline_by_fraction() -> None:
    polyline = [(0.0, 0.0), (10.0, 0.0)]
    x, y = interpolate_point_at_fraction(polyline, 0.25)
    assert x == 2.5
    assert y == 0.0


def test_interpolate_point_on_polyline_by_distance() -> None:
    polyline = [(0.0, 0.0), (3.0, 0.0), (3.0, 4.0)]
    x, y = interpolate_point_at_distance(polyline, 5.0)
    assert x == 3.0
    assert y == 2.0
