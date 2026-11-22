# SPDX-FileCopyrightText: 2026 Pease Technology
# SPDX-License-Identifier: GPL-3.0-or-later

"""View projection and in-progress points for the fixed drawing plane."""

from dataclasses import dataclass
from math import atan2, cos, floor, hypot, isfinite, pi, sin

from bpy_extras import view3d_utils
from mathutils import Vector
from mathutils.geometry import interpolate_bezier


DRAWING_PLANE_KEY = "spline_maker_drawing_plane"
DRAWING_PLANE_XY = "LOCAL_XY"


class DrawingPlane:
    def __init__(self, origin, rotation):
        self.origin = origin.copy()
        self.rotation = rotation.normalized()
        self.inverse = self.rotation.inverted()
        self.normal = self.rotation @ Vector((0, 0, 1))
        self.grid_origin = self.inverse @ -self.origin

    def intersect(self, origin, direction, *, perspective):
        alignment = self.normal.dot(direction)
        if abs(alignment) < 0.01:
            return None
        depth = self.normal.dot(self.origin - origin) / alignment
        if perspective and depth < 0:
            return None
        local = self.inverse @ (origin - self.origin + depth * direction)
        return Vector((local.x, local.y, 0))

    def to_world(self, point):
        return self.origin + self.rotation @ point


def project_view_point(plane, region, view, pixel):
    direction = view3d_utils.region_2d_to_vector_3d(region, view, pixel)
    # An orthographic ray can start anywhere on its line. Avoid offsetting
    # its origin by the far clip, which can reduce placement precision.
    origin = view3d_utils.region_2d_to_origin_3d(region, view, pixel, clamp=0.0)
    return plane.intersect(origin, direction, perspective=view.is_perspective)


def viewport_grid_spacing(context, plane):
    overlay = context.space_data.overlay
    base = overlay.grid_scale_unit
    view = context.region_data
    if (base <= 0 or context.scene.unit_settings.system != "NONE"
            or not view.is_orthographic_side_view
            or abs(plane.normal.dot(view.view_rotation @ Vector((0, 0, 1)))) < 1 - 1e-5):
        return base
    # Match the prominent grid interval in Blender's unitless axis view.
    projection = context.region.width * abs(view.window_matrix[0][0])
    subdivisions = overlay.grid_subdivisions
    if projection <= 0 or subdivisions <= 1:
        return base
    threshold = 120 / projection
    spacing = base / subdivisions ** 3
    for _ in range(7):
        if spacing * subdivisions >= threshold:
            break
        spacing *= subdivisions
    return spacing


@dataclass
class SplinePoint:
    anchor: Vector
    tangent: Vector | None = None


class PointPlacement:
    def __init__(self, pixel, anchor, *, drag_origin=None):
        self.start_pixel = Vector(pixel)
        self.point = SplinePoint(anchor.copy())
        self.drag_origin = anchor.copy() if drag_origin is None else drag_origin.copy()
        self.dragging = False

    def update(self, pixel, coordinate):
        if coordinate is None:
            return
        self.dragging = self.dragging or (Vector(pixel) - self.start_pixel).length_squared >= 25
        if self.dragging:
            offset = coordinate - self.drag_origin
            self.point.tangent = offset if offset.length_squared > 1e-12 else None


def segment_preview(start, end):
    if start.tangent is None and end.tangent is None:
        return (start.anchor, end.anchor)
    chord = (end.anchor - start.anchor) / 3
    outgoing = start.tangent if start.tangent is not None else chord
    incoming = end.tangent if end.tangent is not None else chord
    samples = interpolate_bezier(
        start.anchor, start.anchor + outgoing, end.anchor - incoming, end.anchor, 20
    )
    samples[0], samples[-1] = start.anchor, end.anchor
    return samples


class DrawingSession:
    def __init__(self, plane):
        self.plane = plane
        self.points = []

    def place(self, anchor, tangent=None):
        if self.can_place(anchor):
            self.points.append(SplinePoint(anchor.copy(), tangent.copy() if tangent is not None else None))

    def placement_anchor(self, projected, *, snap, grid_spacing=0.0):
        if projected is None or not snap:
            return projected
        if not self.points:
            if grid_spacing <= 0 or not isfinite(grid_spacing):
                return projected
            origin = self.plane.grid_origin
            snapped = [
                origin[axis] + floor((projected[axis] - origin[axis]) / grid_spacing + 0.5) * grid_spacing
                for axis in range(2)
            ]
            return Vector((*snapped, 0))
        previous = self.points[-1].anchor
        offset = projected - previous
        radius = hypot(offset.x, offset.y)
        step = pi / 4
        direction = floor(atan2(offset.y, offset.x) / step + 0.5) * step
        return previous + Vector((radius * cos(direction), radius * sin(direction), 0))

    def can_place(self, point):
        return point is not None and (
            not self.points or (point - self.points[-1].anchor).length_squared > 1e-12
        )

    def undo_point(self):
        if self.points:
            self.points.pop()

    def cancel(self):
        self.points.clear()
