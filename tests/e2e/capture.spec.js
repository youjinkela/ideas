const {test,expect}=require('@playwright/test');
const png=Buffer.from('89504e470d0a1a0a0000000d49484452000000030000000208020000001216f14d0000001449444154789c63ac9894c300064c108a818101001a94017a9258d0500000000049454e44ae426082','hex');

test.beforeEach(async({page})=>{
  await page.goto('/#e2e-bootstrap');
  await expect(page.locator('#appStatus')).toContainText('已连接本机');
});

test('desktop capture keeps text and images after reload and opens the new inbox item',async({page})=>{
  await page.getByRole('button',{name:'添加点子',exact:true}).click();
  await page.getByLabel('点子内容').fill('电脑新增图文<script>window.captureInjected=1</script>');
  await page.locator('#captureFiles').setInputFiles({name:'fixture.png',mimeType:'image/png',buffer:png});
  await expect(page.locator('#captureImages img')).toHaveCount(1);
  await page.getByRole('button',{name:'移除图片 1'}).click();
  await expect(page.locator('#captureImages img')).toHaveCount(0);
  await page.locator('#captureFiles').setInputFiles({name:'fixture.png',mimeType:'image/png',buffer:png});
  await page.locator('#saveCapture').click();
  await expect(page.locator('#captureDialog')).not.toBeVisible();
  await expect(page.locator('#raw')).toHaveText('电脑新增图文<script>window.captureInjected=1</script>');
  await expect(page.locator('#ideaImages img')).toHaveCount(1);
  expect(await page.evaluate(()=>window.captureInjected)).toBeUndefined();
  await page.reload();
  await expect(page.locator('#appStatus')).toContainText('已连接本机');
  await page.getByRole('button',{name:/电脑新增图文/}).click();
  await expect(page.locator('#ideaImages img')).toHaveCount(1);
});

test('lost creation response preserves the form and retry creates only one idea',async({page})=>{
  await page.getByRole('button',{name:'添加点子',exact:true}).click();
  await page.getByLabel('点子内容').fill('保存确认丢失也只新增一次');
  await page.route('**/local/ideas',async route=>{if(route.request().method()==='POST'){await route.fetch();await route.abort('failed');}else await route.continue();});
  await page.route('**/local/capture/*/receipt',route=>route.fulfill({status:503,json:{detail:'fixture unavailable'}}));
  await page.locator('#saveCapture').click();
  await expect(page.locator('#captureFeedback')).toContainText('保留');
  await expect(page.getByLabel('点子内容')).toHaveValue('保存确认丢失也只新增一次');
  await page.unroute('**/local/ideas');await page.unroute('**/local/capture/*/receipt');
  await page.locator('#saveCapture').click();
  await expect(page.locator('#captureDialog')).not.toBeVisible();
  const data=await page.evaluate(async()=>await(await fetch('/local/ideas?view=all')).json());
  expect(data.ideas.filter(idea=>idea.text==='保存确认丢失也只新增一次')).toHaveLength(1);
});

test('a deleted capture draft can be explicitly saved as a new idea',async({page})=>{
  await page.getByRole('button',{name:'添加点子',exact:true}).click();
  await page.getByLabel('点子内容').fill('明确选择另存的点子');
  await page.route('**/local/ideas',route=>route.request().method()==='POST'?route.fulfill({status:410,json:{detail:{message:'这条点子已删除，当前内容可另存为新点子',deleted_id:'fixture-deleted'}}}):route.continue());
  await page.locator('#saveCapture').click();
  await expect(page.getByRole('button',{name:'另存为新点子'})).toBeVisible();
  await expect(page.getByLabel('点子内容')).toHaveValue('明确选择另存的点子');
  await page.getByRole('button',{name:'另存为新点子'}).click();
  await page.unroute('**/local/ideas');
  await page.locator('#saveCapture').click();
  await expect(page.locator('#captureDialog')).not.toBeVisible();
  await expect(page.locator('#raw')).toHaveText('明确选择另存的点子');
});

test('an older receipt cannot discard edits made after an uncertain save',async({page})=>{
  await page.getByRole('button',{name:'添加点子',exact:true}).click();
  await page.getByLabel('点子内容').fill('第一次已存下的内容');
  await page.route('**/local/ideas',async route=>{if(route.request().method()==='POST'){await route.fetch();await route.abort('failed');}else await route.continue();});
  await page.route('**/local/capture/*/receipt',route=>route.fulfill({status:503,json:{detail:'fixture unavailable'}}));
  await page.locator('#saveCapture').click();
  await expect(page.locator('#captureFeedback')).toContainText('保留');
  await page.getByLabel('点子内容').fill('保存结果未知之后的新修改');
  await page.unroute('**/local/capture/*/receipt');await page.unroute('**/local/ideas');
  await page.route('**/local/ideas',route=>route.request().method()==='POST'?route.fulfill({status:500,json:{detail:'synthetic retry failure'}}):route.continue());
  await page.locator('#saveCapture').click();
  await expect(page.locator('#captureDialog')).toBeVisible();
  await expect(page.getByLabel('点子内容')).toHaveValue('保存结果未知之后的新修改');
  await expect(page.getByRole('button',{name:'另存为新点子'})).toBeVisible();
  await page.getByRole('button',{name:'另存为新点子'}).click();await page.unroute('**/local/ideas');
  await page.locator('#saveCapture').click();
  await expect(page.locator('#raw')).toHaveText('保存结果未知之后的新修改');
});
