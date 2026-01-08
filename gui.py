#!/usr/bin/env python3
"""
可视化 GUI 界面
支持拖拽图片，显示原图和处理结果
"""
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
from PIL import Image, ImageTk
import cv2
import numpy as np
from pathlib import Path
import threading

from outline_extractor import OutlineExtractor
from svg_generator import SVGGenerator


class ImageDropLabel(tk.Label):
    """支持拖拽的图片标签"""

    def __init__(self, master, drop_callback=None, **kwargs):
        super().__init__(master, **kwargs)
        self.drop_callback = drop_callback

        # 绑定拖拽事件
        self.bind('<Button-1>', self._on_click)
        self.bind('<Button-3>', self._on_click)  # 右键也可以

    def _on_click(self, event):
        if self.drop_callback:
            filepath = filedialog.askopenfilename(
                title="选择图片",
                filetypes=[
                    ("图片文件", "*.jpg *.jpeg *.png *.bmp *.tiff *.webp"),
                    ("所有文件", "*.*")
                ]
            )
            if filepath:
                self.drop_callback(filepath)


class OutlineApp:
    """描边提取 GUI 应用"""

    def __init__(self, root):
        self.root = root
        self.root.title("描边提取工具")
        self.root.geometry("1200x700")

        self.current_image_path = None
        self.processed_contours = None
        self.original_width = 0
        self.original_height = 0

        self.extractor = OutlineExtractor()
        self.generator = SVGGenerator()

        self._setup_ui()

    def _setup_ui(self):
        """设置界面"""
        # 主容器
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 配置行列权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # 标题
        title_label = ttk.Label(
            main_frame,
            text="描边提取工具 - 拖入白底图片或点击选择",
            font=("", 16, "bold")
        )
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 15))

        # 左侧面板 - 原图
        left_panel = ttk.LabelFrame(main_frame, text="原图", padding="10")
        left_panel.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(0, weight=1)

        self.original_label = ImageDropLabel(
            left_panel,
            drop_callback=self._load_image,
            bg="#f0f0f0",
            width=50,
            height=20,
            text="点击或拖入图片",
            font=("", 12),
            relief="ridge",
            borderwidth=2
        )
        self.original_label.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 右侧面板 - 结果
        right_panel = ttk.LabelFrame(main_frame, text="描边结果", padding="10")
        right_panel.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(0, weight=1)

        self.result_label = tk.Label(
            right_panel,
            bg="#f0f0f0",
            width=50,
            height=20,
            text="等待处理...",
            font=("", 12),
            relief="sunken",
            borderwidth=1
        )
        self.result_label.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 底部控制面板
        control_panel = ttk.Frame(main_frame)
        control_panel.grid(row=2, column=0, columnspan=3, pady=(15, 0))

        # 参数控制
        params_frame = ttk.LabelFrame(control_panel, text="参数设置", padding="10")
        params_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        # 白色阈值
        ttk.Label(params_frame, text="白色阈值:").grid(row=0, column=0, padx=(0, 5), sticky=tk.W)
        self.threshold_var = tk.IntVar(value=230)
        threshold_scale = ttk.Scale(
            params_frame,
            from_=150, to=255,
            variable=self.threshold_var,
            command=lambda v: self.threshold_label.config(text=f"{int(float(v))}")
        )
        threshold_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        self.threshold_label = ttk.Label(params_frame, text="230", width=5)
        self.threshold_label.grid(row=0, column=2, padx=(0, 15))

        # 描边宽度
        ttk.Label(params_frame, text="描边宽度:").grid(row=0, column=3, padx=(0, 5), sticky=tk.W)
        self.stroke_width_var = tk.DoubleVar(value=2.0)
        stroke_scale = ttk.Scale(
            params_frame,
            from_=0.5, to=10.0,
            variable=self.stroke_width_var,
            command=lambda v: self.stroke_label.config(text=f"{float(v):.1f}")
        )
        stroke_scale.grid(row=0, column=4, sticky=(tk.W, tk.E), padx=5)
        self.stroke_label = ttk.Label(params_frame, text="2.0", width=5)
        self.stroke_label.grid(row=0, column=5, padx=(0, 15))

        params_frame.columnconfigure(1, weight=1)
        params_frame.columnconfigure(4, weight=1)

        # 按钮面板
        button_frame = ttk.Frame(control_panel)
        button_frame.pack(side=tk.LEFT)

        self.process_btn = ttk.Button(
            button_frame,
            text="重新处理",
            command=self._reprocess,
            state=tk.DISABLED
        )
        self.process_btn.pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="保存 SVG",
            command=self._save_svg
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="保存预览图",
            command=self._save_preview
        ).pack(side=tk.LEFT, padx=5)

        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(
            main_frame,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W
        )
        status_bar.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))

        # 绑定拖放事件（macOS 支持）
        self._setup_drag_drop()

    def _setup_drag_drop(self):
        """设置拖放支持"""
        try:
            # macOS 拖放支持
            from AppKit import NSPasteboard
            import tkinterdnd2 as tkdnd
            self.root.drop_target_register(tkdnd.DND_FILES)
            self.root.dnd_bind('<<Drop>>', self._on_drop)
            self.root.dnd_bind('<<DragEnter>>', self._on_drag_enter)
            self.root.dnd_bind('<<DragLeave>>', self._on_drag_leave)
        except ImportError:
            # 如果没有 tkinterdnd2，使用备用方案
            pass

    def _on_drop(self, event):
        """处理拖放事件"""
        files = self.root.tk.splitlist(event.data)
        if files:
            self._load_image(files[0])

    def _on_drag_enter(self, event):
        """拖入时高亮"""
        self.original_label.config(bg="#d0d0ff")

    def _on_drag_leave(self, event):
        """拖出时恢复"""
        self.original_label.config(bg="#f0f0f0")

    def _load_image(self, filepath):
        """加载并显示图片"""
        self.current_image_path = filepath
        self.status_var.set(f"加载: {Path(filepath).name}")

        try:
            # 读取图片
            img = Image.open(filepath)
            img.thumbnail((450, 450), Image.Resampling.LANCZOS)

            # 显示原图
            photo = ImageTk.PhotoImage(img)
            self.original_label.config(
                image=photo,
                text="",
                relief="sunken"
            )
            self.original_label.image = photo

            # 自动处理
            self._process_image()

        except Exception as e:
            self.status_var.set(f"加载失败: {e}")

    def _process_image(self):
        """处理图片"""
        if not self.current_image_path:
            return

        self.status_var.set("正在处理...")
        self.process_btn.config(state=tk.DISABLED)

        # 在后台线程处理
        thread = threading.Thread(target=self._process_thread)
        thread.daemon = True
        thread.start()

    def _process_thread(self):
        """后台处理线程"""
        try:
            # 更新提取器参数
            self.extractor.white_threshold = self.threshold_var.get()

            # 提取轮廓
            width, height, contours = self.extractor.extract_outline(
                self.current_image_path,
                smooth=True
            )

            self.original_width = width
            self.original_height = height
            self.processed_contours = contours

            # 生成预览图
            preview = np.ones((height, width, 3), dtype=np.uint8) * 255
            cv2.drawContours(preview, contours, -1, (0, 0, 0), 2)

            # 在主线程更新 UI
            self.root.after(0, lambda: self._show_result(preview, contours))

        except Exception as e:
            self.root.after(0, lambda: self.status_var.set(f"处理失败: {e}"))
            self.root.after(0, lambda: self.process_btn.config(state=tk.NORMAL))

    def _show_result(self, preview_img, contours):
        """显示处理结果"""
        # 转换预览图
        preview_rgb = cv2.cvtColor(preview_img, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(preview_rgb)
        img.thumbnail((450, 450), Image.Resampling.LANCZOS)

        photo = ImageTk.PhotoImage(img)
        self.result_label.config(
            image=photo,
            text=""
        )
        self.result_label.image = photo

        self.status_var.set(f"处理完成 - 找到 {len(contours)} 个轮廓")
        self.process_btn.config(state=tk.NORMAL)

    def _reprocess(self):
        """使用新参数重新处理"""
        self._process_image()

    def _save_svg(self):
        """保存 SVG 文件"""
        if not self.processed_contours:
            self.status_var.set("没有可保存的结果")
            return

        filepath = filedialog.asksaveasfilename(
            title="保存 SVG",
            defaultextension=".svg",
            filetypes=[("SVG 文件", "*.svg"), ("所有文件", "*.*")]
        )

        if filepath:
            try:
                self.generator.stroke_width = self.stroke_width_var.get()
                self.generator.generate(
                    self.processed_contours,
                    self.original_width,
                    self.original_height,
                    filepath
                )
                self.status_var.set(f"已保存: {Path(filepath).name}")
            except Exception as e:
                self.status_var.set(f"保存失败: {e}")

    def _save_preview(self):
        """保存预览图"""
        if not self.processed_contours:
            self.status_var.set("没有可保存的结果")
            return

        filepath = filedialog.asksaveasfilename(
            title="保存预览图",
            defaultextension=".png",
            filetypes=[("PNG 图片", "*.png"), ("所有文件", "*.*")]
        )

        if filepath:
            try:
                preview = np.ones(
                    (self.original_height, self.original_width, 3),
                    dtype=np.uint8
                ) * 255
                cv2.drawContours(
                    preview,
                    self.processed_contours,
                    -1,
                    (0, 0, 0),
                    int(self.stroke_width_var.get())
                )
                cv2.imwrite(filepath, preview)
                self.status_var.set(f"已保存: {Path(filepath).name}")
            except Exception as e:
                self.status_var.set(f"保存失败: {e}")


def main():
    root = tk.Tk()
    app = OutlineApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
