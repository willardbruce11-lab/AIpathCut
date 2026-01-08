# AIpathCut

让灵感随形而生

从白底图片中提取人物/动物轮廓，生成可缩放的 SVG 矢量图。适用于照片打印、切割机路径等应用场景。

## 功能特点

- 自动识别白色背景
- 提取人物/动物轮廓
- 生成 SVG 矢量图格式
- 支持单张或批量处理
- 可生成预览图
- 可调节描边参数

## 安装

```bash
pip install -r requirements.txt
```

### 依赖

- Python 3.8+
- OpenCV
- NumPy

## 使用方法

### GUI 界面（推荐）

```bash
python gui.py
```

### 命令行

```bash
python main.py input.jpg -o output.svg
```

### 批量处理

```bash
python main.py ./input_dir/ --batch -o ./output_dir/
```

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `input` | 输入图片路径或目录 | 必填 |
| `-o, --output` | 输出路径 | 与输入同目录 |
| `-t, --threshold` | 白色阈值 (0-255) | 230 |
| `--canny-low` | Canny 低阈值 | 50 |
| `--canny-high` | Canny 高阈值 | 150 |
| `-w, --stroke-width` | 描边宽度 | 2.0 |
| `-c, --color` | 描边颜色 | #000000 |
| `--no-smooth` | 禁用轮廓平滑 | - |
| `--no-preview` | 不生成预览图 | - |
| `--batch` | 批量处理模式 | - |

## 使用示例

```bash
# 基本提取
python main.py photo.jpg -o outline.svg

# 调整白色阈值（图片背景不是纯白时）
python main.py photo.jpg -o outline.svg -t 200

# 设置描边样式
python main.py photo.jpg -o outline.svg -w 3 -c "#FF0000"

# 批量处理
python main.py ./images/ --batch -o ./results/
```

## 输入要求

- 图片格式: JPG, PNG, BMP, TIFF, WEBP
- 背景要求: 白色或接近白色的背景
- 推荐分辨率: 500x500 以上

## 输出文件

- `.svg` - 矢量描边文件
- `.png` - 预览图（可选）

## 代码示例

```python
from outline_extractor import OutlineExtractor
from svg_generator import SVGGenerator

# 提取轮廓
extractor = OutlineExtractor()
width, height, contours = extractor.extract_outline("input.jpg")

# 生成 SVG
generator = SVGGenerator(stroke_width=2.0, stroke_color="#000000")
generator.generate(contours, width, height, "output.svg")
```

## 项目结构

```
AIpathCut/
├── main.py                 # 主程序入口
├── gui.py                  # GUI 界面
├── outline_extractor.py    # 描边提取模块
├── svg_generator.py        # SVG 生成模块
├── visualize.py            # 可视化调试工具
├── requirements.txt        # 依赖列表
├── README.md              # 使用说明
├── input/                 # 输入图片目录
└── output/                # 输出目录
```
