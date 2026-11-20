"""A small Edit Mode probe for native picking and tool-local transforms."""

from math import radians

import bpy
from bpy_extras.object_utils import object_data_add
from mathutils import Matrix, Vector


TOOLS = (
    ("Q", "SELECT", "Select"),
    ("W", "MOVE", "Move"),
    ("E", "ROTATE", "Rotate"),
    ("R", "SCALE", "Scale"),
)


def tool_id(mode):
    return f"spline_maker.probe_{mode.lower()}"


def active_mode(context):
    if context.mode != "EDIT_CURVE":
        return None
    tool = context.workspace.tools.from_space_view3d_mode("EDIT_CURVE", create=False)
    return next((mode for _, mode, _ in TOOLS if tool and tool.idname == tool_id(mode)), None)


def editable_bezier_points(context):
    obj = context.edit_object
    if (
        context.mode != "EDIT_CURVE"
        or obj is None
        or len(context.objects_in_mode) != 1
    ):
        return []
    return (
        point
        for spline in obj.data.splines if spline.type == "BEZIER"
        for point in spline.bezier_points if not point.hide
    )


def selected_handles(context):
    return [
        (point, side)
        for point in editable_bezier_points(context)
        for side in ("left", "right")
        if point.select_control_point or getattr(point, f"select_{side}_handle")
    ]


def selected_vertex_handles(context):
    return [(point, side) for point in editable_bezier_points(context)
            if point.select_control_point for side in ("left", "right")]


class SPLINE_MAKER_OT_add_test_curve(bpy.types.Operator):
    bl_idname = "spline_maker.add_test_curve"
    bl_label = "Add Bézier Test Curve"
    bl_description = "Add a native Bézier sample at the 3D cursor for the SM-002 probe"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def execute(self, context):
        curve = bpy.data.curves.new("Spline Maker Test Curve", "CURVE")
        curve.dimensions = "3D"
        points = curve.splines.new("BEZIER").bezier_points
        points.add(1)
        for point, x, y in zip(points, (-2.0, 2.0), (0.0, 1.0)):
            point.co = (x, y, 0.0)
            point.handle_left_type = point.handle_right_type = "FREE"
            point.handle_left = (x - 0.9, y - 0.6, 0.0)
            point.handle_right = (x + 0.9, y + 0.6, 0.0)
        object_data_add(context, curve)
        self.report({"INFO"}, "Enter Edit Mode and activate Spline Maker Select")
        return {"FINISHED"}


