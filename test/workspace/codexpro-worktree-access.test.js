'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const launcherPath = path.resolve(__dirname, '..', '..', 'scripts', 'start-codexpro-full.sh');

test('CodexPro launcher permanently allows Superpowers worktrees only', () => {
  const launcher = fs.readFileSync(launcherPath, 'utf8');

  assert.match(
    launcher,
    /readonly SUPERPOWERS_WORKTREE_ROOT="\/Users\/chat\/\.config\/superpowers\/worktrees"/,
  );
  assert.match(
    launcher,
    /exec codexpro start\s+\\\s*\n\s*--allow-root "\$SUPERPOWERS_WORKTREE_ROOT"/,
  );
  assert.doesNotMatch(launcher, /--allow-home\b/);
  assert.doesNotMatch(
    launcher,
    /--allow-root\s+(?:"\/Users\/chat\/\.config"|'\/Users\/chat\/\.config'|\/Users\/chat\/\.config)(?=\s|$)/,
  );
});
