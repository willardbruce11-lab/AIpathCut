import re

from aipathcut.core.gcode_generator import GCodeGenerator
from aipathcut.core.outline_extractor import OutlineExtractor
from aipathcut.core.transform_utils import build_closure_detour


def parse_gcode(gcode_text):
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
    extractor = OutlineExtractor()
    width, height, contours = extractor.extract_outline("input/cat.jpg")

    ggen = GCodeGenerator()
    gcode = ggen.generate(contours, width, height, 50, 76)

    gcode_points = parse_gcode(gcode)
    if gcode_points and same_point(gcode_points[0], (7.5, -150.0)):
        gcode_points = gcode_points[1:]
    gcode_points = [p for p in gcode_points if not same_point(p, (20.0, 0.0))]

    print("G-code points:", len(gcode_points))
    print("First five gcode coordinates:", gcode_points[:5])

    params = ggen.get_transform_params()
    scale_x = params["scale_x"]
    scale_y = params["scale_y"]
    cx = params["center_x_pixel"]
    cy = params["center_y_pixel"]
    work_contours = ggen._densify_contours(params["work_contours"], scale_x, scale_y)

    expected_points = []
    for contour in work_contours:
        if len(contour) < 2:
            continue

        machine_points = [
            ggen._transform_point(point[0], cx, cy, scale_x, scale_y)
            for point in contour
        ]
        expected_points.append(machine_points[0])
        for point in contour[1:]:
            expected_points.append(ggen._transform_point(point[0], cx, cy, scale_x, scale_y))
        expected_points.extend(build_closure_detour(machine_points, ggen.CLOSURE_OVERSHOOT_MM))

    print("Expected points:", len(expected_points))
    if expected_points and gcode_points:
        print("First expected point:", expected_points[0])
        print("First gcode point:", gcode_points[0])
        print("Last expected point:", expected_points[-1])
        print("Last gcode point:", gcode_points[-1])

    diff_count = sum(
        1
        for a, b in zip(gcode_points, expected_points)
        if not same_point(a, b)
    )
    print("Sample diff count:", diff_count)

    if gcode_points:
        start = gcode_points[0]
        end = gcode_points[-1]
        close_dist = ((start[0] - end[0]) ** 2 + (start[1] - end[1]) ** 2) ** 0.5
        print("Closure distance:", f"{close_dist:.6f}")
        if close_dist < 0.001:
            print("PASS: Path is closed")
        else:
            print("FAIL: Path is not closed")


if __name__ == "__main__":
    main()
