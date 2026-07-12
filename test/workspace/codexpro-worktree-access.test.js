'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const launcherPath = path.resolve(__dirname, '..', '..', 'scripts', 'start-codexpro-full.sh');
const WIDE_ALLOW_ROOTS = new Set([
  '/Users/chat',
  '/Users/chat/.config',
  '$HOME',
  '$HOME/.config',
  '~',
  '~/.config',
]);
const ALLOW_ROOT_ARGUMENT_PATTERN =
  /--allow-root(?:\s+|=)(?:"([^"]+)"|'([^']+)'|([^\s\\]+))/g;

function findWideAllowRoot(source) {
  for (const match of source.matchAll(ALLOW_ROOT_ARGUMENT_PATTERN)) {
    const rawRoot = match[1] ?? match[2] ?? match[3];
    const normalizedRoot = rawRoot.replace(/\/+$/, '');

    if (WIDE_ALLOW_ROOTS.has(normalizedRoot)) {
      return normalizedRoot;
    }
  }

  return undefined;
}

const unsafeAllowRootVariants = [
  {
    argument: '--allow-root "/Users/chat/.config/"',
    expected: '/Users/chat/.config',
    name: 'quoted config root with a trailing slash',
  },
  {
    argument: "--allow-root='/Users/chat/.config'",
    expected: '/Users/chat/.config',
    name: 'equals form with a quoted config root',
  },
  {
    argument: '--allow-root /Users/chat',
    expected: '/Users/chat',
    name: 'user directory root',
  },
  {
    argument: '--allow-root "$HOME/.config/"',
    expected: '$HOME/.config',
    name: 'HOME config root with a trailing slash',
  },
  {
    argument: '--allow-root=~/.config/',
    expected: '~/.config',
    name: 'tilde config root with a trailing slash',
  },
  {
    argument: '--allow-root=$HOME',
    expected: '$HOME',
    name: 'HOME directory root',
  },
  {
    argument: '--allow-root ~',
    expected: '~',
    name: 'tilde directory root',
  },
];

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
  assert.equal(findWideAllowRoot(launcher), undefined);
});

test('CodexPro wide allow-root variants are rejected', () => {
  for (const { argument, expected, name } of unsafeAllowRootVariants) {
    const candidate = ['exec codexpro start \\', '  ' + argument].join('\n');

    assert.equal(findWideAllowRoot(candidate), expected, name);
  }
});
