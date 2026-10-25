# 同步删除更新（2026-10-25）

适用于现有 Ubuntu 24.04 原生安装，不改 Caddy、账号、端口或依赖。电脑与手机需同时使用支持同步删除的新版。

将本机 `artifacts/idea-echo-deletion-2026-10-25.tar.gz` 通过 Workbench 上传到服务器 `/root`，以 root 执行：

```bash
bash <<'UPGRADE_DELETION'
set -euo pipefail
printf '%s\n' '09af2d409c759c70bc436fa2e88cadd2b85406ee8d3f723da990200e70354f92  /root/idea-echo-deletion-2026-10-25.tar.gz' | sha256sum -c -
idea_echo_upgrade=$(mktemp -d /root/idea-echo-deletion.XXXXXXXX)
tar --no-same-owner -xzf /root/idea-echo-deletion-2026-10-25.tar.gz -C "$idea_echo_upgrade"
bash "$idea_echo_upgrade/upgrade-deletion.sh"
UPGRADE_DELETION
```

脚本先运行已有的校验备份，保存上一版服务代码，再离线安装并重启；健康检查失败会恢复上一版代码。更新成功应显示 `"sync_deletion":true`。运行前没有部署成功记录，不应把本地构建视为已更新服务器。

删除操作仅保留防止旧副本复活所需的 UUID。源文字、回顾内容、历史事件和无其他点子引用的图片会清理；其他设备需联网同步。共享图片仅在没有其他点子引用时清理。已导出的 Obsidian 文档保留。历史备份不会自动改写，仍按现有保留周期过期；此前下载的异地备份也不会自动改写。

当前域名备案仍待审核，公网未恢复时不会完成手机/云端同步；删除请求会保存在电脑等待重试。安装包不包含密码、账号或点子数据。
