"""包入口：python -m rag_service。

默认监听 127.0.0.1:8001 —— 文档服务占了 8000，两个服务都要提供 /api/health，
同端口会冲突。可用 HOST / PORT 环境变量覆盖。

开发时要热重载，走 python -m uvicorn rag_service.app:app --reload。
"""

import os
import sys

import uvicorn

from rag_service.app import app
from rag_service.config import DEFAULT_PORT

if __name__ == "__main__":
    # 沿用项目惯例：Windows 控制台默认 GBK，中文日志会乱码
    sys.stdout.reconfigure(encoding="utf-8")

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", str(DEFAULT_PORT)))

    print(f"正在启动 rag_service（http://{host}:{port}），首次启动要加载向量库与精排模型……")
    uvicorn.run(app, host=host, port=port, reload=False)
