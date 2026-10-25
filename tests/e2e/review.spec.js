const { test, expect } = require('@playwright/test');

test.beforeEach(async ({ page }) => {
  page.on('pageerror',error=>console.log('Page error: '+error.message));
  page.on('console',message=>{if(message.type()==='error')console.log('Browser error: '+message.text());});
  await page.goto('/#e2e-bootstrap');
  await expect(page.locator('#appStatus')).toContainText('已连接本机');
});

test('non-JSON local error is explained without leaking response text',async({page})=>{
  await page.locator('#settingsOpen').click();
  await page.route('**/local/settings',async route=>{
    if(route.request().method()==='POST')await route.fulfill({status:500,contentType:'text/plain',body:'Internal Server Error private-debug-marker'});
    else await route.continue();
  });
  await page.locator('#saveSettings').click();
  await expect(page.locator('#notice')).toContainText('HTTP 500');
  await expect(page.locator('#notice')).not.toContainText('Unexpected token');
  await expect(page.locator('#notice')).not.toContainText('private-debug-marker');
});

test('user edits survive switching and raw scripts never execute', async ({ page }) => {
  await page.getByRole('button',{name:/早晨的图文点子/}).click();
  await page.locator('#reflection').fill('由我补充的思路');
  await page.getByRole('button',{name:/昨晚没有回顾/}).click();
  await page.getByRole('button',{name:/早晨的图文点子/}).click();
  await expect(page.locator('#reflection')).toHaveValue('由我补充的思路');
  expect(await page.evaluate(()=>window.__injected)).toBeUndefined();
});

test('review and settings expose no integrated model controls or requests',async({page})=>{
  const modelRequests=[];
  page.on('request',r=>{if(r.url().includes('/local/ai/'))modelRequests.push(r.url());});
  await expect(page.getByRole('button',{name:'追问一个问题'})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'帮我弄清楚'})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'换几个角度'})).toHaveCount(0);
  await page.getByRole('button',{name:/早晨的图文点子/}).click();
  await page.getByRole('button',{name:/昨晚没有回顾/}).click();
  await page.locator('#settingsOpen').click();
  await expect(page.getByLabel('服务器根地址')).toBeVisible();
  await expect(page.locator('#chooseVault')).toBeVisible();
  await expect(page.locator('#aiUrl,#aiModel,#aiKey,#aiPrompt,#aiSend')).toHaveCount(0);
  await page.locator('#saveSettings').click();
  await expect(page.locator('#notice')).toContainText('连接设置已保存');
  expect(modelRequests).toEqual([]);
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

test('a stale second window cannot overwrite a newer local edit', async ({page,context}) => {
  await page.locator('#view').selectOption('all');
  await page.getByRole('button',{name:/早晨的图文点子/}).click();
  const other=await context.newPage();
  await other.goto('/#e2e-bootstrap');
  await expect(other.locator('#appStatus')).toContainText('已连接本机');
  await other.locator('#view').selectOption('all');
  await other.getByRole('button',{name:/早晨的图文点子/}).click();
  await page.locator('#reflection').fill('较新窗口内容');
  await expect(page.locator('#saveStatus')).toHaveText('已保存到本机');
  await other.locator('#reflection').fill('旧窗口不应覆盖');
  await expect(other.locator('#notice')).toContainText('已有新版本');
  const result=await page.evaluate(async()=>await (await fetch('/local/ideas?view=all')).json());
  expect(result.ideas.find(x=>x.text.startsWith('早晨')).reflection).toBe('较新窗口内容');
  await expect(other.locator('#reflection')).toHaveValue('旧窗口不应覆盖');
  await other.close();
});

test('lost commit response and page reload resume the original append', async ({page}) => {
  await page.locator('#view').selectOption('all');
  await page.getByRole('button',{name:/早晨的图文点子/}).click();
  await page.locator('#archive').click();
  await page.locator('#archiveMode').selectOption('append');
  await page.locator('#targetNote').selectOption('已有笔记.md');
  const originalResponse=page.waitForResponse(r=>r.url().endsWith('/local/archive/preview'));
  await page.locator('#previewArchive').click();
  const original=await (await originalResponse).json();
  await page.route('**/local/archive/commit',async route=>{await route.fetch();await route.abort('failed');});
  await page.locator('#commitArchive').click();
  await expect(page.locator('#commitArchive')).toBeEnabled();
  await page.unroute('**/local/archive/commit');
  await page.reload();
  await expect(page.locator('#appStatus')).toContainText('已连接本机');
  await page.locator('#view').selectOption('all');
  await page.getByRole('button',{name:/早晨的图文点子/}).click();
  await page.locator('#archive').click();
  const resumedResponse=page.waitForResponse(r=>r.url().endsWith('/local/archive/preview'));
  await page.locator('#previewArchive').click();
  const resumed=await (await resumedResponse).json();
  expect(resumed.operation_id).toBe(original.operation_id);
  expect(resumed.content).toBe(original.content);
  await page.locator('#commitArchive').click();
  await expect(page.locator('#notice')).toContainText('已保存到');
});

test('remote deletion releases stale draft without trapping navigation',async({page})=>{
  await page.locator('#view').selectOption('all');
  await page.getByRole('button',{name:/早晨的图文点子/}).click();
  await page.route('**/local/reflection',async route=>route.fulfill({status:410,json:{detail:{deleted_id:'11111111-1111-4111-8111-000000000001',message:'该点子已删除'}}}));
  await page.locator('#reflection').fill('远端删除后仍在编辑的文字');
  await expect(page.locator('#saveStatus')).toContainText('已删除');
  await expect(page.locator('#reflection')).toHaveValue('远端删除后仍在编辑的文字');
  await page.unroute('**/local/reflection');
  await page.getByRole('button',{name:/昨晚没有回顾/}).click();
  await expect(page.locator('#ideaTitle')).toContainText('昨晚没有回顾');
});

test('discard requires confirmation; failure preserves edits and deletion survives reload',async({page})=>{
  await page.locator('#view').selectOption('all');
  const idea=page.getByRole('button',{name:/早晨的图文点子/});
  await idea.click();
  await page.locator('#reflection').fill('删除失败也要保留的补充');
  page.once('dialog',dialog=>dialog.dismiss());
  await page.locator('#discard').click();
  await expect(idea).toBeVisible();
  await expect(page.locator('#reflection')).toHaveValue('删除失败也要保留的补充');
  await page.route('**/local/delete',route=>route.fulfill({status:500,json:{detail:'示例删除失败'}}));
  page.once('dialog',dialog=>dialog.accept());
  await page.locator('#discard').click();
  await expect(page.locator('#notice')).toContainText('示例删除失败');
  await expect(page.locator('#reflection')).toHaveValue('删除失败也要保留的补充');
  await page.unroute('**/local/delete');
  let releaseDelete,deleteStarted;
  const started=new Promise(resolve=>{deleteStarted=resolve;});
  await page.route('**/local/delete',async route=>{deleteStarted();await new Promise(resolve=>{releaseDelete=resolve;});await route.continue();});
  page.once('dialog',dialog=>dialog.accept());
  await page.locator('#discard').click();
  await started;
  await expect(page.locator('#reflection')).toBeDisabled();
  releaseDelete();
  await expect(idea).toHaveCount(0);
  await expect(page.locator('#reflection')).toBeEnabled();
  await expect(page.getByRole('button',{name:/昨晚没有回顾/})).toBeVisible();
  await page.reload();
  await expect(page.locator('#appStatus')).toContainText('已连接本机');
  await page.locator('#view').selectOption('all');
  await expect(idea).toHaveCount(0);
});
