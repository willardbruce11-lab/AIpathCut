"""Shared contour transforms for toolpath generation."""

from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

import numpy as np


Point = Tuple[float, float]


def get_contours_bounds(contours):
    """Return contour bounds as min_x, max_x, min_y, max_y."""
    if not contours:
        return 0.0, 0.0, 0.0, 0.0

    min_x = float("inf")
    max_x = float("-inf")
    min_y = float("inf")
    max_y = float("-inf")

    for contour in contours:
        if contour is None or len(contour) == 0:
            continue
        points = contour.reshape(-1, 2)
        min_x = min(min_x, float(np.min(points[:, 0])))
        max_x = max(max_x, float(np.max(points[:, 0])))
        min_y = min(min_y, float(np.min(points[:, 1])))
        max_y = max(max_y, float(np.max(points[:, 1])))

    if min_x == float("inf"):
        return 0.0, 0.0, 0.0, 0.0
    return min_x, max_x, min_y, max_y


def rotate_contours_90(contours, orig_width, orig_height):
    """Rotate contours 90 degrees clockwise around the image frame."""
    min_x, max_x, min_y, max_y = get_contours_bounds(contours)
    width = float(orig_width) if orig_width and orig_width > 0 else max_x - min_x
    height = float(orig_height) if orig_height and orig_height > 0 else max_y - min_y

    rotated = []
    for contour in contours:
        if contour is None or len(contour) == 0:
            continue
        pts = contour.reshape(-1, 2).astype(np.float64)
        rotated_pts = np.empty_like(pts)
        local_x = pts[:, 0] - min_x
        local_y = pts[:, 1] - min_y
        rotated_pts[:, 0] = min_x + height - local_y
        rotated_pts[:, 1] = min_y + local_x
        rotated.append(rotated_pts.reshape(-1, 1, 2))
    return rotated


