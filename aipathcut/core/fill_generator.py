"""
填充G-code生成模块
生成逐行扫描填充路径（根据点是否在轮廓内控制Z轴升降）
只在边界处改变Z轴，中间区域一次性走完
使用精确几何计算

坐标系统说明：
- X轴负值表示进纸，X=0为刀架最外侧
- 纸张中心位置：X=-7, Y=4
- UI基准尺寸：宽50mm × 高76mm
- Gcode基准加工区域：X14 × Y8 (X从-14到0, Y从0到8)
- 比例关系：UI尺寸 × (14/50) = Gcode X范围，UI尺寸 × (8/76) = Gcode Y范围
- 进纸位置 X=-7 对应纸张中心和加工区域中心
"""

import cv2
import numpy as np


class FillGenerator:
    """UV扫描填充生成器"""

    # UI基准尺寸（mm）
    UI_BASE_WIDTH = 50
    UI_BASE_HEIGHT = 76

    # Gcode基准加工区域（mm）
    GCODE_BASE_WIDTH = 14   # X从-14到0
    GCODE_BASE_HEIGHT = 8   # Y从0到8

    def __init__(self, feed_rate=1000, paper_center_x=-7, paper_center_y=4):
        """
        初始化填充生成器

        Args:
            feed_rate: 进给速度 (mm/min)
            paper_center_x: 纸张中心X坐标(mm)，默认-7（进纸位置）
            paper_center_y: 纸张中心Y坐标(mm)，默认4
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
            - 自动旋转：如果图形长宽比与加工区域不匹配，自动旋转90度
        """
        min_x, max_x, min_y, max_y = self._get_contours_bounds(contours)
        orig_width = max_x - min_x if max_x > min_x else 1
        orig_height = max_y - min_y if max_y > min_y else 1

        # 将UI尺寸映射到Gcode加工区域
        gcode_work_width = ui_width * (self.GCODE_BASE_WIDTH / self.UI_BASE_WIDTH)
        gcode_work_height = ui_height * (self.GCODE_BASE_HEIGHT / self.UI_BASE_HEIGHT)

        # 判断是否需要旋转（自动适应幅面）
        rotated = False
        if auto_rotate:
            # 不旋转时的利用率
            scale_no_rotate = min(gcode_work_width / orig_width, gcode_work_height / orig_height)
            # 旋转后的利用率（旋转后宽变高，高变宽）
            scale_rotate = min(gcode_work_width / orig_height, gcode_work_height / orig_width)
            # 选择利用率更高的方向
            if scale_rotate > scale_no_rotate * 1.01:  # 1%容差
                rotated = True

        scale_x = gcode_work_width / (orig_height if rotated else orig_width)
        scale_y = gcode_work_height / (orig_width if rotated else orig_height)
        scale = min(scale_x, scale_y)

        center_x_pixel = (min_x + max_x) / 2
        center_y_pixel = (min_y + max_y) / 2

        return scale, center_x_pixel, center_y_pixel, gcode_work_width, gcode_work_height, rotated

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
            scale = params['scale']
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
            # 添加注释说明使用了切割时的参数
            gcode_lines.append("; === 使用切割时的转换参数，确保填充区域与切割区域完全一致 ===")
        else:
            # 没有外部参数时，独立计算（可能存在偏差）
            gcode_lines.append("; === 警告：未使用切割参数，填充区域可能与切割区域不完全一致 ===")
            # 获取原始轮廓边界
            min_x, max_x, min_y, max_y = self._get_contours_bounds(contours)
            orig_width = max_x - min_x if max_x > min_x else 1
            orig_height = max_y - min_y if max_y > min_y else 1

            # 计算缩放比例和图案中心点，判断是否需要旋转
            scale, center_x_pixel, center_y_pixel, gcode_work_width, gcode_work_height, rotated = \
                self._calculate_scale_and_center(contours, target_width, target_height, auto_rotate=True)

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

        scaled_width = orig_width * scale
        scaled_height = orig_height * scale

        # Z轴安全高度（抬起位置）
        safe_z = 5.0

        # 填充间隔也需要按比例缩放到Gcode尺寸
        fill_interval_scaled = fill_interval * (self.GCODE_BASE_WIDTH / self.UI_BASE_WIDTH)
        x_interval_pixels = fill_interval_scaled / scale if scale > 0 else fill_interval_scaled

        # 扩展边界，确保扫描覆盖整个轮廓
        scan_min_x = min_x - x_interval_pixels
        scan_max_x = max_x + x_interval_pixels

        # G代码头部
        gcode_lines.append("; AIpathCut Fill G-code - UV扫描填充")
        gcode_lines.append(f"; Generated by AIpathCut - Segment-based Scan Fill")
        if rotated:
            gcode_lines.append("; 自动旋转: 是 (顺时针90度)")
        if swap_xz:
            gcode_lines.append("; XZ轴交换模式: X→Z, Z→X, Y→Y")
        gcode_lines.append(f"; 原图轮廓: {orig_height if rotated else max(orig_width, 1):.1f} x {orig_width if rotated else max(orig_height, 1):.1f} 像素 (旋转前)")
        gcode_lines.append(f"; UI输入尺寸: {target_width} x {target_height} mm")
        gcode_lines.append(f"; Gcode加工区域: {gcode_work_width:.2f} x {gcode_work_height:.2f} mm")
        gcode_lines.append(f"; 等比缩放: {scale:.4f}")
        gcode_lines.append(f"; X轴行间隔(UI): {fill_interval} mm -> Gcode: {fill_interval_scaled:.3f} mm")
        gcode_lines.append(f"; Z轴切割深度: {z_depth} mm")
        gcode_lines.append(f"; Z轴安全高度: {safe_z} mm")
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

        # 逐行扫描：固定X（像素坐标），找出垂直线与轮廓的精确交点
        x = scan_min_x

        while x <= scan_max_x:
            # 在当前X位置，找出与轮廓的所有交点
            intersections = self._find_vertical_intersections(x, work_contours)

            if len(intersections) >= 2:
                # 转换X坐标到输出坐标（相对于纸张中心）
                out_x = self.paper_center_x + (x - center_x_pixel) * scale

                # 配对交点生成线段
                # 偶数索引是入口，奇数索引是出口
                for i in range(0, len(intersections) - 1, 2):
                    if i + 1 >= len(intersections):
                        break

                    y_entry = intersections[i]      # 进入轮廓的Y
                    y_exit = intersections[i + 1]   # 离开轮廓的Y

                    # 转换Y坐标到输出坐标（相对于纸张中心，与切割使用完全相同的坐标转换）
                    # 注意：不再添加y_offset偏移，确保填充区域与切割区域严格一致
                    out_y_entry = self.paper_center_y + (center_y_pixel - y_entry) * scale
                    out_y_exit = self.paper_center_y + (center_y_pixel - y_exit) * scale

                    # 进入轮廓：先抬起移动到入口，然后下刀
                    if swap_xz:
                        gcode_lines.append(f"G0 Y{out_y_entry:.3f} Z{out_x:.3f} X{safe_z:.3f}        ; 移动到入口")
                        gcode_lines.append(f"G1 Y{out_y_entry:.3f} Z{out_x:.3f} X{z_depth:.3f}        ; 下刀")
                    else:
                        gcode_lines.append(f"G0 X{out_x:.3f} Y{out_y_entry:.3f} Z{safe_z:.3f}        ; 移动到入口")
                        gcode_lines.append(f"G1 X{out_x:.3f} Y{out_y_entry:.3f} Z{z_depth:.3f}        ; 下刀")

                    # 在轮廓内切割到出口
                    if swap_xz:
                        gcode_lines.append(f"G1 Y{out_y_exit:.3f} Z{out_x:.3f} X{z_depth:.3f}        ; 切割到出口")
                    else:
                        gcode_lines.append(f"G1 X{out_x:.3f} Y{out_y_exit:.3f} Z{z_depth:.3f}        ; 切割到出口")

            x += x_interval_pixels

        # 填充完成后抬起
        gcode_lines.append("")
        if swap_xz:
            gcode_lines.append(f"G0 X{safe_z:.3f}        ; 抬起刀头")
        else:
            gcode_lines.append(f"G0 Z{safe_z:.3f}        ; 抬起刀头")

        gcode_lines.append("")
        gcode_lines.append("; 出纸，刀头归位")
        if swap_xz:
            gcode_lines.append("G1 Z-20 Y0")
        else:
            gcode_lines.append("G1 X-20 Y0")
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
