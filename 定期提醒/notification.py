import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import threading
import time
import random
import json
import csv
import os
import sys
from datetime import datetime

try:
    import pygame
    from plyer import notification
    import pystray  # 导入 pystray
    from pystray import MenuItem as item, Menu as menu
    from PIL import Image, ImageTk  # 导入 Pillow (PIL)

    PYGAME_LOADED = True
    PLYER_LOADED = True
    PYSTRAY_LOADED = True
except ImportError:
    print("错误：缺少必要的库。请运行 'pip install ttkbootstrap pygame plyer pystray pillow'")
    PYGAME_LOADED = False
    PLYER_LOADED = False
    PYSTRAY_LOADED = False

# --- 常量定义 ---
SETTINGS_FILE = "focus_settings.json"
LOG_FILE = "focus_log.csv"

# 获取脚本所在的目录，确保配置文件和日志文件在同一位置
if getattr(sys, 'frozen', False):
    # 如果是打包后的 .exe 文件
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    # 如果是 .py 脚本
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

SETTINGS_PATH = os.path.join(SCRIPT_DIR, SETTINGS_FILE)
LOG_PATH = os.path.join(SCRIPT_DIR, LOG_FILE)


# --- 计时器线程 ---
class TimerThread(threading.Thread):
    """
    在后台运行的独立计时器线程，以防止GUI冻结。
    """

    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance
        self.daemon = True  # 设置为守护线程，主程序退出时自动退出
        self._is_running = True
        self._is_paused = False

        # 从主程序获取配置
        self.config = self.app.settings
        self.total_duration = int(self.config["total_minutes"]) * 60
        self.rest_duration = int(self.config["rest_seconds"])
        self.min_work_sec = int(self.config["min_work_minutes"]) * 60
        self.max_work_sec = int(self.config["max_work_minutes"]) * 60

        # 初始化状态
        self.total_time_left = self.total_duration
        self.current_phase = "WORK"  # "WORK" 或 "REST"
        self.interval_time_left = self.get_random_work_interval()

        self.app.rest_count = 0

    def get_random_work_interval(self):
        """在设定的范围内获取一个随机的工作时间（秒）"""
        return random.randint(self.min_work_sec, self.max_work_sec)

    def run(self):
        """线程主循环"""
        while self.total_time_left > 0 and self._is_running:
            if not self._is_paused:
                # 1. 更新计时器
                self.total_time_left -= 1
                self.interval_time_left -= 1

                # 2. 更新GUI (必须通过 .after() 在主线程中更新)
                self.app.after(0, self.app.update_gui_labels,
                               self.total_time_left,
                               self.interval_time_left,
                               self.current_phase)

                # 3. 检查间隔是否结束
                if self.interval_time_left <= 0:
                    if self.current_phase == "WORK":
                        # 工作结束，开始休息
                        self.current_phase = "REST"
                        self.interval_time_left = self.rest_duration
                        self.app.rest_count += 1
                        self.app.play_sound("sound1_path")
                        # --- 【已修改】指定通知类型为 "interval" ---
                        self.app.send_notification("该休息啦！", f"请休息 {self.rest_duration} 秒钟。",
                                                   notification_type="interval")

                    elif self.current_phase == "REST":
                        # 休息结束，开始工作
                        self.current_phase = "WORK"
                        self.interval_time_left = self.get_random_work_interval()
                        self.app.play_sound("sound2_path")
                        # --- 【已修改】指定通知类型为 "interval" ---
                        self.app.send_notification("休息结束", "新一轮工作开始！", notification_type="interval")

                # 4. 睡眠1秒
                time.sleep(1)
            else:
                # 暂停时，短暂休眠以降低CPU占用
                time.sleep(0.1)

        # 5. 循环结束（时间到或被停止）
        if self._is_running:
            # 只有在时间正常走完时才调用
            self.app.after(0, self.app.stop_session, True)  # True 表示已完成

    def pause(self):
        self._is_paused = True

    def resume(self):
        self._is_paused = False

    def stop(self):
        self._is_running = False


