# AIpathCut

让灵感随形而生

从白底图片中提取人物/动物轮廓，生成切割机专用 G-code 路径。适用于切割刻字、UV 雕刻填充等场景，针对动漫人物轮廓提取进行了优化。

## 功能特点

- 自动识别白色背景，提取人物/动物轮廓
- 生成 SVG 矢量图、切割刀路 G-code、UV 填充 G-code
- 支持偏移补偿（刀具半径补偿）
- 自动等比缩放适配加工区域，支持自动旋转优化
- 集成 UGS (Universal Gcode Sender) 一键发送
- 支持 XZ 轴交换（适配特殊机械结构）
- 支持单张或批量命令行处理
- 附带 ESP32 Z 轴电机控制代码

## 安装

```bash
pip install -r requirements.txt
```

### 依赖

- Python 3.8+
- OpenCV (`opencv-python`)
- NumPy
- Pillow
- Shapely
- tkinterdnd2（拖拽支持，可选）

## 使用方法

### GUI 界面（推荐）

```bash
python main.py --gui
```

或双击 `启动描边工具.bat`（Windows）/ `启动描边工具.command`（macOS）。

操作流程：
1. 拖入或点击选择白底图片
2. 点击 **提取描边** → 预览轮廓
3. 调整偏移距离（刀具补偿）
4. 点击 **刀路G代码** → 生成切割 G-code
5. 点击 **填充G代码** → 生成 UV 扫描填充 G-code
6. 点击 **开始切割** / **开始填充** → 自动启动 UGS 并发送

### 命令行

```bash
# 基本提取（生成 SVG）
python main.py input.jpg -o output.svg

# 调整白色阈值
python main.py input.jpg -o output.svg -t 200

# 设置描边样式
python main.py input.jpg -o output.svg -w 3 -c "#FF0000"

# 批量处理
python main.py ./input_dir/ --batch -o ./output_dir/
```

## 参数说明

### 命令行参数

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
| `--gui` | 启动图形界面 | - |

### GUI 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 白色阈值 | 230 | 越大对白色要求越严格 |
| 偏移距离 | 0.0 px | 刀具补偿，正值外扩，负值内缩 |
| 加工宽 | 50 mm | 目标加工宽度 |
| 加工高 | 76 mm | 目标加工高度 |
| 进给速度 | 100 mm/min | 切割/填充速度 |
| 填充间隔 | 5.0 mm | UV 扫描线间距 |
| Y偏移 | 5.0 mm | 填充 Y 方向偏移 |
| Z深度 | -2.0 mm | UV 雕刻深度 |
| XZ轴交换 | 关闭 | 交换 X 和 Z 轴映射 |

## 输入要求

- 图片格式: JPG, PNG, BMP, TIFF, WEBP
- 背景要求: 白色或接近白色的背景（针对动漫人物优化）
- 推荐分辨率: 500x500 以上

## 输出文件

- `.svg` - 矢量描边文件
- `.gcode` - 切割刀路 G-code
- `*_fill.gcode` - UV 填充 G-code
- `.png` - 预览图（可选）

## 代码示例

```python
from aipathcut.core.outline_extractor import OutlineExtractor
from aipathcut.core.svg_generator import SVGGenerator
from aipathcut.core.gcode_generator import GCodeGenerator
from aipathcut.core.fill_generator import FillGenerator

# 提取轮廓
extractor = OutlineExtractor()
width, height, contours = extractor.extract_outline("input.jpg")

# 生成 SVG
svg_gen = SVGGenerator(stroke_width=1.0, stroke_color="#000000")
svg_gen.generate(contours, width, height, "output.svg")

# 生成切割 G-code
gcode_gen = GCodeGenerator(feed_rate=100)
gcode_gen.save_to_file(contours, "cut.gcode", width, height, 50, 76)

# 生成填充 G-code（共享切割坐标变换）
fill_gen = FillGenerator(feed_rate=100)
fill_gen.set_transform_params(gcode_gen.get_transform_params())
fill_gen.save_to_file(contours, "fill.gcode", fill_interval=5.0,
                      y_offset=5.0, z_depth=-2.0)
```

## 项目结构

```
AIpathCut/
├── main.py                              # 主程序入口（CLI + GUI 启动）
├── aipathcut/
│   ├── gui.py                           # GUI 界面（tkinter）
│   └── core/
│       ├── outline_extractor.py         # 轮廓提取核心
│       ├── svg_generator.py             # SVG 矢量图输出
│       ├── gcode_generator.py           # 切割刀路 G-code 生成
│       ├── fill_generator.py            # UV 扫描填充 G-code 生成
│       ├── transform_utils.py           # 坐标变换工具
│       └── toolpath_pipeline.py         # 共享刀路管线
├── ESP32_code/
│   └── z_axis_motor_control/            # ESP32 Z 轴电机控制
├── build/                               # 打包配置
├── visualize.py                         # 可视化调试工具
├── requirements.txt                     # 依赖列表
├── setup.py                             # 安装配置
├── pyproject.toml                       # 项目元数据
├── 启动描边工具.bat                      # Windows 启动脚本
├── 启动描边工具.command                  # macOS 启动脚本
├── 操作指南.md                          # 详细操作指南
├── README.md                            # 本文件
├── input/                               # 输入图片目录
└── output/                              # 输出目录
```

## UGS 配置

使用「开始切割」或「开始填充」功能需配置 Universal Gcode Sender 路径：
- 支持 `.exe`、`.jar`、`.lnk` 文件
- 下载地址: https://winder.github.io/ugs_website/

## 许可证

MIT License
