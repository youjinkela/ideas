# 备份与恢复

备份使用 SQLite backup API，并冻结附件发布/回收，包含当前已引用原图及 SHA256 清单。损坏或缺失的原图会阻止伪成功；登录会话不包含在恢复后的数据库中。

Windows 手动备份：`scripts/backup.ps1 -OutputFile <明确的zip路径>`。校验：

```powershell
.venv/Scripts/python.exe -m idea_echo.backup verify --file <备份zip>
.venv/Scripts/python.exe -m idea_echo.backup restore --file <备份zip> --destination <新的空目录>
```

不覆盖现有目录。恢复后停止服务，再由你确认切换到新数据目录，重新登录并检查图文。原备份保留，恢复失败不要在运行中的目录上反复覆盖。

轮换只处理 `idea-echo-YYYYMMDDTHHMMSS.zip`，保留最新7个有备份的日期和4个ISO周的最新备份；重叠合并。保留点校验通过后才删除多余同名规则文件；其他文件不动。执行前请确认目录：

```powershell
.venv/Scripts/python.exe -m idea_echo.backup rotate --directory <专用备份目录>
```

同一服务器上的备份不是异地备份。至少定期下载一份到电脑/另一存储位置，并实际恢复到空目录核对图片。备份含私人文字和原图，应使用受控存储；不要公开上传。
