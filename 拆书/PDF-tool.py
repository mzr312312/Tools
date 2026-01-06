import streamlit as st
from pypdf import PdfReader, PdfWriter
import zipfile
import io
import re


# ==========================================
# ⚙️ 核心逻辑函数
# ==========================================

def parse_split_config(config_text):
    """[拆分功能] 解析配置文本"""
    chapters = []
    lines = config_text.strip().split('\n')
    for i, line in enumerate(lines):
        line = line.strip()
        if not line: continue
        parts = line.split(None, 1)
        if len(parts) < 2: continue
        page_str, title = parts
        if not page_str.isdigit(): continue
        chapters.append({'page': int(page_str), 'title': title})
    chapters.sort(key=lambda x: x['page'])
    return chapters


def split_pdf_process(file_buffer, chapters):
    """[拆分功能] 核心切分"""
    reader = PdfReader(file_buffer)
    total_pages = len(reader.pages)
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for i, chapter in enumerate(chapters):
            start_page = chapter['page']
            title = chapter['title']
            end_page = chapters[i + 1]['page'] if i < len(chapters) - 1 else total_pages + 1
            if start_page > total_pages: continue
            writer = PdfWriter()
            for p in range(start_page - 1, min(end_page - 1, total_pages)):
                writer.add_page(reader.pages[p])
            safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
            filename = f"{i + 1:02d}_{safe_title}.pdf"
            pdf_bytes = io.BytesIO()
            writer.write(pdf_bytes)
            zip_file.writestr(filename, pdf_bytes.getvalue())
    zip_buffer.seek(0)
    return zip_buffer


def extract_bookmarks_to_text(reader):
    """[书签功能] 提取现有书签"""
    lines = []

    def _recurse_outline(outline, level=1):
        for item in outline:
            if isinstance(item, list):
                _recurse_outline(item, level + 1)
            else:
                try:
                    page_idx = reader.get_page_number(item.page) + 1
                    lines.append(f"{page_idx} {'#' * level} {item.title}")
                except:
                    continue

    if reader.outline: _recurse_outline(reader.outline)
    return "\n".join(lines)


def parse_bookmark_line(line, offset=0):
    """[书签功能] 解析单行"""
    match = re.match(r'^(\d+)\s+(#*)\s*(.*)$', line.strip())
    if not match: return None
    page_str, hash_str, title = match.groups()
    return {"input_page": int(page_str), "abs_page": int(page_str) + offset, "level": len(hash_str) if hash_str else 1,
            "title": title}


def add_bookmarks_process(file_buffer, front_text, body_text, offset_start_page):
    """[书签功能] 写入逻辑"""
    reader = PdfReader(file_buffer)
    writer = PdfWriter()
    for page in reader.pages: writer.add_page(page)
    bookmarks = []
    for line in front_text.split('\n'):
        res = parse_bookmark_line(line, 0)
        if res: bookmarks.append(res)
    real_offset = offset_start_page - 1
    for line in body_text.split('\n'):
        res = parse_bookmark_line(line, real_offset)
        if res: bookmarks.append(res)
    parent_stack = {}
    for b in bookmarks:
        p_idx = b['abs_page'] - 1
        if 0 <= p_idx < len(reader.pages):
            parent = parent_stack.get(b['level'] - 1) if b['level'] > 1 else None
            new_bm = writer.add_outline_item(b['title'], p_idx, parent=parent)
            parent_stack[b['level']] = new_bm
            for l in list(parent_stack.keys()):
                if l > b['level']: del parent_stack[l]
    out_buffer = io.BytesIO()
    writer.write(out_buffer)
    out_buffer.seek(0)
    return out_buffer


# ==========================================
# 🎨 界面与 UI 设置
# ==========================================

st.set_page_config(page_title="PDF Toolset Pro", layout="wide")

# 自定义 CSS 注入
st.markdown("""
    <style>
    .stTextArea textarea { font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 13px; background-color: #fcfcfc; }
    .stFileUploader section { background-color: #f8f9fa; border-radius: 12px; }
    .guide-container { background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #ff4b4b; margin-bottom: 20px; }
    .guide-title { font-weight: bold; color: #1f2937; margin-bottom: 8px; display: flex; align-items: center; }
    </style>
""", unsafe_allow_html=True)

# 侧边栏：仅保留导航
with st.sidebar:
    st.title("🛠️ PDF 瑞士军刀")
    app_mode = st.radio("请选择任务模式", ["🔪 拆分 PDF", "🔖 批量书签"])
    st.markdown("---")
    st.caption("Version 4.1 | NAS Optimized")

