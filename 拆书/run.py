import streamlit.web.cli as stcli
import os, sys


def resolve_path(path):
    """获取脚本的绝对路径，确保跨平台/跨目录移动后依然有效"""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), path))


if __name__ == "__main__":
    # 您的核心代码文件名
    target_script = "拆书.py"

    # 构造类似于命令行 'streamlit run 拆书.py' 的参数
    # sys.argv[0] 是脚本名，sys.argv[1] 开始是参数
    sys.argv = [
        "streamlit",
        "run",
        resolve_path(target_script),
        "--global.developmentMode=false"
    ]

    # 调用 streamlit 的入口函数
    sys.exit(stcli.main())