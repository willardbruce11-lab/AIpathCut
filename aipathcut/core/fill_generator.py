"""
填充G-code生成模块
生成逐行扫描填充路径（根据点是否在轮廓内控制Z轴升降）
只在边界处改变Z轴，中间区域一次性走完
使用精确几何计算

坐标系统说明：
- X轴负值表示进纸，X=0为刀架最外侧
- 纸张中心位置：X=-3.5, Y=100
- UI基准尺寸：宽50mm × 高76mm
- Gcode基准加工区域：X7 × Y200 (X从-7到0, Y从0到200)
- 比例关系：UI尺寸 × (7/50) = Gcode X范围，UI尺寸 × (200/76) = Gcode Y范围
- 进纸位置 X=-3.5 对应纸张中心和加工区域中心
"""

import cv2
import numpy as np


class FillGenerator:
    """UV扫描填充生成器"""

    # UI基准尺寸（mm）
    UI_BASE_WIDTH = 50
    UI_BASE_HEIGHT = 76

    # Gcode基准加工区域（mm）
    GCODE_BASE_WIDTH = 10    # X从0到10
    GCODE_BASE_HEIGHT = 200  # Y从0到-200

    # 物理标定：每个gcode单位对应的物理mm数（机器特定）
    MM_PER_GCODE_X = 76.0 / 9.0    # ≈ 8.444 mm per gcode X unit
    MM_PER_GCODE_Y = 50.0 / 300.0  # ≈ 0.1667 mm per gcode Y unit

    def __init__(self, feed_rate=1000, paper_center_x=-5.8, paper_center_y=150):
        """
        初始化填充生成器

        Args:
            feed_rate: 进给速度 (mm/min)
            paper_center_x: 纸张中心X坐标(mm)，默认-3.5（进纸位置）
            paper_center_y: 纸张中心Y坐标(mm)，默认100
        """
        self.feed_rate = feed_rate
        self.paper_center_x = paper_center_x
        self.paper_center_y = paper_center_y

        # 外部转换参数（从切割生成器获取，确保使用相同的坐标转换）
        self.external_transform_params = None

    def _get_contours_bounds(self, contours):
        """获取轮廓边界"""
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

    def set_transform_params(self, params):
        """
        设置外部转换参数（从切割生成器获取）
        确保填充和切割使用完全相同的坐标转换

        Args:
            params: 从GCodeGenerator.get_transform_params()获取的参数字典
        """
        self.external_transform_params = params

    def _find_vertical_intersections(self, fixed_x, contours):
        """
        计算垂直线 X=fixed_x 与所有轮廓边段的精确交点

        Args:
            fixed_x: 固定的X坐标
            contours: OpenCV格式的轮廓列表

        Returns:
            list: 交点的Y坐标列表（已排序）
        """
        intersections = []

        for contour in contours:
            n = len(contour)
            for i in range(n):
                p1 = contour[i][0]
                p2 = contour[(i + 1) % n][0]

                x1, y1 = p1
                x2, y2 = p2

                # 检查边段是否与垂直线 X=fixed_x 相交
                # 边段必须跨越 fixed_x（即一个端点在左，一个在右，或端点恰好在线上）
                if (x1 <= fixed_x <= x2) or (x2 <= fixed_x <= x1):
                    # 避免除零（垂直边段）
                    if abs(x2 - x1) < 0.0001:
                        continue

                    # 计算交点的Y坐标（精确值）
                    y = y1 + (fixed_x - x1) * (y2 - y1) / (x2 - x1)
                    intersections.append(y)

        # 排序所有交点
        return sorted(intersections)

    def _calculate_scale_and_center(self, contours, ui_width, ui_height, auto_rotate=True):
        """
        计算缩放比例和图案中心点（等比物理缩放，以Y轴为标准）

        Args:
            contours: OpenCV格式的轮廓列表
            ui_width: UI输入的目标宽度(mm)
            ui_height: UI输入的目标高度(mm)
            auto_rotate: 是否自动旋转以适应加工幅面

        Returns:
            tuple: (scale_x, scale_y, center_x_pixel, center_y_pixel, gcode_work_width, gcode_work_height, rotated)

        说明：
            - Y轴缩放保持不变，X轴从Y轴按物理比例推导
            - 物理比例 = MM_PER_GCODE_Y / MM_PER_GCODE_X
            - 自动旋转：选择输出更大的方向
        """
        min_x, max_x, min_y, max_y = self._get_contours_bounds(contours)
        orig_width = max_x - min_x if max_x > min_x else 1
        orig_height = max_y - min_y if max_y > min_y else 1

        # 将UI尺寸映射到Gcode加工区域
        gcode_work_width = ui_width * (self.GCODE_BASE_WIDTH / self.UI_BASE_WIDTH)
        gcode_work_height = ui_height * (self.GCODE_BASE_HEIGHT / self.UI_BASE_HEIGHT)

        # 物理比例修正因子：确保X和Y方向物理位移等比
        phys_ratio = self.MM_PER_GCODE_Y / self.MM_PER_GCODE_X

        # 不旋转：Y填满gcode_work_height，X按物理比例从Y推导
        sy_no_rot = gcode_work_height / orig_height
        sx_no_rot = sy_no_rot * phys_ratio

        # 旋转时（宽高互换）
        sy_rot = gcode_work_height / orig_width
        sx_rot = sy_rot * phys_ratio

        # 判断是否需要旋转：选输出更大的方向（scale_y更大=物理输出更大）
        rotated = False
        if auto_rotate:
            if sy_rot > sy_no_rot * 1.01:  # 1%容差
                rotated = True

        scale_x = sx_rot if rotated else sx_no_rot
        scale_y = sy_rot if rotated else sy_no_rot

        center_x_pixel = (min_x + max_x) / 2
        center_y_pixel = (min_y + max_y) / 2

        return scale_x, scale_y, center_x_pixel, center_y_pixel, gcode_work_width, gcode_work_height, rotated

    def generate(self, contours, fill_interval, y_offset, z_depth,
                 target_width=0, target_height=0, swap_xz=False):
        """
        生成逐行扫描填充G代码

        Args:
            contours: OpenCV格式的轮廓列表
            fill_interval: X轴行间隔(mm)，每行之间的X距离
            y_offset: Y轴偏移量(mm)，已废弃（保留参数兼容性，不再使用）
            z_depth: Z轴切割深度(mm)，负值表示下探（如-2mm）
            target_width: UI输入的目标宽度(mm)
            target_height: UI输入的目标高度(mm)
            swap_xz: 是否交换XZ轴（X→Z, Z→X, Y→Y）

        Returns:
            str: G代码字符串

        注意：
            填充区域严格使用切割时的坐标转换，与切割区域完全一致
        """
        gcode_lines = []

        # 使用默认UI尺寸
        if target_width <= 0:
            target_width = self.UI_BASE_WIDTH
        if target_height <= 0:
            target_height = self.UI_BASE_HEIGHT

        # 如果有外部转换参数（从切割生成器获取），直接使用，确保填充与切割完全一致
        if self.external_transform_params:
            params = self.external_transform_params
            scale_x = params['scale_x']
            scale_y = params['scale_y']
            center_x_pixel = params['center_x_pixel']
            center_y_pixel = params['center_y_pixel']
            gcode_work_width = params['gcode_work_width']
            gcode_work_height = params['gcode_work_height']
            rotated = params['rotated']
            orig_width = params['orig_width']
            orig_height = params['orig_height']
            min_x = params['min_x']
            max_x = params['max_x']
            min_y = params['min_y']
            max_y = params['max_y']
            # 使用保存的工作轮廓（确保使用相同的旋转状态）
            work_contours = params.get('work_contours', contours)
        else:
            # 获取原始轮廓边界
            min_x, max_x, min_y, max_y = self._get_contours_bounds(contours)
            orig_width = max_x - min_x if max_x > min_x else 1
            orig_height = max_y - min_y if max_y > min_y else 1

            # 计算缩放比例和图案中心点，判断是否需要旋转
            scale_x, scale_y, center_x_pixel, center_y_pixel, gcode_work_width, gcode_work_height, rotated = \
                self._calculate_scale_and_center(contours, target_width, target_height, auto_rotate=True)

            # 将加工路径缩小到0.64倍（两次0.8缩放），中心位置不变
            scale_x *= 0.64
            scale_y *= 0.64

            # 如果需要旋转，先旋转轮廓
            work_contours = contours
            if rotated:
                work_contours = self._rotate_contours_90(contours, orig_width, orig_height)
                # 重新获取轮廓边界和中心点
                min_x, max_x, min_y, max_y = self._get_contours_bounds(work_contours)
                center_x_pixel = (min_x + max_x) / 2
                center_y_pixel = (min_y + max_y) / 2
                # 旋转后的尺寸
                orig_width, orig_height = orig_height, orig_width

        scaled_width = orig_width * scale_x
        scaled_height = orig_height * scale_y

        # 填充间隔：fill_interval是物理mm，转换为像素X间距
        # scale_x * MM_PER_GCODE_X = 每像素在X方向的物理mm
        x_interval_pixels = fill_interval / (scale_x * self.MM_PER_GCODE_X) if scale_x > 0 else fill_interval

        # 扩展边界，确保扫描覆盖整个轮廓
        scan_min_x = min_x - x_interval_pixels
        scan_max_x = max_x + x_interval_pixels

        # G代码头部
        gcode_lines.append("G21")
        gcode_lines.append("G90")
        gcode_lines.append(f"F{self.feed_rate}")
        gcode_lines.append("")
        if swap_xz:
            gcode_lines.append("G92 Z0 Y0")
        else:
            gcode_lines.append("G92 X0 Y0")
        gcode_lines.append("")
        if swap_xz:
            gcode_lines.append(f"G0 Z{-self.paper_center_x} Y{-self.paper_center_y}")
        else:
            gcode_lines.append(f"G0 X{-self.paper_center_x} Y{-self.paper_center_y}")
        gcode_lines.append("")

        # 逐行扫描：固定X（像素坐标），找出垂直线与轮廓的精确交点
        # 先收集所有填充段，再统一输出（刀头全程保持下降，使用M3/M5控制）
        fill_segments = []  # [(out_x, out_y_entry, out_y_exit), ...]

        x = scan_min_x
        while x <= scan_max_x:
            intersections = self._find_vertical_intersections(x, work_contours)

            if len(intersections) >= 2:
                out_x = -(self.paper_center_x + (x - center_x_pixel) * scale_x)

                for i in range(0, len(intersections) - 1, 2):
                    if i + 1 >= len(intersections):
                        break

                    y_entry = intersections[i]
                    y_exit = intersections[i + 1]

                    out_y_entry = -(self.paper_center_y + (center_y_pixel - y_entry) * scale_y)
                    out_y_exit = -(self.paper_center_y + (center_y_pixel - y_exit) * scale_y)

                    fill_segments.append((out_x, out_y_entry, out_y_exit))

            x += x_interval_pixels

        # 输出填充路径：G0到第一个入口 → M3下刀 → G1连续填充 → M5关闭刀头
        if fill_segments:
            first_x, first_y_entry, _ = fill_segments[0]
            if swap_xz:
                gcode_lines.append(f"G0 Y{first_y_entry:.3f} Z{first_x:.3f}")
            else:
                gcode_lines.append(f"G0 X{first_x:.3f} Y{first_y_entry:.3f}")
            gcode_lines.append("M3")
            gcode_lines.append("M4")

            for seg_x, seg_y_entry, seg_y_exit in fill_segments:
                if swap_xz:
                    gcode_lines.append(f"G1 Y{seg_y_entry:.3f} Z{seg_x:.3f}")
                    gcode_lines.append(f"G1 Y{seg_y_exit:.3f} Z{seg_x:.3f}")
                else:
                    gcode_lines.append(f"G1 X{seg_x:.3f} Y{seg_y_entry:.3f}")
                    gcode_lines.append(f"G1 X{seg_x:.3f} Y{seg_y_exit:.3f}")

            gcode_lines.append("M5")

        gcode_lines.append("")
        if swap_xz:
            gcode_lines.append("G0 Z20 Y0")
        else:
            gcode_lines.append("G0 X20 Y0")
        gcode_lines.append("")

        return "\n".join(gcode_lines)

    def save_to_file(self, contours, filepath, fill_interval, y_offset, z_depth,
                     image_width=0, image_height=0,
                     target_width=0, target_height=0, swap_xz=False):
        """
        生成并保存填充G代码

        Args:
            contours: OpenCV格式的轮廓列表
            filepath: 输出文件路径
            fill_interval: X轴行间隔(mm)
            y_offset: Y轴偏移量(mm)
            z_depth: Z轴切割深度(mm)
            image_width: 图像宽度(像素)，未使用（保留用于兼容）
            image_height: 图像高度(像素)，未使用（保留用于兼容）
            target_width: 目标宽度(mm)，为0时使用默认加工区域宽度
            target_height: 目标高度(mm)，为0时使用默认加工区域高度
            swap_xz: 是否交换XZ轴（X→Z, Z→X, Y→Y）

        Returns:
            bool: 是否保存成功
        """
        try:
            gcode = self.generate(contours, fill_interval, y_offset, z_depth,
                                 target_width, target_height, swap_xz)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(gcode)
            return True
        except Exception as e:
            print(f"Error saving Fill G-code: {e}")
            return False