# --- 模式 A：拆分 PDF ---
if app_mode == "🔪 拆分 PDF":
    st.title("🔪 PDF 智能拆书工具")

    # 页面内置示例区
    with st.container():
        st.markdown("""
        <div class="guide-container">
            <div class="guide-title">💡 拆分配置指南</div>
            <div style="font-size: 14px; color: #4b5563;">
                输入格式：<code>起始页码</code> + <code>空格</code> + <code>章节名称</code>。
            </div>
        </div>
        """, unsafe_allow_html=True)

        eg_col1, eg_col2 = st.columns([1, 2])
        with eg_col1:
            st.info("**标准示例**")
            st.code("1 封面与前言\n15 第一章 绪论\n45 第二章 原理", language="text")
        with eg_col2:
            st.info("**逻辑说明**")
            st.markdown(
                "- **01号文件**：PDF 第 1-14 页\n- **02号文件**：PDF 第 15-44 页\n- **03号文件**：PDF 第 45 页至末尾")

    st.markdown("---")
    col1, col2 = st.columns([1, 1], gap="large")
    with col1:
        st.markdown("##### 1. 上传源文件")
        split_file = st.file_uploader("选择 PDF", type=["pdf"], key="up_a")
    with col2:
        st.markdown("##### 2. 填写结构")
        split_config = st.text_area("结构配置区", placeholder="在此粘贴目录结构，例如：1 封面", height=200)

    st.markdown("###")
    _, btn_col, _ = st.columns([1, 1, 1])
    with btn_col:
        if st.button("🚀 执行精准拆分", type="primary", use_container_width=True):
            if split_file and split_config.strip():
                with st.spinner("正在切分原子..."):
                    split_file.seek(0)
                    zip_res = split_pdf_process(split_file, parse_split_config(split_config))
                    if zip_res: st.download_button("📥 下载 ZIP", zip_res, "chapters.zip", use_container_width=True)
            else:
                st.warning("请检查文件与配置")

# --- 模式 B：批量书签 ---
elif app_mode == "🔖 批量书签":
    st.title("🔖 PDF 批量目录编辑器")

    # 页面内置示例区
    with st.expander("📘 查看书签配置语法与层级指南", expanded=True):
        col_eg1, col_eg2, col_eg3 = st.columns([1, 1, 1.2])
        with col_eg1:
            st.markdown("**1. 基础语法**")
            st.code("1 # 一级标题\n5 ## 二级标题\n12 ### 三级标题", language="text")
        with col_eg2:
            st.markdown("**2. 层级符号说明**")
            st.markdown("`#` = 一级目录\n`##` = 二级目录\n`###` = 三级目录")
        with col_eg3:
            st.markdown("**3. 页码映射逻辑**")
            st.success("**前言区**：物理页码 (输入1→第1页)\n\n**正文区**：逻辑页码 (输入1→第1+Offset-1页)")

    st.markdown("---")
    bm_file = st.file_uploader("第一步：上传 PDF", type=["pdf"], key="up_b")

    if 'old_bm' not in st.session_state: st.session_state['old_bm'] = ""
    if bm_file and not st.session_state['old_bm']:
        try:
            st.session_state['old_bm'] = extract_bookmarks_to_text(PdfReader(bm_file))
        except:
            pass

    col_l, col_r = st.columns(2, gap="large")
    with col_l:
        st.markdown("##### 2️⃣ 前言区 (绝对页码)")
        f_text = st.text_area("前言/目录配置区", value=st.session_state['old_bm'], height=250)
    with col_r:
        st.markdown("##### 3️⃣ 正文区 (自动偏移)")
        offset = st.number_input("📌 正文首页在 PDF 中的物理页码：", min_value=1, value=15)
        b_text = st.text_area("正文目录配置区", placeholder="1 # 第一章\n5 ## 1.1 节", height=168)

    if bm_file:
        st.markdown("---")
        st.markdown("##### 👁️ 写入预览 (最终物理页码核对)")
        preview = []
        for l in f_text.split('\n'):
            res = parse_bookmark_line(l, 0)
            if res: preview.append({"类型": "前言", "最终PDF页": res['abs_page'], "层级": res['level'],
                                    "目录标题": "　" * (res['level'] - 1) + "📂 " + res['title']})
        for l in b_text.split('\n'):
            res = parse_bookmark_line(l, offset - 1)
            if res: preview.append({"类型": "正文", "最终PDF页": res['abs_page'], "层级": res['level'],
                                    "目录标题": "　" * (res['level'] - 1) + "📄 " + res['title']})

        if preview:
            st.dataframe(preview, use_container_width=True, hide_index=True)
            if st.button("🔥 重构并下载 PDF", type="primary", use_container_width=True):
                with st.spinner("正在写入书签..."):
                    bm_file.seek(0)
                    final_pdf = add_bookmarks_process(bm_file, f_text, b_text, offset)
                    st.download_button("📥 点击下载", final_pdf, f"bookmarked_{bm_file.name}", use_container_width=True)