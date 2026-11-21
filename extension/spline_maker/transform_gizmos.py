"""Tool-owned Blender-style axes; one group reads the active mode every draw."""

import bpy
from mathutils import Matrix, Vector

from .feasibility import active_mode, move_origin
from . import edit_drag, tangent_drag

_groups = {}


def viewport_key(context):
    return tuple(x.as_pointer() for x in (context.window, context.area, context.region))


def gizmo_highlighted(context):
    group = _groups.get(viewport_key(context))
    if group is None:
        return False
    try:
        return any(not gizmo.hide and gizmo.is_highlight for gizmo, _, _, _ in group.controls)
    except ReferenceError:
        _groups.pop(viewport_key(context), None)
        return False


class VIEW3D_GGT_spline_maker_transform(bpy.types.GizmoGroup):
    bl_idname = "VIEW3D_GGT_spline_maker_transform"
    bl_label = "Splines Transform"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_options = {"3D", "SHOW_MODAL_ALL"}

    @classmethod
    def poll(cls, context):
        return active_mode(context) is not None

    def setup(self, context):
        self.controls = []
        for index, axis in enumerate("XYZ"):
            direction = Vector(tuple(float(i == index) for i in range(3)))
            basis = direction.to_track_quat("Z", "Y").to_matrix().to_4x4()
            color = tuple(0.9 if i == index else 0.2 for i in range(3))
            for mode in ("MOVE", "ROTATE", "SCALE"):
                dial = mode == "ROTATE"
                gizmo = self.gizmos.new("GIZMO_GT_dial_3d" if dial else "GIZMO_GT_arrow_3d")
                if dial:
                    gizmo.draw_options = {"CLIP"}
                elif mode == "SCALE":
                    gizmo.draw_style = "BOX"
                gizmo.matrix_basis = basis
                gizmo.color = color
                gizmo.color_highlight = (1.0, 1.0, 0.65)
                gizmo.alpha = 0.85
                gizmo.alpha_highlight = 1.0
                gizmo.line_width = 2.0
                gizmo.scale_basis = 0.8
                gizmo.use_draw_modal = mode != "MOVE"
                if mode == "MOVE":
                    props = gizmo.target_set_operator("spline_maker.move_drag")
                    props.axis = axis
                else:
                    props = gizmo.target_set_operator("spline_maker.tangent_drag")
                    props.mode, props.axis = mode, axis
                self.controls.append((gizmo, mode, basis, False))
        for plane, normal_index in (("XY", 2), ("YZ", 0), ("XZ", 1)):
            normal = Vector(tuple(float(i == normal_index) for i in range(3)))
            basis = normal.to_track_quat("Z", "Y").to_matrix().to_4x4()
            pad = self.gizmos.new("GIZMO_GT_primitive_3d")
            pad.draw_style = "PLANE"
            pad.color = tuple(0.9 if i == normal_index else 0.2 for i in range(3))
            pad.color_highlight = (1, 1, 0.65)
            pad.alpha, pad.alpha_highlight = 0.45, 0.9
            pad.scale_basis = 0.12
            pad.use_draw_offset_scale = True
            pad.matrix_offset.translation = (2.3, 2.3, 0)
            pad.use_draw_modal = False
            pad.target_set_operator("spline_maker.move_drag").axis = plane
            self.controls.append((pad, "MOVE", basis, False))
        # Offset XY scale square gives a planar drag away from the center.
        self.xy_scale = self.gizmos.new("GIZMO_GT_primitive_3d")
        self.xy_scale.draw_style = "PLANE"
        self.xy_scale.color = (0.2, 0.2, 0.9)
        self.xy_scale.color_highlight = (1.0, 1.0, 0.65)
        self.xy_scale.alpha, self.xy_scale.alpha_highlight = 0.55, 1.0
        self.xy_scale.scale_basis = 0.15
        self.xy_scale.use_draw_offset_scale = True
        self.xy_scale.matrix_offset.translation = (3.5, 3.5, 0)
        self.xy_scale.use_draw_modal = True
        props = self.xy_scale.target_set_operator("spline_maker.tangent_drag")
        props.mode, props.axis = "SCALE", "XY"
        self.controls.append((self.xy_scale, "SCALE", Matrix.Identity(4), False))
        # White outer ring rotates in the view plane; white center box scales
        # uniformly, supplementing the usual red/green/blue axis controls.
        for mode in ("MOVE", "ROTATE", "SCALE"):
            gizmo = self.gizmos.new("GIZMO_GT_dial_3d" if mode == "ROTATE" else "GIZMO_GT_primitive_3d")
            if mode != "ROTATE":
                gizmo.draw_style = "PLANE"
            gizmo.color = (0.85, 0.85, 0.85)
            gizmo.color_highlight = (1.0, 1.0, 0.65)
            gizmo.alpha, gizmo.alpha_highlight = 0.8, 1.0
            gizmo.line_width = 2.0
            gizmo.scale_basis = 0.95 if mode == "ROTATE" else 0.12
            gizmo.use_draw_modal = mode != "MOVE"
            if mode == "MOVE":
                gizmo.target_set_operator("spline_maker.move_drag").axis = "VIEW"
            else:
                props = gizmo.target_set_operator("spline_maker.tangent_drag")
                props.mode = mode
                props.axis = "VIEW" if mode == "ROTATE" else "UNIFORM"
            self.controls.append((gizmo, mode, Matrix.Identity(4), True))

    def draw_prepare(self, context):
        key = viewport_key(context)
        _groups[key] = self
        mode = active_mode(context)
        origin = move_origin(context)
        transform = tangent_drag._active
        transforming_here = transform is not None and transform.mode == mode and transform.key == key
        from .segment_selection import composite
        for gizmo, target, basis, view_facing in self.controls:
            gizmo.hide = (origin is None or mode != target or edit_drag._active is not None
                          or (transform is not None and not transforming_here)
                          or (gizmo is getattr(self, "xy_scale", None) and not composite(context)))
            if not gizmo.hide:
                if view_facing:
                    orientation = context.region_data.view_rotation
                    if transforming_here and mode == "ROTATE" and transform.axis == "VIEW":
                        # The active outer ring keeps the axis captured at press.
                        orientation = transform.axis_world.to_track_quat("Z", "Y")
                    gizmo.matrix_basis = orientation.to_matrix().to_4x4()
                else:
                    gizmo.matrix_basis = basis.copy()
                gizmo.matrix_basis.translation = (
                    transform.center_world if transforming_here else context.edit_object.matrix_world @ origin
                )

    def refresh(self, context):
        self.draw_prepare(context)


CLASSES = (VIEW3D_GGT_spline_maker_transform,)


def unregister():
    _groups.clear()
