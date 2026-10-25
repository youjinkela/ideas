# 点子回声 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建适配华为 P40 的图文离线记录 App，经私人云端同步到每天 19:00 的电脑回顾页，并按用户选择归档到本地 Obsidian。

**Architecture:** 安卓 App 以本地数据库和私有图片文件为保存起点，云端提供版本化记录与私有附件 API。Windows 伴随程序提供本机回顾网页、提醒和受限笔记库写入。三端共用一份协议与样例，首轮联调用本机服务器，公网部署随后进行。2026-10-25用户取消内置AI，Task9已退役。

**Tech Stack:** Kotlin、Android Views、Room、WorkManager；Python/FastAPI、SQLite；普通 HTML/CSS/JavaScript；Caddy、Linux；pytest、JUnit、Android instrumentation、Playwright。

**Spec:** `D:/obsidian/新建文件夹/发散思考26.10/docs/superpowers/specs/2026-10-22-idea-review-design.md`

## Global Constraints

- 实机为华为 P40，HarmonyOS 3.0.0，按安卓 APK 适配；不以 HarmonyOS NEXT 原生应用为首版目标。
- 记录以一两句话为主，手机界面以快速输入和连续记录为优先。
- 点子记录支持插入图片，手机记录、离线保存、云端同步、电脑回顾和 Obsidian 归档均需保留图片。
- 手机离线也能记录，联网后自动上传。
- 用户主导编辑与筛选，不集成AI；需要时由用户自行在外部工具提问。
- 默认新建一篇笔记，另提供追加到已有笔记的操作。
- 时区固定以 Asia/Shanghai 计算，首版每天 19:00。
- 归档不删除云端原文。
- 不内置模型调用，图片不自动 OCR。
- 不依赖 Google 登录、Firebase 或 Google Play 服务。
- 本文件不授权购买服务器/域名、修改真实笔记、设置系统自启动或部署到公网。

## Review Focus

- 中文、emoji、组合字符、同名标题与 Windows 保留文件名：正文不损坏，归档名称安全且不覆盖；Task 8。
- 点子创建成功但图片只传了一半，同时用户退出 App：旧数据仍可读，未完成附件不误报已同步；Task 3、6。
- 手机时间错误或旧点子补传：列表不漏记录，补提醒按电脑上海日期，不能靠设备时间作为同步游标；Task 2、10。
- 已选目录被移动、链接指向库外、Markdown 文件被 Obsidian 同时修改：停止不安全写入并保留可重试内容；Task 8。
- 私密原文包含 HTML、脚本或图片链接：界面不执行，日志不泄露；Task 7。

---

## 工程位置、现状与执行方式

2026-10-22 只读检查：当前工作目录是 Obsidian 笔记库，不是 Git 仓库；本机 PATH 找到 Python 3.10.11、JDK 17 和 Git，未找到 adb、gradle、docker，常见 Android SDK/Studio 目录也未发现。未遍历所有磁盘，不能据此断言这些工具完全未安装。尚未读取真实训练记录、业务笔记或选择归档库。

建议正式代码位于独立子目录 `D:/obsidian/新建文件夹/发散思考26.10/projects/idea-echo/`（下文 PROJECT）。这是实施默认，可由用户指定其他开发目录；不要在笔记库根目录初始化 Git。执行时先检查目标是否存在和是否有用户改动，再按 worktree 技能选择隔离方式。大体积 SDK、构建输出、数据库、图片、密钥不提交到 Git，也不建议放在 Obsidian 同步范围内。

准备依赖时先核查已安装版本，再按实际权限机制申请下载/安装；不因 SDK 缺失阻塞可独立完成的协议、云端、本机服务和网页任务。Python 正式运行目标为 3.12，当前 3.10 只可用于不依赖新语法的工具检查，不把过期运行时作为公网部署基线。

