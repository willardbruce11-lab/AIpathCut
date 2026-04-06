"""Cut path G-code generator."""

from __future__ import annotations

from typing import List

from aipathcut.core.toolpath_pipeline import ToolpathConfig, build_geometry, emit_cut_gcode
from aipathcut.core.transform_utils import (
    densify_contours,
    get_contours_bounds,
    rotate_contours_90,
    transform_point,
)


class GCodeGenerator:
    """Generate cutting G-code from extracted contours."""

    UI_BASE_WIDTH = 50
    UI_BASE_HEIGHT = 76

    GCODE_BASE_WIDTH = 10
    GCODE_BASE_HEIGHT = 200

    MM_PER_GCODE_X = 76.0 / 9.0
    MM_PER_GCODE_Y = 50.0 / 300.0
    SCALE_FACTOR = 0.8
    CLOSURE_OVERSHOOT_MM = 1.2

    def __init__(self, feed_rate=1000, paper_center_x=7.5, paper_center_y=-150):
        self.feed_rate = feed_rate
        self.paper_center_x = paper_center_x
        self.paper_center_y = paper_center_y
        self.last_transform_params = None

    def _get_contours_bounds(self, contours):
        return get_contours_bounds(contours)

    def _rotate_contours_90(self, contours, orig_width, orig_height):
        return rotate_contours_90(contours, orig_width, orig_height)

    def _densify_contours(self, contours, scale_x, scale_y, max_segment_mm=2.0):
        return densify_contours(
            contours,
            scale_x,
            scale_y,
            self.MM_PER_GCODE_X,
            self.MM_PER_GCODE_Y,
            max_segment_mm=max_segment_mm,
        )

    def _transform_point(self, point, center_x_pixel, center_y_pixel, scale_x, scale_y):
        return transform_point(
            point,
            center_x_pixel,
            center_y_pixel,
            scale_x,
            scale_y,
            self.paper_center_x,
            self.paper_center_y,
        )

    def get_transform_params(self):
        return self.last_transform_params

    def _resolve_target_size(self, target_width, target_height):
        if target_width <= 0:
            target_width = self.UI_BASE_WIDTH
        if target_height <= 0:
            target_height = self.UI_BASE_HEIGHT
        return float(target_width), float(target_height)

    def build_config(self, target_width=0, target_height=0):
        """Build a canonical contour-to-machine config for cutting."""
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
            closure_overshoot_mm=self.CLOSURE_OVERSHOOT_MM,
            ui_base_width=self.UI_BASE_WIDTH,
            ui_base_height=self.UI_BASE_HEIGHT,
            gcode_base_width=self.GCODE_BASE_WIDTH,
            gcode_base_height=self.GCODE_BASE_HEIGHT,
        )

    def build_geometry(self, contours, target_width=0, target_height=0):
        """Build the shared intermediate toolpath geometry."""
        geometry = build_geometry(contours, self.build_config(target_width, target_height))
        self.last_transform_params = geometry.as_dict()
        return self.last_transform_params

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

    def _emit_move(self, x, y, swap_xz=False):
        if swap_xz:
            return f"G1 Y{y:.3f} Z{x:.3f}"
        return f"G1 X{x:.3f} Y{y:.3f}"

    def generate(self, contours, image_width=0, image_height=0, target_width=0, target_height=0, swap_xz=False):
        """Generate cutting G-code."""
        geometry = build_geometry(contours, self.build_config(target_width, target_height))
        self.last_transform_params = geometry.as_dict()
        return emit_cut_gcode(geometry, self.feed_rate, swap_xz=swap_xz)

    def save_to_file(
        self,
        contours,
        filepath,
        image_width=0,
        image_height=0,
        target_width=0,
        target_height=0,
        swap_xz=False,
    ):
        """Generate G-code and save it to a file."""
        try:
            gcode = self.generate(
                contours,
                image_width,
                image_height,
                target_width,
                target_height,
                swap_xz,
            )
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(gcode)
            return True
        except Exception as e:
            print(f"Error saving G-code: {e}")
            return False
