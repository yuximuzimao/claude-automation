'use strict';
const fs = require('fs');

/**
 * 原子写入 JSON 文件：先写 .tmp，再 rename 覆盖，写前清理脏 tmp
 */
function safeWriteJson(filePath, data) {
  const tmp = filePath + '.tmp';
  if (fs.existsSync(tmp)) fs.unlinkSync(tmp);
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2));
  fs.renameSync(tmp, filePath);
}

module.exports = { safeWriteJson };