初始工具链选择（AI 工程决定，不宣称是用户指定）：AGP 8.13.2、Gradle 8.13 wrapper、JDK 17、Kotlin 2.2.21、compileSdk/targetSdk 36、minSdk 26、Room 2.8.5、WorkManager 2.11.2。用 kapt 处理 Room，避免再引入 KSP 版本矩阵。界面采用 Kotlin + XML/ViewBinding，首版无需 Compose。安装前检查实际 P40 API 级别不低于 26；若不符，必须调整基线，不能忽略安装失败。

云端 FastAPI 初始固定 0.159.1，其他依赖在对应 Task 首次完成时解析并锁定，不使用浮动镜像 `latest`。应用 Python 3.12，开发和生产使用同一锁文件；构建工具校验文件一并提交。以上版本来自官方发布说明，执行时若发现兼容/安全问题，先记录原因并更新锁定值，不悄悄换技术栈。

## 文件职责图

所有路径相对于 PROJECT；仅列需要设计边界的文件，其余脚手架由对应 Task 引入。

```text
contracts/                  JSON Schema、API 契约、跨端共同样例
server/idea_echo/
  app.py                    应用工厂与路由注册
  settings.py, db.py        配置、数据库连接/迁移
  auth.py                   登录、账号归属、会话与限流
  records.py, attachments.py 点子版本及附件服务
  backup.py                 一致性数据库+附件备份
server/tests/               API、附件、备份集成测试
android/app/src/main/java/com/ideaecho/app/
  MainActivity.kt           导航与输入入口
  data/                    Room 表、Repository、草稿、附件私有存储
  sync/                    API 客户端、Outbox、SyncWorker
  ui/                      记录、历史、设置与冲突提示
android/app/src/main/res/    布局和文案
android/app/src/test/        状态机与同步单元测试
android/app/src/androidTest/ 持久化、迁移、离线与交互测试
desktop/idea_echo_desktop/
  app.py, settings.py       loopback 服务、本地会话、设置
  cache.py, sync.py         本机缓存与云端队列
  vault.py, archive.py      目录边界、归档与操作日志
  reminders.py              本机提醒
desktop/web/                静态回顾页和归档对话框
desktop/tests/              缓存、安全写入、提醒与旧数据兼容测试
tests/e2e/                 跨服务/浏览器场景；全部用临时笔记库
scripts/                   本地启动、检查、APK 构建/签名与诊断
deploy/                    容器、Caddy、备份调度样例
docs/                      开发说明、真机记录、部署/恢复/维护指南
```

## 跨端接口决定

Task 1 将以下内容写成正式 JSON Schema 和样例；后续任务引用，不能各自发明字段。

