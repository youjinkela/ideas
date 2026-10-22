# 0.1.0 测试版

Android包名 `com.ideaecho.app`，versionCode1，minSdk26，targetSdk36。P40实际API31。当前交付调试签名 APK，仅用于验收与个人试用。

`scripts/build-apk.ps1 -Verify` 构建 APK、JVM测试、lint及真机测试包；它不声称已经运行真机测试。`-Release` 目前输出未签名release，不会伪造生产签名。

正式发布前由用户创建并持有长期签名密钥，用 Android 官方 apksigner 流程签名并验证；密码通过交互输入或安全CI注入，不写进源码。至少两份受保护密钥备份，保留别名和证书指纹。debug签名不能无损升级为另一个release签名；迁移必须先导出和校验全部未同步数据，不建议卸载来解决。

发布清单：记录APK SHA256、证书指纹、源码commit、数据库版本、实测设备、已知限制。服务器未部署、模型未配置、长时间后台未测时均明确注明，不把测试服务当作生产服务。
