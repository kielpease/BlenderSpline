"""View projection and in-progress points for the fixed drawing plane."""

from bpy_extras import view3d_utils
from mathutils import Vector


class DrawingPlane:
    def __init__(self, origin, rotation):
        self.origin = origin.copy()
        self.rotation = rotation.normalized()
        self.inverse = self.rotation.inverted()
        self.normal = self.rotation @ Vector((0, 0, 1))

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


class DrawingSession:
    def __init__(self, plane):
        self.plane = plane
        self.points = []

    def place(self, point):
        if not self.points or (point - self.points[-1]).length_squared > 1e-12:
            self.points.append(point.copy())

    def undo_point(self):
        if self.points:
            self.points.pop()

    def cancel(self):
        self.points.clear()