- 所有 ID 为 UUID 字符串；时间为带偏移 ISO 8601；账号身份只来自认证会话，不能信任客户端传入的 owner。
- `IdeaRecord = {id, text, recorded_at, attachments: AttachmentDescriptor[], raw_version}`。
- `AttachmentDescriptor = {id, order, mime_type, size_bytes, sha256}`；内容状态由服务端额外返回 `content_ready`，不能由客户端声明。
- `Review = {idea_id, reflection, review_version}`；`Status = {idea_id, value, status_version}`，value 为 `pending|later|reviewed|archived`。
- `Mutation = {mutation_id, expected_version, payload}`；首次 expected_version=0；返回 `{mutation_id, accepted_version}`。相同 ID+相同请求重试返回原确认，不同内容复用 ID 返回 409。
- 独立维护 raw/review/status 版本；某字段版本冲突返回 409 和服务器副本，客户端保留本机副本并提供选择，不静默覆盖。
- `GET /v1/changes?after=<seq>&limit=100` 返回 `{events:[{seq,kind,entity_id,payload}],next_cursor,has_more}`；seq 为服务端递增整数，事务提交后产生；按它增量读取，不按手机时间。
- `POST /v1/auth/login` 返回随机 opaque token；服务端保存 token 摘要，默认有效 30 天；密码用 Argon2id；限制登录频率，不公开注册。`POST /v1/auth/logout` 撤销 token。
- `PUT /v1/ideas/{id}/record`、`PUT /v1/ideas/{id}/review`、`PUT /v1/ideas/{id}/status` 接受 Mutation；每一请求都做账号归属检查。
- `PUT /v1/attachments/{id}/content` 是已登记附件的单文件流式上传；核验尺寸、SHA-256 和真实格式后原子完成。`GET /v1/attachments/{id}/content` 需要认证且归属匹配；没有公开目录挂载。
- `GET /v1/capabilities` 返回文字/图片配额与支持格式。建议初值：正文 100000 字符，单图 20 MiB，单条 20 张/合计 200 MiB，解码上限 100000000 像素；支持 JPEG/PNG/WebP；均为可配置容量保护，不静默转换或丢弃不支持格式。
- 本地 `/local/*` 由桌面会话保护，不暴露云端密钥；`POST /local/archive/preview` 和 `/local/archive/commit` 使用同一个归档 operation_id 及内容快照。
- 目录/搜索接口为 `POST /local/vault/select`（本机目录选择器）、`GET /local/vault/folders`、`GET /local/vault/notes?q=...`；前端不能通过请求设置任意未授权根目录。Task 7 提供设置和入口，Task 8 完成真实目录访问。
- 附件删除先成为清单变更；服务端提交后再回收无引用内容。首版点子本体没有永久删除入口，避免引入不必要的跨端删除合并。

## 里程碑

| 阶段 | 任务 | 可实际体验的结果 |
|---|---|---|
| A | 1–6 | 安装 App，离线存图文，联网后同步到本机测试服务器 |
| B | 7–10（9已退役） | 电脑手动回顾、选择目录归档图文、19:00 提醒 |
| C | 11–12 | 可恢复备份、可升级 APK、真机验收、准备正式部署 |

### Task 1：建立可验证协议与本地健康检查服务

**Files:** 创建 `contracts/api.md`、`contracts/idea.schema.json`、`contracts/fixtures/{text,image-only,conflict,partial-upload}.json`、`server/pyproject.toml`、`server/idea_echo/{app,settings}.py`、`server/tests/test_contracts.py`、`.gitignore`、`scripts/check-environment.ps1`、`docs/environment.md`。

**Interfaces:** 消费本计划接口决定；产出 `create_app(settings: Settings) -> FastAPI`、`GET /health -> {status:"ok",schema_version:1}` 和四份共同样例。Settings 必须支持临时 data_dir，测试不读取生产路径。

- [ ] 写 `test_contract_fixtures`：文字与纯图样例通过，空文字+空附件拒绝，错误 UUID/负 size/重复 order 拒绝；`test_health_is_private_data_free` 断言只有 status、schema_version。
- [ ] 执行 `python -m pytest server/tests/test_contracts.py -q`，确认因缺少契约/工厂而失败。
- [ ] 在独立工程内初始化 Git、Python 3.12 venv、锁文件与环境诊断脚本，实现上述工厂和 Schema；以 `python -m pip install -e "./server[test]"` 安装本地项目，测试 extra 包含 pytest/HTTP客户端/JSON Schema 校验；`.gitignore` 排除 `.venv`、SDK、`.gradle`、数据、附件、签名私钥和本地配置。只复制设计/计划到工程 docs，不移动用户原文件。
- [ ] 重跑同一命令，全部通过；运行环境检查输出工具路径和缺失项，不打印环境变量全集或凭证。
- [ ] `git add` 仅本 Task 文件并提交 `chore: establish idea echo contract and health service`。

### Task 2：实现认证、版本化记录与增量读取

**Files:** 创建 `server/idea_echo/{db,auth,records}.py`、`server/idea_echo/migrations/001_initial.sql`、`server/tests/test_records.py`、`server/tests/test_auth.py`；修改 `server/idea_echo/app.py`、`server/pyproject.toml`。

