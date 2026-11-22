"""Live cross-sections for native Bézier curve objects."""

from math import pi

import bpy

from . import profile_corners


_GROUP_NAME = "Splines Profile"
_GROUP_KEY = "spline_maker_profile"
_GROUP_VERSION = 2
_MIN_DIMENSION = 1e-6
_RECTANGLE_DIMENSIONS = {
    "Height": "spline_maker_profile_height",
    "Width": "spline_maker_profile_width",
}


def is_profile_modifier(modifier):
    return (modifier.type == "NODES" and modifier.node_group is not None
            and modifier.node_group.get(_GROUP_KEY) in {1, _GROUP_VERSION})


def profile_modifier(obj):
    return next((modifier for modifier in obj.modifiers if is_profile_modifier(modifier)), None)


def profile_input(modifier, name):
    socket = modifier.node_group.interface.items_tree[name]
    return getattr(modifier.properties.inputs, socket.identifier)


def profile_group():
    local = [group for group in bpy.data.node_groups
             if group.bl_idname == "GeometryNodeTree" and group.library is None]
    existing = next((group for group in local if group.get(_GROUP_KEY) == _GROUP_VERSION), None)
    if existing is not None:
        return existing

    group = bpy.data.node_groups.new(_GROUP_NAME, "GeometryNodeTree")
    group.is_modifier = True
    interface = group.interface
    interface.new_socket(name="Curve", in_out="INPUT", socket_type="NodeSocketGeometry")
    interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    shape = interface.new_socket(name="Shape", in_out="INPUT", socket_type="NodeSocketMenu")
    for name, default in (("Height", 1.0), ("Width", 1.0), ("Radius", 0.5)):
        field = interface.new_socket(name=name, in_out="INPUT", socket_type="NodeSocketFloat")
        field.subtype = "DISTANCE"
        field.min_value = _MIN_DIMENSION
        field.default_value = default
    roll = interface.new_socket(name="Roll", in_out="INPUT", socket_type="NodeSocketFloat")
    roll.subtype = "ANGLE"
    roll.default_value = 0.0

    def add_node(node_type, x, y):
        node = group.nodes.new(node_type)
        node.location = (x, y)
        return node

    link = group.links.new
    inputs = add_node("NodeGroupInput", 0, 0)
    outputs = add_node("NodeGroupOutput", 1960, 150)
    normal = add_node("GeometryNodeSetCurveNormal", 690, -475)
    normal.inputs["Mode"].default_value = "Z Up"
    rectangle = add_node("GeometryNodeCurvePrimitiveQuadrilateral", 245, 85)
    rectangle.mode = "RECTANGLE"
    circle = add_node("GeometryNodeCurvePrimitiveCircle", 690, -195)
    circle.mode = "RADIUS"
    circle.inputs["Resolution"].default_value = 32
    combine = add_node("ShaderNodeCombineXYZ", 245, -175)
    rotation = add_node("FunctionNodeEulerToRotation", 465, -175)
    transform = add_node("GeometryNodeTransform", 690, 105)
    miter = add_node("GeometryNodeGroup", 900, 140)
    miter.node_tree = profile_corners.miter_group()
    menu = add_node("GeometryNodeMenuSwitch", 1320, 100)
    menu.data_type = "GEOMETRY"
    menu.enum_items.clear()
    for label in ("Rectangle", "Circle"):
        menu.enum_items.new(label)
    sweep = add_node("GeometryNodeCurveToMesh", 900, -260)
    sweep.inputs["Fill Caps"].default_value = True
    edge_angle = add_node("GeometryNodeInputMeshEdgeAngle", 1255, -180)
    sharp = add_node("FunctionNodeCompare", 1460, -160)
    sharp.data_type = "FLOAT"
    sharp.operation = "GREATER_THAN"
    sharp.inputs["B"].default_value = pi / 4
    shading = add_node("GeometryNodeSetShadeSmooth", 1690, 150)
    shading.domain = "EDGE"
    shading.inputs["Shade Smooth"].default_value = False

    link(inputs.outputs["Curve"], normal.inputs["Curve"])
    for name in ("Height", "Width"):
        link(inputs.outputs[name], rectangle.inputs[name])
    link(inputs.outputs["Radius"], circle.inputs["Radius"])
    link(inputs.outputs["Roll"], combine.inputs["Z"])
    link(combine.outputs["Vector"], rotation.inputs["Euler"])
    link(rotation.outputs["Rotation"], transform.inputs["Rotation"])
    link(rectangle.outputs["Curve"], transform.inputs["Geometry"])
    link(inputs.outputs["Shape"], menu.inputs["Menu"])
    shape.default_value = "Rectangle"
    link(inputs.outputs["Curve"], miter.inputs["Curve"])
    link(transform.outputs["Geometry"], miter.inputs["Profile"])
    link(miter.outputs["Mesh"], menu.inputs["Rectangle"])
    link(circle.outputs["Curve"], sweep.inputs["Profile Curve"])
    link(normal.outputs["Curve"], sweep.inputs["Curve"])
    link(sweep.outputs["Mesh"], menu.inputs["Circle"])
    # Keep rectangular corners and end caps crisp without faceting round walls.
    link(edge_angle.outputs["Unsigned Angle"], sharp.inputs["A"])
    link(sharp.outputs["Result"], shading.inputs["Selection"])
    link(menu.outputs["Output"], shading.inputs["Geometry"])
    link(shading.outputs["Geometry"], outputs.inputs["Geometry"])
    legacy = next((item for item in local if item.get(_GROUP_KEY) == 1), None)
    if legacy is not None:
        for key in _RECTANGLE_DIMENSIONS.values():
            if key in legacy:
                group[key] = legacy[key]
                group.use_fake_user = True
    group[_GROUP_KEY] = _GROUP_VERSION
    return group


