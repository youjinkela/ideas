# 私人服务器部署（尚未实机验证）

此项目没有购买服务器、域名或代替你开通公网端口。2核2GB是计划基线，不是已经做过负载测试的容量保证。个人公开网站不在这次部署范围内。

准备一台受维护的 Linux、Docker Engine 和 Compose 插件。中国内地公网域名接入条件与备案流程请在购买时向实际服务商确认；条件未完成前先用 SSH 隧道测试，不公开明文登录服务。不要将 SQLite、备份目录或8000端口直接暴露。

将源码放在 `/opt/idea-echo`；复制 `deploy/.env.example` 为 `deploy/.env`，填写实际域名。将域名 DNS 指向服务器，按实际接入要求处理80/443。数据目录应先备份，首次空目录可执行：

```sh
cd /opt/idea-echo
mkdir -p data/server data/backups
sudo chown -R 10001:10001 data/server data/backups
docker compose --env-file deploy/.env -f deploy/compose.yaml config
docker compose --env-file deploy/.env -f deploy/compose.yaml build
docker compose --env-file deploy/.env -f deploy/compose.yaml run --rm api python -m idea_echo.auth init-user --username owner
docker compose --env-file deploy/.env -f deploy/compose.yaml up -d
```

Caddy 为实际域名申请 HTTPS；应用单进程、SQLite WAL。容器非 root，API没有公开注册。首次部署必须验证实际镜像标签可拉取、Linux锁依赖可安装、HTTPS可用、上传下载、重启持久化和资源占用。当前电脑无 Docker，以上容器命令未执行，不标记通过。

每天备份示例见 `deploy/systemd`，安装前检查绝对路径。保持系统更新、SSH密钥登录、限制管理端口；不要把密码放在 shell 历史、命令行参数或聊天中。