**Interfaces:** 消费 Mutation/IdeaRecord/Review/Status；产出 `apply_mutation(owner_id: str, kind: str, entity_id: str, mutation: Mutation) -> Ack`、`read_changes(owner_id: str, after: int, limit: int) -> ChangePage` 及登录接口。相同事务内更新实体、确认日志和 seq。

- [ ] 写 `test_retry_after_lost_ack_creates_one_record` 断言两次同请求返回同 Ack 且一条记录；`test_raw_and_review_have_separate_versions`；`test_conflict_preserves_server_copy`；`test_change_cursor_ignores_device_clock`，分别插入过去/未来 recorded_at 仍全量取回；`test_auth_cross_owner_denied`、`test_login_rate_limited`。
- [ ] 执行 `python -m pytest server/tests/test_records.py server/tests/test_auth.py -q`，确认接口未实现而失败。
- [ ] 实现上述服务和路由、Argon2id 单账号 CLI 初始化、token 摘要与过期撤销、数据库迁移及参数化 SQL。所有记录读写都按 owner 过滤；冲突响应不修改服务器值，失败不提交半个事务。
- [ ] 重跑同一测试命令，全部通过；再从空临时库初始化账号、登录、写一条和读取 changes，响应符合 Task 1 样例。
- [ ] 提交 `feat: add authenticated versioned idea synchronization`。

### Task 3：实现私有图片上传与附件完整性

**Files:** 创建 `server/idea_echo/attachments.py`、`server/tests/test_attachments.py`、`server/tests/test_attachment_gc.py`；修改 records/app/settings。

**Interfaces:** 消费附件清单和认证身份；产出 `store_attachment(owner_id: str, attachment_id: str, stream: BinaryIO) -> AttachmentReceipt`、`open_attachment(owner_id: str, attachment_id: str) -> BinaryIO`、`collect_unreferenced(before: datetime) -> int`。缩略图服务同样要求认证。

- [ ] 写 `test_partial_upload_never_marks_content_ready`、`test_same_id_retry_is_idempotent`、`test_wrong_hash_or_mime_rejected`、`test_cross_owner_cannot_download`；`test_gc_keeps_draft_and_pending_references` 断言只删除已过宽限期且无引用文件；参数化测试单图20MiB、总量200MiB、20张、像素上限、JPEG/PNG/WebP 和不支持格式的明确错误。
- [ ] 执行 `python -m pytest server/tests/test_attachments.py server/tests/test_attachment_gc.py -q`，确认失败。
- [ ] 实现流式写入临时文件、完整性检查、原子提交及账号内幂等；服务端只用生成的文件名，图像解码/缩略图并发上限1，保留原文件；GC 宽限期默认7天且只处理已确认无引用文件。
- [ ] 重跑本 Task 测试；中断一次上传再重新上传，检查未完成文件不作为可读取原图返回。
- [ ] 提交 `feat: support private resumable-by-retry image attachments`。

### Task 4：安卓本地数据库、图文草稿与离线首页

**Files:** 创建 `android/{settings.gradle.kts,build.gradle.kts,gradle.properties,gradlew,gradlew.bat}`、wrapper、`android/app/build.gradle.kts`、`AndroidManifest.xml`、`MainActivity.kt`、`data/{AppDatabase,IdeaEntity,AttachmentEntity,DraftEntity,IdeaDao,CaptureRepository,AttachmentStore}.kt`、`ui/CaptureFragment.kt`、布局、`androidTest/CapturePersistenceTest.kt`；补全 `docs/environment.md`。

**Interfaces:** `saveCapture(text: String, attachments: List<LocalAttachment>, saveId: UUID): UUID`；`observeDraft(): Flow<CaptureDraft>`；`saveDraft(draft: CaptureDraft)`；`importImage(uri: Uri): LocalAttachment`。本地未认领 owner 为 null，登录前也可记录；saveId 防双击。

