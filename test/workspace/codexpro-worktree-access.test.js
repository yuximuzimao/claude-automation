'use strict';

const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const repositoryRoot = path.resolve(__dirname, '..', '..');
const launcherPath = path.join('scripts', 'start-codexpro-full.sh');
const worktreeRoot = '/Users/chat/.config/superpowers/worktrees';
const rootEnvironmentNames = [
  'CODEXPRO_ROOT',
  'CODEBASE_BRIDGE_REPO_ROOT',
  'CODEXPRO_ALLOW_HOME',
  'CODEBASE_BRIDGE_ALLOWED_ROOTS',
];

const fakeCodexPro = [
  '#!/usr/bin/env bash',
  'set -e',
  '',
  '{',
  "  printf '%s\\0' \"$PWD\"",
  "  printf '%s\\0' \"$@\"",
  "  printf '\\0'",
  "  printf '%s\\0' \"$CODEXPRO_ROOT\"",
  "  printf '%s\\0' \"$CODEBASE_BRIDGE_REPO_ROOT\"",
  "  printf '%s\\0' \"$CODEXPRO_ALLOW_HOME\"",
  "  printf '%s\\0' \"$CODEBASE_BRIDGE_ALLOWED_ROOTS\"",
  '} > "$CODEXPRO_CAPTURE_PATH"',
  '',
].join('\n');

function readCapture(capturePath) {
  const fields = fs.readFileSync(capturePath, 'utf8').split('\0');

  assert.equal(fields.pop(), '', 'fake capture must end with a NUL byte');

  const argvEnd = fields.indexOf('');
  assert.notEqual(argvEnd, -1, 'fake capture must delimit argv with an empty field');
  assert.equal(
    fields.length,
    argvEnd + 1 + rootEnvironmentNames.length,
    'fake capture must contain exactly the requested root environment values',
  );

  return {
    cwd: fields[0],
    argv: fields.slice(1, argvEnd),
    rootEnvironment: Object.fromEntries(
      rootEnvironmentNames.map((name, index) => [name, fields[argvEnd + 1 + index]]),
    ),
  };
}

test('CodexPro launcher locks roots against a polluted caller environment', (t) => {
  const temporaryDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'codexpro-launcher-'));
  const capturePath = path.join(temporaryDirectory, 'capture');
  const fakeCodexProPath = path.join(temporaryDirectory, 'codexpro');

  t.after(() => fs.rmSync(temporaryDirectory, { force: true, recursive: true }));
  fs.writeFileSync(fakeCodexProPath, fakeCodexPro);
  fs.chmodSync(fakeCodexProPath, 0o755);

  const result = spawnSync('bash', [launcherPath], {
    cwd: repositoryRoot,
    encoding: 'utf8',
    env: {
      ...process.env,
      CODEXPRO_ROOT: '/Users/chat/.config',
      CODEBASE_BRIDGE_REPO_ROOT: '/Users/chat',
      CODEXPRO_ALLOW_HOME: '1',
      CODEBASE_BRIDGE_ALLOWED_ROOTS: '/Users/chat:/Users/chat/.config',
      CODEXPRO_CAPTURE_PATH: capturePath,
      PATH: [temporaryDirectory, process.env.PATH].filter(Boolean).join(path.delimiter),
    },
  });

  assert.equal(result.error, undefined);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(fs.existsSync(capturePath), true, 'fake codexpro should write its capture');

  const capture = readCapture(capturePath);

  assert.equal(capture.cwd, '/Users/chat/claude');
  assert.deepEqual(capture.argv, ['start', '--allow-root', worktreeRoot]);
  assert.deepEqual(capture.rootEnvironment, {
    CODEXPRO_ROOT: '',
    CODEBASE_BRIDGE_REPO_ROOT: '',
    CODEXPRO_ALLOW_HOME: '',
    CODEBASE_BRIDGE_ALLOWED_ROOTS: '',
  });
});
