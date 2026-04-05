"""Fill scan G-code generator."""

from __future__ import annotations

from typing import List

from aipathcut.core.transform_utils import build_toolpath_geometry, get_contours_bounds, rotate_contours_90


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

    def build_geometry(self, contours, target_width=0, target_height=0):
        """Build shared fill geometry, reusing cutting transform when available."""
        if self.external_transform_params:
            geometry = dict(self.external_transform_params)
            geometry["paper_center_x"] = self.paper_center_x
            geometry["paper_center_y"] = self.paper_center_y
            return geometry

        if target_width <= 0:
            target_width = self.UI_BASE_WIDTH
        if target_height <= 0:
            target_height = self.UI_BASE_HEIGHT

        return build_toolpath_geometry(
            contours,
            target_width,
            target_height,
            self.UI_BASE_WIDTH,
            self.UI_BASE_HEIGHT,
            self.GCODE_BASE_WIDTH,
            self.GCODE_BASE_HEIGHT,
            self.MM_PER_GCODE_X,
            self.MM_PER_GCODE_Y,
            self.paper_center_x,
            self.paper_center_y,
            auto_rotate=True,
            scale_factor=self.SCALE_FACTOR,
            closure_overshoot_mm=0.0,
        )

    def _find_vertical_intersections(self, fixed_x, contours):
        intersections = []

        for contour in contours:
            n = len(contour)
            for i in range(n):
                p1 = contour[i][0]
                p2 = contour[(i + 1) % n][0]

                x1, y1 = p1
                x2, y2 = p2

                if (x1 <= fixed_x <= x2) or (x2 <= fixed_x <= x1):
                    if abs(x2 - x1) < 0.0001:
                        continue
                    y = y1 + (fixed_x - x1) * (y2 - y1) / (x2 - x1)
                    intersections.append(y)

        return sorted(intersections)

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

    def _emit_move(self, x, y, swap_xz=False, rapid=False):
        code = "G0" if rapid else "G1"
        if swap_xz:
            return f"{code} Y{y:.3f} Z{x:.3f}"
        return f"{code} X{x:.3f} Y{y:.3f}"

    def generate(self, contours, fill_interval, y_offset, z_depth, target_width=0, target_height=0, swap_xz=False):
        """Generate fill G-code using the shared contour transform."""
        geometry = self.build_geometry(contours, target_width, target_height)

        scale_x = geometry["scale_x"]
        scale_y = geometry["scale_y"]
        center_x_pixel = geometry["center_x_pixel"]
        center_y_pixel = geometry["center_y_pixel"]
        work_contours = geometry["work_contours"]

        x_interval_pixels = fill_interval / (scale_x * self.MM_PER_GCODE_X) if scale_x > 0 else fill_interval

        min_x, max_x, _, _ = self._get_contours_bounds(work_contours)
        scan_min_x = min_x - x_interval_pixels
        scan_max_x = max_x + x_interval_pixels

        gcode_lines: List[str] = []
        gcode_lines.append("G21")
        gcode_lines.append("G90")
        gcode_lines.append(f"F{self.feed_rate}")
        gcode_lines.append("")
        if swap_xz:
            gcode_lines.append("G92 Z0 Y0")
            gcode_lines.append(f"G0 Z{self.paper_center_x:.3f} Y{self.paper_center_y:.3f}")
        else:
            gcode_lines.append("G92 X0 Y0")
            gcode_lines.append(f"G0 X{self.paper_center_x:.3f} Y{self.paper_center_y:.3f}")
        gcode_lines.append("")

        fill_segments = []
        x = scan_min_x
        while x <= scan_max_x:
            intersections = self._find_vertical_intersections(x, work_contours)
            if len(intersections) >= 2:
                out_x = self.paper_center_x + (x - center_x_pixel) * scale_x

                for i in range(0, len(intersections) - 1, 2):
                    if i + 1 >= len(intersections):
                        break

                    y_entry = intersections[i]
                    y_exit = intersections[i + 1]
                    out_y_entry = self.paper_center_y + (y_entry - center_y_pixel) * scale_y
                    out_y_exit = self.paper_center_y + (y_exit - center_y_pixel) * scale_y
                    fill_segments.append((out_x, out_y_entry, out_y_exit))

            x += x_interval_pixels

        if fill_segments:
            first_x, first_y_entry, _ = fill_segments[0]
            gcode_lines.append(self._emit_move(first_x, first_y_entry, swap_xz, rapid=True))
            gcode_lines.append("M3")
            gcode_lines.append("M4")

            for seg_x, seg_y_entry, seg_y_exit in fill_segments:
                gcode_lines.append(self._emit_move(seg_x, seg_y_entry, swap_xz))
                gcode_lines.append(self._emit_move(seg_x, seg_y_exit, swap_xz))

            gcode_lines.append("M5")

        gcode_lines.append("")
        if swap_xz:
            gcode_lines.append("G0 Z20 Y0")
        else:
            gcode_lines.append("G0 X20 Y0")
        gcode_lines.append("")

        return "\n".join(gcode_lines)

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
