'use strict';
const cdp = require('../cdp');
const { navigateErp, checkLogin, recoverLogin, CLOSE_ALL_DIALOGS_JS } = require('./navigate');
const { sleep, retry } = require('../wait');
const { ok, fail } = require('../result');

// 填入子订单号并搜索，返回所有行信息
function makeSearchJS(subOrderId) {
  return `(function(){
    // 找可见的搜索输入框（过滤隐藏元素，见错误#35）
    var inputs = Array.from(document.querySelectorAll('input.el-input__inner')).filter(function(i){
      var r = i.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    });
    // 用 placeholder 精确匹配搜索框（见 RULES 3.5 + 错误#35）
    var inp = inputs.find(function(i){ return i.placeholder && i.placeholder.includes('系统单号'); });
    // 禁止 fallback：找不到精确字段直接报错，不能填错位置
    if (!inp) return JSON.stringify({error:'未找到系统单号搜索框，当前页面可见input placeholders: ' + inputs.map(function(i){return i.placeholder;}).join('|')});
    inp.click();
    inp.focus();
    document.execCommand('selectAll');
    document.execCommand('delete');
    document.execCommand('insertText', false, '${subOrderId}');
    if (inp.value !== '${subOrderId}') return JSON.stringify({error:'填值失败: ' + inp.value, placeholder: inp.placeholder});
    ['keydown','keypress','keyup'].forEach(function(type){
      inp.dispatchEvent(new KeyboardEvent(type, {key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true,cancelable:true}));
    });
    return JSON.stringify({filled: inp.value, placeholder: inp.placeholder, enterSent: true});
  })()`;
}

// 确保 mixKey radio 已勾选（见 RULES 3.5）
const CHECK_MIXKEY_JS = `(function(){
  var radio = document.querySelector('input[value="mixKey"]');
  return JSON.stringify({exists: !!radio, checked: radio ? radio.checked : false});
})()`;

// 读取搜索结果所有行
const READ_ROWS_JS = `(function(){
  var countMatch = document.body.innerText.match(/共(\\d+)条/);
  var totalCount = countMatch ? parseInt(countMatch[1]) : 0;
  var rows = Array.from(document.querySelectorAll('.module-trade-list-item'));
  return JSON.stringify({
    totalCount: totalCount,
    rows: rows.map(function(row){
      var text = row.innerText;
      // 内部单号（ERP内部编号，纯数字9位左右）
      var internalId = (text.match(/\\t(\\d{9,12})\\t/) || [])[1];
      // 快递单号：提取所有"物流 复制"前的快递单号（分包时同一行可能有多个）
      var trackingMatches = Array.from(text.matchAll(/(\\S+)\\n物流\\n复制/g));
      var trackings = trackingMatches.map(function(m){ return m[1]; }).filter(Boolean);
      var tracking = trackings[0] || null;
      // 状态
      var status = '';
      if (text.includes('待审核')) status = '待审核';
      else if (text.includes('待打印')) status = '待打印快递单';
      else if (text.includes('待发货')) status = '待发货';
      else if (text.includes('卖家已发货')) status = '卖家已发货';
      else if (text.includes('交易成功')) status = '交易成功';
      return { internalId, tracking, trackings, status, textSnippet: text.substring(0, 150) };
    })
  });
})()`;

async function erpSearch(targetId, subOrderId) {
  try {
    const loginStatus = await checkLogin(targetId);
    if (!loginStatus.loggedIn) await recoverLogin(targetId);

    // 清理上一次操作可能残留的弹窗（erp-logistics 打开了详情弹窗）
    await cdp.eval(targetId, CLOSE_ALL_DIALOGS_JS);

    await navigateErp(targetId, '订单管理');

    // 确认 mixKey 已选中（reload 后 Vue 组件挂载需要时间，加大重试次数）
    await retry(async () => {
      const mk = await cdp.eval(targetId, CHECK_MIXKEY_JS);
      if (!mk.exists) throw new Error('mixKey radio 不存在');
      if (!mk.checked) {
        await cdp.clickAt(targetId, 'input[value="mixKey"]');
        await sleep(800);
        const mk2 = await cdp.eval(targetId, CHECK_MIXKEY_JS);
        if (!mk2.checked) throw new Error('mixKey 勾选失败');
      }
    }, { maxRetries: 8, delayMs: 1200, label: 'check mixKey' });

    // 填值搜索
    await retry(async () => {
      // 先 clickAt 激活搜索框
      await cdp.clickAt(targetId, 'input.el-input__inner');
      await sleep(800);

      const fill = await cdp.eval(targetId, makeSearchJS(subOrderId));
      if (fill.error) throw new Error(fill.error);
      // 核验：placeholder 必须含「系统单号」，确认填进了正确的字段
      if (!fill.placeholder || !fill.placeholder.includes('系统单号')) {
        throw new Error(`填入字段不正确，placeholder: ${fill.placeholder}，期望含「系统单号」`);
      }

      // 轮询等待「共N条」出现（最多 8s），替换固定 sleep(4500)
      let countText = '';
      for (let w = 0; w < 16; w++) {
        await sleep(500);
        countText = await cdp.eval(targetId, `(document.body.innerText.match(/共\\d+条/) || [''])[0]`);
        if (countText) break;
      }
      if (!countText) throw new Error('搜索未执行（未找到共N条文字）');
    }, { maxRetries: 3, delayMs: 2000, label: `erp-search ${subOrderId}` });

    const rows = await cdp.eval(targetId, READ_ROWS_JS);
    return ok({ subOrderId, rows });
  } catch (e) {
    return fail(e);
  }
}

module.exports = { erpSearch };
