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
import os
import subprocess
import time

from outline_extractor import OutlineExtractor
from svg_generator import SVGGenerator
from gcode_generator import GCodeGenerator


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
        self.last_gcode_path = None  # 记录上次保存的G-code文件路径

        self.extractor = OutlineExtractor(mode="grabcut")
        self.generator = SVGGenerator()
        self.gcode_gen = GCodeGenerator()

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
        params_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # ===== 第一行：白色阈值 + 偏移距离 =====
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
        self.threshold_label.grid(row=0, column=2, padx=(0, 20))

        # 偏移距离（用于切割补偿）
        ttk.Label(params_frame, text="偏移距离:").grid(row=0, column=3, padx=(0, 5), sticky=tk.W)
        self.offset_var = tk.DoubleVar(value=0.0)
        offset_scale = ttk.Scale(
            params_frame,
            from_=-20.0, to=20.0,
            variable=self.offset_var,
            command=lambda v: (self.offset_label.config(text=f"{float(v):.1f}"), self._update_preview_offset())
        )
        offset_scale.grid(row=0, column=4, sticky=(tk.W, tk.E), padx=5)
        self.offset_label = ttk.Label(params_frame, text="0.0", width=5)
        self.offset_label.grid(row=0, column=5, padx=(0, 5))
        # 偏移说明
        ttk.Label(params_frame, text="(正值外扩,负值内缩)", font=("", 8)).grid(row=0, column=6, sticky=tk.W)

        params_frame.columnconfigure(1, weight=1)
        params_frame.columnconfigure(4, weight=1)

        # ===== 第二行：G代码参数 =====
        # 加工宽度（X轴）
        ttk.Label(params_frame, text="加工宽:").grid(row=1, column=0, padx=(0, 5), sticky=tk.W, pady=(8, 0))
        self.target_width_var = tk.DoubleVar(value=200.0)
        target_width_entry = ttk.Entry(params_frame, textvariable=self.target_width_var, width=8)
        target_width_entry.grid(row=1, column=1, padx=2, pady=(8, 0), sticky=tk.W)
        ttk.Label(params_frame, text="mm", font=("", 9)).grid(row=1, column=2, padx=(0, 20), pady=(8, 0))

        # 加工高度（Y轴）
        ttk.Label(params_frame, text="加工高:").grid(row=1, column=3, padx=(0, 5), sticky=tk.W, pady=(8, 0))
        self.target_height_var = tk.DoubleVar(value=200.0)
        target_height_entry = ttk.Entry(params_frame, textvariable=self.target_height_var, width=8)
        target_height_entry.grid(row=1, column=4, padx=2, pady=(8, 0), sticky=tk.W)
        ttk.Label(params_frame, text="mm", font=("", 9)).grid(row=1, column=5, padx=(0, 5), pady=(8, 0))

        # 进给速度
        ttk.Label(params_frame, text="进给:").grid(row=1, column=6, padx=(0, 5), sticky=tk.W, pady=(8, 0))
        self.gcode_feed_var = tk.IntVar(value=1000)
        gcode_feed_entry = ttk.Entry(params_frame, textvariable=self.gcode_feed_var, width=8)
        gcode_feed_entry.grid(row=1, column=7, padx=2, pady=(8, 0), sticky=tk.W)
        ttk.Label(params_frame, text="mm/min", font=("", 9)).grid(row=1, column=8, padx=(0, 10), pady=(8, 0))
        # 等比说明
        tk.Label(params_frame, text="(等比缩放)", font=("", 8), fg="gray").grid(row=1, column=9, sticky=tk.W, pady=(8, 0))

        # ===== 第三行：UGS路径配置 =====
        ttk.Label(params_frame, text="UGS路径:").grid(row=2, column=0, padx=(0, 5), sticky=tk.W, pady=(8, 0))
        self.ugs_path_var = tk.StringVar(value="")
        ugs_path_entry = ttk.Entry(params_frame, textvariable=self.ugs_path_var)
        ugs_path_entry.grid(row=2, column=1, columnspan=8, sticky=(tk.W, tk.E), padx=2, pady=(8, 0))
        ttk.Button(params_frame, text="浏览...", width=8, command=self._browse_ugs_path).grid(row=2, column=9, padx=(5, 0), pady=(8, 0))

        # 按钮面板
        button_frame = ttk.Frame(control_panel)
        button_frame.pack(side=tk.LEFT)

        self.process_btn = tk.Button(
            button_frame,
            text="开始提取描边",
            command=self._process_image,
            bg="#4CAF50",
            fg="white",
            font=("", 12, "bold"),
            width=14,
            state=tk.DISABLED,
            relief="raised",
            cursor="hand2"
        )
        self.process_btn.pack(side=tk.LEFT, padx=5)

        self.gcode_btn = tk.Button(
            button_frame,
            text="生成刀路G代码",
            command=self._save_gcode,
            bg="#2196F3",
            fg="white",
            font=("", 12, "bold"),
            width=14,
            state=tk.DISABLED,
            relief="raised",
            cursor="hand2"
        )
        self.gcode_btn.pack(side=tk.LEFT, padx=5)

        self.cut_btn = tk.Button(
            button_frame,
            text="开始切割",
            command=self._start_cutting,
            bg="#FF5722",
            fg="white",
            font=("", 12, "bold"),
            width=14,
            state=tk.DISABLED,
            relief="raised",
            cursor="hand2"
        )
        self.cut_btn.pack(side=tk.LEFT, padx=5)

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
        self.status_var.set(f"已加载: {Path(filepath).name} - 点击「开始提取描边」按钮")

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
                text="点击「开始提取描边」按钮"
            )
            self.processed_contours = None

            # 启用处理按钮，禁用G代码和切割按钮
            self.process_btn.config(state=tk.NORMAL, bg="#4CAF50")
            self.gcode_btn.config(state=tk.DISABLED, bg="#cccccc")
            self.cut_btn.config(state=tk.DISABLED, bg="#cccccc")

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

            # 提取轮廓（使用grabcut模式）
            width, height, contours = self.extractor.extract_outline(
                self.current_image_path,
                smooth=True
            )

            self.original_width = width
            self.original_height = height
            self.processed_contours = contours

            # 生成预览图（固定描边宽度为1）
            preview = np.ones((height, width, 3), dtype=np.uint8) * 255
            cv2.drawContours(preview, contours, -1, (0, 0, 0), 1)

            # 在主线程更新 UI
            self.root.after(0, lambda: self._show_result(preview, contours))

        except Exception as e:
            self.root.after(0, lambda: self.status_var.set(f"处理失败: {e}"))
            self.root.after(0, lambda: self.process_btn.config(state=tk.NORMAL))

    def _show_result(self, preview_img, contours):
        """显示处理结果"""
        # 使用统一的渲染函数（应用偏移）
        self._render_preview()
        self.process_btn.config(state=tk.NORMAL, bg="#4CAF50")
        self.gcode_btn.config(state=tk.NORMAL, bg="#2196F3")
        self.cut_btn.config(state=tk.NORMAL, bg="#FF5722")

    def _update_preview_offset(self):
        """只更新偏移距离，不重新提取轮廓"""
        self._render_preview()

    def _render_preview(self):
        """渲染预览图（应用偏移）"""
        if not self.processed_contours:
            return

        # 应用偏移
        offset_distance = self.offset_var.get()
        contours = self.extractor.offset_contours(self.processed_contours, offset_distance)

        # 绘制预览（固定描边宽度为1）
        preview = np.ones(
            (self.original_height, self.original_width, 3),
            dtype=np.uint8
        ) * 255
        cv2.drawContours(preview, contours, -1, (0, 0, 0), 1)

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

                self.generator.stroke_width = 1.0  # 固定描边宽度
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
                    1  # 固定描边宽度
                )
                cv2.imwrite(filepath, preview)
                self.status_var.set(f"已保存: {Path(filepath).name}")
            except Exception as e:
                self.status_var.set(f"保存失败: {e}")

    def _save_gcode(self):
        """生成并保存 G 代码文件"""
        if not self.processed_contours:
            self.status_var.set("没有可保存的结果")
            return

        filepath = filedialog.asksaveasfilename(
            title="保存 G 代码",
            defaultextension=".gcode",
            filetypes=[
                ("G 代码文件", "*.gcode"),
                ("NC 文件", "*.nc"),
                ("所有文件", "*.*")
            ]
        )

        if filepath:
            try:
                # 获取G代码参数
                try:
                    target_width = float(self.target_width_var.get())
                    target_height = float(self.target_height_var.get())
                    feed_rate = int(self.gcode_feed_var.get())

                    # 验证参数
                    if target_width <= 0 or target_height <= 0:
                        self.status_var.set("参数错误: 目标尺寸必须大于0")
                        return
                except ValueError:
                    self.status_var.set("参数错误: 请输入有效的数字")
                    return

                # 应用偏移
                offset_distance = self.offset_var.get()
                contours = self.extractor.offset_contours(self.processed_contours, offset_distance)

                # 生成G代码（自动缩放到目标尺寸）
                self.gcode_gen.feed_rate = feed_rate
                self.gcode_gen.save_to_file(
                    contours,
                    filepath,
                    self.original_width,
                    self.original_height,
                    target_width,
                    target_height
                )
                self.status_var.set(f"已保存: {Path(filepath).name} (缩放到 {target_width}x{target_height}mm)")
                # 记录文件路径，供"开始切割"使用
                self.last_gcode_path = filepath
            except Exception as e:
                self.status_var.set(f"保存失败: {e}")

    def _browse_ugs_path(self):
        """浏览选择UGS可执行文件"""
        filepath = filedialog.askopenfilename(
            title="选择Universal Gcode Sender",
            filetypes=[
                ("可执行文件", "*.exe"),
                ("JAR文件", "*.jar"),
                ("快捷方式", "*.lnk"),
                ("所有文件", "*.*")
            ]
        )
        if filepath:
            self.ugs_path_var.set(filepath)

    def _close_ugs_process(self):
        """关闭已运行的UGS进程"""
        try:
            # 常见的UGS进程名
            ugs_process_names = [
                'UniversalGcodeSender.exe',
                'ugs-platform.exe',
                'UniversalGcodeSender',
                'java'  # JAR版本运行在java进程下
            ]

            for proc_name in ugs_process_names:
                try:
                    subprocess.run(['taskkill', '/F', '/IM', proc_name],
                                   shell=True, check=False,
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
                except Exception:
                    pass
        except Exception:
            pass

    def _start_cutting(self):
        """启动UGS并加载G-code"""
        if not self.processed_contours:
            self.status_var.set("没有可处理的轮廓")
            return

        # 确定要使用的G-code文件路径
        if self.last_gcode_path and os.path.exists(os.path.dirname(self.last_gcode_path)):
            # 使用上次保存的文件名
            gcode_path = self.last_gcode_path
        else:
            # 没有保存过，使用临时文件名
            gcode_path = "temp_cut.gcode"

        ugs_path = self.ugs_path_var.get().strip()
        if not ugs_path:
            self.status_var.set("请先配置UGS路径")
            return

        if not os.path.exists(ugs_path):
            self.status_var.set(f"UGS路径不存在: {ugs_path}")
            return

        try:
            # 获取参数并生成G-code（覆盖原有文件）
            target_width = float(self.target_width_var.get())
            target_height = float(self.target_height_var.get())
            feed_rate = int(self.gcode_feed_var.get())
            offset_distance = self.offset_var.get()

            contours = self.extractor.offset_contours(self.processed_contours, offset_distance)

            self.gcode_gen.feed_rate = feed_rate
            self.gcode_gen.save_to_file(
                contours, gcode_path,
                self.original_width, self.original_height,
                target_width, target_height
            )

            # 获取G-code文件的绝对路径
            gcode_abs_path = os.path.abspath(gcode_path)

            # 先关闭已运行的UGS进程
            self._close_ugs_process()
            # 等待进程完全关闭
            time.sleep(0.5)

            # 启动UGS并加载文件
            if ugs_path.lower().endswith('.jar'):
                # JAR版本
                subprocess.Popen(['java', '-jar', ugs_path, gcode_abs_path], shell=False)
                self.status_var.set(f"已启动UGS并加载: {Path(gcode_path).name}")
            elif ugs_path.lower().endswith('.lnk'):
                # 快捷方式 - 复制路径到剪贴板
                subprocess.run(['clip.exe'], input=gcode_abs_path, text=True, shell=True, check=False)
                os.startfile(ugs_path)
                self.status_var.set(f"UGS已启动，文件路径已复制到剪贴板，按Ctrl+V粘贴加载")
            else:
                # EXE版本 - 大多数UGS支持直接传文件路径作为参数
                subprocess.Popen([ugs_path, gcode_abs_path], shell=False)
                self.status_var.set(f"已启动UGS并加载: {Path(gcode_path).name}")

        except Exception as e:
            self.status_var.set(f"启动失败: {e}")


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
