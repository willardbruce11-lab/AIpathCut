"""
描边提取模块
从白底图片中提取人物/动物的轮廓
优化支持白底动漫人物
"""
import cv2
import numpy as np
from typing import Tuple, List, Optional
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union


class OutlineExtractor:
    """白底图片描边提取器"""

    def __init__(self,
                 white_threshold: int = 230,
                 blur_kernel: int = 5,
                 canny_threshold1: int = 50,
                 canny_threshold2: int = 150,
                 mode: str = "auto"):
        """
        初始化提取器

        Args:
            white_threshold: 白色背景的阈值（0-255）
            blur_kernel: 高斯模糊核大小
            canny_threshold1: Canny 边缘检测低阈值
            canny_threshold2: Canny 边缘检测高阈值
            mode: 提取模式 "auto"(自动), "color"(颜色差异), "grabcut"(GrabCut), "edge"(边缘优先)
        """
        self.white_threshold = white_threshold
        self.blur_kernel = blur_kernel
        self.canny_threshold1 = canny_threshold1
        self.canny_threshold2 = canny_threshold2
        self.mode = mode

    def load_image(self, image_path: str) -> np.ndarray:
        """加载图片"""
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"无法加载图片: {image_path}")
        return image

    def remove_white_background_color_aware(self, image: np.ndarray) -> np.ndarray:
        """
        使用颜色感知的方法移除白色背景
        适用于动漫人物（浅色头发/衣服）

        Args:
            image: 输入图片 (BGR)

        Returns:
            二值掩码，前景为255，背景为0
        """
        height, width = image.shape[:2]

        # 转换到 LAB 空间（更好的感知颜色差异）
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)

        # 方法1: 基于灰度阈值
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 方法2: 基于与纯白的颜色差异
        # 纯白色在 LAB 中约为 L=255, A=128, B=128
        white_l = 255
        white_a = 128
        white_b = 128

        # 计算每个像素与白色的颜色距离
        color_distance = np.sqrt(
            (l_channel.astype(float) - white_l) ** 2 +
            (a_channel.astype(float) - white_a) ** 2 * 0.5 +  # A/B 通道权重较低
            (b_channel.astype(float) - white_b) ** 2 * 0.5
        )

        # 方法3: 基于边缘检测（直接在原图上）
        # 使用自适应阈值的边缘检测
        gray_blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges_adaptive = cv2.Canny(gray_blur, 30, 100)

        # 综合判断
        # 1. 灰度低于阈值
        mask_gray = gray < self.white_threshold

        # 2. 颜色距离大于阈值
        color_threshold = 15  # 颜色距离阈值
        mask_color = color_distance > color_threshold

        # 3. 边缘区域扩展（边缘附近也认为是前景）
        kernel_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        edges_dilated = cv2.dilate(edges_adaptive, kernel_dilate, iterations=2)
        mask_edge = edges_dilated > 0

        # 组合所有掩码
        combined_mask = (mask_gray | mask_color | mask_edge).astype(np.uint8) * 255

        # 形态学操作清理
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel)
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel)

        return combined_mask

    def remove_white_background_grabcut(self, image: np.ndarray) -> np.ndarray:
        """
        使用 GrabCut 算法移除白色背景
        适用于复杂场景

        Args:
            image: 输入图片 (BGR)

        Returns:
            二值掩码，前景为255，背景为0
        """
        height, width = image.shape[:2]

        # 创建初始掩码
        mask = np.zeros((height, width), np.uint8)

        # 定义背景模型和前景模型
        bgd_model = np.zeros((1, 65), np.float64)
        fgd_model = np.zeros((1, 65), np.float64)

        # 基于白色阈值创建初始区域标记
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 明确的背景区域（很白的地方）
        sure_bg = (gray > self.white_threshold + 10).astype(np.uint8)

        # 明确的前景区域（明显不是白色的地方）
        sure_fg = (gray < self.white_threshold - 30).astype(np.uint8)

        # 可能的前景/背景区域
        probable_fg = ((gray >= self.white_threshold - 30) &
                       (gray <= self.white_threshold + 10)).astype(np.uint8)

        # GrabCut 需要的标记：0=背景, 1=前景, 2=可能背景, 3=可能前景
        grabcut_mask = np.ones((height, width), np.uint8) * 2  # 默认可能背景
        grabcut_mask[sure_bg > 0] = 0  # 背景
        grabcut_mask[sure_fg > 0] = 1  # 前景
        grabcut_mask[probable_fg > 0] = 3  # 可能前景

        # 运行 GrabCut
        try:
            cv2.grabCut(image, grabcut_mask, None, bgd_model, fgd_model, 5, cv2.GC_INIT_WITH_MASK)

            # 提取前景
            foreground_mask = np.where((grabcut_mask == 1) | (grabcut_mask == 3), 255, 0).astype(np.uint8)

            # 形态学清理
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            foreground_mask = cv2.morphologyEx(foreground_mask, cv2.MORPH_OPEN, kernel)
            foreground_mask = cv2.morphologyEx(foreground_mask, cv2.MORPH_CLOSE, kernel)

            return foreground_mask
        except:
            # GrabCut 失败时回退到简单方法
            return self.remove_white_background_color_aware(image)

    def remove_white_background_edge_priority(self, image: np.ndarray) -> np.ndarray:
        """
        边缘优先的前景提取
        先找边缘，再扩展为区域

        Args:
            image: 输入图片 (BGR)

        Returns:
            二值掩码，前景为255，背景为0
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 多尺度边缘检测
        edges_list = []

        # 不同参数的 Canny
        for low, high in [(20, 60), (40, 120), (60, 180)]:
            edges = cv2.Canny(gray, low, high)
            edges_list.append(edges)

        # 合并边缘
        combined_edges = np.zeros_like(gray)
        for edges in edges_list:
            combined_edges = cv2.bitwise_or(combined_edges, edges)

        # 扩展边缘为区域
        kernel_expand = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
        expanded = cv2.dilate(combined_edges, kernel_expand, iterations=3)

        # 结合灰度阈值
        gray_mask = (gray < self.white_threshold).astype(np.uint8) * 255

        # 合并
        final_mask = cv2.bitwise_or(expanded, gray_mask)

        # 形态学清理
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        final_mask = cv2.morphologyEx(final_mask, cv2.MORPH_OPEN, kernel)
        final_mask = cv2.morphologyEx(final_mask, cv2.MORPH_CLOSE, kernel)

        return final_mask

    def remove_white_background(self, image: np.ndarray) -> np.ndarray:
        """
        移除白色背景，生成掩码（根据模式选择方法）

        Args:
            image: 输入图片 (BGR)

        Returns:
            二值掩码，前景为255，背景为0
        """
        if self.mode == "color":
            return self.remove_white_background_color_aware(image)
        elif self.mode == "grabcut":
            return self.remove_white_background_grabcut(image)
        elif self.mode == "edge":
            return self.remove_white_background_edge_priority(image)
        else:  # auto
            # 自动模式：先尝试简单方法，如果效果不好则用复杂方法
            mask1 = self.remove_white_background_color_aware(image)

            # 检查前景像素比例
            fg_ratio = np.sum(mask1 > 0) / mask1.size

            if fg_ratio < 0.01:  # 前景太少，可能提取失败
                return self.remove_white_background_edge_priority(image)
            return mask1

    def extract_contours(self, image: np.ndarray) -> List[np.ndarray]:
        """
        从图片中提取轮廓

        Args:
            image: 输入图片 (BGR)

        Returns:
            轮廓点列表
        """
        # 移除白色背景获取前景
        foreground = self.remove_white_background(image)

        # 形态学操作去噪
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        foreground = cv2.morphologyEx(foreground, cv2.MORPH_CLOSE, kernel)

        # 使用自适应 Canny 边缘检测
        # 计算图像中前景区域的梯度
        sobelx = cv2.Sobel(foreground, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(foreground, cv2.CV_64F, 0, 1, ksize=3)
        gradient_magnitude = np.sqrt(sobelx**2 + sobely**2)
        gradient_magnitude = np.uint8(gradient_magnitude)

        # 自适应阈值
        mean_grad = np.mean(gradient_magnitude[foreground > 0])
        adaptive_low = max(10, int(mean_grad * 0.3))
        adaptive_high = max(50, int(mean_grad * 1.5))

        # 使用自适应参数的 Canny
        edges = cv2.Canny(foreground, adaptive_low, adaptive_high)

        # 查找轮廓
        contours, _ = cv2.findContours(edges,
                                      cv2.RETR_EXTERNAL,
                                      cv2.CHAIN_APPROX_SIMPLE)

        # 按面积排序，保留较大的轮廓
        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        # 过滤掉太小的轮廓
        min_area = image.shape[0] * image.shape[1] * 0.0005  # 降低最小面积阈值
        contours = [c for c in contours if cv2.contourArea(c) > min_area]

        return contours

    def smooth_contour(self, contour: np.ndarray,
                       epsilon_factor: float = 0.001) -> np.ndarray:
        """
        平滑轮廓，减少噪点

        Args:
            contour: 输入轮廓
            epsilon_factor: 近似精度因子，越小越精细

        Returns:
            平滑后的轮廓
        """
        if len(contour) < 3:
            return contour
        epsilon = epsilon_factor * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)
        return approx

    def offset_contours(self, contours: List[np.ndarray],
                       offset_distance: float) -> List[np.ndarray]:
        """
        偏移轮廓（向外或向内扩展/收缩）

        Args:
            contours: 输入轮廓列表
            offset_distance: 偏移距离（像素），正数向外，负数向内

        Returns:
            偏移后的轮廓列表
        """
        if abs(offset_distance) < 0.1:
            return contours

        offset_contours = []

        for contour in contours:
            if len(contour) < 3:
                offset_contours.append(contour)
                continue

            try:
                # 将 OpenCV 轮廓转换为点列表
                points = [(float(pt[0][0]), float(pt[0][1])) for pt in contour]

                # 创建多边形
                poly = Polygon(points)

                # 检查多边形是否有效
                if not poly.is_valid:
                    poly = poly.buffer(0)

                # 偏移多边形
                offset_poly = poly.buffer(offset_distance)

                # 提取偏移后的轮廓
                if offset_poly.is_empty:
                    # 偏移后可能消失了，返回原轮廓
                    offset_contours.append(contour)
                    continue

                # 处理 MultiPolygon 的情况
                if isinstance(offset_poly, MultiPolygon):
                    # 取最大的部分
                    largest = max(offset_poly.geoms, key=lambda g: g.area)
                    coords = list(largest.exterior.coords)
                else:
                    coords = list(offset_poly.exterior.coords)

                # 转换回 OpenCV 格式
                new_contour = np.array([[[int(x), int(y)]] for x, y in coords], dtype=np.int32)
                offset_contours.append(new_contour)

            except Exception:
                # 失败时返回原轮廓
                offset_contours.append(contour)

        return offset_contours

    def extract_outline(self, image_path: str,
                        smooth: bool = True,
                        simplify_factor: float = 0.001) -> Tuple[int, int, List[np.ndarray]]:
        """
        从白底图片提取描边

        Args:
            image_path: 图片路径
            smooth: 是否平滑轮廓
            simplify_factor: 轮廓简化因子

        Returns:
            (width, height, contours) 图片尺寸和轮廓列表
        """
        image = self.load_image(image_path)
        height, width = image.shape[:2]

        contours = self.extract_contours(image)

        if smooth:
            contours = [self.smooth_contour(c, simplify_factor) for c in contours]

        return width, height, contours

    def preview_outline(self, image_path: str,
                       output_path: Optional[str] = None) -> np.ndarray:
        """
        预览描边效果（返回或保存图片）

        Args:
            image_path: 输入图片路径
            output_path: 输出图片路径（可选）

        Returns:
            描边预览图片
        """
        image = self.load_image(image_path)
        width, height, contours = self.extract_outline(image_path)

        # 创建白色背景预览图
        preview = np.ones((height, width, 3), dtype=np.uint8) * 255

        # 绘制轮廓
        cv2.drawContours(preview, contours, -1, (0, 0, 0), 2)

        if output_path:
            cv2.imwrite(output_path, preview)

        return preview

    def debug_preview(self, image_path: str) -> dict:
        """
        调试预览，显示各个处理步骤

        Args:
            image_path: 输入图片路径

        Returns:
            包含各步骤图片的字典
        """
        image = self.load_image(image_path)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 不同方法的掩码
        mask_color = self.remove_white_background_color_aware(image)
        mask_edge = self.remove_white_background_edge_priority(image)

        return {
            "original": image,
            "gray": gray,
            "mask_color": mask_color,
            "mask_edge": mask_edge,
        }
