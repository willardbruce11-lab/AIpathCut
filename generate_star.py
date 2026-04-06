import math
import os


def to_machine(pt, scale_x, scale_y, center_x, center_y):
    gx = center_x + pt[0] * scale_x
    gy = center_y + pt[1] * scale_y
    return gx, gy


def main():
    R = 30 / (2 * math.cos(math.radians(18)))
    r = R * math.sin(math.radians(18)) / math.sin(math.radians(54))
    points = []
    for i in range(5):
        angle = math.radians(-90 + i * 72)
        points.append((R * math.cos(angle), R * math.sin(angle)))
        angle2 = math.radians(-90 + i * 72 + 36)
        points.append((r * math.cos(angle2), r * math.sin(angle2)))

    scale_x = 1 / (76.0 / 9.0)
    scale_y = 1 / (50.0 / 300.0)
    center_x = 7.5
    center_y = -150

    header = [
        "G21",
        "G90",
        "F100",
        "",
        "G92 X0 Y0",
        "",
        f"G1 X{center_x:.3f} Y{center_y:.3f}",
        "",
    ]

    body = []
    start = points[0]
    start_x, start_y = to_machine(start, scale_x, scale_y, center_x, center_y)
    body.append(f"G1 X{start_x:.3f} Y{start_y:.3f}")
    body.append("M8")

    for pt in points[1:]:
        x, y = to_machine(pt, scale_x, scale_y, center_x, center_y)
        body.append(f"G1 X{x:.3f} Y{y:.3f}")

    body.append(f"G1 X{start_x:.3f} Y{start_y:.3f}")
    body.append(f"G1 X{start_x:.3f} Y{start_y:.3f}")
    body.append("M9")
    body.append("")

    footer = ["G1 X20 Y0", ""]

    os.makedirs("output", exist_ok=True)
    with open("output/五角星_test.gcode", "w", encoding="utf-8") as out:
        out.write("\n".join(header + body + footer))


if __name__ == "__main__":
    main()
