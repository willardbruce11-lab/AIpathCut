#!/usr/bin/env python3
"""
主程序入口
从白底图片提取人物/动物描边并生成 SVG 矢量图
"""
import argparse
from pathlib import Path
from outline_extractor import OutlineExtractor
from svg_generator import SVGGenerator


def process_image(input_path: str,
                  output_path: str,
                  white_threshold: int = 230,
                  canny_low: int = 50,
                  canny_high: int = 150,
                  stroke_width: float = 2.0,
                  stroke_color: str = "#000000",
                  smooth: bool = True,
                  preview: bool = True) -> None:
    """
    处理图片并生成 SVG 描边

    Args:
        input_path: 输入图片路径
        output_path: 输出 SVG 路径
        white_threshold: 白色阈值
        canny_low: Canny 边缘检测低阈值
        canny_high: Canny 边缘检测高阈值
        stroke_width: 描边宽度
        stroke_color: 描边颜色
        smooth: 是否平滑轮廓
        preview: 是否生成预览图
    """
    print(f"处理图片: {input_path}")

    # 初始化提取器
    extractor = OutlineExtractor(
        white_threshold=white_threshold,
        canny_threshold1=canny_low,
        canny_threshold2=canny_high
    )

    # 提取轮廓
    print("提取轮廓中...")
    width, height, contours = extractor.extract_outline(
        input_path,
        smooth=smooth,
        simplify_factor=0.002
    )

    print(f"找到 {len(contours)} 个轮廓")

    if len(contours) == 0:
        print("警告: 未找到任何轮廓，请检查图片是否为白底")
        return

    # 生成预览图
    if preview:
        preview_path = Path(output_path).with_suffix('.png')
        print(f"生成预览图: {preview_path}")
        extractor.preview_outline(input_path, str(preview_path))

    # 生成 SVG
    print(f"生成 SVG: {output_path}")
    generator = SVGGenerator(
        stroke_color=stroke_color,
        stroke_width=stroke_width,
        fill="none"
    )
    generator.generate(contours, width, height, output_path)

    print("完成!")


def batch_process(input_dir: str,
                 output_dir: str,
                 **kwargs) -> None:
    """
    批量处理目录中的图片

    Args:
        input_dir: 输入目录
        output_dir: 输出目录
        **kwargs: 其他参数
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)

    output_path.mkdir(parents=True, exist_ok=True)

    # 支持的图片格式
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}

    image_files = [f for f in input_path.iterdir()
                   if f.suffix.lower() in image_extensions]

    if not image_files:
        print(f"在 {input_dir} 中未找到图片文件")
        return

    print(f"找到 {len(image_files)} 张图片")

    for i, image_file in enumerate(image_files, 1):
        print(f"\n[{i}/{len(image_files)}] 处理: {image_file.name}")
        output_file = output_path / f"{image_file.stem}.svg"

        try:
            process_image(
                str(image_file),
                str(output_file),
                preview=kwargs.get('preview', True),
                **{k: v for k, v in kwargs.items() if k != 'preview'}
            )
        except Exception as e:
            print(f"处理失败: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='从白底图片提取人物/动物描边并生成 SVG 矢量图'
    )

    parser.add_argument(
        'input',
        help='输入图片路径或目录'
    )

    parser.add_argument(
        '-o', '--output',
        help='输出 SVG 文件路径或目录（默认与输入同目录）'
    )

    parser.add_argument(
        '-t', '--threshold',
        type=int,
        default=230,
        help='白色背景阈值 (0-255, 默认: 230)'
    )

    parser.add_argument(
        '--canny-low',
        type=int,
        default=50,
        help='Canny 边缘检测低阈值 (默认: 50)'
    )

    parser.add_argument(
        '--canny-high',
        type=int,
        default=150,
        help='Canny 边缘检测高阈值 (默认: 150)'
    )

    parser.add_argument(
        '-w', '--stroke-width',
        type=float,
        default=2.0,
        help='描边宽度 (默认: 2.0)'
    )

    parser.add_argument(
        '-c', '--color',
        default='#000000',
        help='描边颜色 (默认: #000000)'
    )

    parser.add_argument(
        '--no-smooth',
        action='store_true',
        help='禁用轮廓平滑'
    )

    parser.add_argument(
        '--no-preview',
        action='store_true',
        help='不生成预览图'
    )

    parser.add_argument(
        '--batch',
        action='store_true',
        help='批量处理模式（输入为目录）'
    )

    args = parser.parse_args()

    # 确定输出路径
    if args.output:
        output_path = args.output
    else:
        input_path = Path(args.input)
        if input_path.is_dir():
            output_path = str(input_path / 'output')
        else:
            output_path = str(input_path.with_suffix('.svg'))

    # 处理
    if args.batch or Path(args.input).is_dir():
        batch_process(
            args.input,
            output_path,
            white_threshold=args.threshold,
            canny_low=args.canny_low,
            canny_high=args.canny_high,
            stroke_width=args.stroke_width,
            stroke_color=args.color,
            smooth=not args.no_smooth,
            preview=not args.no_preview
        )
    else:
        process_image(
            args.input,
            output_path,
            white_threshold=args.threshold,
            canny_low=args.canny_low,
            canny_high=args.canny_high,
            stroke_width=args.stroke_width,
            stroke_color=args.color,
            smooth=not args.no_smooth,
            preview=not args.no_preview
        )


if __name__ == '__main__':
    main()
