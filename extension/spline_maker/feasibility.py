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
    from .segment_selection import composite
    if composite(context):
        return []  # Composite levels transform geometry rather than tangents.
    return [(point, side) for point in editable_bezier_points(context)
            if point.select_control_point for side in ("left", "right")]


class SPLINE_MAKER_OT_add_test_curve(bpy.types.Operator):
    bl_idname = "spline_maker.add_test_curve"
    bl_label = "Add Bézier Test Curve"
    bl_description = "Add a native Bézier sample at the 3D cursor for the SM-002 probe"
    bl_options = {"UNDO", "INTERNAL"}

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
    bl_label = "Apply Spline Transform Step"
    bl_description = "Transform vertex tangents, or selected geometry about its center"
    bl_options = {"UNDO", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        from .tangent_drag import has_selection
        return (
            context.area is not None
            and context.area.type == "VIEW_3D"
            and active_mode(context) in {"ROTATE", "SCALE"}
            and has_selection(context)
        )

    def execute(self, context):
        mode = active_mode(context)
        from . import tangent_drag
        from .segment_selection import composite
        matrix = Matrix.Rotation(radians(15), 3, "Z") if mode == "ROTATE" else Matrix.Scale(1.25, 3)
        pivot = move_origin(context) if composite(context) else None
        if pivot is not None:
            world = context.edit_object.matrix_world.to_3x3()
            if abs(world.determinant()) < 1e-12:
                return {"CANCELLED"}
            matrix = world.inverted() @ matrix @ world
        tangent_drag.apply(context.edit_object.data, tangent_drag.capture(context), matrix,
                           rotating=mode == "ROTATE", pivot=pivot)
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
        result = bpy.ops.wm.tool_set_by_id(name=tool_id(self.target), space_type="VIEW_3D")
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


class SPLINE_MAKER_OT_select_shortcut(bpy.types.Operator):
    bl_idname = "spline_maker.select_shortcut"
    bl_label = "Activate Spline Maker Select"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        return SPLINE_MAKER_OT_switch_tangent_tool.poll(context)

    def execute(self, context):
        return bpy.ops.spline_maker.switch_tangent_tool(target="SELECT")


class SPLINE_MAKER_OT_enter_edit(bpy.types.Operator):
    bl_idname = "spline_maker.enter_edit"
    bl_label = "Edit Spline"
    bl_description = "Enter Spline Maker vertex editing for the selected Bezier curve"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        if context.area is None or context.area.type != "VIEW_3D":
            return False
        if context.mode == "EDIT_CURVE":
            return SPLINE_MAKER_OT_switch_tangent_tool.poll(context)
        obj = context.active_object
        return (context.mode == "OBJECT" and obj is not None
                and obj.type == "CURVE" and obj.select_get()
                and len(context.selected_objects) == 1
                and obj.is_editable and obj.data.is_editable
                and bool(obj.data.splines)
                and all(s.type == "BEZIER" for s in obj.data.splines))

    def execute(self, context):
        if context.mode == "OBJECT":
            result = bpy.ops.object.mode_set(mode="EDIT")
            if result != {"FINISHED"}:
                return result
        result = bpy.ops.spline_maker.switch_tangent_tool(target="SELECT")
        if result != {"FINISHED"}:
            return result
        return bpy.ops.spline_maker.selection_level(target="VERTEX")


class SPLINE_MAKER_OT_enter_vertex_edit(bpy.types.Operator):
    bl_idname = "spline_maker.enter_vertex_edit"
    bl_label = "Enter Spline Maker Vertex Editing"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and SPLINE_MAKER_OT_enter_edit.poll(context)

    def execute(self, context):
        return bpy.ops.spline_maker.enter_edit()


class SPLINE_MAKER_OT_finish_edit(bpy.types.Operator):
    bl_idname = "spline_maker.finish_edit"
    bl_label = "Finish Editing — Object Mode"
    bl_description = "Keep curve edits and return to Object Mode with native Select Box"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        return SPLINE_MAKER_OT_switch_tangent_tool.poll(context)

    def execute(self, context):
        from . import edit_drag, tangent_drag, vertex_selection, transform_gizmos
        edit_drag.unregister()
        tangent_drag.unregister()
        vertex_selection.stop_active(context)
        # Reset the Edit tool too, so re-entering Edit Mode starts in Blender's
        # normal selection context rather than the old Spline Maker tool.
        bpy.ops.wm.tool_set_by_id(name="builtin.select_box")
        result = bpy.ops.object.mode_set(mode="OBJECT")
        if result != {"FINISHED"}:
            return result
        bpy.ops.wm.tool_set_by_id(name="builtin.select_box")
        context.window_manager.spline_maker_selection_level = "VERTEX"
        transform_gizmos.unregister()
        context.area.tag_redraw()
        return {"FINISHED"}


class SPLINE_MAKER_OT_exit_edit_shortcut(bpy.types.Operator):
    bl_idname = "spline_maker.exit_edit_shortcut"
    bl_label = "Finish Spline Maker Editing"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        return SPLINE_MAKER_OT_finish_edit.poll(context) and active_mode(context) is not None

    def execute(self, context):
        return bpy.ops.spline_maker.finish_edit()


def move_origin(context):
    from .edit_drag import selected_anchors
    from .segment_selection import composite
    points = selected_anchors(context)
    if points and composite(context):
        return sum((point.co for point in points), Vector()) / len(points)
    return points[0].co if points else None


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
        supported = SPLINE_MAKER_OT_switch_tangent_tool.poll(context)
        mode = active_mode(context) if supported else None
        layout.operator("spline_maker.finish_edit", text="Finish Editing → Object Mode")
        if mode is not None:
            layout.label(text="4 / Esc: Object Mode (cancel drag first)")
        layout.label(text="Spline shortcuts active: Q/W/E/R" if mode is not None else "Choose a tool or selection level to enter")
        for key, target, label in TOOLS:
            op = layout.operator("spline_maker.switch_tangent_tool", text=f"{key}  {label}", depress=mode == target)
            op.target = target
        if supported:
            from .segment_selection import level
            from .region_selection import unavailable_reason, whole_selected
            current_level = level(context)
            segment = current_level != "VERTEX"
            row = layout.row(align=True)
            reason = unavailable_reason(context.edit_object.data)
            for i, (target, label) in enumerate((("VERTEX", "1  Vertex"), ("SEGMENT", "2  Segment"),
                                                ("REGION", "3  Spline"), ("WHOLE", "Whole curve"))):
                if i == 2:
                    row = layout.row(align=True)
                cell = row.row(align=True)
                cell.enabled = target != "REGION" or not reason
                cell.operator("spline_maker.enter_selection_level", text=label,
                              depress=current_level == target).target = target
            if reason:
                from textwrap import wrap
                for line in wrap("Spline: " + reason, 38):
                    layout.label(text=line)
            if current_level == "WHOLE":
                layout.label(text="Geometry selected" if whole_selected(context.edit_object.data) else "Active object; geometry unselected")
                row = layout.row(align=True)
                row.operator("spline_maker.whole_selection", text="Select all geometry").action = "SELECT"
                row.operator("spline_maker.whole_selection", text="Clear selection").action = "CLEAR"
            if mode is not None:
                layout.label(text="Shift-click to toggle")
                layout.label(text="Box touches segment to select" if current_level == "SEGMENT"
                                  else "Box encloses whole selection" if segment else "Drag to box-select vertices")
                layout.label(text="Drag handle diamonds freely")
        if mode == "MOVE":
            layout.label(text="Arrows: axis; squares: plane")
            if current_level == "WHOLE":
                layout.label(text="Move all source splines together")
        elif mode in {"ROTATE", "SCALE"}:
            layout.label(text="Drag an axis ring" if mode == "ROTATE" else "Drag an axis box or center")
            if mode == "SCALE" and segment:
                layout.label(text="Offset square: XY scale (Z fixed)")
            layout.label(text="Pivot: selection center" if segment else "Pivot: each vertex anchor")
            label = (("Rotate Selection 15° (Z)" if mode == "ROTATE" else "Scale Selection ×1.25") if segment
                     else ("Rotate Handles 15°" if mode == "ROTATE" else "Scale Handles ×1.25"))
            layout.operator(SPLINE_MAKER_OT_tangent_step.bl_idname, text=label)
        if mode is not None:
            from .vertex_types import draw_vertex_types
            layout.separator()
            layout.label(text="Vertex Type (both tangents)")
            draw_vertex_types(layout)
        from .display import draw_settings
        draw_settings(layout, context)


TOOL_KEYMAP = tuple(
    ("spline_maker.select_shortcut" if mode == "SELECT" else "spline_maker.tool_shortcut",
     {"type": key, "value": "PRESS"},
     {} if mode == "SELECT" else {"properties": [("target", mode)]})
    for key, mode, _ in TOOLS
)


_curve_shortcuts = []


def register_curve_shortcuts():
    # Both keymaps matter: Industry Compatible binds tools in 3D View, while
    # Blender's default Curve keymap handles E/R before the active tool map.
    # Q is explicit entry from any supported Curve Edit tool; W/E/R stay scoped.
    keyconfig = bpy.context.window_manager.keyconfigs.addon
    if keyconfig is None:
        return
    for name, space_type in (("Curve", "EMPTY"), ("3D View", "VIEW_3D")):
        keymap = keyconfig.keymaps.new(name=name, space_type=space_type, region_type="WINDOW")
        for key, mode, _ in TOOLS:
            item = keymap.keymap_items.new(
                "spline_maker.select_shortcut" if mode == "SELECT" else "spline_maker.tool_shortcut",
                key, "PRESS", head=True
            )
            if mode != "SELECT":
                item.properties.target = mode
            _curve_shortcuts.append((keymap, item))
        for key in ("ESC", "FOUR"):
            item = keymap.keymap_items.new("spline_maker.exit_edit_shortcut", key, "PRESS", head=True)
            _curve_shortcuts.append((keymap, item))
    for name, space_type in (("Object Non-modal", "EMPTY"), ("Object Mode", "EMPTY"),
                             ("Curve", "EMPTY"), ("3D View", "VIEW_3D")):
        keymap = keyconfig.keymaps.new(name=name, space_type=space_type, region_type="WINDOW")
        item = keymap.keymap_items.new("spline_maker.enter_edit", "SIX", "PRESS", head=True)
        _curve_shortcuts.append((keymap, item))
        if name != "Curve":
            item = keymap.keymap_items.new("spline_maker.enter_vertex_edit", "ONE", "PRESS", head=True)
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
    SPLINE_MAKER_OT_select_shortcut,
    SPLINE_MAKER_OT_enter_edit,
    SPLINE_MAKER_OT_enter_vertex_edit,
    SPLINE_MAKER_OT_finish_edit,
    SPLINE_MAKER_OT_exit_edit_shortcut,
    VIEW3D_PT_spline_maker_probe,
)
WORKSPACE_TOOLS = (SplineMakerSelect, SplineMakerMove, SplineMakerRotate, SplineMakerScale)
