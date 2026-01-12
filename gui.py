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
        self.processed_contours = None  # 原始轮廓（未偏移）
        self.original_width = 0
        self.original_height = 0

        self.extractor = OutlineExtractor(mode="auto")
        self.generator = SVGGenerator()
        self.mode_var = tk.StringVar(value="auto")

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

        # 提取模式
        ttk.Label(params_frame, text="提取模式:").grid(row=0, column=0, padx=(0, 5), sticky=tk.W)
        mode_combo = ttk.Combobox(
            params_frame,
            textvariable=self.mode_var,
            values=["auto", "color", "edge", "grabcut"],
            state="readonly",
            width=10
        )
        mode_combo.grid(row=0, column=1, padx=5)
        mode_combo.bind("<<ComboboxSelected>>", lambda e: self._on_mode_change())

        # 模式说明
        self.mode_desc_var = tk.StringVar(value="自动选择最佳方法")
        mode_desc_label = ttk.Label(params_frame, textvariable=self.mode_desc_var, font=("", 9))
        mode_desc_label.grid(row=0, column=2, padx=(5, 15), sticky=tk.W)

        # 白色阈值
        ttk.Label(params_frame, text="白色阈值:").grid(row=0, column=3, padx=(0, 5), sticky=tk.W)
        self.threshold_var = tk.IntVar(value=230)
        threshold_scale = ttk.Scale(
            params_frame,
            from_=150, to=255,
            variable=self.threshold_var,
            command=lambda v: self.threshold_label.config(text=f"{int(float(v))}")
        )
        threshold_scale.grid(row=0, column=4, sticky=(tk.W, tk.E), padx=5)
        self.threshold_label = ttk.Label(params_frame, text="230", width=5)
        self.threshold_label.grid(row=0, column=5, padx=(0, 15))

        # 描边宽度
        ttk.Label(params_frame, text="描边宽度:").grid(row=0, column=6, padx=(0, 5), sticky=tk.W)
        self.stroke_width_var = tk.DoubleVar(value=2.0)
        stroke_scale = ttk.Scale(
            params_frame,
            from_=0.5, to=10.0,
            variable=self.stroke_width_var,
            command=lambda v: (self.stroke_label.config(text=f"{float(v):.1f}"), self._update_preview_stroke())
        )
        stroke_scale.grid(row=0, column=7, sticky=(tk.W, tk.E), padx=5)
        self.stroke_label = ttk.Label(params_frame, text="2.0", width=5)
        self.stroke_label.grid(row=0, column=8, padx=(0, 5))

        # 偏移距离（用于切割补偿）
        ttk.Label(params_frame, text="偏移距离:").grid(row=0, column=9, padx=(5, 5), sticky=tk.W)
        self.offset_var = tk.DoubleVar(value=0.0)
        offset_scale = ttk.Scale(
            params_frame,
            from_=-20.0, to=20.0,
            variable=self.offset_var,
            command=lambda v: (self.offset_label.config(text=f"{float(v):.1f}"), self._update_preview_offset())
        )
        offset_scale.grid(row=0, column=10, sticky=(tk.W, tk.E), padx=5)
        self.offset_label = ttk.Label(params_frame, text="0.0", width=5)
        self.offset_label.grid(row=0, column=11, padx=(0, 5))
        # 偏移说明
        ttk.Label(params_frame, text="(正值外扩, 负值内缩)", font=("", 8)).grid(row=0, column=12, padx=(0, 5))

        params_frame.columnconfigure(1, weight=1)
        params_frame.columnconfigure(4, weight=1)
        params_frame.columnconfigure(7, weight=1)
        params_frame.columnconfigure(10, weight=1)

        # 按钮面板
        button_frame = ttk.Frame(control_panel)
        button_frame.pack(side=tk.LEFT)

        self.process_btn = tk.Button(
            button_frame,
            text="开始处理",
            command=self._process_image,
            bg="#4CAF50",
            fg="white",
            font=("", 11, "bold"),
            width=12,
            state=tk.DISABLED,
            relief="raised",
            cursor="hand2"
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

        # 绑定拖放事件（支持 Windows/macOS/Linux）
        self._setup_drag_drop()

    def _setup_drag_drop(self):
        """设置拖放支持（Windows/macOS/Linux 通用）"""
        try:
            import tkinterdnd2 as tkdnd
            self.root.drop_target_register(tkdnd.DND_FILES)
            self.root.dnd_bind('<<Drop>>', self._on_drop)
            self.root.dnd_bind('<<DragEnter>>', self._on_drag_enter)
            self.root.dnd_bind('<<DragLeave>>', self._on_drag_leave)
        except ImportError:
            # 如果没有 tkinterdnd2，点击选择文件仍然可用
            pass

    def _on_drop(self, event):
        """处理拖放事件（支持 Windows/macOS/Linux 路径格式）"""
        files = self.root.tk.splitlist(event.data)
        if files:
            filepath = files[0]
            # Windows 可能返回 {file:///C:/path} 格式，需要处理
            if filepath.startswith('{') and filepath.endswith('}'):
                filepath = filepath[1:-1]
            if filepath.startswith('file:///'):
                filepath = filepath[8:]
            if filepath.startswith('file://'):
                filepath = filepath[7:]
            self._load_image(filepath)

    def _on_drag_enter(self, event):
        """拖入时高亮"""
        self.original_label.config(bg="#d0d0ff")

    def _on_drag_leave(self, event):
        """拖出时恢复"""
        self.original_label.config(bg="#f0f0f0")

    def _load_image(self, filepath):
        """加载并显示图片"""
        self.current_image_path = filepath
        self.status_var.set(f"已加载: {Path(filepath).name} - 点击「开始处理」按钮")

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

            # 清空右侧预览
            self.result_label.config(
                image="",
                text="点击「开始处理」按钮提取描边"
            )
            self.processed_contours = None

            # 启用处理按钮
            self.process_btn.config(state=tk.NORMAL, bg="#4CAF50")

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

    def _on_mode_change(self):
        """模式变化时"""
        mode = self.mode_var.get()
        descriptions = {
            "auto": "自动选择最佳方法",
            "color": "颜色感知模式 - 适合浅色头发/衣服",
            "edge": "边缘优先模式 - 适合线条清晰",
            "grabcut": "GrabCut算法 - 适合复杂场景"
        }
        self.mode_desc_var.set(descriptions.get(mode, ""))

    def _process_thread(self):
        """后台处理线程"""
        try:
            # 更新提取器参数
            self.extractor.mode = self.mode_var.get()
            self.extractor.white_threshold = self.threshold_var.get()

            # 提取轮廓
            width, height, contours = self.extractor.extract_outline(
                self.current_image_path,
                smooth=True
            )

            self.original_width = width
            self.original_height = height
            self.processed_contours = contours

            # 生成预览图（使用当前描边宽度）
            stroke_width = int(self.stroke_width_var.get())
            preview = np.ones((height, width, 3), dtype=np.uint8) * 255
            cv2.drawContours(preview, contours, -1, (0, 0, 0), stroke_width)

            # 在主线程更新 UI
            self.root.after(0, lambda: self._show_result(preview, contours))

        except Exception as e:
            self.root.after(0, lambda: self.status_var.set(f"处理失败: {e}"))
            self.root.after(0, lambda: self.process_btn.config(state=tk.NORMAL))

    def _show_result(self, preview_img, contours):
        """显示处理结果"""
        # 使用统一的渲染函数（应用偏移和描边宽度）
        self._render_preview()
        self.process_btn.config(state=tk.NORMAL)

    def _update_preview_stroke(self):
        """只更新描边宽度，不重新提取轮廓"""
        self._render_preview()

    def _update_preview_offset(self):
        """只更新偏移距离，不重新提取轮廓"""
        self._render_preview()

    def _render_preview(self):
        """渲染预览图（应用偏移和描边宽度）"""
        if not self.processed_contours:
            return

        # 应用偏移
        offset_distance = self.offset_var.get()
        contours = self.extractor.offset_contours(self.processed_contours, offset_distance)

        # 绘制预览
        stroke_width = int(self.stroke_width_var.get())
        preview = np.ones(
            (self.original_height, self.original_width, 3),
            dtype=np.uint8
        ) * 255
        cv2.drawContours(preview, contours, -1, (0, 0, 0), stroke_width)

        # 转换显示
        preview_rgb = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(preview_rgb)
        img.thumbnail((450, 450), Image.Resampling.LANCZOS)

        photo = ImageTk.PhotoImage(img)
        self.result_label.config(image=photo)
        self.result_label.image = photo

        # 更新状态
        offset_text = f"偏移 {offset_distance:.1f}px" if offset_distance != 0 else ""
        self.status_var.set(f"处理完成 - 找到 {len(self.processed_contours)} 个轮廓 {offset_text}")

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
                # 应用偏移
                offset_distance = self.offset_var.get()
                contours = self.extractor.offset_contours(self.processed_contours, offset_distance)

                self.generator.stroke_width = self.stroke_width_var.get()
                self.generator.generate(
                    contours,
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
                # 应用偏移
                offset_distance = self.offset_var.get()
                contours = self.extractor.offset_contours(self.processed_contours, offset_distance)

                preview = np.ones(
                    (self.original_height, self.original_width, 3),
                    dtype=np.uint8
                ) * 255
                cv2.drawContours(
                    preview,
                    contours,
                    -1,
                    (0, 0, 0),
                    int(self.stroke_width_var.get())
                )
                cv2.imwrite(filepath, preview)
                self.status_var.set(f"已保存: {Path(filepath).name}")
            except Exception as e:
                self.status_var.set(f"保存失败: {e}")


def main():
    # Windows/macOS/Linux 拖放支持需要使用 TkinterDnD
    try:
        from tkinterdnd2 import Tk as DnDTk
        root = DnDTk()
    except ImportError:
        root = tk.Tk()
    app = OutlineApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
