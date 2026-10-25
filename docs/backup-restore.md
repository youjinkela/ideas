# 备份与恢复

备份使用 SQLite backup API，并冻结附件发布/回收，包含当前已引用原图及 SHA256 清单。损坏或缺失的原图会阻止伪成功；登录会话不包含在恢复后的数据库中。

Windows 手动备份：`scripts/backup.ps1 -OutputFile <明确的zip路径>`。校验：

```powershell
.venv/Scripts/python.exe -m idea_echo.backup verify --file <备份zip>
.venv/Scripts/python.exe -m idea_echo.backup restore --file <备份zip> --destination <新的空目录>
```

不覆盖现有目录。恢复后停止服务，再由你确认切换到新数据目录，重新登录并检查图文。原备份保留，恢复失败不要在运行中的目录上反复覆盖。

恢复会生成新的同步代次；电脑检测到代次变化后从头重拉事件，不丢弃本机待传编辑。这样即使恢复较早备份、服务器序号回退，也不会因为电脑仍记着较大的游标而漏收新点子。

轮换只处理 `idea-echo-YYYYMMDDTHHMMSS.zip`，按文件名中的 UTC 日期和 ISO 周分组，保留最新7个有备份的日期和4个ISO周的最新备份；重叠合并，同一天只保留较新恢复点。文件名的 UTC 日期与北京时间日期可能不同。保留点校验通过后才删除多余同名规则文件；其他文件不动。执行前请确认目录：

```powershell
.venv/Scripts/python.exe -m idea_echo.backup rotate --directory <专用备份目录>
```

同一服务器上的备份不是异地备份。至少定期下载一份到电脑/另一存储位置，并实际恢复到空目录核对图片。备份含私人文字和原图，应使用受控存储；不要公开上传。

## Ubuntu 原生版自动备份

当前 ECS 使用原生版，不使用 `deploy/systemd` 下的 Docker 备份服务。新增维护包的安装、首次演练、每天北京时间 03:00 定时任务、关闭方式和下载异地副本步骤见 [原生备份维护说明](../deploy/native/BACKUP-README.md)。服务器执行安装前，仍不能视为已开启自动备份。
