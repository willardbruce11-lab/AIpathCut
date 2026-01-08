#!/usr/bin/env python3
"""
可视化工具
显示提取的轮廓预览
"""
import cv2
import numpy as np
from outline_extractor import OutlineExtractor
from pathlib import Path


def visualize_extraction(image_path: str) -> None:
    """
    可视化提取过程

    Args:
        image_path: 图片路径
    """
    extractor = OutlineExtractor()
    image = extractor.load_image(image_path)
    height, width = image.shape[:2]

    print(f"图片尺寸: {width} x {height}")

    # 1. 原图
    print("\n1. 原图")
    cv2.imshow("Original", cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

    # 2. 移除白色背景后的掩码
    print("2. 前景掩码")
    foreground = extractor.remove_white_background(image)
    cv2.imshow("Foreground Mask", foreground)

    # 3. 边缘检测结果
    print("3. 边缘检测")
    edges = cv2.Canny(foreground, 50, 150)
    cv2.imshow("Edges", edges)

    # 4. 最终轮廓
    print("4. 提取的轮廓")
    contours = extractor.extract_contours(image)
    preview = np.ones((height, width, 3), dtype=np.uint8) * 255
    cv2.drawContours(preview, contours, -1, (0, 0, 0), 2)
    cv2.imshow("Outline Preview", cv2.cvtColor(preview, cv2.COLOR_BGR2RGB))

    # 5. 叠加显示
    print("5. 叠加显示")
    overlay = image.copy()
    cv2.drawContours(overlay, contours, -1, (0, 255, 0), 2)
    cv2.imshow("Overlay", cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB))

    print("\n按任意键关闭窗口...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


def main():
    import argparse

    parser = argparse.ArgumentParser(description='可视化描边提取过程')
    parser.add_argument('input', help='输入图片路径')

    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"文件不存在: {args.input}")
        return

    visualize_extraction(args.input)


if __name__ == '__main__':
    main()
