const { chromium } = require('playwright');

async function viewPage() {
  const browser = await chromium.launch({
    headless: false,
    slowMo: 500
  });

  // 打开快麦ERP
  const erpPage = await browser.newPage();
  await erpPage.goto('https://erpa.superboss.cc/index.html#/tradeNew/manage/');

  // 打开鲸灵平台
  const jinglingPage = await browser.newPage();
  await jinglingPage.goto('https://scrm.jlsupp.com/micro-supplier/business/home');

  console.log('浏览器已打开两个标签页：');
  console.log('1. 快麦ERP: https://erpa.superboss.cc/index.html#/tradeNew/manage/');
  console.log('2. 鲸灵平台: https://scrm.jlsupp.com/micro-supplier/business/home');
  console.log('\n请手动登录，登录后告诉我你的操作流程');
  console.log('按 Ctrl+C 关闭浏览器');

  // 保持浏览器打开
  await new Promise(() => {});
}

viewPage().catch(console.error);
