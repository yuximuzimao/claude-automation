#!/usr/bin/env node
'use strict';

if (process.argv.includes('--verbose')) {
  process.env.VERBOSE = '1';
}

const { getTargetIds } = require('./lib/targets');
const { ok, fail } = require('./lib/result');

const USAGE = `
鲸灵售后自动化 CLI

用法: node cli.js <命令> [参数] [--verbose]

鲸灵命令:
  list                              读工单列表（≤48小时）
  read-ticket <工单号>              读工单详情
  approve <工单号>                  同意退款
  reject <工单号> <原因> <详情>     拒绝退款
  add-note <工单号> <备注内容>      添加内部备注
  remind <工单号> <账号名> <原因>   创建Mac提醒事项（人工上报用）
  logistics <工单号>               读物流信息

ERP命令:
  erp-nav <页面名>                  导航（订单管理/售后工单新版/商品档案V2/商品对应表）
  erp-login                         检查/恢复登录
  erp-search <子订单号>             ERP订单搜索
  erp-aftersale <快递单号>          ERP售后工单搜索
  erp-logistics <行号>              读ERP订单详情物流（0-based）

商品查询:
  product-match <货号> <attr1> <ERP店铺名>   商品对应表查询（店铺名见 lib/erp/shop-map.js）
  product-archive <规格编码>                 商品档案V2查询

所有命令输出 JSON: {"success":true,"data":{...}} 或 {"success":false,"error":"..."}
`.trim();

