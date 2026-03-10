"""
G代码生成模块
将轮廓数据转换为G代码格式，支持自动缩放到指定尺寸

坐标系统说明：
- X轴负值表示进纸，X=0为刀架最外侧
- 纸张中心位置：X=-7, Y=4
- UI基准尺寸：宽50mm × 高76mm
- Gcode基准加工区域：X14 × Y8 (X从-14到0, Y从0到8)
- 比例关系：UI尺寸 × (14/50) = Gcode X范围，UI尺寸 × (8/76) = Gcode Y范围
- 进纸位置 X=-7 对应纸张中心和加工区域中心
"""

import numpy as np


class GCodeGenerator:
    """G代码生成器"""

    # UI基准尺寸（mm）
    UI_BASE_WIDTH = 50
    UI_BASE_HEIGHT = 76

    # Gcode基准加工区域（mm）
    GCODE_BASE_WIDTH = 14   # X从-14到0
    GCODE_BASE_HEIGHT = 8   # Y从0到8

    def __init__(self, feed_rate=1000, paper_center_x=-7, paper_center_y=4):
        """
        初始化G代码生成器

        Args:
            feed_rate: 进给速度 (mm/min)
            paper_center_x: 纸张中心X坐标(mm)，默认-7（进纸位置）
            paper_center_y: 纸张中心Y坐标(mm)，默认4
        """
        self.feed_rate = feed_rate
        self.paper_center_x = paper_center_x
        self.paper_center_y = paper_center_y

        # 保存最后一次计算的转换参数（供填充生成器使用）
        self.last_transform_params = None

    def _get_contours_bounds(self, contours):
        """
        获取所有轮廓的边界框

        Args:
            contours: OpenCV格式的轮廓列表

        Returns:
            tuple: (min_x, max_x, min_y, max_y)
        """
        all_points = [point[0] for contour in contours for point in contour]
        if not all_points:
            return 0, 0, 0, 0
        min_x = min(p[0] for p in all_points)
        max_x = max(p[0] for p in all_points)
        min_y = min(p[1] for p in all_points)
        max_y = max(p[1] for p in all_points)
        return min_x, max_x, min_y, max_y

    def _rotate_contours_90(self, contours, orig_width, orig_height):
        """
        将轮廓旋转90度（顺时针）

        Args:
            contours: OpenCV格式的轮廓列表
            orig_width: 原图宽度
            orig_height: 原图高度

        Returns:
            list: 旋转后的轮廓列表

        旋转后：原图(x,y) -> 新图(orig_height-y, x)
        """
        rotated_contours = []
        for contour in contours:
            new_contour = []
            for point in contour:
                x, y = point[0]
                # 顺时针旋转90度: (x, y) -> (height - y, x)
                new_x = orig_height - y
                new_y = x
                new_contour.append([[new_x, new_y]])
            rotated_contours.append(np.array(new_contour, dtype=np.int32))
        return rotated_contours

    def get_transform_params(self):
        """
        获取最后一次计算的转换参数
        供填充生成器使用，确保填充和切割使用完全相同的坐标转换

        Returns:
            dict: 转换参数字典，如果未生成过G-code则返回None
        """
        return self.last_transform_params

    def _calculate_scale_and_center(self, contours, ui_width, ui_height, auto_rotate=True):
        """
        计算缩放比例和图案中心点（等比例缩放）

        Args:
            contours: OpenCV格式的轮廓列表
            ui_width: UI输入的目标宽度(mm)
            ui_height: UI输入的目标高度(mm)
            auto_rotate: 是否自动旋转以适应加工幅面

        Returns:
            tuple: (scale, center_x_pixel, center_y_pixel, gcode_work_width, gcode_work_height, rotated)

        说明：
            - UI尺寸按比例映射到固定的Gcode加工区域
            - Gcode工作宽度 = UI宽度 × (14/50)
            - Gcode工作高度 = UI高度 × (8/76)
            - 等比例缩放：保持原图长宽比不变形
            - 自动旋转：如果图形长宽比与加工区域不匹配，自动旋转90度
        """
        min_x, max_x, min_y, max_y = self._get_contours_bounds(contours)
        orig_width = max_x - min_x
        orig_height = max_y - min_y

        # 避免除零错误
        if orig_width == 0:
            orig_width = 1
        if orig_height == 0:
            orig_height = 1

        # 将UI尺寸映射到Gcode加工区域
        gcode_work_width = ui_width * (self.GCODE_BASE_WIDTH / self.UI_BASE_WIDTH)
        gcode_work_height = ui_height * (self.GCODE_BASE_HEIGHT / self.UI_BASE_HEIGHT)

        # 计算长宽比
        orig_aspect = orig_width / orig_height if orig_height > 0 else 1
        work_aspect = gcode_work_width / gcode_work_height if gcode_work_height > 0 else 1

        # 判断是否需要旋转（自动适应幅面）
        rotated = False
        if auto_rotate:
            # 如果图形是横向的（宽>高），而加工区域是纵向的（宽<高），则需要旋转
            # 或者反过来
            # 更精确的判断：比较旋转前后的利用率
            # 不旋转时的利用率
            scale_no_rotate = min(gcode_work_width / orig_width, gcode_work_height / orig_height)
            # 旋转后的利用率（旋转后宽变高，高变宽）
            scale_rotate = min(gcode_work_width / orig_height, gcode_work_height / orig_width)
            # 选择利用率更高的方向
            if scale_rotate > scale_no_rotate * 1.01:  # 1%容差，避免几乎相等时也旋转
                rotated = True

        return scale_no_rotate if not rotated else scale_rotate, \
               (min_x + max_x) / 2, (min_y + max_y) / 2, \
               gcode_work_width, gcode_work_height, rotated

    def generate(self, contours, image_width=0, image_height=0,
                 target_width=0, target_height=0, swap_xz=False):
        """
        生成G代码

        Args:
            contours: OpenCV格式的轮廓列表
            image_width: 图像宽度(像素)，未使用
            image_height: 图像高度(像素)，未使用
            target_width: UI输入的目标宽度(mm)
            target_height: UI输入的目标高度(mm)
            swap_xz: 是否交换XZ轴（X→Z, Y→Y）

        Returns:
            str: G代码字符串
        """
        gcode_lines = []

        # 使用默认UI尺寸
        if target_width <= 0:
            target_width = self.UI_BASE_WIDTH
        if target_height <= 0:
            target_height = self.UI_BASE_HEIGHT

        # 获取原始轮廓边界
        min_x, max_x, min_y, max_y = self._get_contours_bounds(contours)
        orig_width = max_x - min_x if max_x > min_x else 0
        orig_height = max_y - min_y if max_y > min_y else 0

        # 计算缩放比例和图案中心点，判断是否需要旋转
        scale, center_x_pixel, center_y_pixel, gcode_work_width, gcode_work_height, rotated = \
            self._calculate_scale_and_center(contours, target_width, target_height, auto_rotate=True)

        # 保存转换参数供填充生成器使用
        self.last_transform_params = {
            'scale': scale,
            'center_x_pixel': center_x_pixel,
            'center_y_pixel': center_y_pixel,
            'gcode_work_width': gcode_work_width,
            'gcode_work_height': gcode_work_height,
            'rotated': rotated,
            'target_width': target_width,
            'target_height': target_height,
            'orig_width': orig_width,
            'orig_height': orig_height,
            'min_x': min_x,
            'max_x': max_x,
            'min_y': min_y,
            'max_y': max_y
        }

        # 如果需要旋转，先旋转轮廓
        work_contours = contours
        if rotated:
            work_contours = self._rotate_contours_90(contours, orig_width, orig_height)
            # 重新计算中心点
            min_x, max_x, min_y, max_y = self._get_contours_bounds(work_contours)
            center_x_pixel = (min_x + max_x) / 2
            center_y_pixel = (min_y + max_y) / 2
            # 旋转后的尺寸
            orig_width, orig_height = orig_height, orig_width
            # 更新转换参数（旋转后的值）
            self.last_transform_params.update({
                'center_x_pixel': center_x_pixel,
                'center_y_pixel': center_y_pixel,
                'orig_width': orig_width,
                'orig_height': orig_height,
                'min_x': min_x,
                'max_x': max_x,
                'min_y': min_y,
                'max_y': max_y
            })

        # 保存工作轮廓（供填充生成器使用，确保使用相同的旋转状态）
        self.last_transform_params['work_contours'] = work_contours

        # 计算实际缩放后的尺寸
        scaled_width = orig_width * scale
        scaled_height = orig_height * scale

        # G代码头部
        gcode_lines.append("; AIpathCut G-code - 切割路径")
        gcode_lines.append(f"; Generated by AIpathCut")
        if rotated:
            gcode_lines.append("; 自动旋转: 是 (顺时针90度)")
        if swap_xz:
            gcode_lines.append("; XZ轴交换模式: X→Z, Y→Y")
        gcode_lines.append(f"; 原图轮廓: {orig_height if rotated else max(orig_width, 1):.1f} x {orig_width if rotated else max(orig_height, 1):.1f} 像素 (旋转前)")
        gcode_lines.append(f"; UI输入尺寸: {target_width} x {target_height} mm")
        gcode_lines.append(f"; Gcode加工区域: {gcode_work_width:.2f} x {gcode_work_height:.2f} mm")
        gcode_lines.append(f"; 等比缩放: {scale:.4f} (保持长宽比)")
        gcode_lines.append(f"; 实际尺寸: {scaled_width:.1f} x {scaled_height:.1f} mm")
        if swap_xz:
            gcode_lines.append(f"; 纸张中心: Z={self.paper_center_x}, Y={self.paper_center_y}")
        else:
            gcode_lines.append(f"; 纸张中心: X={self.paper_center_x}, Y={self.paper_center_y}")
        gcode_lines.append(f"; Feed rate: {self.feed_rate} mm/min")
        gcode_lines.append("; ---")
        gcode_lines.append("G21         ; 使用毫米单位")
        gcode_lines.append("G90         ; 绝对坐标模式")
        gcode_lines.append(f"F{self.feed_rate}        ; 设置速度{self.feed_rate}mm/min")
        gcode_lines.append("")
        gcode_lines.append("; 开始前归零")
        if swap_xz:
            gcode_lines.append("G92 Z0 Y0")
        else:
            gcode_lines.append("G92 X0 Y0")
        gcode_lines.append("")
        gcode_lines.append("; 进纸，刀头到纸张中心位置")
        if swap_xz:
            gcode_lines.append(f"G1 Z{self.paper_center_x} Y{self.paper_center_y}")
        else:
            gcode_lines.append(f"G1 X{self.paper_center_x} Y{self.paper_center_y}")
        gcode_lines.append("")

        # 为每个轮廓生成路径
        for idx, contour in enumerate(work_contours):
            if len(contour) < 2:
                continue

            gcode_lines.append(f"; 轮廓 {idx + 1}")

            # 转换第一个点（起点）
            start = contour[0][0]
            # 坐标映射：图案中心映射到纸张中心
            # X: 图案中心 -> 纸张中心X
            # Y: 图像坐标向下翻转，中心对齐
            x = self.paper_center_x + (start[0] - center_x_pixel) * scale
            y = self.paper_center_y + (center_y_pixel - start[1]) * scale

            if swap_xz:
                gcode_lines.append(f"G1 Y{y:.3f} Z{x:.3f}        ; 起点")
            else:
                gcode_lines.append(f"G1 X{x:.3f} Y{y:.3f}        ; 起点")
            gcode_lines.append("M8         ; 启用刀头")

            # 生成路径点
            for point in contour[1:]:
                px = self.paper_center_x + (point[0][0] - center_x_pixel) * scale
                py = self.paper_center_y + (center_y_pixel - point[0][1]) * scale
                if swap_xz:
                    gcode_lines.append(f"G1 Y{py:.3f} Z{px:.3f}")
                else:
                    gcode_lines.append(f"G1 X{px:.3f} Y{py:.3f}")

            # 闭合路径
            if swap_xz:
                gcode_lines.append(f"G1 Y{y:.3f} Z{x:.3f}        ; 闭合轮廓")
            else:
                gcode_lines.append(f"G1 X{x:.3f} Y{y:.3f}        ; 闭合轮廓")
            gcode_lines.append("M9         ; 关闭刀头")
            gcode_lines.append("")

        # G代码尾部
        gcode_lines.append("")
        gcode_lines.append("; 出纸，刀头归位")
        if swap_xz:
            gcode_lines.append("G1 Z-20 Y0")
        else:
            gcode_lines.append("G1 X-20 Y0")
        gcode_lines.append("")

        return "\n".join(gcode_lines)

    def save_to_file(self, contours, filepath, image_width=0, image_height=0,
                     target_width=0, target_height=0, swap_xz=False):
        """
        生成G代码并保存到文件

        Args:
            contours: OpenCV格式的轮廓列表
            filepath: 输出文件路径
            image_width: 图像宽度(像素)，未使用（保留用于兼容）
            image_height: 图像高度(像素)，未使用（保留用于兼容）
            target_width: 目标宽度(mm)
            target_height: 目标高度(mm)
            swap_xz: 是否交换XZ轴（X→Z, Y→Y）

        Returns:
            bool: 是否保存成功
        """
        try:
            gcode = self.generate(contours, image_width, image_height,
                                 target_width, target_height, swap_xz)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(gcode)
            return True
        except Exception as e:
            print(f"Error saving G-code: {e}")
            return False