- [ ] 写 `CapturePersistenceTest`：首装断网图文/纯图保存后重新打开数据库仍在；`doubleSaveWithSameIdCreatesOneIdea`；`failedImageCopyKeepsDraft`；`draftSurvivesRecreation`。Room v1 Schema 导出并纳入版本库。
- [ ] 配置核实后的 SDK 和 wrapper，运行 `android/gradlew.bat -p android connectedDebugAndroidTest`，确认在已连接测试设备/模拟器上因缺实现失败；若当前无设备，不将编译失败或未运行包装成红灯测试结果，继续可运行的 JVM 部分并记录实机待验。
- [ ] 实现原生首页、多图选择器（旧系统走系统文档选择，不依赖新版 Photo Picker/Google 服务）、图片私有复制、缩略图/大图/顺序/移除、历史页和图文草稿事务。首版不接入直接拍照按钮；用户此前尚未确认需要，选取系统图片足够满足插图。
- [ ] 运行 `android/gradlew.bat -p android assembleDebug testDebugUnitTest lintDebug` 和有设备时的 instrumentation 测试；生成 debug APK，离线首装即可输入，不强迫登录。
- [ ] 提交 `feat: add offline android capture with local images`。

### Task 5：安卓持久上传队列、账号认领与冲突处理

**Files:** 创建 `data/{OutboxEntity,AccountStore}.kt`、`sync/{IdeaApi,SyncRepository,SyncWorker}.kt`、`ui/{SettingsFragment,ConflictFragment}.kt`、`src/test/.../SyncRepositoryTest.kt`、`src/androidTest/.../OutboxMigrationTest.kt`；修改 Repository、数据库和 manifest。

**Interfaces:** `syncOnce(accountId: String): SyncResult`；`enqueueSync(accountId: String)`；`claimLocalRecords(accountId: String, ids: List<UUID>)`；`resolveConflict(id: UUID, choice: ConflictChoice)`。网络客户端以 HTTPS 为生产要求；本地 HTTP 仅 debug 构建且限制明确测试主机，release 禁止全局明文放行。

- [ ] 写 `SyncRepositoryTest`：丢 Ack 重试 mutation_id 不变；旧版 Ack 不清除新版 outbox；401 保留队列；切换账号不上传旧账号记录；409 保留本机与云端并可选合并；首次认领需要用户确认；Room 升级保留待传正文和图片引用。
- [ ] 运行 `android/gradlew.bat -p android testDebugUnitTest`，确认新增测试失败。
- [ ] 实现事务 outbox、唯一 WorkManager 网络约束任务、网络失败退避、前台主动补传和手动重试；附件流独立上传，只有全部对应版本确认才显示已同步；token 用 Android Keystore 保护后保存，不输出到日志。
- [ ] 重跑 JVM 测试和设备迁移测试；用 Task 2/3 本机服务联调，证明正文与附件未全部确认时始终显示待传。
- [ ] 提交 `feat: synchronize android outbox without losing offline edits`。

### Task 6：验证真实手机离线、联网和后台行为

**Files:** 创建 `android/app/src/androidTest/java/com/ideaecho/app/OfflineSyncScenarioTest.kt`、`tests/e2e/test_mobile_api_contract.py`、`docs/p40-verification.md`、`scripts/run-local-server.ps1`；必要时修正 Task 4/5 文件。

**Interfaces:** 消费 APK、本机 API 与同步诊断页；产出可复现的实机检查记录，每项含操作、预期、观察、日志定位；没有设备的项标记未验，不能自动打勾。

