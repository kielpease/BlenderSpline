"""Geometry Nodes for mitering the evaluated rectangular sweep."""

import bpy


MITER_LIMIT = 2.0
_STRAIGHT_TOLERANCE = 1e-6


def miter_group():
    group = bpy.data.node_groups.new("Splines Mitered Sweep", "GeometryNodeTree")
    for name in ("Curve", "Profile"):
        group.interface.new_socket(name=name, in_out="INPUT", socket_type="NodeSocketGeometry")
    group.interface.new_socket(name="Mesh", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    link = group.links.new

    def node(type_name, label, x, y):
        result = group.nodes.new(type_name)
        result.label = label
        result.location = (x, y)
        return result

    def put(socket, value):
        if isinstance(value, (int, float)):
            socket.default_value = value
        else:
            link(value, socket)

    def math(op, a, b, label, x, y):
        item = node("ShaderNodeMath", label, x, y)
        item.operation = op
        put(item.inputs[0], a)
        put(item.inputs[1], b)
        return item.outputs[0]

    def vector(op, a, label, x, y, b=None, *, scale=None):
        item = node("ShaderNodeVectorMath", label, x, y)
        item.operation = op
        link(a, item.inputs[0])
        if b is not None:
            link(b, item.inputs[1])
        if scale is not None:
            put(item.inputs["Scale"], scale)
        return item.outputs["Value" if op in {"LENGTH", "DOT_PRODUCT"} else "Vector"]

    inputs = node("NodeGroupInput", "", 0, 550)
    outputs = node("NodeGroupOutput", "", 2940, 550)
    evaluated = node("GeometryNodeResampleCurve", "Keep evaluated Bézier samples", 230, 550)
    evaluated.inputs["Mode"].default_value = "Evaluated"
    link(inputs.outputs["Curve"], evaluated.inputs["Curve"])
    position = node("GeometryNodeInputPosition", "", 0, 120).outputs["Position"]
    point_index = node("GeometryNodeInputIndex", "", 0, -70).outputs["Index"]

    def neighbor(offset, label, y):
        neighbor_index = node("GeometryNodeOffsetPointInCurve", label, 230, y)
        neighbor_index.inputs["Offset"].default_value = offset
        link(point_index, neighbor_index.inputs["Point Index"])
        return neighbor_index.outputs["Point Index"], neighbor_index.outputs["Is Valid Offset"]

    def at_index(field, index, data_type, label, y):
        point = node("GeometryNodeFieldAtIndex", label, 460, y)
        point.data_type = data_type
        link(index, point.inputs["Index"])
        link(field, point.inputs["Value"])
        return point.outputs["Value"]

    previous_index, has_previous = neighbor(-1, "Previous sample", 120)
    following_index, has_following = neighbor(1, "Next sample", -170)
    previous = at_index(position, previous_index, "FLOAT_VECTOR", "Previous position", 120)
    following = at_index(position, following_index, "FLOAT_VECTOR", "Next position", -170)
    incoming = vector("SUBTRACT", position, "Incoming span", 680, 120, previous)
    outgoing = vector("SUBTRACT", following, "Outgoing span", 680, -170, position)
    forward = vector("NORMALIZE", incoming, "Incoming direction", 900, 120)
    onward = vector("NORMALIZE", outgoing, "Outgoing direction", 900, -170)
    turn = vector("SUBTRACT", onward, "Miter direction", 1120, -150, forward)
    turn_length = vector("LENGTH", turn, "Size of turn", 1335, -150)
    both = node("FunctionNodeBooleanMath", "Interior sample", 680, -470)
    both.operation = "AND"
    link(has_previous, both.inputs[0])
    link(has_following, both.inputs[1])
    interior = both.outputs[0]
    direction_dot = vector("DOT_PRODUCT", forward, "Same direction", 1120, 120, onward)
    nearly_straight = math("LESS_THAN", turn_length, _STRAIGHT_TOLERANCE, "Collinear", 1540, -150)
    forward_turn = math("GREATER_THAN", direction_dot, 0.0, "Nonzero forward spans", 1335, 120)
    prune = math("MULTIPLY", nearly_straight, forward_turn, "Redundant sample", 1740, -160)
    prune = math("MULTIPLY", prune, interior, "Keep open ends", 1940, -160)
    tilt = node("GeometryNodeInputCurveTilt", "", 230, -930).outputs["Tilt"]
    prev_tilt = at_index(tilt, previous_index, "FLOAT", "Previous tilt", -930)
    next_tilt = at_index(tilt, following_index, "FLOAT", "Next tilt", -1160)
    min_tilt = math("MINIMUM", prev_tilt, next_tilt, "Lower neighbor tilt", 670, -930)
    max_tilt = math("MAXIMUM", prev_tilt, next_tilt, "Higher neighbor tilt", 670, -1160)
    min_tilt = math("MINIMUM", min_tilt, tilt, "Minimum tilt", 880, -930)
    max_tilt = math("MAXIMUM", max_tilt, tilt, "Maximum tilt", 880, -1160)
    tilt_range = math("SUBTRACT", max_tilt, min_tilt, "Local tilt change", 1090, -930)
    steady_tilt = math("LESS_THAN", tilt_range, _STRAIGHT_TOLERANCE, "Keep changes in tilt", 1310, -930)
    prune = math("MULTIPLY", prune, steady_tilt, "Remove straight, untwisted samples", 2140, -160)
    delete = node("GeometryNodeDeleteGeometry", "Remove collinear rings before mitering", 460, 550)
    link(evaluated.outputs["Curve"], delete.inputs["Geometry"])
    link(prune, delete.inputs["Selection"])

    # The length of the sum of the two unit directions is 2 cos(turn / 2).
    # Limit the extension and scale only along the bend, across the sweep.
    bisector = vector("ADD", forward, "Sum of directions", 1120, -405, onward)
    denominator = vector("LENGTH", bisector, "Twice cosine of half turn", 1335, -405)
    limited = math("MAXIMUM", denominator, 2 / MITER_LIMIT, "Miter limit", 1540, -405)
    ratio = math("DIVIDE", 2.0, limited, "Width correction", 1740, -405)
    extra = math("SUBTRACT", ratio, 1.0, "Additional extension", 1940, -405)
    # A zero-length span produces a zero direction. The sum of lengths then
    # drops below two, so exclude that case even when the dot is zero.
    before_length = vector("LENGTH", forward, "Incoming direction exists", 900, -675)
    after_length = vector("LENGTH", onward, "Outgoing direction exists", 1120, -675)
    valid = math("MULTIPLY", before_length, after_length, "Two nonzero spans", 1540, -675)
    valid = math("MULTIPLY", valid, interior, "Miter only interior rings", 1740, -675)
    extra = math("MULTIPLY", extra, valid, "Bounded interior correction", 2140, -405)
    weight = math("SQRT", extra, 0.0, "Axis weight", 2340, -405)
    axis = vector("NORMALIZE", turn, "Unit miter axis", 1940, 100)
    weighted_axis = vector("SCALE", axis, "Weighted miter axis", 2530, -200, scale=weight)

    capture = node("GeometryNodeCaptureAttribute", "Keep ring center and miter axis on the mesh", 700, 550)
    capture.capture_items.new("VECTOR", "Center")
    capture.capture_items.new("VECTOR", "Miter Axis")
    link(delete.outputs["Geometry"], capture.inputs["Geometry"])
    link(position, capture.inputs["Center"])
    link(weighted_axis, capture.inputs["Miter Axis"])
    normal = node("GeometryNodeSetCurveNormal", "Z-up cross-section", 950, 550)
    normal.inputs["Mode"].default_value = "Z Up"
    link(capture.outputs["Geometry"], normal.inputs["Curve"])
    sweep = node("GeometryNodeCurveToMesh", "", 1190, 550)
    sweep.inputs["Fill Caps"].default_value = True
    link(normal.outputs["Curve"], sweep.inputs["Curve"])
    link(inputs.outputs["Profile"], sweep.inputs["Profile Curve"])

    radial = vector("SUBTRACT", position, "Offset from ring center", 1470, 500, capture.outputs["Center"])
    weighted_axis = capture.outputs["Miter Axis"]
    projection = vector("DOT_PRODUCT", radial, "Offset along bend", 1740, 500, weighted_axis)
    correction = vector("SCALE", weighted_axis, "Extend the miter", 1990, 500, scale=projection)
    deform = node("GeometryNodeSetPosition", "Miter rectangular corners", 2670, 550)
    link(sweep.outputs["Mesh"], deform.inputs["Geometry"])
    link(correction, deform.inputs["Offset"])
    link(deform.outputs["Geometry"], outputs.inputs["Mesh"])
    return group
