"""
AIpathCut 安装配置
"""
from pathlib import Path
from setuptools import setup, find_packages

# 读取 README
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

setup(
    name="AIpathCut",
    version="1.0.0",
    author="AIpathCut Team",
    description="智能切割路径生成工具",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/willardbruce11-lab/AIpathCut",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Multimedia :: Graphics",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "opencv-python>=4.8.0",
        "numpy>=1.24.0",
        "Pillow>=10.0.0",
        "shapely>=2.0.0",
        "tkinterdnd2>=0.3.0",
    ],
    extras_require={
        "build": ["pyinstaller>=5.13.0"],
    },
    entry_points={
        "console_scripts": [
            "aipathcut=main:main",
        ],
    },
)