def densify_contours(
    contours,
    scale_x,
    scale_y,
    mm_per_gcode_x,
    mm_per_gcode_y,
    max_segment_mm=2.0,
):
    """Insert intermediate points so long segments remain physically smooth."""
    if max_segment_mm <= 0:
        return contours

    dense = []
    for contour in contours:
        if contour is None or len(contour) < 2:
            dense.append(contour)
            continue

        source = contour.reshape(-1, 2).astype(np.float64)
        output: List[List[float]] = []
        count = len(source)
        for i in range(count):
            p1 = source[i]
            p2 = source[(i + 1) % count]
            output.append([p1[0], p1[1]])

            dx_mm = abs((p2[0] - p1[0]) * scale_x * mm_per_gcode_x)
            dy_mm = abs((p2[1] - p1[1]) * scale_y * mm_per_gcode_y)
            segment_mm = (dx_mm * dx_mm + dy_mm * dy_mm) ** 0.5
            extra_points = int(segment_mm // max_segment_mm)

            if extra_points <= 0:
                continue

            steps = extra_points + 1
            for step in range(1, steps):
                t = step / steps
                interp = p1 + (p2 - p1) * t
                output.append([float(interp[0]), float(interp[1])])

        dense.append(np.array(output, dtype=np.float64).reshape(-1, 1, 2))
    return dense


def calculate_transform(
    contours,
    ui_width,
    ui_height,
    ui_base_width,
    ui_base_height,
    gcode_base_width,
    gcode_base_height,
    mm_per_gcode_x,
    mm_per_gcode_y,
    auto_rotate=True,
    scale_factor=1.0,
):
    """Calculate a millimeter-first transform for physically correct output."""
    del ui_base_width, ui_base_height, gcode_base_width, gcode_base_height

    min_x, max_x, min_y, max_y = get_contours_bounds(contours)
    orig_width = max_x - min_x
    orig_height = max_y - min_y

    if orig_width <= 0 or orig_height <= 0:
        return {
            "scale_x": 1.0,
            "scale_y": 1.0,
            "physical_scale_mm_per_pixel": 1.0,
            "center_x_pixel": 0.0,
            "center_y_pixel": 0.0,
            "gcode_work_width": 0.0,
            "gcode_work_height": 0.0,
            "physical_work_width_mm": 0.0,
            "physical_work_height_mm": 0.0,
            "rotated": False,
            "min_x": min_x,
            "max_x": max_x,
            "min_y": min_y,
            "max_y": max_y,
        }

    target_width_mm = float(ui_width) if ui_width and ui_width > 0 else float(orig_width)
    target_height_mm = float(ui_height) if ui_height and ui_height > 0 else float(orig_height)

    no_rot_scale_mm = min(target_width_mm / orig_width, target_height_mm / orig_height)
    rotated = False
    work_width = orig_width
    work_height = orig_height

    if auto_rotate and orig_height > orig_width:
        rotated = True
        work_width = orig_height
        work_height = orig_width

    chosen_scale_mm = min(target_width_mm / work_width, target_height_mm / work_height)

    physical_scale_mm_per_pixel = chosen_scale_mm * float(scale_factor)
    scale_x = physical_scale_mm_per_pixel / mm_per_gcode_x
    scale_y = physical_scale_mm_per_pixel / mm_per_gcode_y

    center_x_pixel = (min_x + max_x) / 2.0
    center_y_pixel = (min_y + max_y) / 2.0
    physical_work_width_mm = work_width * physical_scale_mm_per_pixel
    physical_work_height_mm = work_height * physical_scale_mm_per_pixel

    return {
        "scale_x": scale_x,
        "scale_y": scale_y,
        "physical_scale_mm_per_pixel": physical_scale_mm_per_pixel,
        "center_x_pixel": center_x_pixel,
        "center_y_pixel": center_y_pixel,
        "gcode_work_width": physical_work_width_mm / mm_per_gcode_x,
        "gcode_work_height": physical_work_height_mm / mm_per_gcode_y,
        "physical_work_width_mm": physical_work_width_mm,
        "physical_work_height_mm": physical_work_height_mm,
        "rotated": rotated,
        "min_x": min_x,
        "max_x": max_x,
        "min_y": min_y,
        "max_y": max_y,
    }


def transform_point(
    point,
    center_x_pixel,
    center_y_pixel,
    scale_x,
    scale_y,
    paper_center_x,
    paper_center_y,
):
    """Map a pixel-space point to command-space coordinates."""
    x = paper_center_x + (float(point[0]) - center_x_pixel) * scale_x
    y = paper_center_y + (float(point[1]) - center_y_pixel) * scale_y
    return (x, y)


def contour_to_machine_points(
    contour,
    center_x_pixel,
    center_y_pixel,
    scale_x,
    scale_y,
    paper_center_x,
    paper_center_y,
):
    """Transform a contour to machine-space points."""
    if contour is None or len(contour) == 0:
        return []
    points = contour.reshape(-1, 2)
    return [
        transform_point(
            point,
            center_x_pixel,
            center_y_pixel,
            scale_x,
            scale_y,
            paper_center_x,
            paper_center_y,
        )
        for point in points
    ]


def _normalize_vector(vector: Sequence[float]) -> np.ndarray:
    vec = np.array(vector, dtype=np.float64)
    norm = np.linalg.norm(vec)
    if norm < 1e-9:
        return np.zeros(2, dtype=np.float64)
    return vec / norm


def build_closure_detour(machine_points: Sequence[Point], closure_overshoot_mm: float):
    """Build an external detour that closes the contour with an X-like tail."""
    if closure_overshoot_mm <= 0 or len(machine_points) < 3:
        if len(machine_points) >= 2 and machine_points[-1] != machine_points[0]:
            return [machine_points[0]]
        return []

    start = np.array(machine_points[0], dtype=np.float64)
    end = np.array(machine_points[-1], dtype=np.float64)
    prev = np.array(machine_points[-2], dtype=np.float64)
    next_pt = np.array(machine_points[1], dtype=np.float64)

    exit_dir = _normalize_vector(end - prev)
    entry_dir = _normalize_vector(next_pt - start)
    if np.linalg.norm(exit_dir) < 1e-9 or np.linalg.norm(entry_dir) < 1e-9:
        return [tuple(start)]

    centroid = np.mean(np.array(machine_points, dtype=np.float64), axis=0)
    seam_mid = (start + end) / 2.0
    seam_out = _normalize_vector(seam_mid - centroid)
    if np.linalg.norm(seam_out) < 1e-9:
        seam_out = _normalize_vector(np.array([-exit_dir[1], exit_dir[0]], dtype=np.float64))

    overshoot = float(closure_overshoot_mm)
    exit_point = end + exit_dir * overshoot
    entry_pre = start - entry_dir * overshoot
    bridge_point = (exit_point + entry_pre) / 2.0 + seam_out * overshoot

    return [
        (float(exit_point[0]), float(exit_point[1])),
        (float(bridge_point[0]), float(bridge_point[1])),
        (float(entry_pre[0]), float(entry_pre[1])),
        (float(start[0]), float(start[1])),
    ]


def machine_paths_to_canvas_paths(machine_paths: Iterable[Sequence[Point]], canvas_scale=4.0):
    """Convert machine paths to a simple canvas coordinate system for diagnostics."""
    paths = []
    for path in machine_paths:
        if not path:
            continue
        converted = [
            (float(point[0]) * canvas_scale, float(-point[1]) * canvas_scale)
            for point in path
        ]
        paths.append(converted)
    return paths


def build_toolpath_geometry(
    contours,
    target_width,
    target_height,
    ui_base_width,
    ui_base_height,
    gcode_base_width,
    gcode_base_height,
    mm_per_gcode_x,
    mm_per_gcode_y,
    paper_center_x,
    paper_center_y,
    auto_rotate=True,
    scale_factor=1.0,
    closure_overshoot_mm=0.0,
):
    """Build shared contour geometry for cut or fill output."""
    transform = calculate_transform(
        contours,
        target_width,
        target_height,
        ui_base_width,
        ui_base_height,
        gcode_base_width,
        gcode_base_height,
        mm_per_gcode_x,
        mm_per_gcode_y,
        auto_rotate=auto_rotate,
        scale_factor=scale_factor,
    )

    work_contours = rotate_contours_90(contours, 0, 0) if transform["rotated"] else contours

    min_x, max_x, min_y, max_y = get_contours_bounds(work_contours)
    center_x_pixel = (min_x + max_x) / 2.0
    center_y_pixel = (min_y + max_y) / 2.0

    dense_contours = densify_contours(
        work_contours,
        transform["scale_x"],
        transform["scale_y"],
        mm_per_gcode_x,
        mm_per_gcode_y,
    )

    machine_paths = []
    machine_closed_paths = []

    for contour in dense_contours:
        machine_points = contour_to_machine_points(
            contour,
            center_x_pixel,
            center_y_pixel,
            transform["scale_x"],
            transform["scale_y"],
            paper_center_x,
            paper_center_y,
        )
        if not machine_points:
            continue

        machine_paths.append(machine_points)
        closed_path = list(machine_points)
        if closure_overshoot_mm > 0:
            closed_path.extend(build_closure_detour(machine_points, closure_overshoot_mm))
        elif closed_path[-1] != closed_path[0]:
            closed_path.append(closed_path[0])
        machine_closed_paths.append(closed_path)

    return {
        **transform,
        "work_contours": work_contours,
        "dense_contours": dense_contours,
        "center_x_pixel": center_x_pixel,
        "center_y_pixel": center_y_pixel,
        "min_x": min_x,
        "max_x": max_x,
        "min_y": min_y,
        "max_y": max_y,
        "paper_center_x": paper_center_x,
        "paper_center_y": paper_center_y,
        "mm_per_gcode_x": mm_per_gcode_x,
        "mm_per_gcode_y": mm_per_gcode_y,
        "machine_paths": machine_paths,
        "machine_closed_paths": machine_closed_paths,
    }
