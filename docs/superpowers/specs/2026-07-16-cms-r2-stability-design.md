# CMS 与 R2 稳定上传设计

## 目标

将当前摄影作品集的本地内容后台重构为可测试、可回滚、可安全维护的上传系统。浏览器只访问本机 CMS；本地 Python 服务负责调用受保护的 Cloudflare Worker、更新 SQLite，并在跨系统操作失败时执行补偿清理。

## 已确认的现状

- `cms.html` 的内联 JavaScript 存在语法错误，页面脚本无法正常启动。
- `cms_server.py` 在 `serve_forever()` 之后才定义校验函数与常量。以脚本方式启动后，新建图片组会触发 `NameError` 并断开连接。
- SQLite 未启用外键，当前数据库完整性检查通过，但有 10 条 `photo_items` 记录失去所属图片组。
- 浏览器先上传 R2、再写 SQLite；R2 失败会被忽略，写库失败也不会可靠回滚，容易产生失效链接或云端孤儿对象。
- 批量导入通过 GET 查询参数传递完整 JSON，受 URL 长度、代理和日志泄露影响。
- R2 Worker 允许任意来源上传和删除，没有认证；公开 R2 域名硬编码在源码中，Wrangler 配置没有声明 `MY_BUCKET` 绑定。
- `cms.html` 和 `cms_server.py` 被整个 `upload-tool/` 忽略，没有 Git 历史或可靠回滚点。

## 范围

本次工作覆盖：

- 本地 CMS 前端、Python HTTP API 与 SQLite 访问层。
- 图片组的单张和批量 R2 上传。
- R2 对象删除、失败补偿和连接状态检查。
- `data.js` 与 `commercial.js` 的安全导出。
- R2 Worker 的认证、输入校验、绑定配置和结构化错误响应。
- 自动测试与本地浏览器验收。

本次工作不覆盖：

- 将 SQLite 迁移到云数据库。
- 多用户账号、远程登录或公网 CMS。
- 自动删除现有 10 条孤立数据库记录。
- 未经确认直接部署线上 Worker 或修改线上 R2 内容。

## 架构

### 组件边界

- `upload-tool/cms_server.py`：仅负责本地 HTTP 服务、路由、请求解析和统一 JSON 错误响应。
- `upload-tool/cms_db.py`：负责 SQLite 连接、事务、迁移、查询、排序、导出和数据校验。
- `upload-tool/r2_client.py`：负责带认证调用 Worker、上传、删除、健康检查和错误转换。
- `upload-tool/cms.html`：保留页面结构和样式。
- `upload-tool/cms.js`：负责界面状态、编辑操作、上传队列、进度、失败项重试和提示。
- `upload-tool/r2-upload.js`：只提供受保护的健康检查、上传和删除接口，并通过 `MY_BUCKET` 绑定访问 R2。
- `upload-tool/tests/`：使用临时数据库和模拟 R2，隔离验证各组件。

浏览器不得直接知道 Worker 访问令牌，也不再直接请求 Worker。Python CMS 是浏览器与 R2 之间唯一的协调入口。

### 配置边界

- `upload-tool/cms_config.example.json` 纳入 Git，只描述字段格式。
- `upload-tool/cms_config.json` 保存本机 Worker URL 和访问令牌，继续被 Git 忽略。
- Worker 公开基址是非敏感配置；上传令牌使用 Cloudflare Secret 保存。
- Wrangler 配置显式声明 `MY_BUCKET` R2 binding、必需 secret 和 observability。
- `.gitignore` 改为允许提交 CMS 源码、测试和示例配置，同时继续忽略数据库、媒体缓存、Python 缓存及真实配置。

## 数据流

### 单张上传

1. 浏览器压缩图片并向本地 CMS 提交 multipart 请求，携带图片组、分类和日期。
2. Python 校验图片类型、大小、图片组存在性和日期格式。
3. Python 使用本地令牌调用 Worker 上传接口。
4. Worker 校验 Bearer token、路径、MIME 和请求体后，将请求体流写入 `env.MY_BUCKET`。
5. Worker 返回规范化的 `key` 与公开 `url`。
6. Python 在 SQLite 事务中创建 `photo_items` 记录。
7. 如果第 6 步失败，Python 立即调用 Worker 删除第 4 步创建的对象，并返回包含补偿结果的错误。
8. 浏览器只在两侧均成功后把项目标记为完成。

### 批量上传

1. 浏览器读取文件日期并按月份分组。
2. 对每个月份创建对应图片组，获得真实 `group_id`。
3. 每张图片复用单张上传接口，顺序执行并持续更新进度。
4. 成功项立即从待处理队列移除；失败项保留原因并可单独重试。
5. 批量操作不再使用 `/api/bulk-import-form`，也不通过 URL 查询参数传递 JSON。

### 删除

