import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import os
from datetime import datetime
import threading


class ExcelCompareApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Excel 变更对比工具 (Pro版 - 支持Sheet选择)")
        self.root.geometry("650x650")  # 稍微调高一点高度

        # 变量存储
        self.old_path = tk.StringVar()
        self.new_path = tk.StringVar()
        self.columns = []

        # === 1. 文件选择区域 ===
        file_frame = ttk.LabelFrame(root, text="第一步：选择文件与Sheet页", padding=10)
        file_frame.pack(fill="x", padx=10, pady=5)

        # --- 旧文件区域 ---
        ttk.Label(file_frame, text="旧文件 (Old):").grid(row=0, column=0, sticky="w")
        ttk.Entry(file_frame, textvariable=self.old_path, width=40).grid(row=0, column=1, padx=5)
        ttk.Button(file_frame, text="浏览...", command=lambda: self.select_file(True)).grid(row=0, column=2)

        # 旧文件 Sheet 选择
        ttk.Label(file_frame, text="选择Sheet:").grid(row=1, column=0, sticky="e")
        self.combo_sheet_old = ttk.Combobox(file_frame, state="readonly", width=38)
        self.combo_sheet_old.grid(row=1, column=1, padx=5, pady=(0, 10))

        # --- 新文件区域 ---
        ttk.Label(file_frame, text="新文件 (New):").grid(row=2, column=0, sticky="w")
        ttk.Entry(file_frame, textvariable=self.new_path, width=40).grid(row=2, column=1, padx=5)
        ttk.Button(file_frame, text="浏览...", command=lambda: self.select_file(False)).grid(row=2, column=2)

        # 新文件 Sheet 选择
        ttk.Label(file_frame, text="选择Sheet:").grid(row=3, column=0, sticky="e")
        self.combo_sheet_new = ttk.Combobox(file_frame, state="readonly", width=38)
        self.combo_sheet_new.grid(row=3, column=1, padx=5, pady=(0, 5))
        # 绑定事件：新文件Sheet改变时，重新加载列名
        self.combo_sheet_new.bind("<<ComboboxSelected>>", self.on_new_sheet_change)

        # === 2. 主键选择区域 ===
        key_frame = ttk.LabelFrame(root, text="第二步：指定复合主键 (最少1个，最多3个)", padding=10)
        key_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(key_frame, text="提示：系统会自动读取“新文件”所选Sheet的列名").pack(anchor="w", pady=(0, 5))

        self.combo_key1 = ttk.Combobox(key_frame, state="readonly")
        self.combo_key2 = ttk.Combobox(key_frame, state="readonly")
        self.combo_key3 = ttk.Combobox(key_frame, state="readonly")

        ttk.Label(key_frame, text="主键 1 (必选):").pack(anchor="w")
        self.combo_key1.pack(fill="x", pady=2)

        ttk.Label(key_frame, text="主键 2 (可选):").pack(anchor="w")
        self.combo_key2.pack(fill="x", pady=2)

        ttk.Label(key_frame, text="主键 3 (可选):").pack(anchor="w")
        self.combo_key3.pack(fill="x", pady=2)

        # === 3. 操作区域 ===
        btn_frame = ttk.Frame(root, padding=10)
        btn_frame.pack(fill="x")

        self.btn_run = ttk.Button(btn_frame, text="开始比对并导出结果", command=self.start_thread)
        self.btn_run.pack(fill="x", ipady=10)

        # === 4. 日志输出 ===
        log_frame = ttk.LabelFrame(root, text="运行日志", padding=10)
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.log_text = tk.Text(log_frame, height=10)
        self.log_text.pack(fill="both", expand=True)

    def log(self, message):
        """写入日志到文本框"""
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)

    def select_file(self, is_old):
        filename = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx;*.xls")])
        if filename:
            if is_old:
                self.old_path.set(filename)
                self.load_sheets(filename, self.combo_sheet_old, is_new_file=False)
            else:
                self.new_path.set(filename)
                self.load_sheets(filename, self.combo_sheet_new, is_new_file=True)

    def load_sheets(self, filepath, combo_widget, is_new_file):
        """加载Excel的所有Sheet名到下拉框"""
        try:
            xl = pd.ExcelFile(filepath)
            sheet_names = xl.sheet_names
            combo_widget['values'] = sheet_names

            # 智能默认选中：优先选 '汇总'，否则选第一个
            if '汇总' in sheet_names:
                combo_widget.set('汇总')
            elif sheet_names:
                combo_widget.current(0)

            self.log(f"已加载Sheet列表: {filepath.split('/')[-1]}")

            # 如果是新文件，加载完Sheet后立即加载列名
            if is_new_file:
                self.load_columns(filepath, combo_widget.get())

        except Exception as e:
            messagebox.showerror("错误", f"读取Excel Sheet失败:\n{str(e)}")

    def on_new_sheet_change(self, event):
        """当用户手动切换新文件的Sheet时触发"""
        filepath = self.new_path.get()
        sheet_name = self.combo_sheet_new.get()
        if filepath and sheet_name:
            self.log(f"切换Sheet页: {sheet_name}，正在重新加载列名...")
            self.load_columns(filepath, sheet_name)

    def load_columns(self, filepath, sheet_name):
        """读取指定Sheet的表头填充到下拉框"""
        try:
            # 只读表头
            df = pd.read_excel(filepath, sheet_name=sheet_name, nrows=0)
            self.columns = df.columns.tolist()

            # 更新下拉框
            for combo in [self.combo_key1, self.combo_key2, self.combo_key3]:
                combo['values'] = self.columns
                combo.set('')  # 清空旧值

            self.log(f"✅ 已加载列名 ({len(self.columns)}列) 来自Sheet: {sheet_name}")

        except Exception as e:
            self.log(f"❌ 读取列名失败: {str(e)}")

    def start_thread(self):
        t = threading.Thread(target=self.run_compare)
        t.start()

    def run_compare(self):
        old_p = self.old_path.get()
        new_p = self.new_path.get()
        sheet_old = self.combo_sheet_old.get()
        sheet_new = self.combo_sheet_new.get()

        # 1. 基础校验
        if not old_p or not new_p:
            messagebox.showwarning("提示", "请先选择两个文件！")
            return
        if not sheet_old or not sheet_new:
            messagebox.showwarning("提示", "请确保两个文件都选择了Sheet页！")
            return

        # 2. 获取主键
        keys = []
        if self.combo_key1.get(): keys.append(self.combo_key1.get())
        if self.combo_key2.get(): keys.append(self.combo_key2.get())
        if self.combo_key3.get(): keys.append(self.combo_key3.get())

        if not keys:
            messagebox.showwarning("提示", "至少选择一个主键列！")
            return

        self.btn_run.config(state="disabled")
        self.log("-" * 30)
        self.log(f"开始比对...")
        self.log(f"旧文件Sheet: {sheet_old}")
        self.log(f"新文件Sheet: {sheet_new}")
        self.log(f"复合主键: {keys}")

        try:
            # 3. 读取数据
            self.log("正在读取 Excel 数据，请稍候...")
            df_old = pd.read_excel(old_p, sheet_name=sheet_old)
            df_new = pd.read_excel(new_p, sheet_name=sheet_new)

            # 4. 数据预处理
            # 校验主键列是否存在
            for k in keys:
                if k not in df_old.columns:
                    raise ValueError(f"旧文件中缺少主键列: {k}")
                if k not in df_new.columns:
                    raise ValueError(f"新文件中缺少主键列: {k}")

            df_old[keys] = df_old[keys].fillna('未知')
            df_new[keys] = df_new[keys].fillna('未知')

            # 设置索引
            df_old_idx = df_old.set_index(keys)
            df_new_idx = df_new.set_index(keys)

            # 5. 核心比对逻辑
            # (1) 新增
            added_indices = df_new_idx.index.difference(df_old_idx.index)
            df_added = df_new_idx.loc[added_indices].reset_index()

            # (2) 删除
            removed_indices = df_old_idx.index.difference(df_new_idx.index)
            df_removed = df_old_idx.loc[removed_indices].reset_index()

            # (3) 修改
            common_indices = df_new_idx.index.intersection(df_old_idx.index)

            modified_rows = []
            # 只比对非主键列
            compare_cols = [c for c in df_new.columns if c not in keys]

            total_common = len(common_indices)
            self.log(f"正在分析 {total_common} 条共有数据...")

            for i, idx in enumerate(common_indices):
                if i % 100 == 0:
                    self.root.update_idletasks()

                row_new = df_new_idx.loc[idx]
                row_old = df_old_idx.loc[idx]

                for col in compare_cols:
                    # 如果旧表里没有这个列，跳过（或者你可以视为新增列）
                    if col not in row_old:
                        continue

                    val_new = row_new[col]
                    val_old = row_old[col]

                    if pd.isna(val_new) and pd.isna(val_old):
                        continue

                    if str(val_new) != str(val_old):
                        record = {}
                        if len(keys) == 1:
                            record[keys[0]] = idx
                        else:
                            for k_i, k_name in enumerate(keys):
                                record[k_name] = idx[k_i]

                        record.update({
                            '变更类型': '修改',
                            '变更字段': col,
                            '旧值': val_old,
                            '新值': val_new,
                            '更新人': row_new.get('更新人', ''),
                            '更新时间': row_new.get('更新时间', '')
                        })
                        modified_rows.append(record)

            df_modified = pd.DataFrame(modified_rows)

            self.log(f"✅ 比对完成！")
            self.log(f"➕ 新增: {len(df_added)} 行")
            self.log(f"➖ 删除: {len(df_removed)} 行")
            self.log(f"✏️ 修改: {len(df_modified)} 处")

            # 6. 保存文件
            default_name = f"变更日志_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            save_path = filedialog.asksaveasfilename(
                initialfile=default_name,
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")]
            )

            if save_path:
                with pd.ExcelWriter(save_path, engine='xlsxwriter') as writer:
                    # 优先写修改页
                    if not df_modified.empty:
                        df_modified.to_excel(writer, sheet_name='修改明细', index=False)
                    else:
                        pd.DataFrame({'提示': ['无修改']}).to_excel(writer, sheet_name='修改明细', index=False)

                    if not df_added.empty:
                        df_added.to_excel(writer, sheet_name='新增记录', index=False)
                    else:
                        pd.DataFrame({'提示': ['无新增']}).to_excel(writer, sheet_name='新增记录', index=False)

                    if not df_removed.empty:
                        df_removed.to_excel(writer, sheet_name='删除记录', index=False)
                    else:
                        pd.DataFrame({'提示': ['无删除']}).to_excel(writer, sheet_name='删除记录', index=False)

                    # 简单列宽设置
                    for sheet in writer.sheets.values():
                        sheet.set_column(0, 15, 20)

                self.log(f"文件已保存: {save_path}")
                messagebox.showinfo("成功", "日志文件生成成功！")
            else:
                self.log("用户取消保存。")

        except Exception as e:
            self.log(f"❌ 发生错误: {str(e)}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("错误", f"运行出错:\n{str(e)}")

        finally:
            self.btn_run.config(state="normal")


if __name__ == "__main__":
    root = tk.Tk()
    app = ExcelCompareApp(root)
    root.mainloop()