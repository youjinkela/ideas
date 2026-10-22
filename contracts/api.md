# API v1

所有 `/v1/` 接口除登录外需要 `Authorization: Bearer <token>`。服务端由会话确定账号。

`PUT /v1/ideas/{uuid}/{record|review|status}` 接受 `{mutation_id, expected_version, payload}`。
首次版本0，成功返回 `{mutation_id, accepted_version}`；重试使用相同 ID 和完全相同请求；版本冲突409并返回当前副本，不覆盖。

record payload 是 `idea.schema.json`（不需要传 raw_version）；review 为 `{reflection}`；status 为 `{value: pending|later|reviewed|archived}`。三者版本分开。

`GET /v1/changes?after=0&limit=100` 使用服务端递增 seq，返回 `{events, next_cursor, has_more}`；event 为 `{seq,kind,entity_id,payload}`，附件事件 kind=attachment。

`PUT /v1/attachments/{uuid}/content` 传已登记清单中附件的原始字节（不是multipart），重复相同内容可重试；GET 同一路径读取私有原图。只有服务端校验成功才 content_ready。

`GET /v1/capabilities` 返回容量和格式限制。错误不会把未上传的记录清空。手机原始 recorded_at 只用于展示，不作为同步游标。
