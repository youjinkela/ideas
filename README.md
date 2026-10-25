# 点子回声（ideas）0.1.0（测试版）

安卓离线图文记录 → 私人云收件箱 → Windows 回顾页 → 用户选择 Obsidian 目录归档。目标是在电脑白天关机时也能经云端接收点子。由你自行筛选、整理和补充想法；工具不集成 AI，需要时使用自己的外部 AI 工具。

手机从左到右为“随手记 → 已记录 → 设置”，默认打开最左侧随手记，通过左右滑动切页。添加图片和保存固定在随手记底部，键盘弹出时操作栏位于键盘上方；切页保留草稿与未提交的设置内容。

电脑回顾页右上角“添加点子”支持文字、图片和纯图片，保存后立即进入收件箱。首次使用先在设置中登录账号；已有账号断网时也能先存电脑，再随同步上传云端。取消窗口会保留当前页面中的输入，刷新或关闭前请先保存。

2026-10-25 状态：ECS 原生服务、自动备份安装、首次凌晨定时触发及电脑异地恢复已验收；Windows 通知与自启动已启用。P40 在 USB 供电及单 App 后台数据例外条件下，15 分钟熄屏图文上传和最终真机断言通过。正式域名备案已提交、审核中，等待通过后的公网联调；未充电深度待机、实际重启、系统回收恢复及正式签名仍单独待验。

## 本机启动

回顾页支持红色“留待下次 / 已回顾”和黑色“无价值”操作；“无价值”确认后删除源点子与不再共用的图片，电脑离线排队，云端和手机联网同步后删除。已导出的 Obsidian 文档、历史备份保留。此功能需要更新手机与服务器；原生 ECS 更新步骤见[同步删除更新说明](docs/deletion-upgrade.md)。

在项目根目录使用 PowerShell。需要 Python 3.12、JDK 17；Android 构建另需 SDK 36/build-tools 35。

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.lock
.venv/Scripts/python.exe -m pip install --no-deps -e ./server -e ./desktop
.venv/Scripts/python.exe -m idea_echo.auth init-user --username owner --data-dir data/server
./scripts/start-server.ps1
```

另开终端执行 `./scripts/start-desktop.ps1`。设置中登录本机测试地址 `http://127.0.0.1:8000`，选择笔记库。只有用户点击归档才写入笔记；请先选一个空的测试库。

手机无服务器也能保存文字和图片。USB 联调时执行项目 SDK 中的 `adb reverse tcp:8000 tcp:8000`，手机设置同一本机地址。生产环境必须 HTTPS，正式服务器未部署前，不承诺跨网络自动同步。

## 验证与构建

```powershell
.venv/Scripts/python.exe -m pytest server/tests desktop/tests tests/e2e -q
npm.cmd ci
npm.cmd test
./scripts/build-apk.ps1 -Verify
```

调试 APK 位于 `android/app/build/outputs/apk/debug/app-debug.apk`。这是调试签名，不是用户持有密钥签名的正式发布包。不要卸载应用来解决签名冲突，否则会丢失本机未同步数据。

## 文档

中国内地 ECS 无法连接 Docker Hub 时，本项目已提供[Ubuntu 24.04 原生部署](docs/deploy-native.md)。这与 Docker 部署二选一，不要同时运行两个服务占用8000端口。

- [实测和待验清单](docs/acceptance.md)
- [电脑端设置](docs/desktop-setup.md)
- [部署](docs/deploy.md)、[备份恢复](docs/backup-restore.md)、[维护](docs/maintenance.md)
- [版本与签名](docs/release.md)、[服务器学习顺序](docs/learning-roadmap.md)
- [P40 后台验收与隔离测试工具](docs/p40-verification.md)

源码位于独立 Git 子项目。`.tooling`、`.venv`、`data`、密钥与构建产物不提交；若此父目录参与 Obsidian 同步，请排除整个 `projects/idea-echo`，避免同步大型 SDK 和私有缓存。
