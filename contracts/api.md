# API v1

所有 `/v1/` 接口除登录外需要 `Authorization: Bearer <token>`。服务端由会话确定账号。

`PUT /v1/ideas/{uuid}/{record|review|status}` 接受 `{mutation_id, expected_version, payload}`。
首次版本0，成功返回 `{mutation_id, accepted_version}`；重试使用相同 ID 和完全相同请求；版本冲突409并返回当前副本，不覆盖。

record payload 是 `idea.schema.json`（不需要传 raw_version）；review 为 `{reflection}`；status 为 `{value: pending|later|reviewed|archived}`。三者版本分开。

`PUT /v1/ideas/{uuid}/delete` 使用相同 mutation 外壳、空 payload。删除优先于离线旧编辑，不以 expected_version 拒绝已确认删除；重复请求安全。删除清理原文/回顾/状态及其历史事件，并清理未被其他点子引用的图片；保留仅含 UUID 的删除事件 `{kind: delete, entity_id, payload: {id, attachment_ids}}` 供离线设备清理。此后包括旧 mutation 重试在内的记录写入均返回410，不能复活。其他账号不可删除或查询该记录。

桌面离线删除立即移出本机并持久排队，云端/手机删除需完成联网同步。Android 同步先读取删除事件再上传，游标按服务器和账号隔离。已导出 Obsidian 文档保留；历史备份不自动改写，按原有保留策略过期。`/health` 的 `sync_deletion: true` 标记服务器已支持该协议。

`GET /v1/changes?after=0&limit=100` 使用服务端递增 seq，返回 `{events, next_cursor, has_more}`；event 为 `{seq,kind,entity_id,payload}`，附件事件 kind=attachment。

`PUT /v1/attachments/{uuid}/content` 传已登记清单中附件的原始字节（不是multipart），重复相同内容可重试；GET 同一路径读取私有原图。只有服务端校验成功才 content_ready。

`GET /v1/capabilities` 返回容量和格式限制。错误不会把未上传的记录清空。手机原始 recorded_at 只用于展示，不作为同步游标。

`GET /v1/attachments/{uuid}` 返回经过账号验证的附件元数据与 `content_ready`。客户端重新引用图片时以服务器当前状态为准，不能仅依赖很久以前的本地上传记录。
# Restore generation

`GET /v1/changes` additionally accepts optional `generation` and returns the current `generation`. A restored database gets a new generation. Stale generation or an out-of-range cursor returns 409 with `detail={cursor_reset:true,generation:...}`. Desktop resets only its cursor and preserves local drafts/outbox, pulls from zero, then sends pending edits with normal version conflict checks.

