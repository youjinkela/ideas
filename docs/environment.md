# 开发环境

所有命令在本工程根目录运行，Python 使用 `.venv/Scripts/python.exe`，避免误用系统 PATH 中的 Python 3.10。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e './server[test]'
.\.venv\Scripts\python.exe -m pytest
```

正式运行目标为 Python 3.12。Android 工具只放在项目忽略目录 `.tooling`；每次从官方仓库下载时核对发布清单校验值。Android 开发依赖的 Google Maven 仓库与 App 运行时的 Google 服务无关，App 不使用后者。

测试不读取用户真实笔记库、不调用计费模型、不安装系统自启动。P40 真机测试需要用户连接设备并授权调试，不能用模拟器/接口测试冒充已经验证。
