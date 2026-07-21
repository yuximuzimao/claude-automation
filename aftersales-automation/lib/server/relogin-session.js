'use strict';

const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

function shouldInitializePhoneForAccount({ account, sessionsDir, fsImpl = fs }) {
  if (!account || !account.file) return false;
  return !fsImpl.existsSync(path.join(sessionsDir, account.file));
}

async function startReloginSession({
  num,
  sessionsDir,
  initializePhone = false,
  fsImpl = fs,
  spawnImpl = spawn,
  wait = ms => new Promise(resolve => setTimeout(resolve, ms)),
  timeoutMs = 8000,
  pollMs = 200,
}) {
  const portFile = path.join(sessionsDir, `.relogin-port-${num}`);
  if (fsImpl.existsSync(portFile)) fsImpl.unlinkSync(portFile);

  const args = [path.join(sessionsDir, 'jl.js'), 'add', String(num), '--auto-save'];
  if (initializePhone) args.push('--initialize-phone');
  spawnImpl('node', args, { detached: true, stdio: 'ignore' }).unref();

  let waited = 0;
  while (!fsImpl.existsSync(portFile) && waited < timeoutMs) {
    await wait(pollMs);
    waited += pollMs;
  }
  if (!fsImpl.existsSync(portFile)) {
    throw new Error('登录窗口启动失败，请重试');
  }

  return { portFile };
}

module.exports = {
  shouldInitializePhoneForAccount,
  startReloginSession,
};
