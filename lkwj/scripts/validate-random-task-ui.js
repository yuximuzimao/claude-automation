const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');

function getFunctionBody(name) {
  const start = html.indexOf(`function ${name}`);
  if (start < 0) return '';
  const braceStart = html.indexOf('{', start);
  if (braceStart < 0) return '';

  let depth = 0;
  for (let i = braceStart; i < html.length; i++) {
    if (html[i] === '{') depth += 1;
    if (html[i] === '}') depth -= 1;
    if (depth === 0) return html.slice(braceStart + 1, i);
  }
  return '';
}

const randomModule = getFunctionBody('renderRandomModule');
const spriteMarker = getFunctionBody('markRandomSpriteTask');
const formRenderer = getFunctionBody('renderRandomFormTask');
const fruitRenderer = getFunctionBody('renderRandomFruitTask');

const checks = [
  ['random modules use a header refresh icon', randomModule.includes('random-refresh-btn') && randomModule.includes('aria-label')],
  ['random modules no longer render text refresh buttons', !html.includes('>换一个</button>')],
  ['form random task uses a checkbox', formRenderer.includes('check-btn') && formRenderer.includes('markRandomFormTask')],
  ['fruit random task uses a checkbox', fruitRenderer.includes('check-btn') && fruitRenderer.includes('markRandomFruitTask')],
  ['form random task removed mark-complete button', !html.includes('markRandomFormDone') && !html.includes('>标记完成</button>')],
  ['fruit random task removed mark-complete button', !html.includes('markRandomFruitDone')],
  ['sprite random task refresh is gated by all displayed tasks', html.includes('isRandomSpriteTaskComplete') && spriteMarker.includes('isRandomSpriteTaskComplete')],
  ['sprite random task is not cleared unconditionally after one checkbox', !spriteMarker.includes("clearRandomTask('sprite')")],
];

const failures = checks.filter(([, ok]) => !ok).map(([name]) => name);
if (failures.length) {
  console.error(failures.join('\n'));
  process.exit(1);
}

console.log(JSON.stringify({ checks: checks.length }, null, 2));
