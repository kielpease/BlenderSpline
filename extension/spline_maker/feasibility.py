"""A small Edit Mode probe for native picking and tool-local transforms."""

from math import radians

import bpy
from bpy_extras import view3d_utils
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
        if getattr(point, f"handle_{side}_type") in {"FREE", "VECTOR"}
        and (point.select_control_point or getattr(point, f"select_{side}_handle"))
    ]


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
            and bool(selected_handles(context))
        )

    def execute(self, context):
        mode = active_mode(context)
        matrix = Matrix.Rotation(radians(15), 3, "Z") if mode == "ROTATE" else Matrix.Scale(1.25, 3)
        handles = [
            (point, f"handle_{side}", point.co + matrix @ (getattr(point, f"handle_{side}") - point.co))
            for point, side in selected_handles(context)
        ]
        for point, attribute, coordinate in handles:
            if getattr(point, f"{attribute}_type") == "VECTOR":
                setattr(point, f"{attribute}_type", "FREE")
            setattr(point, attribute, coordinate)
        context.edit_object.data.update_tag()
        context.area.tag_redraw()
        return {"FINISHED"}


class SPLINE_MAKER_OT_switch_tangent_tool(bpy.types.Operator):
    bl_idname = "spline_maker.switch_tangent_tool"
    bl_label = "Switch Spline Maker Tangent Tool"
    bl_options = {"INTERNAL"}

    target: bpy.props.EnumProperty(items=(
        ("ROTATE", "Rotate", ""),
        ("SCALE", "Scale", ""),
    ))

    @classmethod
    def poll(cls, context):
        return (
            context.area is not None
            and context.area.type == "VIEW_3D"
            and active_mode(context) is not None
        )

    def execute(self, context):
        return bpy.ops.wm.tool_set_by_id(name=tool_id(self.target))


class VIEW3D_GGT_spline_maker_tangent(bpy.types.GizmoGroup):
    bl_idname = "VIEW3D_GGT_spline_maker_tangent"
    bl_label = "Spline Maker Tangent Step"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_options = {"PERSISTENT", "SCALE"}

    @classmethod
    def poll(cls, context):
        return SPLINE_MAKER_OT_tangent_step.poll(context)

    def setup(self, context):
        self.button = self.gizmos.new("GIZMO_GT_button_2d")
        self.button.target_set_operator(SPLINE_MAKER_OT_tangent_step.bl_idname)
        self.button.draw_options = {"BACKDROP", "OUTLINE"}
        self.button.scale_basis = 14
        self.button.color = (0.15, 0.55, 1.0)
        self.button.color_highlight = (0.35, 0.75, 1.0)
        self.button.alpha = 0.85
        self.button.alpha_highlight = 1.0

    def draw_prepare(self, context):
        handles = selected_handles(context)
        position = None
        if handles:
            anchor = context.edit_object.matrix_world @ handles[0][0].co
            position = view3d_utils.location_3d_to_region_2d(context.region, context.region_data, anchor)
        self.button.hide = position is None
        if position is not None:
            self.button.icon = (
                "DRIVER_ROTATIONAL_DIFFERENCE"
                if active_mode(context) == "ROTATE"
                else "FULLSCREEN_ENTER"
            )
            self.button.matrix_basis.translation = (position.x, position.y + 36, 0)


def move_origin(context):
    for point in editable_bezier_points(context):
        if point.select_control_point:
            return point.co
        if point.select_left_handle:
            return point.handle_left
        if point.select_right_handle:
            return point.handle_right
    return None


