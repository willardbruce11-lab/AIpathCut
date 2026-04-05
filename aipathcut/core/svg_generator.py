"""SVG generator helpers."""

from __future__ import annotations

from pathlib import Path
from typing import List, Sequence, Tuple

import numpy as np


class SVGGenerator:
    """SVG vector generator."""

    def __init__(
        self,
        stroke_color: str = "#000000",
        stroke_width: float = 2.0,
        fill: str = "none",
        width: int = 500,
        height: int = 500,
    ):
        self.stroke_color = stroke_color
        self.stroke_width = stroke_width
        self.fill = fill
        self.width = width
        self.height = height

    def _contour_to_path(self, contour: np.ndarray, scale_x: float, scale_y: float) -> str:
        if len(contour) == 0:
            return ""

        points = []
        for point in contour:
            x = float(point[0][0]) * scale_x
            y = float(point[0][1]) * scale_y
            points.append(f"{x:.2f},{y:.2f}")

        return " M " + " L ".join(points) + " Z"

    def _path_points_to_path(self, path_points: Sequence[Tuple[float, float]]) -> str:
        if not path_points:
            return ""

        start = path_points[0]
        segments = [f"M {start[0]:.2f},{start[1]:.2f}"]
        for x, y in path_points[1:]:
            segments.append(f"L {x:.2f},{y:.2f}")
        return " ".join(segments)

    def _write_svg(self, svg_parts: List[str], output_path: str) -> None:
        svg_content = "\n".join(svg_parts)
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(svg_content)

    def generate(
        self,
        contours: List[np.ndarray],
        original_width: int,
        original_height: int,
        output_path: str,
        viewbox: bool = True,
    ) -> None:
        if viewbox:
            scale_x = 1.0
            scale_y = 1.0
            svg_width = original_width
            svg_height = original_height
        else:
            scale_x = self.width / original_width
            scale_y = self.height / original_height
            svg_width = self.width
            svg_height = self.height

        svg_parts = []
        if viewbox:
            svg_header = (
                f'<svg xmlns="http://www.w3.org/2000/svg" '
                f'viewBox="0 0 {original_width} {original_height}" '
                f'width="{original_width}" height="{original_height}">'
            )
        else:
            svg_header = (
                f'<svg xmlns="http://www.w3.org/2000/svg" '
                f'width="{svg_width}" height="{svg_height}">'
            )

        svg_parts.append(svg_header)
        svg_parts.append('  <rect width="100%" height="100%" fill="white"/>')

        for contour in contours:
            if len(contour) < 3:
                continue

            path_data = self._contour_to_path(contour, scale_x, scale_y)
            if path_data:
                svg_parts.append(
                    f'  <path d="{path_data}" '
                    f'stroke="{self.stroke_color}" '
                    f'stroke-width="{self.stroke_width}" '
                    f'fill="{self.fill}" '
                    f'stroke-linejoin="round" '
                    f'stroke-linecap="round"/>'
                )

        svg_parts.append("</svg>")
        self._write_svg(svg_parts, output_path)

    def generate_paths(
        self,
        paths: Sequence[Sequence[Tuple[float, float]]],
        output_path: str,
        width: float | None = None,
        height: float | None = None,
        padding: float = 2.0,
    ) -> None:
        """Generate SVG from precomputed toolpath polylines."""
        if not paths:
            self._write_svg(
                [
                    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" width="10" height="10">',
                    '  <rect width="100%" height="100%" fill="white"/>',
                    "</svg>",
                ],
                output_path,
            )
            return

        all_points = [point for path in paths for point in path]
        min_x = min(point[0] for point in all_points)
        max_x = max(point[0] for point in all_points)
        min_y = min(point[1] for point in all_points)
        max_y = max(point[1] for point in all_points)

        view_width = max_x - min_x
        view_height = max_y - min_y
        svg_width = width if width is not None else view_width + 2 * padding
        svg_height = height if height is not None else view_height + 2 * padding

        svg_parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{min_x - padding:.2f} {min_y - padding:.2f} {view_width + 2 * padding:.2f} {view_height + 2 * padding:.2f}" width="{svg_width:.2f}" height="{svg_height:.2f}">',
            '  <rect width="100%" height="100%" fill="white"/>',
        ]

        for path in paths:
            if len(path) < 2:
                continue
            path_data = self._path_points_to_path(path)
            svg_parts.append(
                f'  <path d="{path_data}" '
                f'stroke="{self.stroke_color}" '
                f'stroke-width="{self.stroke_width}" '
                f'fill="none" '
                f'stroke-linejoin="round" '
                f'stroke-linecap="round"/>'
            )

        svg_parts.append("</svg>")
        self._write_svg(svg_parts, output_path)

    def generate_inline_svg(self, contours: List[np.ndarray], original_width: int, original_height: int) -> str:
        scale_x = 1.0
        scale_y = 1.0

        svg_parts = []
        svg_header = (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {original_width} {original_height}" '
            f'width="{original_width}" height="{original_height}">'
        )
        svg_parts.append(svg_header)
        svg_parts.append('  <rect width="100%" height="100%" fill="white"/>')

        for contour in contours:
            if len(contour) < 3:
                continue

            path_data = self._contour_to_path(contour, scale_x, scale_y)
            if path_data:
                svg_parts.append(
                    f'  <path d="{path_data}" '
                    f'stroke="{self.stroke_color}" '
                    f'stroke-width="{self.stroke_width}" '
                    f'fill="{self.fill}" '
                    f'stroke-linejoin="round" '
                    f'stroke-linecap="round"/>'
                )

        svg_parts.append("</svg>")
        return "\n".join(svg_parts)

    def simplify_path(self, contours: List[np.ndarray], tolerance: float = 1.0) -> List[np.ndarray]:
        simplified = []
        for contour in contours:
            if len(contour) > 2:
                step = max(1, int(tolerance))
                simplified.append(contour[::step])
            else:
                simplified.append(contour)
        return simplified
