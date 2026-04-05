"""Cut path G-code generator."""

from __future__ import annotations

from typing import List

from aipathcut.core.transform_utils import (
    calculate_transform,
    contour_to_machine_points,
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

    def _calculate_scale_and_center(self, contours, ui_width, ui_height, auto_rotate=True):
        params = calculate_transform(
            contours,
            ui_width,
            ui_height,
            self.UI_BASE_WIDTH,
            self.UI_BASE_HEIGHT,
            self.GCODE_BASE_WIDTH,
            self.GCODE_BASE_HEIGHT,
            self.MM_PER_GCODE_X,
            self.MM_PER_GCODE_Y,
            auto_rotate=auto_rotate,
        )
        return (
            params["scale_x"],
            params["scale_y"],
            params["center_x_pixel"],
            params["center_y_pixel"],
            params["gcode_work_width"],
            params["gcode_work_height"],
            params["rotated"],
        )

    def _emit_move(self, x, y, swap_xz=False):
        if swap_xz:
            return f"G1 Y{y:.3f} Z{x:.3f}"
        return f"G1 X{x:.3f} Y{y:.3f}"

    def generate(self, contours, image_width=0, image_height=0, target_width=0, target_height=0, swap_xz=False):
        """Generate cutting G-code."""
        if target_width <= 0:
            target_width = self.UI_BASE_WIDTH
        if target_height <= 0:
            target_height = self.UI_BASE_HEIGHT

        params = calculate_transform(
            contours,
            target_width,
            target_height,
            self.UI_BASE_WIDTH,
            self.UI_BASE_HEIGHT,
            self.GCODE_BASE_WIDTH,
            self.GCODE_BASE_HEIGHT,
            self.MM_PER_GCODE_X,
            self.MM_PER_GCODE_Y,
            auto_rotate=True,
        )

        params["scale_x"] *= 0.64
        params["scale_y"] *= 0.64
        self.last_transform_params = params

        work_contours = params["work_contours"]
        scale_x = params["scale_x"]
        scale_y = params["scale_y"]
        center_x_pixel = params["center_x_pixel"]
        center_y_pixel = params["center_y_pixel"]
        orig_width = params["orig_width"]
        orig_height = params["orig_height"]

        # Keep the pre-densified contours for downstream consumers.
        self.last_transform_params["work_contours"] = work_contours

        work_contours = self._densify_contours(work_contours, scale_x, scale_y)

        gcode_lines: List[str] = []
        gcode_lines.append("G21")
        gcode_lines.append("G90")
        gcode_lines.append(f"F{self.feed_rate}")
        gcode_lines.append("")
        if swap_xz:
            gcode_lines.append("G92 Z0 Y0")
            gcode_lines.append(f"G1 Z{self.paper_center_x:.3f} Y{self.paper_center_y:.3f}")
        else:
            gcode_lines.append("G92 X0 Y0")
            gcode_lines.append(f"G1 X{self.paper_center_x:.3f} Y{self.paper_center_y:.3f}")
        gcode_lines.append("")

        for contour in work_contours:
            if len(contour) < 2:
                continue

            machine_points = contour_to_machine_points(
                contour,
                center_x_pixel,
                center_y_pixel,
                scale_x,
                scale_y,
                self.paper_center_x,
                self.paper_center_y,
            )
            start_x, start_y = machine_points[0]

            gcode_lines.append(self._emit_move(start_x, start_y, swap_xz))
            gcode_lines.append("M8")

            for x, y in machine_points[1:]:
                gcode_lines.append(self._emit_move(x, y, swap_xz))

            # Close the contour explicitly back to the start point.
            gcode_lines.append(self._emit_move(start_x, start_y, swap_xz))
            gcode_lines.append("M9")
            gcode_lines.append("")

        gcode_lines.append("")
        if swap_xz:
            gcode_lines.append("G1 Z20 Y0")
        else:
            gcode_lines.append("G1 X20 Y0")
        gcode_lines.append("")

        return "\n".join(gcode_lines)

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