async function main() {
  const args = process.argv.slice(2).filter(a => a !== '--verbose');
  const cmd = args[0];

  if (!cmd || cmd === '--help' || cmd === '-h') {
    console.log(USAGE);
    process.exit(0);
  }

  // reload-jl：注入账号后全页重载，让 Vue 应用用新 session 重新初始化
  // 不需要 ERP 标签，单独处理
  if (cmd === 'reload-jl') {
    const cdpM = require('./lib/cdp');
    const { sleep, waitFor } = require('./lib/wait');
    const targets = await cdpM.getTargets();
    const jl = targets.find(t => t.url && t.url.includes('scrm.jlsupp.com'));
    if (!jl) {
      console.log(JSON.stringify(fail('JL标签页未找到')));
      process.exit(1);
    }
    await cdpM.navigate(jl.targetId, 'https://scrm.jlsupp.com/micro-customer/business/after-sale-list');
    try {
      await waitFor(async () => {
        try {
          const ready = await cdpM.eval(jl.targetId, `(function(){
            var app = document.querySelector('#app');
            if (!app || !app.__vue__) return false;
            var t = document.body.innerText || '';
            // 列表数据已加载：页面出现"工单号"或明确的空状态提示
            return (t.includes('工单号') || t.includes('暂无数据') || t.includes('没有更多')) ? true : false;
          })()`);
          return ready || null;
        } catch { return null; }
      }, { timeoutMs: 12000, intervalMs: 1000, label: 'reload-jl list loaded' });
    } catch { /* 超时后仍继续，由 approve/reject 的验证环节兜底 */ }
    console.log(JSON.stringify(ok({ reloaded: true })));
    process.exit(0);
  }

  // remind 命令不需要浏览器，单独处理
  if (cmd === 'remind') {
    const { execSync } = require('child_process');
    const workOrderNum = args[1];
    const accountName = args[2] || '未知账号';
    if (!workOrderNum) {
      console.log(JSON.stringify(fail('用法: remind <工单号> <账号名> [快递单号] [子订单号] [商品名] [数量] [收件人] [省市]')));
      process.exit(1);
    }

    // 新格式（拦截提醒）：有快递单号时用详细格式
    const shipTracking = args[3] || '';
    const internalId   = args[4] || '';
    const goodsName    = args[5] || '';
    const qty          = args[6] || '';

    let title;
    if (shipTracking) {
      // 格式：【拦截】YT7612...（圆通）/ 百浩-RITEKOKO / 子订单737081117 / 生椰拿铁×7
      const carrierMap = { SF: '顺丰', YT: '圆通', ZT: '中通', STO: '申通', YD: '韵达', JD: '京东', EMS: '邮政', KY: '跨越', BS: '百世' };
      const carrierPrefix = shipTracking.match(/^([A-Z]{2,4})/)?.[1] || '';
      const carrier = carrierMap[carrierPrefix] || carrierPrefix;
      const parts = [`【拦截】${shipTracking}${carrier ? `（${carrier}）` : ''}`];
      parts.push(accountName);
      if (internalId) parts.push(`子订单${internalId}`);
      if (goodsName) parts.push(qty ? `${goodsName}×${qty}` : goodsName);
      title = parts.join(' / ');
    } else {
      title = `【待人工】${accountName} 工单${workOrderNum}`;
    }

    // 不设 remind me date，避免 AppleScript 超时 (-1712)
    const script = `tell application "Reminders" to make new reminder at end of list "待办" of default account with properties {name:"${title.replace(/"/g, '\\"')}"}`;
    execSync(`osascript -e '${script}'`);
    const result = ok({ reminded: true, title });
    console.log(JSON.stringify(result, null, 2));
    process.exit(0);
  }

  let result;
  try {
    const { jlId, erpId } = await getTargetIds();

    switch (cmd) {
      case 'list': {
        const { listTickets } = require('./lib/jl/list');
        const maxHours = args[1] ? parseInt(args[1]) : undefined;
        result = await listTickets(jlId, maxHours);
        break;
      }
      case 'read-ticket': {
        if (!args[1]) throw new Error('缺少工单号');
        const { readTicket } = require('./lib/jl/read-ticket');
        result = await readTicket(jlId, args[1]);
        break;
      }
      case 'approve': {
        if (!args[1]) throw new Error('缺少工单号');
        const { approveTicket } = require('./lib/jl/approve');
        result = await approveTicket(jlId, args[1]);
        break;
      }
      case 'reject': {
        if (!args[1] || !args[2] || !args[3]) throw new Error('用法: reject <工单号> <原因> <详情> [图片URL]');
        const { rejectTicket } = require('./lib/jl/reject');
        result = await rejectTicket(jlId, args[1], args[2], args[3], args[4]);
        break;
      }
      case 'add-note': {
        if (!args[1] || !args[2]) throw new Error('用法: add-note <工单号> <备注内容>');
        const { addNote } = require('./lib/jl/add-note');
        result = await addNote(jlId, args[1], args[2]);
        break;
      }
      case 'logistics': {
        if (!args[1]) throw new Error('缺少工单号');
        const { getLogistics } = require('./lib/jl/logistics');
        result = await getLogistics(jlId, args[1]);
        break;
      }
      case 'open-ticket': {
        if (!args[1]) throw new Error('缺少工单号');
        const { navigate: jlNavigate } = require('./lib/jl/navigate');
        await jlNavigate(jlId, '/business/after-sale-detail', { workOrderNum: args[1] });
        result = ok({ opened: true, workOrderNum: args[1] });
        break;
      }
      case 'erp-nav': {
        if (!args[1]) throw new Error('缺少页面名');
        const { erpNav } = require('./lib/erp/navigate');
        result = await erpNav(erpId, args[1]);
        break;
      }
      case 'erp-login': {
        const { checkLogin, recoverLogin } = require('./lib/erp/navigate');
        const status = await checkLogin(erpId);
        if (!status.loggedIn) {
          await recoverLogin(erpId);
          result = ok({ recovered: true });
        } else {
          result = ok({ loggedIn: true, title: status.title });
        }
        break;
      }
      case 'erp-search': {
        if (!args[1]) throw new Error('缺少子订单号');
        const { erpSearch } = require('./lib/erp/search');
        result = await erpSearch(erpId, args[1]);
        break;
      }
      case 'erp-aftersale': {
        if (!args[1]) throw new Error('缺少退货快递单号');
        const { erpAftersale } = require('./lib/erp/aftersale');
        result = await erpAftersale(erpId, args[1]);
        break;
      }
      case 'erp-logistics': {
        const rowIndex = args[1] !== undefined ? parseInt(args[1]) : 0;
        const { readErpLogistics } = require('./lib/erp/read-logistics');
        result = await readErpLogistics(erpId, rowIndex);
        break;
      }
      case 'product-match': {
        if (!args[1] || !args[3]) throw new Error('用法: product-match <货号> <attr1> <ERP店铺名>  例: product-match 0401-2 "精华水 150ml*3" 百浩创展');
        const { productMatch } = require('./lib/product/match');
        result = await productMatch(erpId, args[1], args[2], args[3]);
        break;
      }
      case 'product-archive': {
        if (!args[1]) throw new Error('缺少规格商家编码');
        const { productArchive } = require('./lib/product/archive');
        result = await productArchive(erpId, args[1]);
        break;
      }
      default:
        result = fail(`未知命令: ${cmd}\n运行 node cli.js --help 查看帮助`);
    }
  } catch (e) {
    result = fail(e);
  }

  console.log(JSON.stringify(result, null, 2));
  process.exit(result.success ? 0 : 1);
}

main();
