# SPDX-FileCopyrightText: 2026 Pease Technology
# SPDX-License-Identifier: GPL-3.0-or-later

"""Conservative planar-loop validation; no viewport or source data mutation."""

from dataclasses import dataclass
from mathutils import Vector

from .segment_selection import curve_edges


def cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def edges(polygon):
    return list(zip(polygon, polygon[1:] + polygon[:1]))


def touch(a, b, c, d, epsilon):
    if (max(a[0], b[0]) < min(c[0], d[0]) - epsilon
            or max(c[0], d[0]) < min(a[0], b[0]) - epsilon
            or max(a[1], b[1]) < min(c[1], d[1]) - epsilon
            or max(c[1], d[1]) < min(a[1], b[1]) - epsilon):
        return False
    tolerance = epsilon * max((Vector(b) - Vector(a)).length, (Vector(d) - Vector(c)).length, epsilon)
    ab = (cross(a, b, c), cross(a, b, d))
    cd = (cross(c, d, a), cross(c, d, b))
    return (min(ab) <= tolerance and max(ab) >= -tolerance
            and min(cd) <= tolerance and max(cd) >= -tolerance)


def inside(point, polygon):
    result = False
    x, y = point
    for a, b in edges(polygon):
        if (a[1] > y) != (b[1] > y):
            crossing = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if x < crossing:
                result = not result
    return result


def crossings(first, second=None, epsilon=1e-7):
    """Sweep broad phase, including boundary touches; skip adjacent self-edges."""
    same = second is None
    second = first if same else second
    items = [(min(a[0], b[0]), max(a[0], b[0]), i, 0, a, b) for i, (a, b) in enumerate(edges(first))]
    if not same:
        items += [(min(a[0], b[0]), max(a[0], b[0]), i, 1, a, b) for i, (a, b) in enumerate(edges(second))]
    active = []
    for item in sorted(items, key=lambda entry: entry[0]):
        xmin, xmax, index, group, a, b = item
        active = [other for other in active if other[1] >= xmin - epsilon]
        for other in active:
            _, _, j, other_group, c, d = other
            if same and (abs(index - j) == 1 or {index, j} == {0, len(first) - 1}):
                continue
            if not same and group == other_group:
                continue
            if touch(a, b, c, d, epsilon):
                return True
        active.append(item)
    return False


@dataclass
class Loop:
    index: int
    origin: Vector
    u: Vector
    v: Vector
    normal: Vector
    polygon: list
    scale: float

    def uv(self, point):
        delta = point - self.origin
        return (delta.dot(self.u), delta.dot(self.v))

    def local(self, point):
        return self.origin + point[0] * self.u + point[1] * self.v


def make_loop(index, spline):
    if not spline.use_cyclic_u:
        return None, "Open splines have no closed region"
    points = spline.bezier_points
    if len(points) < 3:
        return None, "A region needs at least three vertices"
    if any(point.hide for point in points):
        return None, "Reveal hidden vertices to select regions"
    controls = [coord.copy() for p in points for coord in (p.co, p.handle_left, p.handle_right)]
    origin = points[0].co.copy()
    offsets = [point - origin for point in controls]
    u = max(offsets, key=lambda point: point.length_squared).copy()
    scale = u.length
    if scale < 1e-8:
        return None, "Degenerate loop has no region"
    normal = max((u.cross(point) for point in offsets), key=lambda point: point.length_squared)
    if normal.length < scale * scale * 1e-8:
        return None, "Collinear loop has no region"
    u.normalize()
    normal.normalize()
    if any(abs(point.dot(normal)) > max(scale * 1e-5, 1e-6) for point in offsets):
        return None, "Nonplanar loops are unsupported"
    loop = Loop(index, origin, u, normal.cross(u).normalized(), normal, [], scale)
    tolerance = max(scale * 0.0005, 1e-6)
    factor = 0.75 / tolerance
    for i, a in enumerate(points):
        b = points[(i + 1) % len(points)]
        sampled = curve_edges((a.co.copy(), a.handle_right.copy(), b.handle_left.copy(), b.co.copy()),
                              lambda p: tuple(value * factor for value in loop.uv(p)))
        for start, _ in sampled:
            point = (start[0] / factor, start[1] / factor)
            if not loop.polygon or (Vector(point) - Vector(loop.polygon[-1])).length > tolerance * 1e-3:
                loop.polygon.append(point)
        if len(loop.polygon) > 2048:
            return None, "Loop is too complex for region selection"
    polygon = loop.polygon
    if len(polygon) < 3:
        return None, "Degenerate loop has no region"
    epsilon = max(scale * 1e-7, 1e-8)
    for i, b in enumerate(polygon):
        a, c = polygon[i - 1], polygon[(i + 1) % len(polygon)]
        if abs(cross(a, b, c)) <= epsilon * scale and (Vector(a) - Vector(b)).dot(Vector(c) - Vector(b)) > 0:
            return None, "Retraced boundaries are unsupported"
    if crossings(polygon, epsilon=epsilon):
        return None, "Self-intersecting or touching loops are unsupported"
    area = abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in edges(polygon))) / 2
    if area < scale * scale * 1e-8:
        return None, "Degenerate loop has no region"
    return loop, ""


def validate(data):
    loops, reasons = {}, []
    invalid_closed = False
    for index, spline in enumerate(data.splines):
        loop, reason = make_loop(index, spline)
        if loop is not None:
            loops[index] = loop
        else:
            message = f"Spline {index + 1}: {reason}"
            reasons.insert(0, message) if spline.use_cyclic_u else reasons.append(message)
            invalid_closed |= bool(spline.use_cyclic_u)
    # An invalid closed boundary might overlap a valid one. Fail conservatively.
    if invalid_closed:
        return {}, reasons
    rejected = set()
    values = list(loops.values())
    for i, a in enumerate(values):
        for b in values[i + 1:]:
            epsilon = max(a.scale, b.scale) * 1e-5
            if (a.normal.cross(b.normal).length < 1e-5
                    and abs((b.origin - a.origin).dot(a.normal)) <= epsilon):
                other = [a.uv(b.local(p)) for p in b.polygon]
                if (crossings(a.polygon, other, epsilon)
                        or inside(a.polygon[0], other) or inside(other[0], a.polygon)):
                    rejected.update((a.index, b.index))
    if rejected:
        reasons.append("Overlapping, touching, or nested loops are unsupported")
    return {index: loop for index, loop in loops.items() if index not in rejected}, reasons