- [ ] 写场景断言：离线两条文字+一条纯图，重开内容不变；上传中断/退后台后最终服务端每个ID恰一份；设备时间偏差一天仍同步完整；强制停止后再次打开可恢复；旧 APK 升级迁移后待传图文完整。
- [ ] 先执行 `python -m pytest tests/e2e/test_mobile_api_contract.py -q`，确认缺少联调入口的失败，再补入口；设备步骤需用户连接手机并允许 USB 调试，不能伪造运行结果。
- [ ] 实现不含正文/凭证的诊断页和本地联调脚本，分别记录前台、后台、划掉任务、系统回收、强制停止和重启；按 P40 实际行为补充后台运行设置说明。
- [ ] 运行 API 场景和设备场景，通过项填入实际证据；不要求后台秒级执行，必须满足前台兜底。联调服务只在用户需要手机测试时开放指定局域网接口，不创建公网暴露。
- [ ] 提交 `test: verify p40 offline capture and background synchronization`。

### Task 7：Windows 本机缓存与可编辑的回顾网页

**Files:** 创建 `desktop/pyproject.toml`、`desktop/idea_echo_desktop/{app,settings,cache,sync}.py`、`desktop/web/{index.html,app.js,styles.css}`、`desktop/tests/test_cache.py`、`tests/e2e/review.spec.js`、`package.json`、`package-lock.json`、`playwright.config.js`。

**Interfaces:** `sync_cloud(settings: DesktopSettings) -> SyncSummary`；`save_reflection(idea_id: str, text: str, expected_version: int) -> LocalReview`；`GET /local/ideas?view=pending|all`；loopback 绑定 `127.0.0.1:47821`，冲突自动选择空闲本机端口并更新允许 Origin。

- [ ] 写缓存测试：断网编辑重启后仍在；changes 多页全量取回；错时钟点子不丢。浏览器测试 `review.spec.js` 断言切换点子保留草稿、旧待回顾可见、图片待传占位、原文含 `<script>` 不执行、切换/编辑绝不调用 AI。
- [ ] 执行 `python -m pytest desktop/tests/test_cache.py -q` 与 `npx playwright test tests/e2e/review.spec.js`，确认失败。
- [ ] 实现本机缓存/outbox、文件选择设置入口、回顾两栏、原图查看、自动保存提示、待回顾/已回顾/已归档过滤；正文用 textContent 或安全 Markdown 渲染，禁用原生 HTML。用 `python -m pip install -e "./desktop[test]"` 安装本机服务；Node 项目只含 Playwright 测试依赖，不引入生产前端构建链，锁定 npm 依赖。会话用 HttpOnly/SameSite=Strict cookie，校验 Host、Origin 和 CSRF；启动令牌不写 URL 查询或访问日志。
- [ ] 重跑测试；暂停云端服务后回顾、编辑、重启，再恢复同步，确认无数据丢失和伪成功提示。
- [ ] 提交 `feat: add private desktop review with durable local edits`。

### Task 8：可恢复的 Obsidian 图文新建与追加

**Files:** 创建 `desktop/idea_echo_desktop/{vault,archive}.py`、`desktop/tests/{test_vault,test_archive,test_archive_recovery}.py`；修改本机 app 和网页归档对话框。

**Interfaces:** `list_folders(vault_root: Path) -> list[str]`；`search_notes(vault_root: Path, query: str) -> list[NoteTarget]`；`preview_archive(request: ArchiveRequest) -> ArchivePreview`；`commit_archive(operation_id: str) -> ArchiveReceipt`。ArchiveRequest 含 idea_id、版本、模式new/append、相对目标、正文快照、附件清单；commit 不重新从当前编辑区取内容。

- [ ] 写参数化测试：中文/emoji/空标题/CON/尾空格/同名标题、`..`/绝对路径/NTFS链接/隐藏配置；正文含伪造归档标记不能制造假成功。测试写图后崩溃、追加后未回Ack、外部编辑、磁盘失败、缺图；重试只有一个操作标记且原正文完整。
- [ ] 执行 `python -m pytest desktop/tests/test_vault.py desktop/tests/test_archive.py desktop/tests/test_archive_recovery.py -q`，确认失败。
- [ ] 实现授权库选择、目录/笔记搜索、预览、操作日志、附件校验与暂存、可恢复提交；默认附件目录为目标笔记旁 `_attachments`，按稳定 ID 命名。新建采用无覆盖创建；追加检测目标快照变化并保持原换行/编码，保留恢复副本。相对图片 URL 按 Markdown 规则转义，兼容空格/中文；不使用云端地址。
- [ ] 重跑测试；只用临时库模拟两个目标目录、新建、追加、重复重试和中断恢复，再断开云端检查图文可读；跨站请求与库外写入均拒绝。
- [ ] 提交 `feat: archive reviewed ideas and images safely into obsidian`。

