'use strict';
// UNUSED: 曾计划用 Doubao AI 做识图，最终改用 Claude 亲自识图。未接入任何模块。可安全删除。
const cdp = require('./cdp');
const { sleep } = require('./wait');
const http = require('http');
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const DB_ID = 'AABE6EDFFCCB6976DB4A41610B7E3032';
const Q = '这张商品图片显示的是一个组合套装，请列出套装包含的所有商品名称和对应数量，格式：商品名 x数量，每行一个，只列清单不要其他说明';

function rawSetFiles(targetId, files) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({ selector: 'input[type=file]', files });
    const req = http.request({
      hostname: 'localhost', port: 3456, method: 'POST',
      path: '/setFiles?target=' + targetId,
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) }
    }, res => {
      const c = []; res.on('data', d => c.push(d));
      res.on('end', () => { try { resolve(JSON.parse(Buffer.concat(c).toString())); } catch { resolve({}); } });
    });
    req.on('error', reject); req.write(body); req.end();
  });
}

/**
 * 用豆包识图，返回组合装商品清单文字
 * @param {string} imgUrl - 商品图片 URL
 * @param {string} [tmpPath] - 本地临时文件路径，默认 /tmp/doubao_img.jpg
 * @returns {Promise<string>} 豆包回复文字（空字符串表示超时无回复）
 */
async function askDoubao(imgUrl, tmpPath = '/tmp/doubao_img.jpg') {
  // 1. 点「新对话」（SPA内跳转，React保持初始化）
  await cdp.eval(DB_ID, `(function(){
    var btns = document.querySelectorAll("button,a,[role=button]");
    for(var i=0;i<btns.length;i++){
      if(btns[i].innerText.trim()==="新对话"){btns[i].click();return;}
    }
  })()`);
  await sleep(1200);

  // 2. 清空 file input 残留（新对话后仍可能有未清除的图片）
  await cdp.eval(DB_ID, `(function(){
    var inp = document.querySelector("input[type=file]");
    if(inp){ try { inp.value = ""; } catch(e){} }
    var dels = document.querySelectorAll("[class*=delete],[class*=remove],[aria-label*=删除],[aria-label*=移除]");
    for(var i=0;i<dels.length;i++){ dels[i].click(); }
  })()`);
  await sleep(300);

  // 3. 下载图片到本地
  execSync(`curl -s -o "${tmpPath}" "${imgUrl}"`);
  if (!fs.existsSync(tmpPath)) throw new Error('图片下载失败: ' + imgUrl);

  // 4. 激活 DOM 会话，再注入文件（必须先 eval 再 setFiles）
  await cdp.eval(DB_ID, 'document.querySelector("input[type=file]") ? 1 : 0');
  await sleep(200);
  const fr = await rawSetFiles(DB_ID, [tmpPath]);
  if (!fr.success) throw new Error('setFiles失败: ' + JSON.stringify(fr));
  await sleep(800);

  // 5. 输入问题
  await cdp.eval(DB_ID, `(function(){
    var ta = document.querySelector("textarea");
    var s = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,"value").set;
    s.call(ta, ${JSON.stringify(Q)});
    ta.dispatchEvent(new Event("input",{bubbles:true}));
  })()`);
  await sleep(400);

  // 6. 发送（找右下角发送按钮）
  await cdp.eval(DB_ID, `(function(){
    var btns = document.querySelectorAll("button");
    for(var i=btns.length-1;i>=0;i--){
      var r = btns[i].getBoundingClientRect();
      if(r.x>1100 && r.y>820){ btns[i].click(); return; }
    }
  })()`);
  await sleep(1000);

  // 7. 等待回复（每5s检查，最多20s，超时则跳过思考）
  for (let i = 0; i < 4; i++) {
    await sleep(5000);
    const replyText = await extractLastReply();
    if (replyText && replyText.length > 10) return replyText;
  }

  // 超时 → 跳过思考
  await cdp.eval(DB_ID, `(function(){
    var all = document.querySelectorAll("*");
    for(var i=0;i<all.length;i++){
      if(all[i].childElementCount===0 && all[i].innerText && all[i].innerText.trim()==="跳过"){
        all[i].click(); return;
      }
    }
  })()`);
  await sleep(10000);
  return await extractLastReply() || '';
}

async function extractLastReply() {
  await cdp.eval(DB_ID, 'window.scrollTo(0, document.body.scrollHeight)');
  await sleep(300);

  const text = await cdp.eval(DB_ID, 'document.body.innerText');
  if (typeof text !== 'string' || text.length < 50) return '';

  const qMarker = Q.substring(0, 20);
  const lastQIdx = text.lastIndexOf(qMarker);
  if (lastQIdx < 0) return '';

  const after = text.substring(lastQIdx + Q.length).trim();
  if (!after || after.length < 5) return '';

  const SKIP = new Set(['思考','视频生成','编程','帮我写作','图像生成','翻译','更多','快速','发消息...','新对话','AI 创作','云盘']);
  const lines = after.split('\n')
    .map(s => s.trim())
    .filter(s => s.length > 1 && !SKIP.has(s));

  const endIdx = lines.findIndex(l => l.includes(qMarker) || l.startsWith('用户'));
  const replyLines = endIdx > 0 ? lines.slice(0, endIdx) : lines;

  return replyLines.slice(0, 15).join('\n');
}

module.exports = { askDoubao };