def unit_scale(scene):
    units = scene.unit_settings
    return units.scale_length if units.system != "NONE" else 1.0


def add_profile(obj, scene):
    group = profile_group()
    modifier = obj.modifiers.new(_GROUP_NAME, "NODES")
    modifier.node_group = group
    modifier.show_in_editmode = True
    scale = unit_scale(scene)
    size = 0.3048 / scale if scene.unit_settings.system == "IMPERIAL" else 1.0
    for name, key in _RECTANGLE_DIMENSIONS.items():
        remembered = group.get(key)
        value = size if remembered is None else max(remembered / scale, _MIN_DIMENSION)
        profile_input(modifier, name).value = value
    profile_input(modifier, "Radius").value = size / 2
    return modifier


class SPLINE_MAKER_OT_toggle_profile(bpy.types.Operator):
    bl_idname = "spline_maker.toggle_profile"
    bl_label = "Make Profile"
    bl_description = "Show or hide a live profile along the selected Bézier curve"
    bl_options = {"UNDO", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        from .feasibility import SPLINE_MAKER_OT_enter_edit
        return (context.mode == "OBJECT" and SPLINE_MAKER_OT_enter_edit.poll(context)
                and len(context.selected_objects) == 1)

    def execute(self, context):
        obj = context.active_object
        modifier = profile_modifier(obj)
        enabled = modifier is None or not modifier.show_viewport
        data = obj.data
        if enabled and (data.extrude or data.bevel_depth
                        or (data.bevel_mode == "OBJECT" and data.bevel_object is not None)):
            self.report({"WARNING"}, "Clear the curve's native bevel and extrusion before making a profile")
            return {"CANCELLED"}
        if modifier is None:
            modifier = add_profile(obj, context.scene)
        modifier.show_viewport = modifier.show_render = enabled
        obj.update_tag()
        context.area.tag_redraw()
        return {"FINISHED"}


class SPLINE_MAKER_OT_set_profile_dimension(bpy.types.Operator):
    bl_idname = "spline_maker.set_profile_dimension"
    bl_label = "Set Profile Dimension"
    bl_description = "Set this dimension and remember it for new profiles in this file"
    bl_options = {"UNDO", "INTERNAL"}

    dimension: bpy.props.EnumProperty(items=(("Height", "Height", ""), ("Width", "Width", "")))
    value: bpy.props.FloatProperty(name="Dimension", subtype="DISTANCE", unit="LENGTH",
                                   default=1.0, min=_MIN_DIMENSION)

    @classmethod
    def poll(cls, context):
        if not SPLINE_MAKER_OT_toggle_profile.poll(context):
            return False
        modifier = profile_modifier(context.active_object)
        return (modifier is not None and modifier.show_viewport
                and profile_input(modifier, "Shape").value == "Rectangle")

    def invoke(self, context, event):
        modifier = profile_modifier(context.active_object)
        self.value = profile_input(modifier, self.dimension).value
        return context.window_manager.invoke_props_dialog(self, width=230, title=f"Profile {self.dimension}",
                                                          confirm_text="Set")

    def draw(self, context):
        row = self.layout.row()
        row.activate_init = True
        row.prop(self, "value", text=self.dimension)

    def execute(self, context):
        obj = context.active_object
        modifier = profile_modifier(obj)
        profile_input(modifier, self.dimension).value = self.value
        # Commit the modifier value and file default in the same Undo step.
        group = profile_group()
        group[_RECTANGLE_DIMENSIONS[self.dimension]] = self.value * unit_scale(context.scene)
        group.use_fake_user = True
        obj.update_tag()
        context.area.tag_redraw()
        return {"FINISHED"}


class SPLINE_MAKER_OT_update_profile(bpy.types.Operator):
    bl_idname = "spline_maker.update_profile"
    bl_label = "Update Profile Corners"
    bl_description = "Apply the current corner joins to this profile and keep its dimensions"
    bl_options = {"UNDO", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        if not SPLINE_MAKER_OT_toggle_profile.poll(context):
            return False
        modifier = profile_modifier(context.active_object)
        return modifier is not None and modifier.node_group.get(_GROUP_KEY) == 1

    def execute(self, context):
        obj = context.active_object
        modifier = profile_modifier(obj)
        values = {name: profile_input(modifier, name).value
                  for name in ("Shape", "Height", "Width", "Radius", "Roll")}
        modifier.node_group = profile_group()
        for name, value in values.items():
            profile_input(modifier, name).value = value
        obj.update_tag()
        context.area.tag_redraw()
        return {"FINISHED"}


def draw_profile_settings(layout, context):
    if not SPLINE_MAKER_OT_toggle_profile.poll(context):
        return
    obj = context.active_object
    modifier = profile_modifier(obj)
    enabled = modifier is not None and modifier.show_viewport
    layout.separator()
    layout.prop(obj.data, "resolution_u", text="Curve Resolution")
    toggle = layout.row()
    toggle.alignment = "LEFT"
    toggle.operator("spline_maker.toggle_profile",
                    icon="CHECKBOX_HLT" if enabled else "CHECKBOX_DEHLT", emboss=False)
    if modifier is not None and modifier.node_group.get(_GROUP_KEY) == 1:
        layout.operator("spline_maker.update_profile")
    if enabled:
        controls = layout.column(align=True)
        controls.operator_context = "INVOKE_REGION_WIN"
        shape = profile_input(modifier, "Shape")
        controls.prop(shape, "value", text="Shape")
        if shape.value == "Rectangle":
            units = context.scene.unit_settings
            for name in _RECTANGLE_DIMENSIONS:
                value = profile_input(modifier, name).value
                text = (f"{value:.5g}" if units.system == "NONE" else bpy.utils.units.to_string(
                    units.system, "LENGTH", value * unit_scale(context.scene), precision=5,
                    split_unit=units.use_separate))
                row = controls.split(factor=0.26, align=True)
                row.label(text=f"{name}:")
                row.operator("spline_maker.set_profile_dimension", text=text).dimension = name
            controls.prop(profile_input(modifier, "Roll"), "value", text="Roll")
        else:
            controls.prop(profile_input(modifier, "Radius"), "value", text="Radius")


CLASSES = (SPLINE_MAKER_OT_toggle_profile, SPLINE_MAKER_OT_set_profile_dimension, SPLINE_MAKER_OT_update_profile)
