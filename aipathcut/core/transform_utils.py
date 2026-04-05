"""Shared contour transform helpers."""

from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np


def get_contours_bounds(contours) -> Tuple[float, float, float, float]:
    """Return the bounding box of all contour points."""
    all_points = [point[0] for contour in contours for point in contour]
    if not all_points:
        return 0.0, 0.0, 0.0, 0.0

    min_x = min(p[0] for p in all_points)
    max_x = max(p[0] for p in all_points)
    min_y = min(p[1] for p in all_points)
    max_y = max(p[1] for p in all_points)
    return float(min_x), float(max_x), float(min_y), float(max_y)


def rotate_contours_90(contours, orig_width, orig_height):
    """Rotate contours 90 degrees clockwise."""
    rotated_contours = []
    for contour in contours:
        new_contour = []
        for point in contour:
            x, y = point[0]
            new_x = orig_height - y
            new_y = x
            new_contour.append([[new_x, new_y]])
        rotated_contours.append(np.array(new_contour, dtype=np.int32))
    return rotated_contours


def calculate_transform(
    contours,
    ui_width: float,
    ui_height: float,
    ui_base_width: float,
    ui_base_height: float,
    gcode_base_width: float,
    gcode_base_height: float,
    mm_per_gcode_x: float,
    mm_per_gcode_y: float,
    auto_rotate: bool = True,
    scale_factor: float = 1.0,
) -> Dict[str, object]:
    """
    Calculate scaling and optional rotation for contour export.

    Height is treated as the primary axis, then X is derived from the machine
    calibration ratio so the output keeps the real-world proportions.
    """
    min_x, max_x, min_y, max_y = get_contours_bounds(contours)
    orig_width = max_x - min_x if max_x > min_x else 1.0
    orig_height = max_y - min_y if max_y > min_y else 1.0

    gcode_work_width = ui_width * (gcode_base_width / ui_base_width)
    gcode_work_height = ui_height * (gcode_base_height / ui_base_height)

    phys_ratio = mm_per_gcode_y / mm_per_gcode_x

    sy_no_rot = gcode_work_height / orig_height
    sx_no_rot = sy_no_rot * phys_ratio

    sy_rot = gcode_work_height / orig_width
    sx_rot = sy_rot * phys_ratio

    rotated = False
    if auto_rotate and sy_rot > sy_no_rot * 1.01:
        rotated = True

    scale_x = (sx_rot if rotated else sx_no_rot) * scale_factor
    scale_y = (sy_rot if rotated else sy_no_rot) * scale_factor

    work_contours = contours
    if rotated:
        work_contours = rotate_contours_90(contours, orig_width, orig_height)
        min_x, max_x, min_y, max_y = get_contours_bounds(work_contours)
        orig_width = max_x - min_x if max_x > min_x else 1.0
        orig_height = max_y - min_y if max_y > min_y else 1.0

    center_x_pixel = (min_x + max_x) / 2.0
    center_y_pixel = (min_y + max_y) / 2.0

    return {
        "scale_x": scale_x,
        "scale_y": scale_y,
        "center_x_pixel": center_x_pixel,
        "center_y_pixel": center_y_pixel,
        "gcode_work_width": gcode_work_width,
        "gcode_work_height": gcode_work_height,
        "rotated": rotated,
        "orig_width": orig_width,
        "orig_height": orig_height,
        "min_x": min_x,
        "max_x": max_x,
        "min_y": min_y,
        "max_y": max_y,
        "work_contours": work_contours,
        "scale_factor": scale_factor,
        "ui_width": ui_width,
        "ui_height": ui_height,
    }


def densify_contours(
    contours,
    scale_x: float,
    scale_y: float,
    mm_per_gcode_x: float,
    mm_per_gcode_y: float,
    max_segment_mm: float = 2.0,
):
    """
    Densify long contour edges in machine space.

    This keeps non-uniformly scaled paths visually smooth after conversion.
    """
    densified_contours = []
    for contour in contours:
        if len(contour) < 2:
            densified_contours.append(contour)
            continue

        new_contour = []
        n = len(contour)
        for i in range(n):
            p1 = contour[i][0]
            p2 = contour[(i + 1) % n][0]

            new_contour.append(contour[i])

            dx_phys = (p2[0] - p1[0]) * scale_x * mm_per_gcode_x
            dy_phys = (p2[1] - p1[1]) * scale_y * mm_per_gcode_y
            dist = (dx_phys * dx_phys + dy_phys * dy_phys) ** 0.5

            if dist > max_segment_mm:
                n_segments = int(dist / max_segment_mm) + 1
                for j in range(1, n_segments):
                    t = j / n_segments
                    new_x = p1[0] + (p2[0] - p1[0]) * t
                    new_y = p1[1] + (p2[1] - p1[1]) * t
                    new_contour.append([[new_x, new_y]])

        densified_contours.append(np.array(new_contour, dtype=np.float32))

    return densified_contours


def transform_point(
    point: Sequence[float],
    center_x_pixel: float,
    center_y_pixel: float,
    scale_x: float,
    scale_y: float,
    paper_center_x: float,
    paper_center_y: float,
) -> Tuple[float, float]:
    """Map a contour point to machine coordinates."""
    x = paper_center_x + (point[0] - center_x_pixel) * scale_x
    y = paper_center_y + (point[1] - center_y_pixel) * scale_y
    return float(x), float(y)


def contour_to_machine_points(
    contour,
    center_x_pixel: float,
    center_y_pixel: float,
    scale_x: float,
    scale_y: float,
    paper_center_x: float,
    paper_center_y: float,
) -> List[Tuple[float, float]]:
    """Convert a contour to machine-space points, preserving order."""
    return [
        transform_point(
            point[0],
            center_x_pixel,
            center_y_pixel,
            scale_x,
            scale_y,
            paper_center_x,
            paper_center_y,
        )
        for point in contour
    ]
