import math
import os

import numpy as np

from aipathcut.core.fill_generator import FillGenerator
from aipathcut.core.gcode_generator import GCodeGenerator


def build_star():
    r_outer = 30 / (2 * math.cos(math.radians(18)))
    r_inner = r_outer * math.sin(math.radians(18)) / math.sin(math.radians(54))
    coords = []
    for i in range(5):
        outer_angle = math.radians(-90 + i * 72)
        inner_angle = math.radians(-90 + i * 72 + 36)
        coords.append((r_outer * math.cos(outer_angle), r_outer * math.sin(outer_angle)))
        coords.append((r_inner * math.cos(inner_angle), r_inner * math.sin(inner_angle)))
    contour = np.array([[[x, y]] for x, y in coords], dtype=np.float32)
    return [contour]


def main():
    contours = build_star()

    generator = GCodeGenerator()
    generator.generate(contours, 0, 0, 50, 76)

    fill_gen = FillGenerator()
    fill_gen.set_transform_params(generator.get_transform_params())

    os.makedirs("output", exist_ok=True)
    fill_gen.save_to_file(
        contours,
        "output/五角星_fill_test.gcode",
        fill_interval=3.0,
        y_offset=5.0,
        z_depth=-2.0,
        target_width=50,
        target_height=76,
        swap_xz=False,
    )


if __name__ == "__main__":
    main()
