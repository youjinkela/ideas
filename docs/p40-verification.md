# P40 后台同步验收

设备：华为 P40 ANA-AN00，HarmonyOS 3.0.0 / Android API31。本文区分已观察事实与待验条件，不能用短时 API 测试替代锁屏、重启或公网验收。

## 已有证据

- 日常调试版的图文持久化、失败保留、恢复上传、重试去重、缩略图和点击放大已通过真机及人工验证。
- 2026-10-24 增加独立 `acceptance` 构建，包名 `com.ideaecho.app.acceptance`，显示名“点子回声·后台验收”。同源默认 debug 构建的 SHA256 仍为 `59a8b5c910022355d64387a57aa83384252a6c423afe0f509b8c0fe10be5dc96`，日常 App 未被覆盖。
- 设备开启流量节省，蜂窝默认网络已验证。起初验收任务等待 CONNECTIVITY；给验收 UID 添加后台数据例外后该条件满足。全局流量节省保留。例外只改变所选 App 是否可使用后台计量网络，不解决备案或 TLS 入口问题。
- 初版准备 instrumentation 在结束时被系统以 `finished inst` 停掉目标进程，随后读取状态曾得到 RUNNING。这是验收工具干扰，未记为后台上传通过，也没有据此修改产品同步逻辑。
- 当前长时场景的最终结果见下方“实际运行结果”；没有结果的场景保持待验。

## 为什么用独立验收版

真实 `SyncWorker` 使用应用自己的默认数据库和账号存储。独立包有自己的 UID、目录与 Keystore，可以在默认路径验证实际生产类，又不更换日常 App 的账号或接触私人点子。

准备入口只编译进 `src/acceptance`，不进入 debug/release。接收器要求系统级 `android.permission.DUMP`，仅供 ADB 调试者准备固定本机临时账号与合成图片，不接收任意服务器地址或密码参数。

## 可复现步骤

以下面向维护者，先按项目工具链准备 Python、Gradle 和 Android SDK，连接并授权手机。临时服务器只绑定电脑 loopback，不使用 ECS 数据。

1. 在电脑运行 `.venv/Scripts/python.exe scripts/serve-android-e2e.py`，再用 SDK 的 adb 设置 `reverse tcp:47841 tcp:47841`。
2. 构建 `assembleAcceptance assembleAcceptanceAndroidTest -PinstrumentationBuildType=acceptance`，安装 acceptance APK 与它的测试 APK。默认 debug/release 的 applicationId 保持原值。
3. 如设备启用流量节省，只为验收版允许后台数据；先记录原值，结束后恢复该例外。不要关闭全局流量节省、修改移动热点或全局电池策略。
4. 首次打开独立验收版，随后用有明确 action 的广播准备一条图文和延迟任务。不要用 instrumentation 做准备，因为测试结束会停止目标进程。

```powershell
$adb='./.tooling/android-sdk/platform-tools/adb.exe'
& $adb shell am start -W -n com.ideaecho.app.acceptance/com.ideaecho.app.MainActivity
& $adb shell am broadcast --user 0 -a com.ideaecho.app.ACCEPTANCE_PREPARE -n com.ideaecho.app.acceptance/com.ideaecho.app.BackgroundProbeReceiver --es phase long --ei delaySeconds 900
& $adb shell input keyevent KEYCODE_HOME
& $adb shell input keyevent KEYCODE_SLEEP
```

准备成功应返回 result=-1 和测试回执。没有 action 的广播在本机没有执行接收器，不能把 result=0 当作准备成功。同一 phase 仅准备一次；重复运行需保留证据后明确清理独立验收数据，不能清空日常 App。

5. 保持手机熄屏，运行独立观察器。它只向临时服务读取测试记录及两张图片的回执，并通过 run-as 读取验收包的非敏感状态，不启动 App 或测试 runner。

```powershell
.venv/Scripts/python.exe scripts/observe-background-upload.py --phase long --screen-off-seconds 900 --timeout-seconds 1200 --output .superpowers/sdd/2026-10-22-idea-echo-implementation/background-long-observation.json
```