class SPLINE_MAKER_OT_tangent_step(bpy.types.Operator):
    bl_idname = "spline_maker.tangent_step"
    bl_label = "Apply Tangent Step"
    bl_description = "Rotate or scale selected handles around their anchors, freeing vector handles"
    bl_options = {"UNDO", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        return (
            context.area is not None
            and context.area.type == "VIEW_3D"
            and active_mode(context) in {"ROTATE", "SCALE"}
            and bool(selected_vertex_handles(context))
        )

    def execute(self, context):
        mode = active_mode(context)
        matrix = Matrix.Rotation(radians(15), 3, "Z") if mode == "ROTATE" else Matrix.Scale(1.25, 3)
        handles = [
            (point, f"handle_{side}", point.co + matrix @ (getattr(point, f"handle_{side}") - point.co))
            for point, side in selected_vertex_handles(context)
        ]
        for point, attribute, coordinate in handles:
            if getattr(point, f"{attribute}_type") in {"VECTOR", "AUTO"}:
                # Automatic tangents cannot retain a manual edit. Preserve
                # linked Smooth tangents; Corner tangents become independent.
                target_type = "ALIGNED" if getattr(point, f"{attribute}_type") == "AUTO" else "FREE"
                point.handle_left_type = point.handle_right_type = target_type
            setattr(point, attribute, coordinate)
        context.edit_object.data.update_tag()
        context.area.tag_redraw()
        return {"FINISHED"}


class SPLINE_MAKER_OT_switch_tangent_tool(bpy.types.Operator):
    bl_idname = "spline_maker.switch_tangent_tool"
    bl_label = "Switch Spline Maker Tool"
    bl_options = {"INTERNAL"}

    target: bpy.props.EnumProperty(items=(
        ("SELECT", "Select", ""),
        ("MOVE", "Move", ""),
        ("ROTATE", "Rotate", ""),
        ("SCALE", "Scale", ""),
    ))

    @classmethod
    def poll(cls, context):
        return (
            context.area is not None
            and context.area.type == "VIEW_3D"
            and context.mode == "EDIT_CURVE" and context.edit_object is not None
            and len(context.objects_in_mode) == 1
            and all(s.type == "BEZIER" for s in context.edit_object.data.splines)
        )

    def execute(self, context):
        from . import tangent_drag, edit_drag, vertex_selection
        edit_drag.unregister()
        vertex_selection.stop_active(context)
        if tangent_drag._active is not None:
            tangent_drag._active.finish(context, cancel=True)
        result = bpy.ops.wm.tool_set_by_id(name=tool_id(self.target))
        # Tool changes from the sidebar need to invalidate the WINDOW region
        # as well as the sidebar. No timers or forced viewport motion needed.
        context.area.tag_redraw()
        for region in context.area.regions:
            region.tag_redraw()
        return result


class SPLINE_MAKER_OT_tool_shortcut(bpy.types.Operator):
    bl_idname = "spline_maker.tool_shortcut"
    bl_label = "Switch Active Spline Maker Tool"
    bl_options = {"INTERNAL"}

    target: bpy.props.EnumProperty(items=tuple((mode, label, "") for _, mode, label in TOOLS))

    @classmethod
    def poll(cls, context):
        return SPLINE_MAKER_OT_switch_tangent_tool.poll(context) and active_mode(context) is not None

    def execute(self, context):
        return bpy.ops.spline_maker.switch_tangent_tool(target=self.target)


def move_origin(context):
    for point in editable_bezier_points(context):
        if point.select_control_point:
            return point.co
    return None


class VIEW3D_PT_spline_maker_probe(bpy.types.Panel):
    bl_label = "Spline Maker Edit"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Spline Maker"

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_CURVE"

    def draw(self, context):
        layout = self.layout
        # Sidebar clicks must run in the viewport's WINDOW region, just like
        # shortcuts and gizmos. Execute these discrete actions without invoking
        # an interactive transform.
        layout.operator_context = "EXEC_REGION_WIN"
        mode = active_mode(context)
        layout.label(text="Spline shortcuts active: Q/W/E/R" if mode is not None else "Click Q Select to enter Spline Maker")
        for key, target, label in TOOLS:
            op = layout.operator("spline_maker.switch_tangent_tool", text=f"{key}  {label}", depress=mode == target)
            op.target = target
        if mode is not None:
            layout.label(text="Shift-click to toggle")
            layout.label(text="Drag to box-select vertices")
            layout.label(text="Drag handle diamonds freely")
        if mode == "MOVE":
            layout.label(text="Arrows: axis; squares: plane")
        elif mode in {"ROTATE", "SCALE"}:
            layout.label(text="Drag an axis ring" if mode == "ROTATE" else "Drag an axis box or center")
            label = "Rotate Handles 15°" if mode == "ROTATE" else "Scale Handles ×1.25"
            layout.operator(SPLINE_MAKER_OT_tangent_step.bl_idname, text=label)
        if mode is not None:
            from .vertex_types import draw_vertex_types
            layout.separator()
            layout.label(text="Vertex Type (both tangents)")
            draw_vertex_types(layout)


TOOL_KEYMAP = tuple(
    ("spline_maker.tool_shortcut", {"type": key, "value": "PRESS"},
     {"properties": [("target", mode)]})
    for key, mode, _ in TOOLS
)


_curve_shortcuts = []


def register_curve_shortcuts():
    # Both keymaps matter: Industry Compatible binds tools in 3D View, while
    # Blender's default Curve keymap handles E/R before the active tool map.
    # The shortcut poll confines priority to an active Spline Maker tool.
    keyconfig = bpy.context.window_manager.keyconfigs.addon
    if keyconfig is None:
        return
    for name, space_type in (("Curve", "EMPTY"), ("3D View", "VIEW_3D")):
        keymap = keyconfig.keymaps.new(name=name, space_type=space_type, region_type="WINDOW")
        for key, mode, _ in TOOLS:
            item = keymap.keymap_items.new(
                SPLINE_MAKER_OT_tool_shortcut.bl_idname, key, "PRESS", head=True
            )
            item.properties.target = mode
            _curve_shortcuts.append((keymap, item))


def unregister_curve_shortcuts():
    for keymap, item in _curve_shortcuts:
        keymap.keymap_items.remove(item)
    _curve_shortcuts.clear()


class SplineMakerSelect(bpy.types.WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "EDIT_CURVE"
    bl_idname = tool_id("SELECT")
    bl_label = "Spline Maker Select"
    bl_icon = "ops.generic.select"
    bl_keymap = TOOL_KEYMAP
    bl_widget = "VIEW3D_GGT_spline_maker_transform"


class SplineMakerMove(bpy.types.WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "EDIT_CURVE"
    bl_idname = tool_id("MOVE")
    bl_label = "Spline Maker Move"
    bl_icon = "ops.transform.translate"
    bl_keymap = TOOL_KEYMAP
    bl_widget = "VIEW3D_GGT_spline_maker_transform"


class SplineMakerRotate(bpy.types.WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "EDIT_CURVE"
    bl_idname = tool_id("ROTATE")
    bl_label = "Spline Maker Rotate"
    bl_icon = "ops.transform.rotate"
    bl_keymap = TOOL_KEYMAP
    bl_widget = "VIEW3D_GGT_spline_maker_transform"


class SplineMakerScale(bpy.types.WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "EDIT_CURVE"
    bl_idname = tool_id("SCALE")
    bl_label = "Spline Maker Scale"
    bl_icon = "ops.transform.resize"
    bl_keymap = TOOL_KEYMAP
    bl_widget = "VIEW3D_GGT_spline_maker_transform"


CLASSES = (
    SPLINE_MAKER_OT_add_test_curve,
    SPLINE_MAKER_OT_tangent_step,
    SPLINE_MAKER_OT_switch_tangent_tool,
    SPLINE_MAKER_OT_tool_shortcut,
    VIEW3D_PT_spline_maker_probe,
)
WORKSPACE_TOOLS = (SplineMakerSelect, SplineMakerMove, SplineMakerRotate, SplineMakerScale)
