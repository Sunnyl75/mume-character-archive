const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(require('node:path').join(__dirname, '../integrations/wordpress/bree-deck-of-chars/data-loader.js'), 'utf8');

async function check(failures) {
  let requests = 0;
  const scripts = [];
  const message = {textContent: ''};
  const context = {
    URL, Date,
    window: {BREE_DECK_CONFIG: {dataUrl: 'https://example.test/data', fallbackDataUrl: 'https://example.test/ajax', scriptUrl: 'https://example.test/deck.js'}},
    document: {createElement: () => ({}), body: {appendChild: script => scripts.push(script)}, getElementById: () => message},
    fetch: async () => {
      requests++;
      if (requests <= failures) throw Error('Host blocked endpoint');
      return {ok: true, json: async () => ({characters: [{id: 'test'}]})};
    }
  };
  await vm.runInNewContext(source, context);
  return {context, requests, scripts, message};
}

(async () => {
  let result = await check(0);
  assert.equal(result.requests, 1);
  assert.equal(result.context.window.DECK_CHARS.characters[0].id, 'test');
  assert.equal(result.scripts[0].src, 'https://example.test/deck.js');
  result = await check(1);
  assert.equal(result.requests, 2);
  assert.equal(result.scripts.length, 1);
  result = await check(2);
  assert.equal(result.scripts.length, 0);
  assert.match(result.message.textContent, /could not be loaded/);
  console.log('Data loader checks passed: primary endpoint, AJAX fallback and visible load failure.');
})().catch(error => { console.error(error); process.exit(1); });
