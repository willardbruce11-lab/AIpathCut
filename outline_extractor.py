"""
描边提取模块
从白底图片中提取人物/动物的轮廓
"""
import cv2
import numpy as np
from typing import Tuple, List, Optional


class OutlineExtractor:
    """白底图片描边提取器"""

    def __init__(self,
                 white_threshold: int = 230,
                 blur_kernel: int = 5,
                 canny_threshold1: int = 50,
                 canny_threshold2: int = 150):
        """
        初始化提取器

        Args:
            white_threshold: 白色背景的阈值（0-255）
            blur_kernel: 高斯模糊核大小
            canny_threshold1: Canny 边缘检测低阈值
            canny_threshold2: Canny 边缘检测高阈值
        """
        self.white_threshold = white_threshold
        self.blur_kernel = blur_kernel
        self.canny_threshold1 = canny_threshold1
        self.canny_threshold2 = canny_threshold2

    def load_image(self, image_path: str) -> np.ndarray:
        """加载图片"""
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"无法加载图片: {image_path}")
        return image

    def remove_white_background(self, image: np.ndarray) -> np.ndarray:
        """
        移除白色背景，生成掩码

        Args:
            image: 输入图片 (BGR)

        Returns:
            二值掩码，前景为255，背景为0
        """
        # 转换为灰度图
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 创建白色背景掩码（接近白色的像素）
        white_mask = gray > self.white_threshold

        # 反转得到前景掩码
        foreground_mask = (~white_mask).astype(np.uint8) * 255

        return foreground_mask

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
        foreground = cv2.morphologyEx(foreground, cv2.MORPH_OPEN, kernel)

        # 使用 Canny 边缘检测
        edges = cv2.Canny(foreground,
                         self.canny_threshold1,
                         self.canny_threshold2)

        # 查找轮廓
        contours, _ = cv2.findContours(edges,
                                      cv2.RETR_EXTERNAL,
                                      cv2.CHAIN_APPROX_SIMPLE)

        # 按面积排序，保留较大的轮廓
        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        # 过滤掉太小的轮廓
        min_area = image.shape[0] * image.shape[1] * 0.001
        contours = [c for c in contours if cv2.contourArea(c) > min_area]

        return contours

    def smooth_contour(self, contour: np.ndarray,
                       epsilon_factor: float = 0.002) -> np.ndarray:
        """
        平滑轮廓，减少噪点

        Args:
            contour: 输入轮廓
            epsilon_factor: 近似精度因子，越小越精细

        Returns:
            平滑后的轮廓
        """
        epsilon = epsilon_factor * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)
        return approx

    def extract_outline(self, image_path: str,
                        smooth: bool = True,
                        simplify_factor: float = 0.002) -> Tuple[int, int, List[np.ndarray]]:
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
