const { test, expect } = require('@playwright/test');

test.beforeEach(async ({ page }) => {
  page.on('pageerror',error=>console.log('Page error: '+error.message));
  page.on('console',message=>{if(message.type()==='error')console.log('Browser error: '+message.text());});
  await page.goto('/#e2e-bootstrap');
  await expect(page.locator('#appStatus')).toContainText('已连接本机');
});

test('user edits survive switching; raw scripts never execute; AI stays idle', async ({ page }) => {
  const aiRequests=[];
  page.on('request',r=>{ if(r.url().includes('/local/ai/ask')) aiRequests.push(r.url()); });
  await page.getByRole('button',{name:/早晨的图文点子/}).click();
  await page.locator('#reflection').fill('由我补充的思路');
  await page.getByRole('button',{name:/昨晚没有回顾/}).click();
  await page.getByRole('button',{name:/早晨的图文点子/}).click();
  await expect(page.locator('#reflection')).toHaveValue('由我补充的思路');
  expect(await page.evaluate(()=>window.__injected)).toBeUndefined();
  expect(aiRequests).toEqual([]);
});

test('images render; new note destination and append are explicit', async ({ page }) => {
  await page.getByRole('button',{name:/早晨的图文点子/}).click();
  await expect(page.locator('#ideaImages img')).toHaveCount(1);
  await page.locator('#archive').click();
  await expect(page.locator('#archiveMode')).toHaveValue('new');
  await page.locator('#folder').selectOption('学习');
  await page.locator('#noteTitle').fill('我的图文点子');
  await page.locator('#previewArchive').click();
  await expect(page.locator('#archivePreview')).toContainText('_attachments/');
  await page.locator('#commitArchive').click();
  await expect(page.locator('#notice')).toContainText('已保存到');
  await page.locator('#view').selectOption('all');
  await page.getByRole('button',{name:/早晨的图文点子/}).click();
  await page.locator('#archive').click();
  await page.locator('#archiveMode').selectOption('append');
  await page.locator('#noteSearch').fill('已有笔记');
  await expect(page.locator('#targetNote option')).toHaveCount(1);
  await page.locator('#targetNote').selectOption('已有笔记.md');
  await page.locator('#previewArchive').click();
  await expect(page.locator('#archivePreview')).toContainText('用户原文');
  await page.locator('#commitArchive').click();
  await expect(page.locator('#notice')).toContainText('已保存到');
});

test('pending images are shown honestly and screenshot is reviewable', async ({ page }) => {
  await page.getByRole('button',{name:/昨晚没有回顾/}).click();
  await expect(page.locator('#ideaImages')).toContainText('图片待上传');
  await page.screenshot({path:'artifacts/desktop-review.png',fullPage:true});
});
