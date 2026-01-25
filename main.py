import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import queue
from core import BatchProcessor
from utils import is_valid_suffix, get_7z_path, set_custom_7z_path

class MainApplication(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("批量文件 7Z 压缩 / 解密工具")
        self.geometry("550x650")
        self.resizable(True, True)

        # Variables
        self.mode_var = tk.StringVar(value="compress")
        self.folder_path_var = tk.StringVar()
        self.output_path_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.show_password_var = tk.BooleanVar(value=False)
        self.compress_level_var = tk.StringVar(value="标准")
        self.suffix_var = tk.StringVar(value="_压缩后")
        self.overwrite_var = tk.StringVar(value="overwrite") # overwrite or skip
        
        # State
        self.is_running = False
        self.processor = None
        self.log_queue = queue.Queue()
        self.progress_queue = queue.Queue()
        self.file_progress_queue = queue.Queue()
        self.result_queue = queue.Queue()

        self.create_widgets()
        self.setup_layout()
        self.on_mode_change()
        
        # Start queue checkers
        self.check_queues()
        
        # Check 7z availability
        self.ensure_7z_availability()

    def ensure_7z_availability(self):
        path = get_7z_path()
        if not path:
            response = messagebox.askyesno(
                "缺少组件", 
                "未检测到 7z.exe，无法执行压缩/解密任务。\n是否现在手动指定 7z.exe 的路径？"
            )
            if response:
                file_path = filedialog.askopenfilename(
                    title="选择 7z.exe",
                    filetypes=[("Executables", "*.exe"), ("All Files", "*.*")]
                )
                if file_path and os.path.basename(file_path).lower() == "7z.exe":
                    set_custom_7z_path(file_path)
                    messagebox.showinfo("成功", "已指定 7z.exe 路径。")
                elif file_path:
                    messagebox.showerror("错误", "选择的文件似乎不是 7z.exe。")
            else:
                self.log("警告：未检测到 7z.exe，请确保系统已安装 7-Zip 或将其放置在程序目录下。", error=True)

    def create_widgets(self):
        # 1. Title & Mode
        self.title_label = ttk.Label(self, text="批量文件 7Z 压缩 / 解密工具", font=("Arial", 14, "bold"))
        
        self.mode_frame = ttk.Frame(self)
        self.rb_compress = ttk.Radiobutton(self.mode_frame, text="压缩模式", variable=self.mode_var, value="compress", command=self.on_mode_change)
        self.rb_decrypt = ttk.Radiobutton(self.mode_frame, text="解密模式", variable=self.mode_var, value="decrypt", command=self.on_mode_change)

        # 2. Core Settings
        self.settings_frame = ttk.LabelFrame(self, text="核心设置")
        
        # Folder
        self.lbl_folder = ttk.Label(self.settings_frame, text="选择目标文件夹：")
        self.entry_folder = ttk.Entry(self.settings_frame, textvariable=self.folder_path_var)
        self.btn_browse = ttk.Button(self.settings_frame, text="浏览", command=self.browse_folder)

        # Output Folder
        self.lbl_out_folder = ttk.Label(self.settings_frame, text="输出目录（可选）：")
        self.entry_out_folder = ttk.Entry(self.settings_frame, textvariable=self.output_path_var)
        self.btn_browse_out = ttk.Button(self.settings_frame, text="浏览", command=self.browse_output_folder)

        # Password
        self.lbl_pwd = ttk.Label(self.settings_frame, text="密码：")
        self.entry_pwd = ttk.Entry(self.settings_frame, textvariable=self.password_var, show="*")
        self.btn_show_pwd = ttk.Checkbutton(self.settings_frame, text="显示", variable=self.show_password_var, command=self.toggle_password_visibility)

        # Compression Level (only for compress)
        self.lbl_level = ttk.Label(self.settings_frame, text="压缩级别：")
        self.combo_level = ttk.Combobox(self.settings_frame, textvariable=self.compress_level_var, values=["快速", "标准", "最高"], state="readonly")

        # Output Suffix
        self.lbl_suffix = ttk.Label(self.settings_frame, text="输出文件夹后缀：")
        self.entry_suffix = ttk.Entry(self.settings_frame, textvariable=self.suffix_var)

        # Duplicate Handling
        self.lbl_dup = ttk.Label(self.settings_frame, text="重复文件处理：")
        self.dup_frame = ttk.Frame(self.settings_frame)
        self.rb_overwrite = ttk.Radiobutton(self.dup_frame, text="覆盖现有文件", variable=self.overwrite_var, value="overwrite")
        self.rb_skip = ttk.Radiobutton(self.dup_frame, text="跳过已存在文件", variable=self.overwrite_var, value="skip")

        # 3. Execution & Progress
        self.exec_frame = ttk.Frame(self)
        self.btn_start = ttk.Button(self.exec_frame, text="开始压缩", command=self.toggle_start)
        
        self.progress_frame = ttk.Frame(self)
        self.lbl_overall_progress = ttk.Label(self.progress_frame, text="全局进度：0%（已处理 0 / 总 0）")
        self.pb_overall = ttk.Progressbar(self.progress_frame, orient="horizontal", mode="determinate")
        
        self.lbl_current_task = ttk.Label(self.progress_frame, text="当前任务：准备就绪")
        self.lbl_current_file = ttk.Label(self.progress_frame, text="当前文件：")
        # Note: 'Single file progress' is tricky with 7z CLI without parsing stdout percentages continuously.
        # For simplicity and robustness, we might simulate it or just use indeterminate if parsing is hard.
        # But requirements ask for it. 7z outputs "%" in stdout. 
        # For V1.0, to ensure stability, I might make the single file bar indeterminate or just step it if possible.
        # Given the subprocess implementation in core.py waits for communicate(), we don't get real-time 7z progress.
        # To get real-time 7z progress we need to read stdout line by line.
        # For this version, I will stick to file-level granularity for the overall progress. 
        # The "Single file progress" will be indeterminate mode during processing of one file.
        self.lbl_file_progress = ttk.Label(self.progress_frame, text="当前文件进度：0%")
        self.pb_file = ttk.Progressbar(self.progress_frame, orient="horizontal", mode="determinate")

        self.log_text = tk.Text(self.progress_frame, height=6, state="disabled")
        self.scrollbar = ttk.Scrollbar(self.progress_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=self.scrollbar.set)
        
        # Context menu for log
        self.log_menu = tk.Menu(self, tearoff=0)
        self.log_menu.add_command(label="复制", command=self.copy_log)
        self.log_text.bind("<Button-3>", self.show_log_menu)

        # 4. Footer
        self.footer_frame = ttk.Frame(self)
        self.btn_open_output = ttk.Button(self.footer_frame, text="打开输出目录", state="disabled", command=self.open_output_dir)
        self.btn_clear_log = ttk.Button(self.footer_frame, text="清空日志", command=self.clear_log)
        self.lbl_status = ttk.Label(self.footer_frame, text="状态：未开始", relief="sunken", anchor="w")

    def setup_layout(self):
        # Grid/Pack layout
        self.title_label.pack(pady=5)
        
        self.mode_frame.pack(pady=2)
        self.rb_compress.pack(side="left", padx=10)
        self.rb_decrypt.pack(side="left", padx=10)

        self.settings_frame.pack(fill="x", padx=10, pady=2)
        # Grid inside settings
        self.lbl_folder.grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.entry_folder.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        self.btn_browse.grid(row=0, column=2, padx=5, pady=2)

        self.lbl_out_folder.grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.entry_out_folder.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        self.btn_browse_out.grid(row=1, column=2, padx=5, pady=2)
        
        self.lbl_pwd.grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.entry_pwd.grid(row=2, column=1, sticky="ew", padx=5, pady=2)
        self.btn_show_pwd.grid(row=2, column=2, padx=5, pady=2)

        self.lbl_level.grid(row=3, column=0, sticky="w", padx=5, pady=2)
        self.combo_level.grid(row=3, column=1, sticky="ew", padx=5, pady=2)

        self.lbl_suffix.grid(row=4, column=0, sticky="w", padx=5, pady=2)
        self.entry_suffix.grid(row=4, column=1, sticky="ew", padx=5, pady=2)

        self.lbl_dup.grid(row=5, column=0, sticky="w", padx=5, pady=2)
        self.dup_frame.grid(row=5, column=1, columnspan=2, sticky="w", padx=5, pady=2)
        self.rb_overwrite.pack(side="left", padx=5)
        self.rb_skip.pack(side="left", padx=5)

        self.settings_frame.columnconfigure(1, weight=1)

        self.exec_frame.pack(pady=5)
        self.btn_start.pack(ipadx=20, ipady=2)

        self.progress_frame.pack(fill="both", expand=True, padx=10)
        self.lbl_overall_progress.pack(anchor="w")
        self.pb_overall.pack(fill="x", pady=2)
        self.lbl_current_task.pack(anchor="w", pady=(2,0))
        self.lbl_current_file.pack(anchor="w")
        self.lbl_file_progress.pack(anchor="w")
        self.pb_file.pack(fill="x", pady=2)
        
        self.log_text.pack(side="left", fill="both", expand=True, pady=2)
        self.scrollbar.pack(side="right", fill="y", pady=2)

        self.footer_frame.pack(fill="x", padx=10, pady=5)
        self.btn_open_output.pack(side="left", padx=5)
        self.btn_clear_log.pack(side="left", padx=5)
        self.lbl_status.pack(side="right", fill="x", expand=True, padx=5)

    def on_mode_change(self):
        if self.is_running:
            return # Should be disabled anyway
        
        mode = self.mode_var.get()
        self.clear_log()
        self.reset_progress()
        
        if mode == "compress":
            self.btn_start.config(text="开始压缩")
            self.lbl_level.grid()
            self.combo_level.grid()
            self.suffix_var.set("_压缩后")
            self.lbl_pwd.config(text="密码：")
        else:
            self.btn_start.config(text="开始解密")
            self.lbl_level.grid_remove()
            self.combo_level.grid_remove()
            self.suffix_var.set("_解密后")
            self.lbl_pwd.config(text="密码：(必填)")

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_path_var.set(folder)

    def browse_output_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_path_var.set(folder)

    def toggle_password_visibility(self):
        if self.show_password_var.get():
            self.entry_pwd.config(show="")
        else:
            self.entry_pwd.config(show="*")

    def log(self, message, error=False):
        self.log_queue.put((message, error))

    def update_progress(self, current, total, folder, file):
        self.progress_queue.put((current, total, folder, file))

    def update_file_progress(self, percent):
        self.file_progress_queue.put(percent)

    def task_complete(self, success, summary):
        self.result_queue.put((success, summary))

    def check_queues(self):
        # Process Log Queue
        try:
            while True:
                msg, is_error = self.log_queue.get_nowait()
                self.log_text.config(state="normal")
                tag = "error" if is_error else "normal"
                self.log_text.tag_config("error", foreground="red")
                self.log_text.tag_config("normal", foreground="black")
                self.log_text.insert("end", msg + "\n", tag)
                self.log_text.see("end")
                self.log_text.config(state="disabled")
        except queue.Empty:
            pass

        # Process Progress Queue
        try:
            while True:
                current, total, folder, file = self.progress_queue.get_nowait()
                percent = (current / total) * 100
                self.pb_overall["value"] = percent
                self.lbl_overall_progress.config(text=f"全局进度：{percent:.1f}%（已处理 {current} / 总 {total}）")
                self.lbl_current_task.config(text=f"当前文件夹：{folder}")
                self.lbl_current_file.config(text=f"当前处理文件：{file}")
                # Reset file progress bar
                self.pb_file["value"] = 0
                self.lbl_file_progress.config(text="当前文件进度：0%")
        except queue.Empty:
            pass

        # Process File Progress Queue
        try:
            while True:
                percent = self.file_progress_queue.get_nowait()
                self.pb_file["value"] = percent
                self.lbl_file_progress.config(text=f"当前文件进度：{percent}%")
        except queue.Empty:
            pass

        # Process Result Queue
        try:
            while True:
                success, summary = self.result_queue.get_nowait()
                self.finish_task(success, summary)
        except queue.Empty:
            pass

        self.after(100, self.check_queues)

    def toggle_start(self):
        if self.is_running:
            # Cancel
            if messagebox.askyesno("确认", "确定要终止当前操作吗？"):
                if self.processor:
                    self.processor.stop()
                self.log("正在停止...", error=True)
                self.lbl_status.config(text="状态：正在停止...")
        else:
            # Start
            self.start_task()

    def start_task(self):
        # Validation
        folder = self.folder_path_var.get()
        if not folder or not os.path.exists(folder):
            messagebox.showwarning("提示", "请先选择有效的目标文件夹")
            return
        
        suffix = self.suffix_var.get()
        if not is_valid_suffix(suffix):
            messagebox.showwarning("提示", "输出后缀包含非法字符")
            return

        password = self.password_var.get()
        mode = self.mode_var.get()
        
        custom_output = self.output_path_var.get().strip()
        if custom_output:
            if not os.path.exists(custom_output):
                # Try to create it? Or warn?
                # User might have typed a new path.
                try:
                    os.makedirs(custom_output, exist_ok=True)
                except Exception as e:
                    messagebox.showwarning("提示", f"无法创建输出目录：\n{e}")
                    return
        else:
            custom_output = None

        if mode == "decrypt" and not password:
            messagebox.showwarning("提示", "请输入解密密码")
            return

        # UI Update
        self.is_running = True
        self.btn_start.config(text="停止") # Or Cancel
        self.set_inputs_state("disabled")
        self.btn_open_output.config(state="disabled")
        self.lbl_status.config(text=f"状态：{'压缩中' if mode == 'compress' else '解密中'}")
        self.reset_progress()
        
        # Start Thread
        self.processor = BatchProcessor(self.update_progress, self.log, self.task_complete, self.update_file_progress)
        
        if mode == "compress":
            level = self.compress_level_var.get()
            overwrite = self.overwrite_var.get()
            t = threading.Thread(target=self.processor.run_compression, 
                                 args=(folder, suffix, password, level, overwrite, custom_output))
        else:
            overwrite = self.overwrite_var.get()
            t = threading.Thread(target=self.processor.run_decryption,
                                 args=(folder, suffix, password, overwrite, custom_output))
        
        t.daemon = True
        t.start()

    def finish_task(self, success, summary):
        self.is_running = False
        self.processor = None
        self.pb_file["value"] = 0
        self.lbl_file_progress.config(text="当前文件进度：0%")
        
        mode_text = "压缩" if self.mode_var.get() == "compress" else "解密"
        self.btn_start.config(text=f"开始{mode_text}")
        self.set_inputs_state("normal")
        
        if success:
            self.lbl_status.config(text="状态：完成")
            self.last_output_path = summary.get("output_path")
            if self.last_output_path:
                self.btn_open_output.config(state="normal")
            
            msg = f"操作完成！\n总文件数：{summary['total']}\n成功：{summary['success']}\n失败：{summary['fail']}\n输出目录：{summary['output_path']}"
            messagebox.showinfo("完成", msg)
        else:
            self.lbl_status.config(text="状态：已终止")

    def set_inputs_state(self, state):
        self.rb_compress.config(state=state)
        self.rb_decrypt.config(state=state)
        self.entry_folder.config(state=state)
        self.btn_browse.config(state=state)
        self.entry_out_folder.config(state=state)
        self.btn_browse_out.config(state=state)
        self.entry_pwd.config(state=state)
        self.combo_level.config(state=state)
        self.entry_suffix.config(state=state)
        self.rb_overwrite.config(state=state)
        self.rb_skip.config(state=state)

    def reset_progress(self):
        self.pb_overall["value"] = 0
        self.lbl_overall_progress.config(text="全局进度：0%（已处理 0 / 总 0）")
        self.lbl_current_task.config(text="当前文件夹：")
        self.lbl_current_file.config(text="当前处理文件：")
        self.pb_file["value"] = 0

    def clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, "end")
        self.log_text.config(state="disabled")

    def copy_log(self):
        try:
            sel = self.log_text.get("sel.first", "sel.last")
            self.clipboard_clear()
            self.clipboard_append(sel)
        except tk.TclError:
            pass # No selection

    def show_log_menu(self, event):
        self.log_menu.post(event.x_root, event.y_root)

    def open_output_dir(self):
        if hasattr(self, 'last_output_path') and self.last_output_path and os.path.exists(self.last_output_path):
            os.startfile(self.last_output_path)

if __name__ == "__main__":
    app = MainApplication()
    app.mainloop()
