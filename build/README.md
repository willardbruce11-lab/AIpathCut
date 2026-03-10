# AIpathCut 打包说明

本目录包含 AIpathCut 的打包配置文件。

## 打包步骤

### 方法一：直接运行打包脚本（推荐）

```bash
# 1. 安装打包依赖
pip install -r ../requirements.txt

# 2. 运行打包脚本
python build/build.py
```

打包完成后，可执行文件位于 `dist/AIpathCut/` 目录。

### 方法二：手动使用 PyInstaller

```bash
# 1. 安装打包依赖
pip install pyinstaller

# 2. 运行 PyInstaller
pyinstaller build/build_spec.py
```

## 创建安装程序

如果需要创建 Windows 安装程序（.exe）：

1. 先完成上述打包步骤
2. 下载并安装 [NSIS](https://nsis.sourceforge.io/)
3. 运行以下命令创建安装程序：
   ```bash
   makensis build/build_nsis.nsi
   ```
4. 生成的安装程序：`AIpathCut_Setup_1.0.0.exe`

## 应用图标

将应用图标文件 `icon.ico` 放在 `resources/` 目录下。
推荐尺寸：256x256 像素。

## 分发

打包完成后，有两种分发方式：

1. **绿色版**：直接压缩 `dist/AIpathCut/` 文件夹，用户解压即可使用
2. **安装版**：使用 NSIS 生成的 `AIpathCut_Setup_1.0.0.exe`

## 注意事项

- 首次打包需要下载 PyInstaller 引导程序，可能需要几分钟
- 杀毒软件可能会误报，需要添加信任
- 打包后的程序不依赖 Python 环境
