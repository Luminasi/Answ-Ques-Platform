"""包入口：python -m docs_service。

默认监听 127.0.0.1:8000，可用 HOST / PORT 环境变量覆盖。
开发时要热重载，走 python -m uvicorn docs_service.app:app --reload。
"""

import os
import sys

import uvicorn

from docs_service.app import DEFAULT_PORT, app

if __name__ == "__main__":
    # 沿用项目惯例：Windows 控制台默认 GBK，中文日志会乱码
    sys.stdout.reconfigure(encoding="utf-8")

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", str(DEFAULT_PORT)))

    uvicorn.run(app, host=host, port=port, reload=False)
