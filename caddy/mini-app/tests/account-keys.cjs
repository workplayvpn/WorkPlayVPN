// Run with node caddy/mini-app/tests/account-keys.cjs (no packages required).
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(require('node:path').join(__dirname, '../assets/app.js'), 'utf8');
function element() {
  const classes = new Set(['hidden']);
  return {value: '', textContent: '', src: '', classList: {
    add: (v) => classes.add(v), remove: (v) => classes.delete(v),
    contains: (v) => classes.has(v), toggle: (v, on) => on ? classes.add(v) : classes.delete(v),
  }, removeAttribute(name) {delete this[name];}, focus() {}, select() {}};
}
function harness() {
  const nodes = new Map();
  const calls = [], copies = [];
  const context = vm.createContext({Map, ApiError: Error,
    state: {detailTier: 'basic'}, tierLabel: (tier) => tier,
    humanError: (error) => error.message, showToast() {}, haptic() {},
    document: {querySelector(selector) {if (!nodes.has(selector)) nodes.set(selector, element()); return nodes.get(selector);}},
    navigator: {clipboard: {writeText: async (value) => {copies.push(value);}}},
    api: async (path) => {calls.push(path); return {url: 'happ://crypt5/'+path.split('/').pop(), qr_data_url:'data:image/svg+xml;base64,QR'};},
    openSheet: (node) => node.classList.remove('hidden'), closeSheet: (node) => node.classList.add('hidden'),
  });
  const start = source.indexOf('const keySheet =');
  const end = source.indexOf('function handleMiniAppBack()', start);
  vm.runInContext(source.slice(start, end), context);
  return {context, calls, copies, nodes, run: (text) => vm.runInContext(text, context)};
}
(async () => {
  const h = harness();
  await h.run('prepareSubscriptionKey("basic")');
  await h.run('prepareSubscriptionKey("basic")');
  assert.deepEqual(h.calls, ['/mini-app/keys/basic']);
  h.run('keyMode="qr"; openSheet(keySheet)');
  await h.run('loadSubscriptionKey()');
  assert.equal(h.nodes.get('#key-qr-image').src, 'data:image/svg+xml;base64,QR');
  const button = {dataset: {keyAction:'copy'}, textContent:'Скопировать ключ'};
  h.context.trigger = button;
  await h.run('copyDisplayedKey(trigger)');
  assert.deepEqual(h.copies, ['happ://crypt5/basic']);
  assert.equal(button.textContent, '✓ Скопировано');
  h.run('state.detailTier="mobile"');
  await h.run('loadSubscriptionKey()');
  await h.run('copyDisplayedKey(trigger)');
  assert.deepEqual(h.copies, ['happ://crypt5/basic', 'happ://crypt5/mobile']);
  assert.deepEqual(h.calls, ['/mini-app/keys/basic', '/mini-app/keys/mobile']);
  h.run('navigator.clipboard.writeText = async () => {throw Error("permission denied")}; trigger.textContent="Скопировать ключ"');
  await h.run('copyDisplayedKey(trigger)');
  assert.equal(button.textContent, 'Скопировать ключ');
  assert.match(h.nodes.get('#key-sheet-status').textContent, /Буфер обмена недоступен/);
  h.run('clearKeyOutput()');
  assert.equal(h.nodes.get('#key-full-value').value, '');
  const stale = harness();
  stale.context.api = () => new Promise((resolve) => {stale.context.finish = resolve;});
  const pending = stale.run('prepareSubscriptionKey("basic")');
  stale.run('keyGeneration++; subscriptionKeys.clear(); preparedKeyValues.clear()');
  stale.context.finish({url: 'happ://crypt5/old'});
  await pending;
  assert.equal(stale.run('preparedKeyValues.size'), 0);
  console.log('Account key UI: cache, tier separation, QR, copying, denied clipboard and stale response checks passed');
})().catch((error) => {console.error(error); process.exitCode = 1;});