# --- 设置窗口 ---
class SettingsDialog(tk.Toplevel):
    """
    用于配置时间和声音的弹出窗口。
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.config = parent.settings.copy()  # 使用父窗口的设置副本

        self.title("设置")
        self.geometry(f"{self.config['settings_width']}x{self.config['settings_height']}")
        self.transient(parent)
        self.grab_set()

        container = ttk.Frame(self, padding=15)
        container.pack(fill=BOTH, expand=YES)

        # --- 时间设置 ---
        time_frame = ttk.LabelFrame(container, text="时间设置", padding=10)
        time_frame.pack(fill=X, pady=5)

        self.add_setting_entry(time_frame, "总专注时长 (分钟):", "total_minutes")
        self.add_setting_entry(time_frame, "最短工作间隔 (分钟):", "min_work_minutes")
        self.add_setting_entry(time_frame, "最长工作间隔 (分钟):", "max_work_minutes")
        self.add_setting_entry(time_frame, "休息时长 (秒):", "rest_seconds")

        # --- 声音设置 ---
        sound_frame = ttk.LabelFrame(container, text="声音设置", padding=10)
        sound_frame.pack(fill=X, pady=5)

        self.sound1_var = tk.StringVar(value=self.config.get("sound1_path", ""))
        self.sound2_var = tk.StringVar(value=self.config.get("sound2_path", ""))
        # --- 【已添加】会话结束提示音 ---
        self.sound3_var = tk.StringVar(value=self.config.get("sound3_path", ""))

        self.add_sound_picker(sound_frame, "提示音1 (休息提醒):", self.sound1_var, "sound1_path")
        self.add_sound_picker(sound_frame, "提示音2 (工作提醒):", self.sound2_var, "sound2_path")
        # --- 【已添加】会话结束提示音UI ---
        self.add_sound_picker(sound_frame, "提示音3 (会话结束):", self.sound3_var, "sound3_path")

        # --- 其他设置 ---
        other_frame = ttk.LabelFrame(container, text="通知设置", padding=10)
        other_frame.pack(fill=X, pady=5)

        # --- 【已修改】分为两个开关 ---
        self.show_interval_notifications_var = tk.BooleanVar(
            value=self.config.get("show_interval_notifications", True)
        )
        ttk.Checkbutton(
            other_frame,
            text="显示 (工作/休息) 间隔通知",
            variable=self.show_interval_notifications_var,
            bootstyle="primary-round-toggle"
        ).pack(side=LEFT, padx=5)

        self.show_session_end_notification_var = tk.BooleanVar(
            value=self.config.get("show_session_end_notification", True)
        )
        ttk.Checkbutton(
            other_frame,
            text="显示 (总时长) 结束通知",
            variable=self.show_session_end_notification_var,
            bootstyle="primary-round-toggle"
        ).pack(side=LEFT, padx=10)
        # --- 结束修改 ---

        # --- 控制按钮 ---
        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill=X, pady=10, side=BOTTOM)

        ttk.Button(btn_frame, text="保存", command=self.on_save, style="success.TButton").pack(side=LEFT, expand=True,
                                                                                               padx=5)
        ttk.Button(btn_frame, text="取消", command=self.on_cancel, style="light.TButton").pack(side=LEFT, expand=True,
                                                                                               padx=5)

        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

    def add_setting_entry(self, parent, label_text, config_key):
        """辅助函数：添加一行设置"""
        frame = ttk.Frame(parent)
        frame.pack(fill=X, pady=2)
        ttk.Label(frame, text=label_text, width=25).pack(side=LEFT)
        var = tk.StringVar(value=self.config.get(config_key, ""))
        setattr(self, f"{config_key}_var", var)
        ttk.Entry(frame, textvariable=var, width=10).pack(side=LEFT)

    def add_sound_picker(self, parent, label_text, var, config_key):
        """辅助函数：添加一行声音文件选择器"""
        frame = ttk.Frame(parent)
        frame.pack(fill=X, pady=2)
        ttk.Label(frame, text=label_text, width=20).pack(side=LEFT)

        entry = ttk.Entry(frame, textvariable=var, state="readonly")
        entry.pack(side=LEFT, fill=X, expand=True)

        def browse():
            file_path = filedialog.askopenfilename(
                title=f"选择 {label_text}",
                filetypes=[("音频文件", "*.mp3 *.wav"), ("所有文件", "*.*")]
            )
            if file_path:
                var.set(file_path)
                self.config[config_key] = file_path

        def test_sound():
            self.parent.play_sound(config_key, temp_path=var.get())

        ttk.Button(frame, text="浏览...", width=6, command=browse).pack(side=LEFT, padx=3)
        ttk.Button(frame, text="试听", width=5, command=test_sound).pack(side=LEFT, padx=3)

    def save_geometry(self):
        """保存当前窗口的几何信息到父窗口的设置中"""
        try:
            geom = self.geometry()
            size_str = geom.split('+')[0]
            width, height = size_str.split('x')
            # 直接修改父窗口的设置
            self.parent.settings['settings_width'] = int(width)
            self.parent.settings['settings_height'] = int(height)
            self.parent.save_settings()  # 调用父窗口的保存方法
        except Exception as e:
            print(f"Warning: Could not save settings window geometry: {e}")

    def on_cancel(self):
        """点“取消”或“X”时调用：只保存窗口大小，不保存设置"""
        self.save_geometry()
        self.destroy()

    def on_save(self):
        """点“保存”时调用：保存设置，也保存窗口大小"""
        try:
            # 验证和收集时间数据
            self.config["total_minutes"] = int(self.total_minutes_var.get())
            min_work = int(self.min_work_minutes_var.get())
            max_work = int(self.max_work_minutes_var.get())
            self.config["rest_seconds"] = int(self.rest_seconds_var.get())

            if min_work > max_work:
                messagebox.showerror("输入错误", "最短工作时间不能大于最长工作时间。")
                return

            self.config["min_work_minutes"] = min_work
            self.config["max_work_minutes"] = max_work

            # 收集声音数据
            self.config["sound1_path"] = self.sound1_var.get()
            self.config["sound2_path"] = self.sound2_var.get()
            # --- 【已添加】保存 sound3 ---
            self.config["sound3_path"] = self.sound3_var.get()

            # --- 【已修改】收集两个通知开关数据 ---
            self.config["show_interval_notifications"] = self.show_interval_notifications_var.get()
            self.config["show_session_end_notification"] = self.show_session_end_notification_var.get()
            # 移除旧的键（如果存在）
            if "show_notifications" in self.config:
                del self.config["show_notifications"]
            # --- 结束修改 ---

            # 将更新后的副本写回主程序
            self.parent.settings = self.config
            self.parent.save_settings()  # 保存所有设置

            self.save_geometry()  # 再次调用以确保几何信息被保存

            messagebox.showinfo("已保存", "设置已保存。新设置将在下一次会话启动时生效。")
            self.destroy()

        except ValueError:
            messagebox.showerror("输入错误", "所有时间设置必须为整数。")
        except Exception as e:
            messagebox.showerror("保存失败", f"发生错误：{e}")


# --- 日志查看窗口 ---
class LogDialog(tk.Toplevel):
    """
    用于查看日志的弹出窗口。
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.title("专注日志")
        self.geometry("700x400")
        self.transient(parent)
        self.grab_set()

        container = ttk.Frame(self, padding=10)
        container.pack(fill=BOTH, expand=YES)

        # 创建 Treeview
        columns = ("date", "start_time", "end_time", "actual_duration", "rest_count")
        self.tree = ttk.Treeview(container, columns=columns, show="headings")

        # 定义表头
        self.tree.heading("date", text="日期")
        self.tree.heading("start_time", text="开始时间")
        self.tree.heading("end_time", text="结束时间")
        self.tree.heading("actual_duration", text="实际时长 (分钟)")
        self.tree.heading("rest_count", text="休息次数")

        # 设置列宽
        self.tree.column("date", width=100, anchor=CENTER)
        self.tree.column("start_time", width=100, anchor=CENTER)
        self.tree.column("end_time", width=100, anchor=CENTER)
        self.tree.column("actual_duration", width=150, anchor=CENTER)
        self.tree.column("rest_count", width=100, anchor=CENTER)

        # 添加滚动条
        scrollbar = ttk.Scrollbar(container, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)

        scrollbar.pack(side=RIGHT, fill=Y)
        self.tree.pack(side=LEFT, fill=BOTH, expand=YES)

        self.load_logs()

    def load_logs(self):
        """从 CSV 文件加载日志并填充到 Treeview"""
        if not os.path.exists(LOG_PATH):
            return

        try:
            with open(LOG_PATH, mode='r', encoding='utf-8', newline='') as f:
                reader = csv.reader(f)
                try:
                    next(reader)  # 跳过表头
                except StopIteration:
                    return

                rows = list(reader)
                for row in reversed(rows):
                    if len(row) == 6:
                        self.tree.insert("", END, values=(row[0], row[1], row[2], row[4], row[5]))
        except Exception as e:
            messagebox.showerror("日志读取失败", f"无法加载日志文件：{e}")


