"""
顶层可执行入口：在项目根目录直接 `python run_baseline.py` 即可。

为什么要有这个文件：rag_baseline/main.py 是包内模块，用相对导入，
只能以 `python -m rag_baseline.main` 或作为包成员调用；
直接执行 `python rag_baseline/main.py` 会报
「attempted relative import with no known parent package」。
这个脚本站在包外面，把入口接出来，任何方式都能直接跑。

注意：语料/库路径是相对路径，先 cd 到本项目根目录再运行。
"""
from rag_baseline.main import main

if __name__ == "__main__":
    main()