### Task 9：已取消内置 AI（2026-10-25）

用户选择在外部AI工具中自行提问，认为集成会使记录工具臃肿。原模型适配器、路由、侧栏和配置入口已从当前范围撤销，不再作为待接通功能。

- 保留用户手动编辑、同步、提醒与归档能力；回顾页改为两栏。
- 不删除旧版本可能已有的对话表和加密配置，不新增模型账号或密钥要求。
- 用兼容性及浏览器回归确认模型入口移除，原始图文、手动编辑与新建/追加归档不受影响。

### Task 10：19:00 提醒、补提醒与可选自启动

**Files:** 创建 `desktop/idea_echo_desktop/reminders.py`、`desktop/tests/test_reminders.py`、`scripts/start-desktop.ps1`、`scripts/configure-startup.ps1`、`docs/desktop-setup.md`；修改本机设置页。

**Interfaces:** `reminder_due(now: datetime, last_sent_day: date | None, pending_count: int) -> bool`；`send_reminder(review_url: str) -> NotificationResult`。使用 zoneinfo 和 Windows tzdata；当天提醒记录持久化，默认关闭自动打开浏览器，仅用户点击通知时打开。

- [ ] 写固定时钟测试：18:59不提醒、19:00提醒、有旧待回顾也提醒、20:00首次登录补提醒、唤醒重复触发只提醒一次、次日重新可提醒、无待回顾不提醒、通知权限失败仍显示页面提示。
- [ ] 执行 `python -m pytest desktop/tests/test_reminders.py -q`，确认失败。
- [ ] 实现通知适配器和启动/唤醒检查；提供用户主动开启/撤销的 HKCU 登录自启动设置与状态检查，不在测试或安装时默认修改真实系统配置。
- [ ] 重跑测试，用假通知适配器验证点击目标 URL；真实系统通知、自启动只在用户启用后验收。
- [ ] 提交 `feat: add daily desktop review reminders with catch-up`。

### Task 11：备份恢复与小服务器部署包

**Files:** 创建 `server/idea_echo/backup.py`、`server/tests/test_backup.py`、`deploy/{Dockerfile,compose.yaml,Caddyfile,.env.example}`、`deploy/systemd/idea-echo-backup.timer`、`scripts/{backup,restore}.ps1`、`docs/{deploy,backup-restore,maintenance}.md`。

**Interfaces:** `create_backup(data_dir: Path, destination: Path) -> BackupManifest`；`verify_backup(path: Path) -> VerificationResult`；`restore_backup(source: Path, empty_destination: Path) -> None`，只向显式空目录恢复，不覆盖运行中数据库。清单记录数据库与每个已引用附件 SHA-256。

- [ ] 写 `test_backup_restores_database_and_images`、`test_backup_during_upload_has_consistent_references`、`test_restore_refuses_nonempty_destination`、`test_corruption_detected`、`test_secrets_and_text_not_in_logs`。
- [ ] 执行 `python -m pytest server/tests/test_backup.py -q`，确认失败。
- [ ] 实现 SQLite backup API 和附件固定引用快照，备份/GC 互斥，默认保留7个日备份+4个周备份。部署一份应用进程、反向代理和持久卷；默认不公开注册，配置附件配额/磁盘余量，健康检查不泄露信息。备份导出电脑路径需用户配置，不把同服务器副本称为异地备份。
- [ ] 重跑测试；本地/临时环境执行备份-校验-恢复，核对附件 hash；有 Docker 时执行 `docker compose -f deploy/compose.yaml config`。真实域名、备案、HTTPS、公网端口和服务器账号留待用户具备条件后执行；未执行的部署步骤不标记通过。
- [ ] 提交 `ops: package lightweight deployment and verified backups`。

