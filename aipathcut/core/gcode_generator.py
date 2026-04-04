"""
G代码生成模块
将轮廓数据转换为G代码格式，支持自动缩放到指定尺寸

坐标系统说明：
- X轴负值表示进纸，X=0为刀架最外侧
- 纸张中心位置：X=-3.5, Y=100
- UI基准尺寸：宽50mm × 高76mm
- Gcode基准加工区域：X7 × Y200 (X从-7到0, Y从0到200)
- 比例关系：UI尺寸 × (7/50) = Gcode X范围，UI尺寸 × (200/76) = Gcode Y范围
- 进纸位置 X=-3.5 对应纸张中心和加工区域中心
"""

import numpy as np


class GCodeGenerator:
    """G代码生成器"""

    # UI基准尺寸（mm）
    UI_BASE_WIDTH = 50
    UI_BASE_HEIGHT = 76

    # Gcode基准加工区域（mm）
    GCODE_BASE_WIDTH = 10    # X从0到10
    GCODE_BASE_HEIGHT = 200  # Y从0到-200

    # 物理标定：每个gcode单位对应的物理mm数（机器特定）
    MM_PER_GCODE_X = 76.0 / 9.0    # ≈ 8.444 mm per gcode X unit
    MM_PER_GCODE_Y = 50.0 / 300.0  # ≈ 0.1667 mm per gcode Y unit

    def __init__(self, feed_rate=1000, paper_center_x=-7.5, paper_center_y=150):
        """
        初始化G代码生成器

        Args:
            feed_rate: 进给速度 (mm/min)
            paper_center_x: 纸张中心X坐标(mm)，默认-3.5（进纸位置）
            paper_center_y: 纸张中心Y坐标(mm)，默认100
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

    def _densify_contours(self, contours, scale_x, scale_y, max_segment_mm=2.0):
        """
        对gcode空间中过长的线段进行加密插值

        非等比缩放时，Y轴放大倍数远大于X轴，轮廓中原本相邻的点
        在gcode空间中Y方向可能相距很远，导致曲线不够光滑。
        此方法对过长的线段进行细分，插入插值点。

        Args:
            contours: OpenCV格式的轮廓列表
            scale_x: X轴缩放比例
            scale_y: Y轴缩放比例
            max_segment_mm: gcode空间中线段最大长度(mm)

        Returns:
            list: 加密后的轮廓列表
        """
        densified_contours = []
        for contour in contours:
            if len(contour) < 2:
                densified_contours.append(contour)
                continue

            new_contour = []
            n = len(contour)
            for i in range(n):
                p1 = contour[i][0]
                p2 = contour[(i + 1) % n][0]

                new_contour.append(contour[i])

                # 计算物理空间中的距离
                dx_phys = (p2[0] - p1[0]) * scale_x * self.MM_PER_GCODE_X
                dy_phys = (p2[1] - p1[1]) * scale_y * self.MM_PER_GCODE_Y
                dist = (dx_phys * dx_phys + dy_phys * dy_phys) ** 0.5

                if dist > max_segment_mm:
                    n_segments = int(dist / max_segment_mm) + 1
                    for j in range(1, n_segments):
                        t = j / n_segments
                        new_x = p1[0] + (p2[0] - p1[0]) * t
                        new_y = p1[1] + (p2[1] - p1[1]) * t
                        new_contour.append([[new_x, new_y]])

            densified_contours.append(np.array(new_contour, dtype=np.float32))

        return densified_contours

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

        return scale_x, scale_y, \
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
        scale_x, scale_y, center_x_pixel, center_y_pixel, gcode_work_width, gcode_work_height, rotated = \
            self._calculate_scale_and_center(contours, target_width, target_height, auto_rotate=True)

        # 将加工路径缩小到0.64倍（两次0.8缩放），中心位置不变
        scale_x *= 0.64
        scale_y *= 0.64

        # 保存转换参数供填充生成器使用
        self.last_transform_params = {
            'scale_x': scale_x,
            'scale_y': scale_y,
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

        # 非等比缩放时加密轮廓点，保证Y轴放大后曲线光滑
        work_contours = self._densify_contours(work_contours, scale_x, scale_y)

        # 计算实际缩放后的尺寸
        scaled_width = orig_width * scale_x
        scaled_height = orig_height * scale_y

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
            gcode_lines.append(f"G1 Z{-self.paper_center_x} Y{-self.paper_center_y}")
        else:
            gcode_lines.append(f"G1 X{-self.paper_center_x} Y{-self.paper_center_y}")
        gcode_lines.append("")

        # 为每个轮廓生成路径
        for idx, contour in enumerate(work_contours):
            if len(contour) < 2:
                continue

            # 转换第一个点（起点）
            start = contour[0][0]
            x = -(self.paper_center_x + (start[0] - center_x_pixel) * scale_x)
            y = -(self.paper_center_y + (center_y_pixel - start[1]) * scale_y)

            if swap_xz:
                gcode_lines.append(f"G1 Y{y:.3f} Z{x:.3f}")
            else:
                gcode_lines.append(f"G1 X{x:.3f} Y{y:.3f}")
            gcode_lines.append("M8")

            # 生成路径点
            for point in contour[1:]:
                px = -(self.paper_center_x + (point[0][0] - center_x_pixel) * scale_x)
                py = -(self.paper_center_y + (center_y_pixel - point[0][1]) * scale_y)
                if swap_xz:
                    gcode_lines.append(f"G1 Y{py:.3f} Z{px:.3f}")
                else:
                    gcode_lines.append(f"G1 X{px:.3f} Y{py:.3f}")

            # 闭合路径
            if swap_xz:
                gcode_lines.append(f"G1 Y{y:.3f} Z{x:.3f}")
            else:
                gcode_lines.append(f"G1 X{x:.3f} Y{y:.3f}")
            gcode_lines.append("M9")
            gcode_lines.append("")

        # G代码尾部
        gcode_lines.append("")
        if swap_xz:
            gcode_lines.append("G1 Z20 Y0")
        else:
            gcode_lines.append("G1 X20 Y0")
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
