"""
SVG 生成模块
将提取的轮廓转换为 SVG 矢量图
"""
import numpy as np
from typing import List, Tuple, Optional
from pathlib import Path


class SVGGenerator:
    """SVG 矢量图生成器"""

    def __init__(self,
                 stroke_color: str = "#000000",
                 stroke_width: float = 2.0,
                 fill: str = "none",
                 width: int = 500,
                 height: int = 500):
        """
        初始化 SVG 生成器

        Args:
            stroke_color: 描边颜色（十六进制或颜色名）
            stroke_width: 描边宽度
            fill: 填充颜色
            width: SVG 画布宽度
            height: SVG 画布高度
        """
        self.stroke_color = stroke_color
        self.stroke_width = stroke_width
        self.fill = fill
        self.width = width
        self.height = height

    def _contour_to_path(self, contour: np.ndarray,
                        scale_x: float,
                        scale_y: float) -> str:
        """
        将 OpenCV 轮廓转换为 SVG 路径

        Args:
            contour: OpenCV 轮廓点集
            scale_x: X 方向缩放比例
            scale_y: Y 方向缩放比例

        Returns:
            SVG 路径字符串
        """
        if len(contour) == 0:
            return ""

        # OpenCV 轮廓格式是 [[x,y], [x,y], ...]
        points = []
        for point in contour:
            x = float(point[0][0]) * scale_x
            y = float(point[0][1]) * scale_y
            points.append(f"{x:.2f},{y:.2f}")

        # 创建闭合路径
        path_data = " M " + " L ".join(points) + " Z"

        return path_data

    def generate(self,
                contours: List[np.ndarray],
                original_width: int,
                original_height: int,
                output_path: str,
                viewbox: bool = True) -> None:
        """
        生成 SVG 文件

        Args:
            contours: 轮廓列表
            original_width: 原始图片宽度
            original_height: 原始图片高度
            output_path: 输出 SVG 文件路径
            viewbox: 是否使用 viewBox 进行自适应缩放
        """
        # 计算缩放比例
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

        # 生成 SVG 内容
        svg_parts = []

        # SVG 头部
        if viewbox:
            svg_header = (f'<svg xmlns="http://www.w3.org/2000/svg" '
                         f'viewBox="0 0 {original_width} {original_height}" '
                         f'width="{original_width}" height="{original_height}">')
        else:
            svg_header = (f'<svg xmlns="http://www.w3.org/2000/svg" '
                         f'width="{svg_width}" height="{svg_height}">')

        svg_parts.append(svg_header)

        # 添加背景（可选，白色）
        svg_parts.append(f'  <rect width="100%" height="100%" fill="white"/>')

        # 添加每个轮廓的路径
        for contour in contours:
            if len(contour) < 3:
                continue

            path_data = self._contour_to_path(contour, scale_x, scale_y)
            if path_data:
                path_element = (f'  <path d="{path_data}" '
                              f'stroke="{self.stroke_color}" '
                              f'stroke-width="{self.stroke_width}" '
                              f'fill="{self.fill}" '
                              f'stroke-linejoin="round" '
                              f'stroke-linecap="round"/>')
                svg_parts.append(path_element)

        # SVG 尾部
        svg_parts.append('</svg>')

        # 写入文件
        svg_content = '\n'.join(svg_parts)

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(svg_content)

    def generate_inline_svg(self,
                           contours: List[np.ndarray],
                           original_width: int,
                           original_height: int) -> str:
        """
        生成内联 SVG 字符串

        Args:
            contours: 轮廓列表
            original_width: 原始图片宽度
            original_height: 原始图片高度

        Returns:
            SVG 字符串
        """
        scale_x = 1.0
        scale_y = 1.0

        svg_parts = []
        svg_header = (f'<svg xmlns="http://www.w3.org/2000/svg" '
                     f'viewBox="0 0 {original_width} {original_height}" '
                     f'width="{original_width}" height="{original_height}">')
        svg_parts.append(svg_header)
        svg_parts.append(f'  <rect width="100%" height="100%" fill="white"/>')

        for contour in contours:
            if len(contour) < 3:
                continue

            path_data = self._contour_to_path(contour, scale_x, scale_y)
            if path_data:
                path_element = (f'  <path d="{path_data}" '
                              f'stroke="{self.stroke_color}" '
                              f'stroke-width="{self.stroke_width}" '
                              f'fill="{self.fill}" '
                              f'stroke-linejoin="round" '
                              f'stroke-linecap="round"/>')
                svg_parts.append(path_element)

        svg_parts.append('</svg>')

        return '\n'.join(svg_parts)

    def simplify_path(self, contours: List[np.ndarray],
                     tolerance: float = 1.0) -> List[np.ndarray]:
        """
        简化路径，减少点数

        Args:
            contours: 原始轮廓列表
            tolerance: 简化容差

        Returns:
            简化后的轮廓列表
        """
        # 这里可以添加更复杂的简化算法
        # 目前使用基本的点减少
        simplified = []
        for contour in contours:
            if len(contour) > 2:
                # 每隔 n 个点采样
                step = max(1, int(tolerance))
                simplified.append(contour[::step])
            else:
                simplified.append(contour)

        return simplified
