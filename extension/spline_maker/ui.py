"""3D Viewport entry points for the foundation milestone."""

import bpy


class SPLINE_MAKER_OT_draw_spline(bpy.types.Operator):
    bl_idname = "spline_maker.draw_spline"
    bl_label = "Draw Spline"
    bl_description = "Show the current status of spline drawing"

    @classmethod
    def poll(cls, context):
        return (
            context.mode == "OBJECT"
            and context.area is not None
            and context.area.type == "VIEW_3D"
        )

    def execute(self, context):
        self.report({"INFO"}, "Spline drawing is not implemented yet")
        return {"CANCELLED"}


class VIEW3D_PT_spline_maker(bpy.types.Panel):
    bl_label = "Spline Maker"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Spline Maker"
    bl_context = "objectmode"

    def draw(self, context):
        self.layout.label(text="Spline drawing is in development")
        self.layout.operator(SPLINE_MAKER_OT_draw_spline.bl_idname)


def draw_curve_add_menu(self, context):
    self.layout.operator(SPLINE_MAKER_OT_draw_spline.bl_idname)


CLASSES = (SPLINE_MAKER_OT_draw_spline, VIEW3D_PT_spline_maker)
