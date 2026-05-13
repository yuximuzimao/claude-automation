'use strict';
/**
 * cli.js - 退货入库自动化入口
 * 用法:
 *   node cli.js run                    # 读 data/input.txt
 *   node cli.js run SF123,SF456        # 直接传单号（逗号分隔）
 */
const fs = require('fs');
const path = require('path');
const { processAll } = require('./lib/workflow');

const INPUT_FILE = path.join(__dirname, 'data/input.txt');

const [,, cmd, arg] = process.argv;

if (cmd !== 'run') {
  console.log('用法: node cli.js run [单号1,单号2,...]');
  process.exit(0);
}

let trackingNumbers;
if (arg) {
  trackingNumbers = arg.split(',').map(s => s.trim()).filter(Boolean);
} else {
  if (!fs.existsSync(INPUT_FILE)) {
    console.error('data/input.txt 不存在，请创建后填入快递单号（每行一个）');
    process.exit(1);
  }
  const content = fs.readFileSync(INPUT_FILE, 'utf8');
  trackingNumbers = content.split('\n').map(s => s.trim()).filter(Boolean);
}

if (trackingNumbers.length === 0) {
  console.error('没有找到任何快递单号');
  process.exit(1);
}

console.log(`共 ${trackingNumbers.length} 个单号，开始处理...`);
processAll(trackingNumbers).catch(e => {
  console.error('致命错误:', e.message);
  process.exit(1);
});