### Task 12：签名 APK、端到端验收与交付

**Files:** 创建 `scripts/build-apk.ps1`、`tests/e2e/test_full_journey.py`、`docs/{acceptance,release,learning-roadmap}.md`；更新 README 和各组件锁文件/迁移记录。

**Interfaces:** 固定包名 `com.ideaecho.app`；debug 与 release 分开。release 签名文件路径与密码从用户安全配置注入；不会在用户未提供的情况下虚构生产签名。交付源码、构建命令、APK hash、版本号及实测清单。

- [ ] 写全流程测试：文字+两图从 API 上传→本机回顾→用户修改→选择两种归档→断网查看本地图片→重试不重复；另外覆盖409冲突和模型超时不影响归档。测试不涉及真实笔记库或计费模型。
- [ ] 执行 `python -m pytest tests/e2e/test_full_journey.py -q`，确认未完成连接的场景失败，再补齐必要组件连接。
- [ ] 完成构建/签名脚本、版本和迁移记录、用户持有签名密钥的备份步骤；提供环境、部署、维护、恢复的学习顺序。对未验证的 P40/正式服务器项目保留明确待验状态。
- [ ] 运行 `python -m pytest server/tests desktop/tests tests/e2e -q`、Playwright 浏览器场景、Android `assembleDebug testDebugUnitTest lintDebug`、有设备时 `connectedDebugAndroidTest`；每类一次完整运行，只有新变更/失败时重跑相关范围。审查权限、无内置模型入口、脱网附件和备份证据；记录实际结果，不能用接口测试代替实机后台测试。
- [ ] 提交 `release: document verified idea echo workflow and artifacts`；按分支收尾技能报告集成选项，不擅自推送远程、购买或部署。

## 需求覆盖与计划自审

- 设计§1–4：Task 1、4–6；图片端到端为 Task 3、4、6–8、11、12。
- 设计§5：Task 1–3、5、7；版本冲突、幂等、迟到事件都有具名测试。
- 设计§6：Task 7、10；19:00/时区/补提醒/可选自启动已覆盖。
- 设计§7：Task 8、12；选择目标库、不覆盖、追加防重复、离线图片均覆盖。
- 设计§8：Task 9；没有用户提供模型凭证也能开发验收其余功能。
- 设计§9：Task 1、11、12；没有服务器/域名也能完成本地验证，公网动作单独等待真实条件。
- 设计§10十五项场景：分别落在 Task 2、3、4、5、6、8、9、10、11、12；未具备设备时不得报告完全验收。
- Review Focus 五类输入：已分别加入 Task 2/3/6/7/8/9/10 的测试步骤；签名升级和 Room 迁移由 Task 5/6 覆盖。
- 无永久删除、没有直接拍照、没有图库 AI/OCR、没有公开个人网站；这些未确认扩展不进入首版实现。

## 官方工具链参考

- [AGP 8.13 兼容表：Gradle 8.13、JDK 17](https://developer.android.com/build/releases/agp-8-13-0-release-notes)
- [Room 发布说明](https://developer.android.com/jetpack/androidx/releases/room)
- [AndroidX 版本列表](https://developer.android.com/jetpack/androidx/versions)
- [FastAPI 发布说明](https://fastapi.tiangolo.com/release-notes/)

## 实施交接

该计划未执行任何产品代码、安装、APK构建、真实笔记归档或公网部署。建议由当前会话逐项实施，在阶段节点进行独立审查；跨端共享协议较多，连续执行可减少接口偏差。若用户选择子代理逐项实施，则每个任务使用独立实现与审查流程。执行前保留用户选择的方法，不反复询问已经作出的决定。
