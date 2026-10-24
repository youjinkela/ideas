# 原生部署备份维护包 2026-10-24

适用：已安装的 Ubuntu 24.04 原生版点子回声，不依赖 Docker，不更换 API、不重启业务服务、不开放端口。

## 安装

先将 `idea-echo-maintenance-2026-10-24.tar.gz` 上传到 `/root`，核对交付说明中的 SHA256，再在 Workbench 执行：

```bash
bash <<'INSTALL_BACKUP'
set -euo pipefail
umask 077
package=/root/idea-echo-maintenance-2026-10-24.tar.gz
test -f "$package"
stage=$(mktemp -d /root/idea-echo-maintenance.XXXXXXXX)
tar --no-same-owner --no-same-permissions -xzf "$package" -C "$stage"
bash "$stage/install-backup.sh"
INSTALL_BACKUP
```

安装程序先校验现有路径与系统配置；遇到不同版本的同名维护文件会停止，不覆盖定制配置。只新增维护脚本、备份服务和定时器。已有点子、账号及运行中的 API 不变。

首次完整备份和空目录试恢复成功后才启用定时器。每天北京时间 03:00 起延迟至多约 6 分钟运行（随机延迟及系统调度精度）；关机错过则在恢复运行后补一次。文件名使用 UTC 时间，并非北京时间。

## 验收

```bash
systemctl is-enabled idea-echo-native-backup.timer
systemctl is-active idea-echo-native-backup.timer
systemctl list-timers idea-echo-native-backup.timer --no-pager
journalctl -u idea-echo-native-backup.service -n 20 --no-pager
ls -lh /var/lib/idea-echo/backups
curl --fail --max-time 5 http://127.0.0.1:8000/health
```

成功日志应有 `"restore_checked": true`、备份文件名和轮换删除数量。一次性备份服务完成后变为 inactive 是正常的；定时器才应保持 active。

每份备份包含数据库与已确认的引用图片，不包含有效登录会话。先检查图像哈希，再恢复到独立临时空目录并检查数据库完整性，成功后原子发布压缩包，最后轮换。保留最近 7 个有备份的日期及 4 个 ISO 周的最新备份，重叠合并；损坏图片或恢复失败时不轮换旧备份。只轮换专用目录内符合 `idea-echo-YYYYMMDDTHHMMSS.zip` 的文件，不处理其他命名文件。

## 日常使用与关闭

```bash
# 手动运行（同一服务不会并行启动多个实例）
systemctl start idea-echo-native-backup.service
# 查看运行结果
journalctl -u idea-echo-native-backup.service -n 20 --no-pager
# 可随时关闭定时器；不删除任何备份
systemctl disable --now idea-echo-native-backup.timer
```

不要绕开 systemd 同时直接启动多个备份脚本。磁盘不足、超时或校验失败会在日志中显示失败；此包尚不包含失败推送告警，需定期检查备份日期与磁盘容量。

## 必须另存一份到电脑

同盘备份不能抵御服务器/磁盘整体丢失。安装成功后，在 Workbench 文件管理器进入 `/var/lib/idea-echo/backups`，下载最新 ZIP 到电脑受控目录；之后至少每周保存一份。ZIP 含私人文字和图片，不要发到聊天或公开目录。已有 SSH 隧道专用密钥不能用于下载，不要放宽它的限制。

从已下载的 ZIP 在电脑进行恢复演练：在项目目录打开 PowerShell，将两个路径替换为真实备份文件和**不存在的新目录**。

```powershell
.venv/Scripts/python.exe -m idea_echo.backup verify --file 'D:/你的私密备份目录/实际文件名.zip'
.venv/Scripts/python.exe -m idea_echo.backup restore --file 'D:/你的私密备份目录/实际文件名.zip' --destination 'D:/你的私密备份目录/新的恢复演练目录'
```

演练不切换正式服务。真正恢复时先停止 API，确认新目录数据完整后再人工切换，重新登录；不要覆盖运行中的数据目录。

## 验证边界

已在本地用临时数据库/图片验证真实备份、恢复和失败保护。Linux 定时器的实际安装、触发和权限限制需要以上服务器验收结果；不能把本地测试当作已经上线。

2026-10-24 已由用户在 ECS 执行安装，首次备份及空目录试恢复成功，日志 `restore_checked: true`，定时器列出下次北京时间 2026-10-25 03:00:08，API 健康检查正常。实际定时触发与下载到电脑后的异地恢复演练仍待验。

原始 Windows 打包文件权限为 0666，root 解压保留该权限时，systemd 校验临时目录中的配置会提示 world-writable。安装脚本已通过 `install -o root -g root -m 0644` 设置正式脚本与两个正式配置的权限；用 `stat` 核对即可，无需重装。上方解压命令增加 `umask 077` 和 `--no-same-permissions`，供后续安装使用；已交付压缩包和校验值没有改变。

后续验收已确认正式三份文件均为 `644 root:root`；2026-10-24 的首次 ZIP 已下载到电脑，整包 SHA256 与服务器一致，独立恢复后数据库、业务记录数量及 2 张图片验证通过。详见 [电脑异地恢复记录](../../docs/diagnostics/2026-10-24-offsite-backup-restore.md)。日历自动触发仍以随后服务器日志为准。

配置依据：[systemd 定时器](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html)、[日历与时区格式](https://www.freedesktop.org/software/systemd/man/latest/systemd.time.html)。
