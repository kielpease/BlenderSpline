"""Rebase a viewport gesture when native navigation changes its projection."""

_NAVIGATION = {
    "MIDDLEMOUSE", "WHEELUPMOUSE", "WHEELDOWNMOUSE", "WHEELINMOUSE", "WHEELOUTMOUSE",
    "WHEELLEFTMOUSE", "WHEELRIGHTMOUSE", "TRACKPADPAN", "TRACKPADZOOM", "MOUSEROTATE",
    "NUMPAD_PLUS", "NUMPAD_MINUS", "NUMPAD_PERIOD",
    "NDOF_MOTION", "NDOF_BUTTON_FIT", "NDOF_BUTTON_FRONT", "NDOF_BUTTON_BACK",
    "NDOF_BUTTON_LEFT", "NDOF_BUTTON_RIGHT", "NDOF_BUTTON_TOP", "NDOF_BUTTON_BOTTOM",
} | {f"NUMPAD_{digit}" for digit in range(10)}
_INDUSTRY_VIEWS = {"F1", "F2", "F3", "F4", "F5"}


class DragNavigation:
    def __init__(self, context):
        self.matrix = context.region_data.perspective_matrix.copy()
        self.size = (context.region.width, context.region.height)
        self.pending = False
        keyconfigs = getattr(context.window_manager, "keyconfigs", None)
        name = keyconfigs.active.name if keyconfigs and keyconfigs.active else ""
        self.industry = name.replace("_", " ").casefold() == "industry compatible"

    def forward(self, event):
        # The caller returns PASS_THROUGH alone so native keymaps still see the event.
        if (event.type in _NAVIGATION
                or (self.industry and event.type in _INDUSTRY_VIEWS)
                or (event.type in {"LEFTMOUSE", "RIGHTMOUSE"} and event.value == "PRESS"
                    and getattr(event, "alt", False))):
            self.pending = True
            return True
        return False

    def rebase(self, context):
        matrix = context.region_data.perspective_matrix
        size = (context.region.width, context.region.height)
        if not self.pending and matrix == self.matrix and size == self.size:
            return False
        self.pending = False
        self.matrix = matrix.copy()
        self.size = size
        return True