class VIEW3D_GGT_spline_maker_move(bpy.types.GizmoGroup):
    bl_idname = "VIEW3D_GGT_spline_maker_move"
    bl_label = "Spline Maker Move Axes"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_options = {"PERSISTENT", "3D", "SCALE"}

    @classmethod
    def poll(cls, context):
        return active_mode(context) == "MOVE" and move_origin(context) is not None

    def setup(self, context):
        self.arrows = []
        for axis in range(3):
            direction = Vector(tuple(float(i == axis) for i in range(3)))
            arrow = self.gizmos.new("GIZMO_GT_arrow_3d")
            arrow.matrix_basis = direction.to_track_quat("Z", "Y").to_matrix().to_4x4()
            arrow.color = tuple(0.95 if i == axis else 0.18 for i in range(3))
            arrow.color_highlight = (1.0, 1.0, 1.0)
            arrow.alpha = 0.85
            arrow.alpha_highlight = 1.0
            arrow.scale_basis = 0.8
            props = arrow.target_set_operator("transform.translate")
            props.constraint_axis = tuple(i == axis for i in range(3))
            props.orient_type = "GLOBAL"
            props.release_confirm = True
            self.arrows.append(arrow)

    def draw_prepare(self, context):
        origin = move_origin(context)
        for arrow in self.arrows:
            arrow.hide = origin is None
            if origin is not None:
                arrow.matrix_basis.translation = context.edit_object.matrix_world @ origin


class VIEW3D_PT_spline_maker_probe(bpy.types.Panel):
    bl_label = "Bézier Interaction Test"
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
        for key, target, label in TOOLS:
            op = layout.operator("wm.tool_set_by_id", text=f"{key}  {label}", depress=mode == target)
            op.name = tool_id(target)
            op.space_type = "VIEW_3D"
        if mode in {"ROTATE", "SCALE"}:
            label = "Rotate Handles 15°" if mode == "ROTATE" else "Scale Handles ×1.25"
            layout.operator(SPLINE_MAKER_OT_tangent_step.bl_idname, text=label)


TOOL_KEYMAP = tuple(
    ("wm.tool_set_by_id", {"type": key, "value": "PRESS"},
     {"properties": [("name", tool_id(mode))]})
    for key, mode, _ in TOOLS if mode in {"SELECT", "MOVE"}
)


_curve_shortcuts = []


def register_curve_shortcuts():
    # Native Curve mode handles E and R before the active tool keymap.
    # Poll lets Blender's bindings run whenever a Spline Maker tool is inactive.
    keyconfig = bpy.context.window_manager.keyconfigs.addon
    if keyconfig is None:
        return
    keymap = keyconfig.keymaps.new(name="Curve", space_type="EMPTY", region_type="WINDOW")
    for key, mode, _ in TOOLS:
        if mode in {"ROTATE", "SCALE"}:
            item = keymap.keymap_items.new(
                SPLINE_MAKER_OT_switch_tangent_tool.bl_idname, key, "PRESS", head=True
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


class SplineMakerMove(bpy.types.WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "EDIT_CURVE"
    bl_idname = tool_id("MOVE")
    bl_label = "Spline Maker Move"
    bl_icon = "ops.transform.translate"
    bl_keymap = TOOL_KEYMAP


class SplineMakerRotate(bpy.types.WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "EDIT_CURVE"
    bl_idname = tool_id("ROTATE")
    bl_label = "Spline Maker Rotate"
    bl_icon = "ops.transform.rotate"
    bl_keymap = TOOL_KEYMAP


class SplineMakerScale(bpy.types.WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "EDIT_CURVE"
    bl_idname = tool_id("SCALE")
    bl_label = "Spline Maker Scale"
    bl_icon = "ops.transform.resize"
    bl_keymap = TOOL_KEYMAP


CLASSES = (
    SPLINE_MAKER_OT_add_test_curve,
    SPLINE_MAKER_OT_tangent_step,
    SPLINE_MAKER_OT_switch_tangent_tool,
    VIEW3D_GGT_spline_maker_tangent,
    VIEW3D_GGT_spline_maker_move,
    VIEW3D_PT_spline_maker_probe,
)
WORKSPACE_TOOLS = (SplineMakerSelect, SplineMakerMove, SplineMakerRotate, SplineMakerScale)
