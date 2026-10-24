# 2026-10-23 公网连接重置：备案拦截证据

状态：发现明确的阿里云备案拦截响应；具体备案/接入状态需由账号持有人或阿里云核查。公网 App 登录和同步尚未验收通过。

## 当前服务

- 域名：`ideas.duckegg-cc.xyz`，主域名 `duckegg-cc.xyz`。
- ECS 公网 IP：`39.108.105.156`；Ubuntu 24.04，原生 Python + systemd，Caddy HTTPS 入口。
- 业务服务只监听 `127.0.0.1:8000`，此前服务器本机健康检查成功。
- 用户表示域名此前已在阿里云备案。此陈述与当前拦截并存，不能直接认定用户未备案，也不能直接要求注销或重新备案。

## 确认的现象

1. Windows curl / Python HTTPS 连接失败；指定服务器 IP 并保留业务域名 SNI 时仍失败。TLS 1.2 和 TLS 1.3 分别测试均失败。
2. 临时 Edge 浏览器无缓存访问成功。强制指定 IP、禁用显式代理和 QUIC 的浏览器测试也返回 HTTP 200，协议 h2。这不等于所有客户端都能正常访问。
3. 用户反馈退出 Clash 后 curl 仍报连接重置。不能继续将故障简单归因于 Clash 全局模式或 TUN。
4. 用户手机和电脑共用手机移动网络；手机浏览器健康检查成功，手机原生 App 在设置中点击“登录并连接”报 `connection reset`。这次是前台登录结果，不是 WorkManager 排队提示。
5. 服务器抓包显示来自客户端方向的多次 RST，紧随第一段客户端握手数据出现。仅凭报文源 IP 不能确定真实发包设备。
6. Windows PktMon 两次捕获（nics / all）均只有 3 个会话元数据事件，无数据包。空捕获不能证明客户端未发包，已停止重复这一方法。

## 决定性 HTTP 对照

助手在 Windows 使用 `httpx.Client(trust_env=False, follow_redirects=False)` 请求同一个公开 IP 的 `/health`，只改变 HTTP Host；未发送账号、令牌或点子。

| 请求 | 结果 |
| --- | --- |
| `http://39.108.105.156/health`，Host `ideas.duckegg-cc.xyz` | HTTP 403，Server `Beaver` |
| 相同 IP 和路径，Host `diagnostic.invalid` | HTTP 308，Server `Caddy`，Location `https://diagnostic.invalid/health` |

业务域名的 403 HTML 包含：

```text
<title>Non-compliance ICP Filing</title>
http://www.aliyun.com/beian/beian-block?id=00000000005988833737
```

TLS 名称对照也支持域名相关性：同一 Python 客户端连接同一 IP，SNI 为 `ideas.duckegg-cc.xyz`、`duckegg-cc.xyz` 或 `probe.duckegg-cc.xyz` 时出现 EOF；SNI 为 `diagnostic.invalid`、`duckegg-cc.invalid` 或 `example.com` 时收到 TLS internal-error alert。对照名称未配置证书，收到该 alert 不是业务成功；它说明两组请求的连接行为不同。未关闭证书验证，未向对照域名服务器发送请求。

## 当前判断与边界

已确认业务域名请求收到阿里云备案拦截页面。结合官方说明，这与 403 / TLS reset 现象一致，当前应优先处理备案入口的识别/接入问题。

尚未确认的细项包括：有效备案是否包含此主域名、阿里云接入状态是否有效、信息是否尚未同步、是否存在核查限制或误拦截。浏览器成功的具体差异仍未定位；不把它当作排除备案拦截的证据。

不通过换端口、跳过证书验证或改写握手来绕过拦截。无需继续调整客户端代理规则、重装 App 或重签证书。

## 下一步

1. 用户登录原备案账号，在阿里云“我的备案”核对 `duckegg-cc.xyz` 对应的网站与接入状态、核查/取消接入通知。
2. 如果该域名状态正常，向阿里云备案支持提交以下已整理说明，要求核对实际拦截原因与备案数据同步；不直接重新备案。
3. 阿里云解除拦截或所需备案处理完成后，依次验证公开 HTTP 正常重定向、Python/curl HTTPS 健康检查、手机 App 登录和上传、电脑回顾页接收。
4. 保留原有本机记录和服务器数据库。整体离线记录→手机独立上传→电脑回顾目标仍未完成最终公网验收。

## 可提交给阿里云支持的说明（尚未发送）

域名 ideas.duckegg-cc.xyz（主域名 duckegg-cc.xyz），解析至本人阿里云 ECS 公网 IP 39.108.105.156。本人此前在阿里云办理过该域名备案，请核对当前有效备案及接入状态。2026-10-23 测试时，向该 IP 的 HTTP /health 请求携带 Host: ideas.duckegg-cc.xyz，返回 HTTP 403、Server: Beaver，页面标题为 Non-compliance ICP Filing，拦截页编号 00000000005988833737。同一 IP 使用对照 Host 则返回 Caddy 的 308。业务本机健康检查正常；电脑 curl/Python 及 Android App 的业务域名 HTTPS 连接被 reset，而浏览器可成功访问。请查询备案拦截原因；若备案及接入有效，请核对识别数据、同步状态或误拦截并协助恢复。可按需要补充备案号和账号信息，请告知应提供哪些资料。

## 官方参考

- [阿里云公网连通 FAQ：RST、备案及云安全拦截](https://help.aliyun.com/zh/eip/support/faq-about-internet-connectivity)
- [接入备案 FAQ：已备案域名的 403 / TLS reset](https://help.aliyun.com/zh/icp-filing/basic-icp-service/support/access-for-the-record-the-faq/)
- [备案相关 FAQ：备案、接入与专项核查](https://help.aliyun.com/zh/dns/pubz-filing-domain-name-related-faq)
