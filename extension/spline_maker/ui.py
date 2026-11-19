"""3D Viewport entry points for the foundation milestone."""

import bpy

from .drawing_probe import SPLINE_MAKER_OT_draw_spline


class VIEW3D_PT_spline_maker(bpy.types.Panel):
    bl_label = "Spline Maker"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Spline Maker"
    bl_context = "objectmode"

    def draw(self, context):
        row = self.layout.row()
        row.operator_context = "INVOKE_REGION_WIN"
        row.operator(SPLINE_MAKER_OT_draw_spline.bl_idname)
        self.layout.operator("spline_maker.add_test_curve")


def draw_curve_add_menu(self, context):
    row = self.layout.row()
    row.operator_context = "INVOKE_REGION_WIN"
    row.operator(SPLINE_MAKER_OT_draw_spline.bl_idname)


CLASSES = (SPLINE_MAKER_OT_draw_spline, VIEW3D_PT_spline_maker)
