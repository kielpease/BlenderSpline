# SPDX-FileCopyrightText: 2026 Pease Technology
# SPDX-License-Identifier: GPL-3.0-or-later

"""Screen-space tolerances for Shift snapping during curve edits."""

from mathutils import Vector


SHIFT_KEYS = {"LEFT_SHIFT", "RIGHT_SHIFT"}
SNAP_RADIUS = 10


def alignment_axes(axis, normal):
    """Yield unit-coordinate corrections that respect the active Move constraint."""
    for index, label in enumerate("XY"):
        if axis != "VIEW" and label not in axis:
            continue
        direction = Vector((float(index == 0), float(index == 1), 0))
        if axis == "VIEW":
            direction -= normal * direction.dot(normal)
            if direction[index] < 1e-6:
                continue
            direction /= direction[index]
        yield index, direction


def vertex_alignment(position, targets, axes, screen):
    pixel = screen(position)
    if pixel is None:
        return position
    best = position
    distance_squared = SNAP_RADIUS ** 2
    for index, direction in axes:
        for target in targets:
            offset = target[index] - position[index]
            if abs(offset) < 1e-7:
                continue
            candidate = position + offset * direction
            projected = screen(candidate)
            if projected is None:
                continue
            distance = (projected - pixel).length_squared
            if 1e-8 < distance <= distance_squared:
                best, distance_squared = candidate, distance
    return best


def nearest_line_pixel(pixel, start, end):
    if pixel is None or start is None or end is None:
        return None
    line = end - start
    if line.length_squared < 1e-6:
        return None
    nearest = start + line * (pixel - start).dot(line) / line.length_squared
    if (nearest - pixel).length_squared > SNAP_RADIUS ** 2:
        return None
    return nearest