# --- 主应用 ---
class FocusApp(tb.Window):
    """
    主应用程序窗口。
    """

    def __init__(self, theme="cosmo"):
        # 检查所有依赖
        if not PYGAME_LOADED or not PLYER_LOADED or not PYSTRAY_LOADED:
            return

        super().__init__(themename=theme)
        self.title("倒计时&提醒")

        # --- 【已修改】使用Pillow(ImageTk)设置窗口任务栏图标 ---
        self.taskbar_icon = None  # 必须保持对PhotoImage的引用
        try:
            # 确定图标路径 (这个逻辑你的代码里已经有了)
            if getattr(sys, 'frozen', False):
                # 如果是打包后的 .exe 文件
                SCRIPT_DIR = os.path.dirname(sys.executable)
            else:
                # 如果是 .py 脚本
                SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

            icon_path = os.path.join(SCRIPT_DIR, "app_icon.ico")

            if os.path.exists(icon_path):
                # 1. 使用Pillow/ImageTk加载，这比iconbitmap更健壮
                img = Image.open(icon_path)
                self.taskbar_icon = ImageTk.PhotoImage(img)
                self.iconphoto(True, self.taskbar_icon)
            else:
                print(f"警告：未找到窗口图标文件: {icon_path}")

        except Exception as e:
            print(f"使用ImageTk设置窗口图标失败: {e}")
            # 2. 尝试回退到 iconbitmap (以防万一)
            try:
                if os.path.exists(icon_path):
                    self.iconbitmap(icon_path)
                    print("ImageTk失败，回退到iconbitmap成功。")
            except Exception as e2:
                print(f"回退到iconbitmap也失败了: {e2}")
        # --- 结束修改 ---

        self.settings = {}
        self.load_settings()  # 必须在创建窗口前加载

        self.geometry(f"{self.settings['main_width']}x{self.settings['main_height']}")

        # 初始化pygame混音器
        try:
            pygame.mixer.init()
        except pygame.error as e:
            messagebox.showwarning("音频错误", f"无法初始化音频播放器：{e}\n提示音将无法播放。")

        self.timer_thread = None
        self.session_start_time = None
        self.rest_count = 0
        self.is_paused = False
        self.icon = None  # 用于存放系统托盘图标对象

        self.create_widgets()
        self.create_menu()
        self.setup_tray_icon()  # 设置系统托盘
        self.reset_gui_to_stopped()

        # 将 'X' 按钮绑定到 hide_window 方法
        self.protocol("WM_DELETE_WINDOW", self.hide_window)

    def create_widgets(self):
        """创建主界面组件"""
        container = ttk.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=YES)

        # 总倒计时
        self.lbl_total_time = ttk.Label(container, text="90:00",
                                        font=("Helvetica", 60, "bold"),
                                        bootstyle=PRIMARY)
        self.lbl_total_time.pack(pady=10, expand=True)

        # 当前状态
        self.lbl_current_state = ttk.Label(container, text="已停止",
                                           font=("Helvetica", 14),
                                           bootstyle=INFO)
        self.lbl_current_state.pack(pady=5, expand=True)

        # 间隔倒计时
        self.lbl_interval_time = ttk.Label(container, text="00:00",
                                           font=("Helvetica", 16, "bold"),
                                           bootstyle=SECONDARY)
        self.lbl_interval_time.pack(pady=5, expand=True)

        # --- 按钮控制区 ---
        btn_frame = ttk.Frame(container)
        btn_frame.pack(pady=15, fill=X, side=BOTTOM)

        self.btn_start = ttk.Button(btn_frame, text="启动",
                                    command=self.start_session,
                                    bootstyle=SUCCESS)
        self.btn_start.pack(side=LEFT, expand=True, padx=5, ipady=5)

        self.btn_pause = ttk.Button(btn_frame, text="暂停",
                                    command=self.pause_resume_session,
                                    bootstyle=WARNING)
        self.btn_pause.pack(side=LEFT, expand=True, padx=5, ipady=5)

        self.btn_stop = ttk.Button(btn_frame, text="停止",
                                   command=lambda: self.stop_session(completed=False),
                                   bootstyle=DANGER)
        self.btn_stop.pack(side=LEFT, expand=True, padx=5, ipady=5)

    def create_menu(self):
        """创建顶部菜单栏"""
        menu_bar = tk.Menu(self)
        self.config(menu=menu_bar)

        file_menu = tk.Menu(menu_bar, tearoff=False)
        menu_bar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="设置...", command=self.open_settings)
        file_menu.add_separator()
        # 将 "退出" 移至系统托盘菜单
        file_menu.add_command(label="最小化到托盘", command=self.hide_window)
        file_menu.add_command(label="退出", command=self.quit_program)

        view_menu = tk.Menu(menu_bar, tearoff=False)
        menu_bar.add_cascade(label="查看", menu=view_menu)
        view_menu.add_command(label="查看日志...", command=self.open_logs)

    # --- 核心功能 ---

    def start_session(self):
        """启动一个新的专注会话"""
        if self.timer_thread and self.timer_thread.is_alive():
            messagebox.showwarning("提示", "会话已在运行中。")
            return

        self.btn_start.config(state=DISABLED)
        self.btn_pause.config(state=NORMAL, text="暂停")
        self.btn_stop.config(state=NORMAL)
        self.is_paused = False

        self.session_start_time = datetime.now()
        self.rest_count = 0

        self.timer_thread = TimerThread(self)
        self.timer_thread.start()

    def pause_resume_session(self):
        """暂停或恢复会话"""
        if not self.timer_thread:
            return

        if self.is_paused:
            self.timer_thread.resume()
            self.btn_pause.config(text="暂停")
            self.is_paused = False
            self.lbl_current_state.config(text=f"工作中 - {self.timer_thread.current_phase}")
        else:
            self.timer_thread.pause()
            self.btn_pause.config(text="继续")
            self.is_paused = True
            self.lbl_current_state.config(text="已暂停")

    def stop_session(self, completed=False):
        """停止当前会话（手动或自动）"""
        if self.timer_thread:
            self.timer_thread.stop()
            self.timer_thread = None

        if self.session_start_time:
            self.log_session()

        self.reset_gui_to_stopped()

        if completed:
            self.lbl_total_time.config(text="完成!")
            # --- 【已添加】播放会话结束提示音 ---
            self.play_sound("sound3_path")
            # --- 【已修改】指定通知类型为 "session_end" ---
            self.send_notification("会话完成！", "恭喜你完成了一次专注会话！", notification_type="session_end")
        else:
            self.lbl_total_time.config(text=self.format_time(int(self.settings["total_minutes"]) * 60))

    def reset_gui_to_stopped(self):
        """将会话状态重置为“已停止”"""
        total_sec = int(self.settings.get("total_minutes", 90)) * 60
        self.lbl_total_time.config(text=self.format_time(total_sec))
        self.lbl_current_state.config(text="已停止")
        self.lbl_interval_time.config(text="00:00")

        self.btn_start.config(state=NORMAL)
        self.btn_pause.config(state=DISABLED, text="暂停")
        self.btn_stop.config(state=DISABLED)
        self.is_paused = False

    # --- GUI 更新与辅助 ---

    def update_gui_labels(self, total_left, interval_left, phase):
        """
        （由计时器线程调用）在主线程中安全地更新GUI标签。
        """
        self.lbl_total_time.config(text=self.format_time(total_left))
        self.lbl_interval_time.config(text=self.format_time(interval_left))

        if phase == "WORK":
            self.lbl_current_state.config(text="工作中", bootstyle=SUCCESS)
        else:  # REST
            self.lbl_current_state.config(text="休息中", bootstyle=INFO)

    def format_time(self, seconds):
        """将秒数格式化为 MM:SS"""
        m, s = divmod(seconds, 60)
        return f"{m:02d}:{s:02d}"

    def save_window_geometry(self):
        """保存主窗口的几何信息"""
        try:
            # 仅在窗口未最小化时获取几何信息
            if self.state() == 'normal':
                geom = self.geometry()
                size_str = geom.split('+')[0]
                width, height = size_str.split('x')
                self.settings['main_width'] = int(width)
                self.settings['main_height'] = int(height)
                self.save_settings()
        except Exception as e:
            print(f"Warning: Could not save main window geometry: {e}")

    # --- 系统托盘和窗口关闭逻辑 (已修改) ---

    def setup_tray_icon(self):
        """创建系统托盘图标"""
        try:
            # 确保使用 SCRIPT_DIR 来定位图标文件
            icon_path = os.path.join(SCRIPT_DIR, "app_icon.ico")
            image = Image.open(icon_path)
            menu_options = (item('显示', self.show_window, default=True), item('退出', self.quit_program))
            self.icon = pystray.Icon("FocusApp", image, "专注助手", menu_options)
            # 在单独的线程中运行托盘图标，以免阻塞Tkinter主循环
            threading.Thread(target=self.icon.run, daemon=True).start()
        except Exception as e:
            print(f"无法创建系统托盘图标: {e}")
            messagebox.showerror("错误", f"无法加载托盘图标 'app_icon.ico'。\n请确保文件存在于程序目录。\n错误: {e}")

    def show_window(self, icon=None, item=None):
        """从托盘菜单中显示窗口"""
        self.deiconify()  # 显示窗口
        self.attributes('-topmost', 1)  # 确保窗口在最前面
        self.after(100, lambda: self.attributes('-topmost', 0))  # 短暂置顶后取消

    def hide_window(self):
        """点击 'X' 按钮时隐藏窗口（而不是退出）"""
        self.save_window_geometry()
        self.withdraw()
        # --- 【已修改】指定通知类型为 "misc" (杂项)，将由 "interval" 开关控制 ---
        self.send_notification("专注助手", "已最小化到系统托盘。", notification_type="misc")

    def quit_program(self, icon=None, item=None):
        """从托盘菜单中退出应用程序"""
        is_running = self.timer_thread and self.timer_thread.is_alive()

        if is_running:
            if not messagebox.askyesno("退出确认", "专注会话正在进行中，你确定要退出吗？"):
                return  # 中止退出
            else:
                self.stop_session(completed=False)  # 停止并记录会话

        # 保存最后的窗口几何信息
        self.save_window_geometry()

        # 停止托盘图标
        if self.icon:
            self.icon.stop()

        # 清理
        pygame.mixer.quit()

        # 销毁窗口
        self.destroy()

        # --- 新增代码 ---
        # 显式退出程序进程，防止进程残留
        sys.exit()
        # --- 结束新增 ---

    # --- 设置与日志 ---

    def load_settings(self):
        """加载 JSON 配置文件"""
        # --- 【已修改】更新默认配置 ---
        default_config = {
            "total_minutes": 90,
            "min_work_minutes": 3,
            "max_work_minutes": 5,
            "rest_seconds": 15,
            "sound1_path": "",
            "sound2_path": "",
            "sound3_path": "",  # <-- 新增
            "main_width": 450,
            "main_height": 330,
            "settings_width": 550,
            "settings_height": 450,
            # "show_notifications": True, # <-- 移除
            "show_interval_notifications": True,  # <-- 新增
            "show_session_end_notification": True  # <-- 新增
        }
        try:
            with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
                self.settings = json.load(f)

            # --- 【已添加】向后兼容：如果旧配置存在，则沿用 ---
            if 'show_notifications' in self.settings:
                if 'show_interval_notifications' not in self.settings:
                    self.settings['show_interval_notifications'] = self.settings['show_notifications']
                if 'show_session_end_notification' not in self.settings:
                    self.settings['show_session_end_notification'] = self.settings['show_notifications']
            # --- 结束添加 ---

            # 确保所有键都存在
            for key, value in default_config.items():
                if key not in self.settings:
                    self.settings[key] = value

        except (FileNotFoundError, json.JSONDecodeError):
            self.settings = default_config
            self.save_settings()

    def save_settings(self):
        """保存配置到 JSON 文件"""
        try:
            with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            messagebox.showerror("保存失败", f"无法写入设置文件：{e}")

    def log_session(self):
        """将会话数据记录到 CSV 文件"""
        try:
            end_time = datetime.now()
            actual_duration = (end_time - self.session_start_time).total_seconds()
            actual_duration_min = round(actual_duration / 60, 2)

            log_data = [
                self.session_start_time.strftime("%Y-%m-%d"),
                self.session_start_time.strftime("%H:%M:%S"),
                end_time.strftime("%H:%M:%S"),
                self.settings["total_minutes"],
                actual_duration_min,
                self.rest_count
            ]

            file_exists = os.path.exists(LOG_PATH)

            with open(LOG_PATH, mode='a', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(
                        ["Date", "Start Time", "End Time", "Planned Duration (min)", "Actual Duration (min)",
                         "Rest Count"])
                writer.writerow(log_data)

        except Exception as e:
            messagebox.showerror("日志记录失败", f"无法写入日志文件：{e}")
        finally:
            self.session_start_time = None
            self.rest_count = 0

    def open_settings(self):
        """打开设置对话框"""
        SettingsDialog(self)

    def open_logs(self):
        """打开日志查看器"""
        LogDialog(self)

    # --- 声音与通知 ---

    def play_sound(self, sound_key, temp_path=None):
        """播放指定的声音文件"""
        if not PYGAME_LOADED: return

        path = temp_path if temp_path else self.settings.get(sound_key)

        if not path or not os.path.exists(path):
            print(f"警告：声音文件未找到或未设置：{path}")
            return

        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
        except Exception as e:
            print(f"播放声音失败：{e}")
            messagebox.showwarning("播放失败", f"无法播放声音文件：{path}\n错误：{e}")

    # --- 【已修改】修改通知逻辑 ---
    def send_notification(self, title, message, notification_type="interval"):
        """
        发送桌面通知
        notification_type: 'interval' (工作/休息/杂项) 或 'session_end' (总时长结束)
        """

        # 根据通知类型，确定使用哪个设置键
        setting_key = "show_session_end_notification" if notification_type == "session_end" else "show_interval_notifications"

        if not self.settings.get(setting_key, True):
            return

        if not PLYER_LOADED: return

        try:
            # 确保使用 SCRIPT_DIR 来定位图标文件
            icon_path = os.path.join(SCRIPT_DIR, "app_icon.ico")

            notification.notify(
                title=title,
                message=message,
                app_name="专注助手",
                app_icon=icon_path,  # 添加图标到通知
                timeout=5
            )
        except Exception as e:
            print(f"发送通知失败：{e}")
    # --- 结束修改 ---


# --- 程序入口 ---
if __name__ == "__main__":
    # 检查所有依赖项
    if PYGAME_LOADED and PLYER_LOADED and PYSTRAY_LOADED:
        app = FocusApp(theme="cosmo")
        app.mainloop()
    else:
        print("必要组件缺失，程序无法启动。")
        root = tk.Tk()
        root.title("错误")
        root.geometry("400x100")  # 稍微加宽以显示完整消息
        label = tk.Label(root,
                         text="错误：缺少必要的库。\n请在命令行运行:\npip install ttkbootstrap pygame plyer pystray pillow",
                         fg="red", font=("Arial", 10))
        label.pack(pady=20, padx=10)
        root.mainloop()