1. Python 先从 SQLite 读取对象 URL 并提取受限于 `images/` 前缀的 R2 key。
2. Python 同步调用 Worker 删除接口，等待明确结果。
3. R2 删除成功后，Python 在事务中删除数据库记录。
4. 任一步失败均返回结构化错误；前端保留当前状态并允许重试，不再吞掉异常。

R2 与 SQLite 无法共享真正的分布式事务，因此使用“上传后写库、写库失败删除对象”的补偿事务。删除路径选择云端成功后再删本地记录，以避免后台失去重试所需的 key。

## SQLite 与导出

- 每个连接启用 `PRAGMA foreign_keys = ON` 和 `busy_timeout`。
- 初始化时启用 WAL，以减少后台并发读写导致的锁冲突。
- 使用 `PRAGMA user_version` 管理迁移；迁移前创建带时间戳的数据库备份。
- 保留现有孤立记录并在健康状态中报告，未经用户确认不清理。
- 编辑记录时只更新请求明确提供的字段，避免把 `sort_order` 静默重置为 0。
- 排序接口同时校验表名和父字段名，不允许动态 SQL 注入未验证的标识符。
- `data.js` 与 `commercial.js` 先写入同目录临时文件，成功刷新后使用原子替换；任何失败都保留旧文件。

## Worker 安全与稳定性

- 上传、删除和健康检查使用明确路径与方法，不再让任意 DELETE 请求进入删除逻辑。
- 所有写操作要求 `Authorization: Bearer <token>`，并使用 Web Crypto 对固定长度摘要做时序安全比较。
- token 只通过 Worker Secret 注入，不写入源码或普通 `vars`。
- 只接受允许的图片 MIME、合理文件大小、合法分类和 ISO 日期。
- key 使用 `crypto.randomUUID()` 生成，扩展名由经过验证的 MIME 决定。
- 上传时把请求体流直接传给 `R2Bucket.put()`，避免把整个图片复制成额外的 `ArrayBuffer`。
- 删除只允许 `images/` 前缀，支持幂等处理。
- JSON 响应包含稳定的 `ok`、`code`、`message`、`key` 或 `url` 字段；服务端日志使用结构化 JSON。
- Wrangler 配置声明 `MY_BUCKET`、公开基址、必需 secret 和日志观测；真实 bucket 名在部署前由本地配置补齐。

## CMS 交互

- 页面顶部显示数据库状态、R2 配置与连接状态、上次导出结果。
- 加载失败、上传失败和保存失败显示服务端返回的具体原因。
- 保存按钮在请求期间禁用，避免重复提交。
- 新建模式使用显式状态，不再临时覆盖全局 `savePanel()`。
- 图片压缩处理 `onerror`，释放对象 URL，并根据实际输出 JPEG 设置文件名和 MIME。
- 上传完成提示必须反映真实成功数和失败数；存在失败项时不得显示笼统的“上传完成”。

## 测试策略

### Python 自动测试

- 服务入口启动后，新建图片组不再出现 `NameError`。
- 无效 JSON、日期、枚举、ID 和不存在资源返回稳定的 4xx JSON。
- 临时 SQLite 启用外键，删除图片组可级联删除其图片。
- 编辑标题不改变既有排序。
- 模拟 R2 上传成功且写库失败时，会调用删除补偿。
- 模拟 R2 超时、认证失败和异常响应时，不写入 SQLite。
- 导出失败不会覆盖现有 JS 数据文件。

### Worker 自动测试

- 缺少或错误 token 返回 401/403。
- 非图片、超限请求和非法路径返回 400/413。
- 上传把流、MIME 和生成 key 正确交给 R2 binding。
- 删除拒绝 `images/` 之外的 key。

### 前端静态测试

- 从 `cms.html`/`cms.js` 提取的脚本可通过 Node 语法检查。
- 上传队列正确区分成功与失败，失败项可重试。

### 人工验收

- 使用 `http://127.0.0.1:8090` 运行 CMS。
- 按项目 `AGENTS.md` 的三栏、编辑、拖拽、删除、批量上传、导出和静态页面清单逐项验证。
- 使用测试图片验证 R2 上传和删除；部署线上 Worker 前先完成本地或预览环境验证。

## Git 与发布顺序

1. 单独提交本设计文档。
2. 提交测试基线与 CMS 源码跟踪规则。
3. 修复 Python/SQLite 基础稳定性并通过测试。
4. 重构 Worker 与本地 R2 客户端并通过模拟测试。
5. 切换前端单张、批量上传和删除链路。
6. 完成真实 CMS 验收。
7. 用户提供 bucket 名并配置 Worker Secret 后，再部署 Worker。
8. 确认真实上传成功后，导出数据并按现有流程部署静态网站。

每个阶段都必须可独立验证；不提交现有无关删除或用户正在编辑的 `r2-upload.js` 改动，除非该阶段明确接管并保留其语义。
