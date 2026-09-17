"""
题集：15 道库内题（分三组）+ 5 道拒答题。

每题三个字段：
  q     问题（原样丢给 RAG，不做任何改写 —— 测的就是裸流水线的本事）
  src   该被检索到的那篇文档。可以写多篇：命中其中任意一篇都算对。
        **必须是列表** —— 写成字符串不会报错，但会静默退化成子串匹配
        （"a/cor.md" 能命中 "a/cors.md"），分数虚高。只写一篇也要 [] 包起来。
                写法是 data/fastapi_docs 下的**相对路径 + 正斜杠**。

        ⚠️ 别信「和库里 metadata["source"] 一模一样」—— 那句是错的，原文已删。
        库里存的其实是**反斜杠**（Windows 的 os.path.relpath 产物）：
            库里    'advanced\\websockets.md'
            题集    'advanced/websockets.md'
        两边**不一样**。能对上，是因为匹配时 eval.norm() 把**两侧都**折成
        「正斜杠 + 小写」再比（见 Eval/eval.py:71）。所以你照正斜杠写就对。
  must  答案里应该出现的关键词（只在 CHECK_ANSWER=True 时用，英文不区分大小写）

加题就照抄一个字典改内容。选题的判断标准只有一条：
**这道题的答案只应该来自 src 里那几篇** —— 如果好几篇文档都能答，要么把 src 写全，
要么这题不合格（它测不出东西，因为怎么检索都算对）。

三组不是凑数：A 组测「词对得上」的情况，C 组测「词对不上、只有意思对得上」的情况。
真实用户问的是 C 组那种。以后加优化（改写、混合检索、精排），看哪一组涨得最多，
就知道那个优化在治什么病。
"""

GROUPS = {
    "A 组 · 词面直白（文档里就叫这个词）": [
        {"q": "CORS 是什么？怎么在 FastAPI 里配置？",
         "src": ["tutorial/cors.md"],
         "must": ["allow_origins"]},

        {"q": "怎么用 FastAPI 上传文件？",
         "src": ["tutorial/request-files.md", "tutorial/request-forms-and-files.md"],
         "must": ["UploadFile"]},

        {"q": "怎么添加后台任务？",
         "src": ["tutorial/background-tasks.md"],
         "must": ["BackgroundTasks"]},

        {"q": "FastAPI 怎么做依赖注入？",
         "src": ["tutorial/dependencies/index.md",
                 "tutorial/dependencies/classes-as-dependencies.md",
                 "tutorial/dependencies/sub-dependencies.md",
                 "tutorial/dependencies/dependencies-with-yield.md"],
         "must": ["Depends"]},

        {"q": "怎么写 WebSocket 接口？",
         "src": ["advanced/websockets.md"],
         "must": ["WebSocket"]},
    ],

    "B 组 · 换个说法（概念对得上，字面不一样）": [
        {"q": "怎么限制查询参数的最大值和最小值？",
         "src": ["tutorial/query-params-str-validations.md",
                 "tutorial/path-params-numeric-validations.md"],
         "must": ["Query"]},

        {"q": "怎么控制接口返回的数据结构？",
         "src": ["tutorial/response-model.md"],
         "must": ["response_model"]},

        {"q": "一次请求里要怎么接收多个请求体参数？",
         "src": ["tutorial/body-multiple-params.md"],
         "must": ["Body"]},

        {"q": "怎么用中间件给每个请求计时？",
         "src": ["tutorial/middleware.md", "advanced/middleware.md"],
         "must": ["middleware"]},

        {"q": "接口报错时怎么返回自定义的错误信息？",
         "src": ["tutorial/handling-errors.md"],
         "must": ["HTTPException"]},
    ],

    "C 组 · 口语化（文档里根本不出现这些词）": [
        {"q": "前端调我的接口被浏览器拦住了，说是跨域，怎么办？",
         "src": ["tutorial/cors.md"],
         "must": ["CORSMiddleware"]},

        {"q": "程序启动时要连数据库、关闭时要断开，这段代码写哪儿？",
         "src": ["advanced/events.md"],
         "must": ["lifespan"]},

        {"q": "怎么让某个接口必须登录才能用，没登录就报错？",
         "src": ["tutorial/security/first-steps.md",
                 "tutorial/security/index.md",
                 "tutorial/security/get-current-user.md",
                 "advanced/security/http-basic-auth.md"],
         "must": ["401"]},

        {"q": "用户登录之后，我想给他发一个 Cookie 记着，怎么写？",
         "src": ["advanced/response-cookies.md"],
         "must": ["set_cookie"]},

        {"q": "上线部署的时候怎么用 Docker 打包？",
         "src": ["deployment/docker.md"],
         "must": ["Dockerfile"]},
    ],
}

# ---------- 拒答题 ----------
# 库里**根本没有答案**的问题。正确答案是「不知道」，不是「找个最像的答一遍」。
#
# ⚠️ 故意**不放进 GROUPS** —— GROUPS 里的每一题都会被算进 Hit@K，
# 而拒答题的标准答案是「哪篇都不该命中」。混进去它只会永远判 ❌，
# 把 Hit@1 那些数悄悄拉低。**分母被污染是不报错的**，所以从结构上隔开。
#
# 选题有两类，因为它们考的是不同难度：
#   远的（红烧肉、电影）  —— 语义上八竿子打不着，应该很好拒
#   近的（Django、GC）    —— **陷阱题**：同为 Python / Web 话题，
#                            词面高度接近，嵌入距离会被拉得很近。
#                            阈值守卫真正的对手是这一类，不是前一类。
REFUSALS = [
    # 远的
    "红烧肉怎么做才好吃？",
    "推荐几部科幻电影",
    "怎么用 Excel 做数据透视表？",
    # 近的（陷阱题）
    "怎么用 Django 写一个博客系统？",
    "Python 的垃圾回收是怎么工作的？",
]