观察器要求单个测试记录事件、两张已确认图片、成功时间不早于本条准备时间，以及连续抽样熄屏满 900 秒。正常周期任务也可以先于延迟探针完成上传；因此不错误要求上传时间一定晚于探针最早调度时间。

6. 保存独立完成回执后，才允许启动 verifier，传入观察到的 last_success_at 作为上界。这样不能把 verifier 启动 App 后触发的上传误认作事前成功。

```powershell
$observation=Get-Content .superpowers/sdd/2026-10-22-idea-echo-implementation/background-long-observation.json -Raw | ConvertFrom-Json
& $adb shell am instrument -w -r -e class 'com.ideaecho.app.BackgroundAcceptanceTest#verifyBackgroundUpload' -e backgroundAcceptance true -e phase long -e completionObservedAt $observation.last_success_at com.ideaecho.app.acceptance.test/androidx.test.runner.AndroidJUnitRunner
```

verifier 还要求服务器严格为 `http://127.0.0.1:47841`，当前 owner 等于固定临时账号登录结果；核对真实 WorkManager 成功状态、Room 已同步状态、服务器单个记录事件与原图哈希。未显式传入验收开关或目标不是独立包时，测试会跳过，跳过不算通过。

7. 结束后撤销自己新增的验收 UID 例外、停止临时服务器、删除仅 47841 的 USB 映射，清理自己安装的两个验收包。保留用户原有 USB 映射和日常 App。

## 实际运行结果

2026-10-24 长时后台图文观察已通过。独立观察结果：

| 项目 | 实际结果 |
|---|---|
| 图文准备时间 | 北京时间 13:52:04.667 |
| 服务器确认上传的手机时间 | 14:06:33.198 |
| 独立观察完成时间 | 14:12:06.666 |
| 连续抽样熄屏时长 | 906 秒，即 15 分 6 秒 |
| 指定测试记录事件 | 1 份 |
| 已确认图片 | 2 张，哈希一致 |
| 完成是否先于 verifier | 是；观察过程中没有启动 verifier |
| 条件 | USB 供电、经电脑 loopback 临时服务、验收版后台数据例外开启 |

正常周期任务先于延迟探针约 31 秒完成了这条上传，符合实际 App 的调度方式。此结果只报告已观察的后台图文上传与去重，不要求所有上传必须由延迟探针独占执行。

`am kill` 未证明进程真的消失；同 UID 发信号结束进程在本机返回 unknown pid，而系统进程列表仍显示该 PID。观察器记录 process_absent_at_observation_start=false，因此本轮不报告系统回收恢复通过。

复核后的 verifier 测试包已构建，正在等待手机允许覆盖安装后进行最后的 WorkManager/Room 断言；不能将这一项提前记作通过。

日常 App 的后台数据例外由 false 改为 true，目标为本机实际解析的日常包 UID10388，保持全局流量节省 enabled。这样为备案后的日常后台联网补齐系统条件。验收 UID10390 的临时例外在收尾时撤销，不影响其他 App。

如希望恢复日常 App 的原流量策略，可在系统设置中针对“点子回声”取消流量节省例外；取消后，在计量网络中后台上传仍可能等待，打开 App 可使用前台兜底。

## 仍需单独观察

- USB 供电与 loopback 通道不能代表未充电的深度 Doze、真正移动网络恢复或电脑关机后的公网直连。
- 强制停止属于用户主动停止；需要再次打开 App 才能观察恢复，不要求在强停标志仍在时偷偷运行。
- 手机重启会影响用户当前热点网络，本轮没有自动重启设备。
- 正式签名升级、备案后的公网链路、长期电池策略需各自验收。

华为如继续限制 App，可在应用启动管理中按需要允许后台活动；仅在实际需要时调整。参考 [华为 HarmonyOS 4.X 及以下的后台管理说明](https://consumer.huawei.com/cn/support/content/zh-cn00410039/)、[Android 流量节省与单 App 例外](https://developer.android.com/develop/connectivity/network-ops/data-saver)、[WorkManager 延迟与约束](https://developer.android.com/develop/background-work/background-tasks/persistent/getting-started/define-work)。
