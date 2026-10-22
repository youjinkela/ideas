# 验收记录

日期：2026-10-22。自动测试只用临时账号、数据库、图片和笔记库，未修改真实 Obsidian 笔记。

- Python服务器/桌面/端到端：最终全量59项通过；有一项上游 Starlette/httpx 测试工具弃用警告。
- 浏览器：最终3项通过，包含草稿切换、HTML不执行、无主动AI调用、目录新建/追加和缺图提示。
- Android：assembleDebug、4项JVM测试、lintDebug、assembleDebugAndroidTest构建成功。lint存在非阻塞警告。
- P40：ANA-AN00/API31，connectedDebugAndroidTest第二轮2项通过、0失败、0错误。覆盖重复保存、Room重开、草稿、图片私有复制、纯图片记录、Keystore加密、连接失败保留队列、恢复服务后上传、重试去重和退出账号保留本机记录。测试库和测试偏好在结束后清理，不清空应用数据。
- P40冷启动：`am start -W`返回Status ok，TotalTime691ms；应用已在手机打开。这个启动检查不替代人工界面验收。
- 备份：空目录恢复、图片校验、损坏拒绝、非空目录拒绝与7日/4周轮换测试通过。
- 未验：真实公网部署、Docker/Linux运行、真实AI服务、真实Windows通知/自启动、华为锁屏后台及重启恢复、正式release签名升级。

真机离线重试通过不可等同于华为锁屏后台全部通过；本轮通过拒绝连接的测试地址模拟网络不可用，未切换手机全局网络。USB测试端口映射已撤销、临时服务已停止；手机当前不连接假生产服务。

APK SHA256：`5f5948a649a3754fc7e105cc91f34388a8d7ffede947622dcc4f8b8aeb53a553`；apksigner验证通过，证书是Android Debug，SHA256指纹`4eeff7981a8d88bf34c7864e2a6958866fbe815a1866e07be07ad8cca49a9140`。

API/数据库测试不能代替系统后台与断电场景；当前只有调试测试包，不宣称生产完全验收。
