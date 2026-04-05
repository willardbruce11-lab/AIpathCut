"""Shared contour and toolpath transform helpers."""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

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
    """Densify long contour edges in machine space."""
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


def _normalize_vector(vec: np.ndarray) -> np.ndarray:
    length = float(np.linalg.norm(vec))
    if length < 1e-9:
        return np.array([0.0, 0.0], dtype=np.float64)
    return vec / length


def build_closure_detour(
    machine_points: List[Tuple[float, float]],
    overshoot_mm: float = 1.2,
    bridge_factor: float = 0.9,
) -> List[Tuple[float, float]]:
    """Build an external detour that closes the path outside the contour."""
    if len(machine_points) < 2:
        return []
    if overshoot_mm <= 0:
        return [machine_points[0]]

    start = np.array(machine_points[0], dtype=np.float64)
    second = np.array(machine_points[1], dtype=np.float64)
    end = np.array(machine_points[-1], dtype=np.float64)
    prev = np.array(machine_points[-2], dtype=np.float64)

    start_dir = _normalize_vector(second - start)
    end_dir = _normalize_vector(end - prev)

    if np.allclose(start_dir, 0.0):
        start_dir = np.array([1.0, 0.0], dtype=np.float64)
    if np.allclose(end_dir, 0.0):
        end_dir = np.array([-1.0, 0.0], dtype=np.float64)

    exit_point = end + end_dir * overshoot_mm
    entry_point = start - start_dir * overshoot_mm

    contour_center = np.mean(np.asarray(machine_points, dtype=np.float64), axis=0)
    mid_point = (exit_point + entry_point) / 2.0

    bridge_dir = _normalize_vector(end_dir - start_dir)
    if np.allclose(bridge_dir, 0.0):
        bridge_dir = np.array([-start_dir[1], start_dir[0]], dtype=np.float64)
    if np.allclose(bridge_dir, 0.0):
        bridge_dir = np.array([0.0, 1.0], dtype=np.float64)

    if np.dot(bridge_dir, mid_point - contour_center) < 0:
        bridge_dir = -bridge_dir

    bridge_point = mid_point + bridge_dir * overshoot_mm * bridge_factor
    return [
        (float(exit_point[0]), float(exit_point[1])),
        (float(bridge_point[0]), float(bridge_point[1])),
        (float(entry_point[0]), float(entry_point[1])),
        (float(start[0]), float(start[1])),
    ]


def machine_paths_to_canvas_paths(
    machine_paths: List[List[Tuple[float, float]]],
    canvas_width: int,
    canvas_height: int,
    padding: int = 10,
) -> List[np.ndarray]:
    """Fit machine-space paths onto a preview canvas."""
    if not machine_paths:
        return []

    all_points = [point for path in machine_paths for point in path]
    min_x = min(point[0] for point in all_points)
    max_x = max(point[0] for point in all_points)
    min_y = min(point[1] for point in all_points)
    max_y = max(point[1] for point in all_points)

    span_x = max(max_x - min_x, 1e-6)
    span_y = max(max_y - min_y, 1e-6)
    usable_width = max(canvas_width - 2 * padding, 1)
    usable_height = max(canvas_height - 2 * padding, 1)
    scale = min(usable_width / span_x, usable_height / span_y)

    canvas_paths = []
    for path in machine_paths:
        canvas_points = []
        for x, y in path:
            px = padding + (x - min_x) * scale
            py = padding + (y - min_y) * scale
            canvas_points.append([[px, py]])
        canvas_paths.append(np.array(canvas_points, dtype=np.int32))

    return canvas_paths


def build_toolpath_geometry(
    contours,
    ui_width: float,
    ui_height: float,
    ui_base_width: float,
    ui_base_height: float,
    gcode_base_width: float,
    gcode_base_height: float,
    mm_per_gcode_x: float,
    mm_per_gcode_y: float,
    paper_center_x: float,
    paper_center_y: float,
    auto_rotate: bool = True,
    scale_factor: float = 0.8,
    max_segment_mm: float = 2.0,
    closure_overshoot_mm: float = 0.0,
) -> Dict[str, object]:
    """Build the shared intermediate geometry used by preview and G-code."""
    params = calculate_transform(
        contours,
        ui_width,
        ui_height,
        ui_base_width,
        ui_base_height,
        gcode_base_width,
        gcode_base_height,
        mm_per_gcode_x,
        mm_per_gcode_y,
        auto_rotate=auto_rotate,
        scale_factor=scale_factor,
    )

    densified_contours = densify_contours(
        params["work_contours"],
        params["scale_x"],
        params["scale_y"],
        mm_per_gcode_x,
        mm_per_gcode_y,
        max_segment_mm=max_segment_mm,
    )

    machine_open_paths: List[List[Tuple[float, float]]] = []
    machine_closed_paths: List[List[Tuple[float, float]]] = []
    for contour in densified_contours:
        if len(contour) < 2:
            continue

        open_path = contour_to_machine_points(
            contour,
            params["center_x_pixel"],
            params["center_y_pixel"],
            params["scale_x"],
            params["scale_y"],
            paper_center_x,
            paper_center_y,
        )
        machine_open_paths.append(open_path)
        closure_path = build_closure_detour(open_path, closure_overshoot_mm)
        machine_closed_paths.append(open_path + closure_path)

    geometry = dict(params)
    geometry.update(
        {
            "paper_center_x": paper_center_x,
            "paper_center_y": paper_center_y,
            "max_segment_mm": max_segment_mm,
            "closure_overshoot_mm": closure_overshoot_mm,
            "densified_contours": densified_contours,
            "machine_open_paths": machine_open_paths,
            "machine_closed_paths": machine_closed_paths,
        }
    )
    return geometry
