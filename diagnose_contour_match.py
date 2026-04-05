#!/usr/bin/env python3
"""Validate that extracted contours match the generated G-code path."""

import numpy as np

from aipathcut.core.gcode_generator import GCodeGenerator


def make_l_shape():
    """Create a non-symmetric L-shape contour for direction checks."""
    points = [
        [10, 10],
        [100, 10],
        [100, 50],
        [50, 50],
        [50, 100],
        [10, 100],
    ]
    contour = np.array([[[p[0], p[1]]] for p in points], dtype=np.int32)
    return [contour]


def parse_gcode_points(gcode_text):
    import re

    points = []
    for line in gcode_text.splitlines():
        line = line.strip()
        if not line.startswith("G1"):
            continue
        match = re.search(r"X([-0-9.]+)\s+Y([-0-9.]+)", line)
        if match:
            points.append((float(match.group(1)), float(match.group(2))))
    return points


def same_point(a, b, tol=0.001):
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


def main():
    print("=" * 60)
    print("Diagnostic: verify contour matches gcode output")
    print("=" * 60)

    contours = make_l_shape()
    contour = contours[0]

    print("\n--- Original L-shape contour (pixel coords) ---")
    for i in range(len(contour)):
        pt = contour[i][0]
        print(f"  Point {i}: ({pt[0]}, {pt[1]})")

    inner_corner = contour[3][0]
    print(f"\nL-shape inner corner: ({inner_corner[0]}, {inner_corner[1]})")

    gen = GCodeGenerator(feed_rate=100)
    gcode = gen.generate(contours, target_width=50, target_height=76)
    points = parse_gcode_points(gcode)

    if points and same_point(points[0], (7.5, -150.0)):
        points = points[1:]
    points = [p for p in points if not same_point(p, (20.0, 0.0))]

    paper_center = (7.5, -150.0)
    print(f"\nPaper center: X={paper_center[0]:.3f}, Y={paper_center[1]:.3f}")
    print(f"Path points count: {len(points)}")

    if len(points) >= 2:
        start = points[0]
        end = points[-1]
        close_dist = ((start[0] - end[0]) ** 2 + (start[1] - end[1]) ** 2) ** 0.5
        print("\nPath closure check:")
        print(f"  Start: ({start[0]:.3f}, {start[1]:.3f})")
        print(f"  End:   ({end[0]:.3f}, {end[1]:.3f})")
        print(f"  Closure distance: {close_dist:.6f}")
        if close_dist < 0.001:
            print("  PASS: Path is closed")
        else:
            print("  FAIL: Path is NOT closed")

    params = gen.last_transform_params
    cx = params["center_x_pixel"]
    cy = params["center_y_pixel"]
    sx = params["scale_x"]
    sy = params["scale_y"]
    rotated = params["rotated"]

    print("\nTransform params:")
    print(f"  Rotated: {rotated}")
    print(f"  Center pixel: ({cx:.1f}, {cy:.1f})")
    print(f"  scale_x: {sx:.8f}, scale_y: {sy:.8f}")

    if not rotated:
        left_bottom = contour[0][0]
        right_bottom = contour[1][0]
        top_left = contour[5][0]
        bottom_left = contour[0][0]

        x_left = gen._transform_point(left_bottom, cx, cy, sx, sy)[0]
        x_right = gen._transform_point(right_bottom, cx, cy, sx, sy)[0]
        y_top = gen._transform_point(top_left, cx, cy, sx, sy)[1]
        y_bottom = gen._transform_point(bottom_left, cx, cy, sx, sy)[1]

        print("\n--- X-axis direction check ---")
        print(f"  Left-bottom pixel  ({left_bottom[0]},{left_bottom[1]}) -> gcode X={x_left:.3f}")
        print(f"  Right-bottom pixel ({right_bottom[0]},{right_bottom[1]}) -> gcode X={x_right:.3f}")
        print(f"  Paper center X={paper_center[0]}")
        if x_left < x_right:
            print("  PASS: X-axis direction correct")
        else:
            print("  FAIL: X-axis direction is mirrored")

        print("\n--- Y-axis direction check ---")
        print(f"  Top-left pixel     ({top_left[0]},{top_left[1]}) -> gcode Y={y_top:.3f}")
        print(f"  Bottom-left pixel  ({bottom_left[0]},{bottom_left[1]}) -> gcode Y={y_bottom:.3f}")
        print(f"  Paper center Y={paper_center[1]}")
        if y_top > y_bottom:
            print("  PASS: Y-axis direction correct")
        else:
            print("  FAIL: Y-axis direction is reversed")
    else:
        print("\nContour was rotated; skipping direct axis-direction comparison.")

    print("\n--- Physical size ---")
    print(f"  scale_x * MM_PER_GCODE_X = {sx * gen.MM_PER_GCODE_X:.4f} mm/pixel")
    print(f"  scale_y * MM_PER_GCODE_Y = {sy * gen.MM_PER_GCODE_Y:.4f} mm/pixel")
    print("  (These should match for an undistorted output)")

    print("\n--- Gcode path points ---")
    for i, p in enumerate(points[:50]):
        print(f"  Point {i}: X={p[0]:.3f}, Y={p[1]:.3f}")

    print("\n" + "=" * 60)
    print("Diagnostic complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
