# 验收记录

日期：2026-10-22。自动测试只用临时账号、数据库、图片和笔记库，未修改真实 Obsidian 笔记。

- Python服务器/桌面/端到端：58项通过；新增多进程提醒测试另8项提醒测试通过，最终全量待更新。
- 浏览器：此前3项通过，包含草稿切换、HTML不执行、无主动AI调用、目录新建/追加和缺图提示。
- Android：assembleDebug、4项JVM测试、lintDebug、assembleDebugAndroidTest构建成功。lint存在非阻塞警告。
- P40：已识别ANA-AN00/API31，用户已授权USB调试；connectedDebugAndroidTest进行中，不能预先报告通过。
- 备份：空目录恢复、图片校验、损坏拒绝、非空目录拒绝与7日/4周轮换测试通过。
- 未验：真实公网部署、Docker/Linux运行、真实AI服务、真实Windows通知/自启动、华为锁屏后台及重启恢复、正式release签名升级。

完成真机测试后更新结果。API/数据库测试不能代替系统后台与断电场景；当前只有调试测试包，不宣称生产完全验收。
