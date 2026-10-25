# 0.1.0 测试版

Android包名 `com.ideaecho.app`，versionCode1，minSdk26，targetSdk36。P40实际API31。当前交付调试签名 APK，仅用于验收与个人试用。

`scripts/build-apk.ps1 -Verify` 构建 APK、JVM测试、lint及真机测试包；它不声称已经运行真机测试。`-Release` 目前输出未签名release，不会伪造生产签名。

正式发布前由用户创建并持有长期签名密钥，用 Android 官方 apksigner 流程签名并验证；密码通过交互输入或安全CI注入，不写进源码。至少两份受保护密钥备份，保留别名和证书指纹。debug签名不能无损升级为另一个release签名；迁移必须先导出和校验全部未同步数据，不建议卸载来解决。

发布清单：记录APK SHA256、证书指纹、源码commit、数据库版本、实测设备、已知限制。公网链路或长时间后台未测时均明确注明，不把测试服务当作生产服务。按2026-10-25用户调整，本工具不再集成AI，模型配置不属于发布前置条件。

2026-10-25 当前日常测试包：`artifacts/idea-echo-0.1.0-debug-partial-upload-status.apk`，SHA256 `d4c1404fb43c80dbc6b3feb757b7b34f2f0e618a2034109d8c113ca1904d023e`。修复部分批次失败后遗漏既有成功上传时间的问题；6项真机回归通过，同一调试签名覆盖安装成功，数据库版本仍为1。本包仍为0.1.0调试版，未升级为正式release签名。
