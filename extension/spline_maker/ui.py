# SPDX-FileCopyrightText: 2026 Pease Technology
# SPDX-License-Identifier: GPL-3.0-or-later

"""Spline viewport controls and selection-aware sidebar navigation."""

import bpy

from .drawing_probe import SPLINE_MAKER_OT_draw_spline


SIDEBAR_CATEGORY = "Spline"
_sidebar_selection = {}
_sidebar_updates = {}


def _active_selection(context):
    if context.mode == "EDIT_CURVE":
        return context.edit_object
    obj = context.active_object
    return obj if context.mode == "OBJECT" and obj is not None and obj.select_get() else None


def follow_active_object(context):
    """Observe selection changes during redraw, then change tabs outside drawing."""
    if context.window is None or context.area is None or context.area.type != "VIEW_3D":
        return
    area = context.area
    key = (context.window.as_pointer(), area.as_pointer())
    if not context.space_data.show_region_ui:
        _sidebar_selection.pop(key, None)
        return

    obj = _active_selection(context)
    signature = (context.mode, obj.as_pointer() if obj is not None else None)
    if _sidebar_selection.get(key) == signature:
        return
    sidebar = next((region for region in area.regions if region.type == "UI"), None)
    if sidebar is None:
        return
    _sidebar_selection[key] = signature
    if obj is None:
        return

    from .curve_connections import editable_curve
    category = sidebar.active_panel_category
    if context.mode == "EDIT_CURVE" or editable_curve(obj):
        target = SIDEBAR_CATEGORY
    elif category == SIDEBAR_CATEGORY:
        target = "Item"
    else:
        return

    if category != target:
        _sidebar_updates[key] = (context.window, area, signature, target)
        if not bpy.app.timers.is_registered(apply_sidebar_updates):
            bpy.app.timers.register(apply_sidebar_updates)


def apply_sidebar_updates():
    pending = tuple(_sidebar_updates.items())
    _sidebar_updates.clear()
    context = bpy.context
    for key, (window, area, signature, target) in pending:
        try:
            if (window not in tuple(context.window_manager.windows)
                    or area not in tuple(window.screen.areas)
                    or area.type != "VIEW_3D" or not area.spaces.active.show_region_ui):
                _sidebar_selection.pop(key, None)
                continue
            sidebar = next((region for region in area.regions if region.type == "UI"), None)
            if sidebar is None:
                _sidebar_selection.pop(key, None)
                continue
            with context.temp_override(window=window, area=area, region=sidebar):
                obj = _active_selection(context)
                if obj is None or (context.mode, obj.as_pointer()) != signature:
                    continue
                if target == "Item" and sidebar.active_panel_category != SIDEBAR_CATEGORY:
                    continue
                sidebar.active_panel_category = target
                sidebar.tag_redraw()
        except (ReferenceError, TypeError):
            # A closed area or a category Blender has yet to draw can be
            # encountered when switching objects and workspaces together.
            _sidebar_selection.pop(key, None)


def reset_sidebar_following():
    if bpy.app.timers.is_registered(apply_sidebar_updates):
        bpy.app.timers.unregister(apply_sidebar_updates)
    _sidebar_updates.clear()
    _sidebar_selection.clear()


class VIEW3D_PT_spline_maker(bpy.types.Panel):
    bl_label = "Spline"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = SIDEBAR_CATEGORY
    bl_context = "objectmode"

    def draw(self, context):
        layout = self.layout.box()
        row = layout.row()
        row.operator_context = "INVOKE_REGION_WIN"
        row.operator(SPLINE_MAKER_OT_draw_spline.bl_idname)
        row = layout.row()
        row.operator_context = "EXEC_REGION_WIN"
        label = "6  Edit Active" if len(context.selected_objects) > 1 else "6  Edit Spline"
        row.operator("spline_maker.enter_edit", text=label)
        row.operator("spline_maker.attach_curves")
        from .profile import draw_profile_settings
        draw_profile_settings(layout, context)
        from .display import draw_settings
        draw_settings(layout, context)


def draw_curve_add_menu(self, context):
    row = self.layout.row()
    row.operator_context = "INVOKE_REGION_WIN"
    row.operator(SPLINE_MAKER_OT_draw_spline.bl_idname, icon="CURVE_BEZCURVE")


CLASSES = (SPLINE_MAKER_OT_draw_spline, VIEW3D_PT_spline_maker)
