"""
AIpathCut - 智能切割路径生成工具

核心功能：
- 描边提取：从白底图片中提取人物/动物轮廓
- SVG生成：生成可缩放的矢量图
- G-code生成：生成切割机专用G代码
- UV填充：生成逐行扫描填充路径
"""

__version__ = "1.0.0"
__author__ = "AIpathCut Team"

from aipathcut.core.outline_extractor import OutlineExtractor
from aipathcut.core.gcode_generator import GCodeGenerator
from aipathcut.core.fill_generator import FillGenerator
from aipathcut.core.svg_generator import SVGGenerator

__all__ = [
    "OutlineExtractor",
    "GCodeGenerator",
    "FillGenerator",
    "SVGGenerator",
]
