# 手机滑动页面 Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans. UI test authoring may run in parallel with dependency preparation; implementation follows observed RED.

**Goal:** 手机从左到右为随手记、已记录、设置；默认最左随手记；底部导航改为保存操作，添加图片和保存固定在键盘上方。

**Architecture:** 原生 ViewPager2 承载三个常驻页面，不通过手势重建输入框。捕获草稿/附件沿用现有模型与持久化；页面独立更新。捕获页共享固定操作栏，其他页面隐藏保存；adjustResize/WindowInsets 处理键盘与系统栏，滑出输入页时收起键盘。

**Tech Stack:** Existing Kotlin Views / Room / AndroidX; ViewPager2 1.1.0 per official AndroidX stable release. No server/web protocol changes.

**Spec:** User confirmed order 随手记 → 已记录 → 设置, home index0. Replace bottom navigation with 保存点子; 添加图片 above the IME. Footer call: image action left, primary save right, both remain usable above keyboard. Preserve text/images and login fields on page swipes.

## Constraints

- MainActivity keeps offline saving, images, login, synchronization and export behavior.
- Vertical scrolling, text selection and history image-strip scrolling must remain usable.
- Default capture page, no circular wrap; restore current page on activity recreation.
- No real data in tests: UI instrumentation runs only in independently installed acceptance package.
- Same-signature daily update, never clear daily app data; sync GitHub after checks.

## Task 1: Pages and capture actions

- [x] Add UI IDs/dependency and acceptance-only interaction tests; observe failure on current UI.
- [x] Replace bottom navigation with persistent pager, isolate page render targets, move actions to fixed footer.
- [x] Validate real swipes, draft preservation, IME geometry, image-picker cancellation and save deduplication on P40.
- [x] Build/lint/JVM and relevant mobile regression: 26 device tests,6JVM,lint0errors/27warnings; synthetic screenshot inspected and focused code review found no blockers.
- [x] Same-signature daily cover-install Success, cold start ok/848ms; disposable acceptance packages and USB47841 cleaned. Document verification and sync original feature branch. No backend upgrade.

References: https://developer.android.com/jetpack/androidx/releases/viewpager2 ; https://developer.android.com/develop/ui/views/touch-and-input/keyboard-input/visibility
