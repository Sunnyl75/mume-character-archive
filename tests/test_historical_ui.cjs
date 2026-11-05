const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../site/deck-of-chars/deck-of-chars.js'), 'utf8');
const part = (start, end) => source.slice(source.indexOf(start), source.indexOf(end));
const grid = {};
let title = '';
const context = {
  URL,
  document: {getElementById: () => grid},
  setText: (_, text) => { title = text; },
  currentCharacter: {name: 'Observer', history: {trophies: [
    {victim: '<script>bad</script>', count: 2, date: '1995', title: 'One', url: 'javascript:alert(1)'},
    {victim: 'Other', count: 3, date: '1996', title: 'Two', url: 'https://example.org/log?a=1&b=2'}
  ]}}
};
vm.createContext(context);
vm.runInContext(part('function escapeHtml(', 'function escapeAttr(')
  + part('function historicalReference(', 'function openScroll(')
  + part('function showTrophies(', 'function fitCardText('), context);
vm.runInContext('showTrophies()', context);
assert.equal(title, 'Trophy snapshots — Observer');
assert.doesNotMatch(grid.innerHTML, /javascript:|<script>/);
assert.match(grid.innerHTML, /&lt;script&gt;/);
assert.match(grid.innerHTML, /At least 2 kill/);
assert.match(grid.innerHTML, /At least 3 kill/);
assert.doesNotMatch(grid.innerHTML, /At least 5 kill/);
assert.match(grid.innerHTML, /rel="noopener noreferrer"/);
assert.match(grid.innerHTML, /a=1&amp;b=2/);
context.currentCharacter.history.trophies = [];
vm.runInContext('showTrophies()', context);
assert.match(grid.innerHTML, /No trophy snapshots/);
console.log('Historical UI checks passed: separate snapshots, safe links, escaped text and empty state.');
