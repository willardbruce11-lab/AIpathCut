"""Fill scan G-code generator."""

from __future__ import annotations

from aipathcut.core.toolpath_pipeline import (
    ToolpathConfig,
    build_geometry,
    clone_geometry_for_center,
    emit_fill_gcode,
    geometry_from_dict,
)
from aipathcut.core.transform_utils import get_contours_bounds, rotate_contours_90


class FillGenerator:
    """Generate scan-line fill G-code."""

    UI_BASE_WIDTH = 50
    UI_BASE_HEIGHT = 76

    GCODE_BASE_WIDTH = 10
    GCODE_BASE_HEIGHT = 200

    MM_PER_GCODE_X = 76.0 / 9.0
    MM_PER_GCODE_Y = 50.0 / 300.0
    SCALE_FACTOR = 0.8

    def __init__(self, feed_rate=1000, paper_center_x=5.8, paper_center_y=-150):
        self.feed_rate = feed_rate
        self.paper_center_x = paper_center_x
        self.paper_center_y = paper_center_y
        self.external_transform_params = None

    def _get_contours_bounds(self, contours):
        return get_contours_bounds(contours)

    def _rotate_contours_90(self, contours, orig_width, orig_height):
        return rotate_contours_90(contours, orig_width, orig_height)

    def set_transform_params(self, params):
        self.external_transform_params = params

    def _resolve_target_size(self, target_width, target_height):
        if target_width <= 0:
            target_width = self.UI_BASE_WIDTH
        if target_height <= 0:
            target_height = self.UI_BASE_HEIGHT
        return float(target_width), float(target_height)

    def build_config(self, target_width=0, target_height=0):
        target_width, target_height = self._resolve_target_size(target_width, target_height)
        return ToolpathConfig(
            target_width_mm=target_width,
            target_height_mm=target_height,
            paper_center_x=self.paper_center_x,
            paper_center_y=self.paper_center_y,
            mm_per_gcode_x=self.MM_PER_GCODE_X,
            mm_per_gcode_y=self.MM_PER_GCODE_Y,
            scale_factor=self.SCALE_FACTOR,
            auto_rotate=True,
            closure_overshoot_mm=0.0,
            ui_base_width=self.UI_BASE_WIDTH,
            ui_base_height=self.UI_BASE_HEIGHT,
            gcode_base_width=self.GCODE_BASE_WIDTH,
            gcode_base_height=self.GCODE_BASE_HEIGHT,
        )

    def build_geometry(self, contours, target_width=0, target_height=0):
        """Build shared fill geometry, reusing cutting transform when available."""
        return self._build_geometry_model(contours, target_width, target_height).as_dict()

    def _build_geometry_model(self, contours, target_width=0, target_height=0):
        if self.external_transform_params:
            base_config = self.build_config(target_width, target_height)
            base_geometry = geometry_from_dict(self.external_transform_params, base_config)
            return clone_geometry_for_center(
                base_geometry,
                self.paper_center_x,
                self.paper_center_y,
                closure_overshoot_mm=0.0,
            )
        return build_geometry(contours, self.build_config(target_width, target_height))

    def _calculate_scale_and_center(self, contours, ui_width, ui_height, auto_rotate=True):
        geometry = self.build_geometry(contours, ui_width, ui_height)
        return (
            geometry["scale_x"],
            geometry["scale_y"],
            geometry["center_x_pixel"],
            geometry["center_y_pixel"],
            geometry["gcode_work_width"],
            geometry["gcode_work_height"],
            geometry["rotated"],
        )

    def generate(self, contours, fill_interval, y_offset, z_depth, target_width=0, target_height=0, swap_xz=False):
        """Generate fill G-code using the shared contour transform."""
        del y_offset, z_depth
        geometry = self._build_geometry_model(contours, target_width, target_height)
        return emit_fill_gcode(geometry, fill_interval, self.feed_rate, swap_xz=swap_xz)

    def save_to_file(
        self,
        contours,
        filepath,
        fill_interval,
        y_offset,
        z_depth,
        image_width=0,
        image_height=0,
        target_width=0,
        target_height=0,
        swap_xz=False,
    ):
        """Generate fill G-code and save it to a file."""
        try:
            gcode = self.generate(
                contours,
                fill_interval,
                y_offset,
                z_depth,
                target_width,
                target_height,
                swap_xz,
            )
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(gcode)
            return True
        except Exception as e:
            print(f"Error saving Fill G-code: {e}")
            return False
