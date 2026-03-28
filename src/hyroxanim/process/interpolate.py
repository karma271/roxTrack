"""Polyline interpolation helpers used by trajectory transforms."""

import math

Point = tuple[float, float]


def polyline_length(polyline: list[Point]) -> float:
    """Return total Euclidean length of a polyline."""

    if len(polyline) < 2:
        return 0.0

    total = 0.0
    for idx in range(1, len(polyline)):
        x1, y1 = polyline[idx - 1]
        x2, y2 = polyline[idx]
        total += math.dist((x1, y1), (x2, y2))
    return total


def interpolate_point_at_distance(polyline: list[Point], distance: float) -> Point:
    """Return point located at absolute distance along a polyline."""

    if not polyline:
        raise ValueError("polyline must contain at least one point")
    if len(polyline) == 1:
        return polyline[0]

    total = polyline_length(polyline)
    if total == 0:
        return polyline[0]

    clamped = max(0.0, min(distance, total))
    traversed = 0.0

    for idx in range(1, len(polyline)):
        start = polyline[idx - 1]
        end = polyline[idx]
        seg_len = math.dist(start, end)
        if seg_len == 0:
            continue

        if traversed + seg_len >= clamped:
            remaining = clamped - traversed
            ratio = remaining / seg_len
            x = start[0] + (end[0] - start[0]) * ratio
            y = start[1] + (end[1] - start[1]) * ratio
            return (x, y)
        traversed += seg_len

    return polyline[-1]


def interpolate_point_at_fraction(polyline: list[Point], fraction: float) -> Point:
    """Return point located at fraction (0..1) of polyline length."""

    total = polyline_length(polyline)
    if total == 0:
        if not polyline:
            raise ValueError("polyline must contain at least one point")
        return polyline[0]
    clamped_fraction = max(0.0, min(fraction, 1.0))
    return interpolate_point_at_distance(polyline, total * clamped_fraction)
