"""Shared toolpath pipeline for contour-based outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

import numpy as np

from aipathcut.core.transform_utils import (
    build_toolpath_geometry,
    build_closure_detour,
    contour_to_machine_points,
    get_contours_bounds,
)


Point = Tuple[float, float]


@dataclass(frozen=True)
class ToolpathConfig:
    """Configuration for contour-to-machine toolpath conversion."""

    target_width_mm: float
    target_height_mm: float
    paper_center_x: float
    paper_center_y: float
    mm_per_gcode_x: float
    mm_per_gcode_y: float
    scale_factor: float
    auto_rotate: bool = True
    closure_overshoot_mm: float = 0.0
    ui_base_width: float = 50.0
    ui_base_height: float = 76.0
    gcode_base_width: float = 10.0
    gcode_base_height: float = 200.0


@dataclass
class ToolpathGeometry:
    """Intermediate toolpath geometry derived from extracted contours."""

    config: ToolpathConfig
    work_contours: List[np.ndarray]
    dense_contours: List[np.ndarray]
    machine_paths: List[List[Point]]
    machine_closed_paths: List[List[Point]]
    scale_x: float
    scale_y: float
    center_x_pixel: float
    center_y_pixel: float
    rotated: bool
    min_x: float
    max_x: float
    min_y: float
    max_y: float
    physical_scale_mm_per_pixel: float
    physical_work_width_mm: float
    physical_work_height_mm: float
    gcode_work_width: float
    gcode_work_height: float

    def as_dict(self):
        return {
            "work_contours": self.work_contours,
            "dense_contours": self.dense_contours,
            "machine_paths": self.machine_paths,
            "machine_closed_paths": self.machine_closed_paths,
            "scale_x": self.scale_x,
            "scale_y": self.scale_y,
            "center_x_pixel": self.center_x_pixel,
            "center_y_pixel": self.center_y_pixel,
            "rotated": self.rotated,
            "min_x": self.min_x,
            "max_x": self.max_x,
            "min_y": self.min_y,
            "max_y": self.max_y,
            "physical_scale_mm_per_pixel": self.physical_scale_mm_per_pixel,
            "physical_work_width_mm": self.physical_work_width_mm,
            "physical_work_height_mm": self.physical_work_height_mm,
            "gcode_work_width": self.gcode_work_width,
            "gcode_work_height": self.gcode_work_height,
            "paper_center_x": self.config.paper_center_x,
            "paper_center_y": self.config.paper_center_y,
            "mm_per_gcode_x": self.config.mm_per_gcode_x,
            "mm_per_gcode_y": self.config.mm_per_gcode_y,
        }


def _clone_contours(contours: Sequence[np.ndarray]) -> List[np.ndarray]:
    return [np.array(contour, copy=True) for contour in contours]


def build_geometry(contours: Sequence[np.ndarray], config: ToolpathConfig) -> ToolpathGeometry:
    """Build the canonical toolpath geometry from extracted contours."""
    raw = build_toolpath_geometry(
        contours,
        config.target_width_mm,
        config.target_height_mm,
        config.ui_base_width,
        config.ui_base_height,
        config.gcode_base_width,
        config.gcode_base_height,
        config.mm_per_gcode_x,
        config.mm_per_gcode_y,
        config.paper_center_x,
        config.paper_center_y,
        auto_rotate=config.auto_rotate,
        scale_factor=config.scale_factor,
        closure_overshoot_mm=config.closure_overshoot_mm,
    )

    return ToolpathGeometry(
        config=config,
        work_contours=_clone_contours(raw["work_contours"]),
        dense_contours=_clone_contours(raw["dense_contours"]),
        machine_paths=[list(path) for path in raw["machine_paths"]],
        machine_closed_paths=[list(path) for path in raw["machine_closed_paths"]],
        scale_x=raw["scale_x"],
        scale_y=raw["scale_y"],
        center_x_pixel=raw["center_x_pixel"],
        center_y_pixel=raw["center_y_pixel"],
        rotated=raw["rotated"],
        min_x=raw["min_x"],
        max_x=raw["max_x"],
        min_y=raw["min_y"],
        max_y=raw["max_y"],
        physical_scale_mm_per_pixel=raw["physical_scale_mm_per_pixel"],
        physical_work_width_mm=raw["physical_work_width_mm"],
        physical_work_height_mm=raw["physical_work_height_mm"],
        gcode_work_width=raw["gcode_work_width"],
        gcode_work_height=raw["gcode_work_height"],
    )


def geometry_from_dict(params: dict, config: ToolpathConfig) -> ToolpathGeometry:
    """Rehydrate a geometry object from the legacy dict representation."""
    return ToolpathGeometry(
        config=config,
        work_contours=_clone_contours(params["work_contours"]),
        dense_contours=_clone_contours(params["dense_contours"]),
        machine_paths=[list(path) for path in params["machine_paths"]],
        machine_closed_paths=[list(path) for path in params["machine_closed_paths"]],
        scale_x=params["scale_x"],
        scale_y=params["scale_y"],
        center_x_pixel=params["center_x_pixel"],
        center_y_pixel=params["center_y_pixel"],
        rotated=params["rotated"],
        min_x=params["min_x"],
        max_x=params["max_x"],
        min_y=params["min_y"],
        max_y=params["max_y"],
        physical_scale_mm_per_pixel=params["physical_scale_mm_per_pixel"],
        physical_work_width_mm=params["physical_work_width_mm"],
        physical_work_height_mm=params["physical_work_height_mm"],
        gcode_work_width=params["gcode_work_width"],
        gcode_work_height=params["gcode_work_height"],
    )


def clone_geometry_for_center(
    geometry: ToolpathGeometry,
    paper_center_x: float,
    paper_center_y: float,
    closure_overshoot_mm: float | None = None,
) -> ToolpathGeometry:
    """Reuse the same contour transform but emit machine points around a new center."""
    overshoot = geometry.config.closure_overshoot_mm if closure_overshoot_mm is None else closure_overshoot_mm
    config = ToolpathConfig(
        target_width_mm=geometry.config.target_width_mm,
        target_height_mm=geometry.config.target_height_mm,
        paper_center_x=paper_center_x,
        paper_center_y=paper_center_y,
        mm_per_gcode_x=geometry.config.mm_per_gcode_x,
        mm_per_gcode_y=geometry.config.mm_per_gcode_y,
        scale_factor=geometry.config.scale_factor,
        auto_rotate=geometry.config.auto_rotate,
        closure_overshoot_mm=overshoot,
        ui_base_width=geometry.config.ui_base_width,
        ui_base_height=geometry.config.ui_base_height,
        gcode_base_width=geometry.config.gcode_base_width,
        gcode_base_height=geometry.config.gcode_base_height,
    )

    machine_paths: List[List[Point]] = []
    machine_closed_paths: List[List[Point]] = []
    for contour in geometry.dense_contours:
        machine_points = contour_to_machine_points(
            contour,
            geometry.center_x_pixel,
            geometry.center_y_pixel,
            geometry.scale_x,
            geometry.scale_y,
            paper_center_x,
            paper_center_y,
        )
        if not machine_points:
            continue
        machine_paths.append(machine_points)
        closed = list(machine_points)
        if overshoot > 0:
            closed.extend(build_closure_detour(machine_points, overshoot))
        elif closed[-1] != closed[0]:
            closed.append(closed[0])
        machine_closed_paths.append(closed)

    return ToolpathGeometry(
        config=config,
        work_contours=_clone_contours(geometry.work_contours),
        dense_contours=_clone_contours(geometry.dense_contours),
        machine_paths=machine_paths,
        machine_closed_paths=machine_closed_paths,
        scale_x=geometry.scale_x,
        scale_y=geometry.scale_y,
        center_x_pixel=geometry.center_x_pixel,
        center_y_pixel=geometry.center_y_pixel,
        rotated=geometry.rotated,
        min_x=geometry.min_x,
        max_x=geometry.max_x,
        min_y=geometry.min_y,
        max_y=geometry.max_y,
        physical_scale_mm_per_pixel=geometry.physical_scale_mm_per_pixel,
        physical_work_width_mm=geometry.physical_work_width_mm,
        physical_work_height_mm=geometry.physical_work_height_mm,
        gcode_work_width=geometry.gcode_work_width,
        gcode_work_height=geometry.gcode_work_height,
    )


def emit_cut_gcode(
    geometry: ToolpathGeometry,
    feed_rate: int,
    swap_xz: bool = False,
    spindle_on: str = "M8",
    spindle_off: str = "M9",
) -> str:
    """Serialize a cutting geometry to G-code."""
    lines: List[str] = ["G21", "G90", f"F{feed_rate}", ""]

    if swap_xz:
        lines.extend(
            [
                "G92 Z0 Y0",
                f"G1 Z{geometry.config.paper_center_x:.3f} Y{geometry.config.paper_center_y:.3f}",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "G92 X0 Y0",
                f"G1 X{geometry.config.paper_center_x:.3f} Y{geometry.config.paper_center_y:.3f}",
                "",
            ]
        )

    for path in geometry.machine_closed_paths:
        if len(path) < 2:
            continue
        start_x, start_y = path[0]
        lines.append(_emit_move(start_x, start_y, swap_xz))
        lines.append(spindle_on)
        for x, y in path[1:]:
            lines.append(_emit_move(x, y, swap_xz))
        lines.append(spindle_off)
        lines.append("")

    lines.extend(["", _emit_move(20.0, 0.0, swap_xz), ""])
    return "\n".join(lines)


def build_fill_segments(geometry: ToolpathGeometry, fill_interval_mm: float) -> List[Tuple[float, float, float]]:
    """Build fill segments from the transformed contour geometry."""
    if fill_interval_mm <= 0:
        return []

    x_interval_pixels = fill_interval_mm / geometry.physical_scale_mm_per_pixel
    min_x, max_x, _, _ = get_contours_bounds(geometry.work_contours)
    scan_min_x = min_x - x_interval_pixels
    scan_max_x = max_x + x_interval_pixels

    segments: List[Tuple[float, float, float]] = []
    x = scan_min_x
    while x <= scan_max_x:
        intersections = _find_vertical_intersections(x, geometry.work_contours)
        if len(intersections) >= 2:
            out_x = geometry.config.paper_center_x + (x - geometry.center_x_pixel) * geometry.scale_x
            for i in range(0, len(intersections) - 1, 2):
                y_entry = intersections[i]
                y_exit = intersections[i + 1]
                out_y_entry = geometry.config.paper_center_y + (y_entry - geometry.center_y_pixel) * geometry.scale_y
                out_y_exit = geometry.config.paper_center_y + (y_exit - geometry.center_y_pixel) * geometry.scale_y
                segments.append((out_x, out_y_entry, out_y_exit))
        x += x_interval_pixels

    return segments


def emit_fill_gcode(
    geometry: ToolpathGeometry,
    fill_interval_mm: float,
    feed_rate: int,
    swap_xz: bool = False,
) -> str:
    """Serialize fill scan segments to G-code."""
    lines: List[str] = ["G21", "G90", f"F{feed_rate}", ""]

    if swap_xz:
        lines.extend(
            [
                "G92 Z0 Y0",
                f"G0 Z{geometry.config.paper_center_x:.3f} Y{geometry.config.paper_center_y:.3f}",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "G92 X0 Y0",
                f"G0 X{geometry.config.paper_center_x:.3f} Y{geometry.config.paper_center_y:.3f}",
                "",
            ]
        )

    segments = build_fill_segments(geometry, fill_interval_mm)
    if segments:
        first_x, first_y_entry, _ = segments[0]
        lines.append(_emit_move(first_x, first_y_entry, swap_xz, rapid=True))
        lines.extend(["M3", "M4"])
        for seg_x, seg_y_entry, seg_y_exit in segments:
            lines.append(_emit_move(seg_x, seg_y_entry, swap_xz))
            lines.append(_emit_move(seg_x, seg_y_exit, swap_xz))
        lines.append("M5")

    lines.extend(["", _emit_move(20.0, 0.0, swap_xz, rapid=True), ""])
    return "\n".join(lines)


def _emit_move(x: float, y: float, swap_xz: bool, rapid: bool = False) -> str:
    code = "G0" if rapid else "G1"
    if swap_xz:
        return f"{code} Y{y:.3f} Z{x:.3f}"
    return f"{code} X{x:.3f} Y{y:.3f}"


def _find_vertical_intersections(fixed_x: float, contours: Sequence[np.ndarray]) -> List[float]:
    intersections: List[float] = []
    for contour in contours:
        points = contour.reshape(-1, 2)
        count = len(points)
        for index in range(count):
            x1, y1 = points[index]
            x2, y2 = points[(index + 1) % count]
            if not ((x1 <= fixed_x <= x2) or (x2 <= fixed_x <= x1)):
                continue
            if abs(x2 - x1) < 1e-6:
                continue
            y = y1 + (fixed_x - x1) * (y2 - y1) / (x2 - x1)
            intersections.append(float(y))
    return sorted(intersections)
