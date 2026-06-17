#!/usr/bin/env node
'use strict';
/**
 * 鲸灵安全注入编排：打开 login 页 → 读取登录态 → 按账号匹配决定复用/退出/注入。
 *
 * 本脚本只串联已验证的 01/02/03/04 原子步骤，不复制原子步骤内部逻辑。
 */

const { openAccountFlow } = require('../../lib/jl/open-account-flow');

if (require.main === module) {
  const accountNum = process.argv[2];
  openAccountFlow(accountNum)
    .then(r => {
      console.log(JSON.stringify(r));
      process.exit(r.success ? 0 : 1);
    })
    .catch(e => {
      console.log(JSON.stringify({ success: false, error: e.message }));
      process.exit(1);
    });
}

module.exports = { openAccountFlow };
