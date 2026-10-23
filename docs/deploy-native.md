# Ubuntu 24.04 原生部署

2026-10-23 用户确认采用 Python venv + systemd，绕过 ECS 无法连接 Docker Hub 的问题。保留 Docker，不改变手机/桌面协议。默认仅监听127.0.0.1:8000；公网反向代理、域名/备案和HTTPS仍待下一阶段。

## 首次安装

安装前确认8000端口未被其他服务占用：`ss -ltnp 'sport = :8000'`。若有监听，停止操作，不终止未知进程。

上传原生部署包到 `/root/idea-echo-native-0.1.0.tar.gz`。先执行：

```bash
apt-get update
apt-get install python3.12-venv ca-certificates
```

确认 `/opt/idea-echo-native/app` 不存在，再新建、解压。下面的 `mkdir` 在目录存在时停止，tar拒绝覆盖已有文件：

```bash
mkdir -p /opt/idea-echo-native
mkdir /opt/idea-echo-native/app
tar --no-same-owner --keep-old-files -xzf /root/idea-echo-native-0.1.0.tar.gz -C /opt/idea-echo-native/app
bash /opt/idea-echo-native/app/deploy/native/install.sh
```

逐条执行，任一步报错就停下。安装器仅支持首次安装，不覆盖现有不同的systemd单元、不替换虚拟环境；失败时保留现场，不删除数据后重试。pip默认使用官方索引；网络/版本/轮子安装报错需先核对，不放宽锁版本或TLS校验。源码和venv由root管理，专用服务账号仅能写 `/var/lib/idea-echo`。

## 创建私人账号并启动

下面会交互输入两次新密码（至少12字符，输入时不显示）。只在服务器输入，不要将密码发给助手：

```bash
runuser -u idea-echo -- env IDEA_ECHO_DATA=/var/lib/idea-echo /opt/idea-echo-native/venv/bin/python -m idea_echo.auth init-user --username owner
systemctl enable --now idea-echo
systemctl is-active idea-echo
curl --fail --max-time 5 http://127.0.0.1:8000/health
ss -ltnp 'sport = :8000'
```

只有看到health成功且监听127.0.0.1才算本机启动通过。不要将8000端口改为0.0.0.0或在安全组开放。检查错误用 `journalctl -u idea-echo -n 60 --no-pager`，分享前遮住私人信息。原生systemd在真实Ubuntu上尚待验，Windows本地配置测试不能代替服务器验收。

## 备份与维护

原Docker备份timer不适用于此模式，不要直接安装它。手动备份到专用目录：

```bash
install -d -m 0700 -o idea-echo -g idea-echo /var/lib/idea-echo/backups
runuser -u idea-echo -- env IDEA_ECHO_DATA=/var/lib/idea-echo /opt/idea-echo-native/venv/bin/python -m idea_echo.backup create --file /var/lib/idea-echo/backups/idea-echo-$(date +%Y%m%dT%H%M%S).zip
```

同机备份不是异地备份，后续需配置自动备份和下载电脑副本。暂停服务可用 `systemctl stop idea-echo`，取消开机启动可用 `systemctl disable idea-echo`，不删除数据。公网HTTPS接入、自动备份和正式升级流程仍需后续配置。
