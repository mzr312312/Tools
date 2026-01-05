import streamlit as st
from pypdf import PdfReader, PdfWriter
import zipfile
import io
import re


def parse_config(config_text):
    """
    解析用户输入的配置文本。
    输入：多行字符串 "页码 标题"
    输出：列表 [{'page': int, 'title': str}, ...]，按页码排序
    """
    chapters = []
    lines = config_text.strip().split('\n')

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        # 核心逻辑：maxsplit=1 确保只在第一个空格处切分
        # 即使标题里有空格（如"第一章 绪论"），也会被完整保留在 parts[1] 中
        parts = line.split(None, 1)

        if len(parts) < 2:
            st.warning(f"⚠️ 第 {i + 1} 行格式似乎不对（缺少标题？），已跳过: {line}")
            continue

        page_str, title = parts

        # 尝试将页码转为数字
        if not page_str.isdigit():
            st.warning(f"⚠️ 第 {i + 1} 行页码不是数字，已跳过: {line}")
            continue

        # 存入列表 (注意：这里暂不减1，保留人类直觉的页码，处理时再转)
        chapters.append({
            'page': int(page_str),
            'title': title
        })

    # 按页码从小到大排序，防止用户乱序输入
    chapters.sort(key=lambda x: x['page'])
    return chapters


def split_pdf(file_buffer, chapters):
    """
    核心拆分逻辑
    输入：PDF文件流, 章节配置列表
    输出：BytesIO (包含ZIP文件的内存流)
    """
    reader = PdfReader(file_buffer)
    total_pages = len(reader.pages)

    # 准备一个内存中的 ZIP 文件
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:

        for i, chapter in enumerate(chapters):
            start_page = chapter['page']
            title = chapter['title']

            # 确定结束页码
            # 如果不是最后一章，结束页 = 下一章的起始页
            if i < len(chapters) - 1:
                end_page = chapters[i + 1]['page']
            else:
                # 如果是最后一章，结束页 = PDF总页数 + 1 (因为range是左闭右开)
                end_page = total_pages + 1

            # 逻辑校验：防止页码越界
            if start_page > total_pages:
                st.error(f"❌ 错误：章节 '{title}' 的起始页 ({start_page}) 超过了PDF总页数 ({total_pages})。")
                return None

            # --- 核心切片 ---
            writer = PdfWriter()

            # Python索引从0开始，所以人类页码需要 -1
            # range(start_idx, end_idx)
            page_start_idx = start_page - 1
            page_end_idx = end_page - 1

            # 也就是从 page_start_idx 读到 page_end_idx (不含)
            for p in range(page_start_idx, min(page_end_idx, total_pages)):
                writer.add_page(reader.pages[p])

            # --- 写入单个PDF ---
            # 清理文件名中的非法字符
            safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
            # 添加序号前缀，保证排序 (01_..., 02_...)
            filename = f"{i + 1:02d}_{safe_title}.pdf"

            # 将 writer 的内容写入临时内存流
            pdf_bytes = io.BytesIO()
            writer.write(pdf_bytes)

            # 将该 PDF 添加到 ZIP 包中
            zip_file.writestr(filename, pdf_bytes.getvalue())

    zip_buffer.seek(0)
    return zip_buffer


# --- Streamlit 界面构建 ---
st.set_page_config(page_title="PDF 拆书工具", layout="centered")

st.title("📚 PDF 智能拆书工具")
st.markdown("---")

# 1. 文件上传
uploaded_file = st.file_uploader("第一步：上传 PDF 文件", type=["pdf"])

# 2. 文本配置
st.subheader("第二步：定义章节结构")
st.info("格式说明：每行输入 `起始页码` + `空格` + `章节标题`")

default_text = """1 封面与前言
15 第一章 绪论
38 第二章 基础理论
"""
config_text = st.text_area("在此输入目录结构：", value=default_text, height=200)

# 3. 执行按钮
if st.button("开始拆分", type="primary"):
    if not uploaded_file:
        st.error("请先上传 PDF 文件！")
    elif not config_text.strip():
        st.error("请输入章节配置信息！")
    else:
        with st.spinner("正在拆解原子..."):
            # A. 解析配置
            chapters = parse_config(config_text)

            if chapters:
                # B. 执行拆分
                zip_result = split_pdf(uploaded_file, chapters)

                if zip_result:
                    st.success(f"✅ 成功拆分为 {len(chapters)} 个章节！")

                    # C. 提供下载
                    st.download_button(
                        label="📦 下载所有章节 (ZIP)",
                        data=zip_result,
                        file_name="split_chapters.zip",
                        mime="application/zip"
                    )