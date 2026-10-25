# 网页添加点子 Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans; image helper/testing may run independently of cache/sync work.

**Goal:** 右上角添加点子，支持文字、图片和纯图片；当前账号下先存电脑、立即进入收件箱，联网上传云端。用户明确不要求手机接收电脑新增点子。

**Architecture:** 本机新增记录与稳定UUID/请求一起原子入队，图片先按点子UUID暂存并校验，保存后发布至账号附件目录。同步先提交原文和完整图片再确认原文请求，随后发送回顾/状态。使用现有云端接口，不修改手机或服务器协议。首次需配置账号，已有账号可离线新增，避免未关联记录在切换账号时丢失。

**Tech Stack:** Existing FastAPI/SQLite/Pillow/httpx and browser DOM; no new dependencies.

**Spec:** This conversation: text+images, computerreview/cloudonly. Header entry, dialog with text/photo previews/removal, save receipt and auto-selection in pending inbox. Preserve entered data on failure; repeated save/retry cannot duplicate. Empty input rejected; image count/size limits same as mobile (20 /20MiB each/200MiB total), text100000 characters.

## Constraints

- Current-account scope bound on image upload/create; no cross-account silent saves. No real notes/credentials in tests orGit.
- Stable creation UUID plus fingerprint; uploads and create retries idempotent. Acknowledgement requires complete graph and images.
- Preserve local raw data during cloud conflicts; record upload precedes review/status. A never-uploaded local deletion need not create a cloud deletion request; attempted uploads retain deletion reconciliation.
- Existing reflection/archive/image/status behavior and user-led UI remain; unsaved capture form warns before reload.
- No AI integration, phone pull expansion, account migration or new server deployment in this task.

## Task 1: Local capture and cloud queue

- [x] Observe failing persistence/idempotence/scope and graph-sync tests, then implement Cache/API/image helper and acknowledgement/order handling.
- [x] Add button/dialog and previews; preserve failed form and recover lost response receipts; browser behavior tests before implementation.
- [x] Python97/browser13 pass; scoped review fixes rechecked; synthetic dialog checked at1440/390px and actual workspace-drive storage smoke passed.
- [x] Confirm current reflection saved/no open forms; update service PID43836, open live creation dialog with controls visible; document and sync original feature branch.

Review rulings: receipts must match the current submitted text/manifest before clearing inputs. Missing remote deletions are acknowledged only after verifying server deletion capability; UUID tombstones remain and enqueue deletion for delayed raw events, so absence does not block sync or resurrect a local record. No server upgrade or placeholder records required.
