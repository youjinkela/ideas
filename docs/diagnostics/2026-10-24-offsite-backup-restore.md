# 2026-10-24 电脑异地备份与恢复验收

用户提供的服务器 SHA256：`d6231dfe01a4e6d39ef8afc559fcad6f22688bc53d80c45bd2e5fe684c826a8f`。

下载文件：`C:/Users/zs/Downloads/idea-echo-20261024T052103.zip`。本机实测 SHA256 与服务器一致，备份清单及所有文件哈希验证通过。

恢复位置：`D:/obsidian/新建文件夹/发散思考26.10/projects/idea-echo/data/restore-drills/ecs-20261024T052103-cc8f4c5017f14f348501f4cbc1492642`。该目录是新建的独立演练副本，没有切换正式服务。

实际验证结果：

- SQLite integrity_check 为 ok，foreign_key_check 无错误，数据库版本保持一致。
- users、entities、events、mutations、attachments、attachment_refs 的记录数量与压缩包原数据库逐表一致。核对只输出成功与否，没有输出点子正文、用户名、密码哈希或令牌。
- 已确认且被引用的 2 张图片与数据库描述中的 SHA256 一致，与备份清单中的图片总数一致，并通过 Pillow 图片文件验证。
- 恢复后的 sessions 数量为 0，同步 generation 已重新生成。
- 正式备份文件、手机数据和正在运行的电脑/服务器服务没有改变。演练副本保留在项目被 Git 忽略的 data 目录内。

用户同时提供服务器正式文件权限：备份 service、timer、runner 均为 `644 root:root`，确认临时解压文件的 world-writable 警告没有遗留到正式安装目标。

验证工具说明：首次额外计数核对使用 SQLite 内存反序列化读取 WAL 数据库失败，恢复本身已经完成；改为临时解压原数据库只读查询后核对通过。临时目录访问另受 Windows 沙箱限制，获准后完成检查。该过程不涉及应用代码修复，也不表示原备份或生产数据库损坏。

当前已完成首次服务器备份、同机试恢复、电脑下载校验、电脑独立恢复。2026-10-25 凌晨的首次日历自动触发尚未观察；备案后的公网同步等其他待验项保持独立记录。
