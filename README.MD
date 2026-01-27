# 🛠️ Python Efficiency Tools Collection

个人开发的 Python 桌面效率工具集。包含专注力管理、文档处理及数据比对工具。

## 📂 工具列表

| 工具名称 | 对应目录 | 核心功能 | 主要技术栈 |
| :--- | :--- | :--- | :--- |
| **Random Interval Focus** | [📂 定期提醒](./定期提醒/) | 随机间隔倒计时、系统托盘驻留、多维提醒 | `pygame` `pystray` `plyer` |
| **Excel Compare Pro** | [📂 对比excel](./对比excel/) | Excel 变更比对、复合主键支持、多Sheet处理 | `pandas` `tkinter` |
| **PDF Toolset Pro** | [📂 拆书](./拆书/) | PDF 智能章节拆分、批量书签重构 | `streamlit` `pypdf` |


### 📦 统一环境配置 

一次性安装所有工具的依赖，请在根目录下运行：

```bash
pip install ttkbootstrap pygame plyer pystray pillow streamlit pypdf pandas openpyxl xlsxwriter