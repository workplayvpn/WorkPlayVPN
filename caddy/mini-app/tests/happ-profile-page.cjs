const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../assets/app.js'), 'utf8');
const start = source.indexOf('      const subscriptionStart =');
const end = source.indexOf('      state.initialViewApplied = true;', start);
assert(start >= 0 && end > start);
const code = source.slice(start, end);
function launch(startParam, tiers, fallback = null) {
  const calls = [];
  vm.runInNewContext(code, {
    telegram: { initDataUnsafe: { start_param: startParam } },
    params: new URLSearchParams(fallback ? { tgWebAppStartParam: fallback } : {}),
    activeSubscriptions: () => tiers.map(tier => ({tier})),
    subscriptionTier: entry => entry.tier,
    openSubscription: tier => calls.push(['subscription', tier]),
    setView: name => calls.push(['view', name]),
  });
  return calls;
}
assert.deepEqual(launch('subscription_basic', ['basic', 'mobile']), [['subscription', 'basic']]);
assert.deepEqual(launch('subscription_mobile', ['basic', 'mobile']), [['subscription', 'mobile']]);
assert.deepEqual(launch('subscription_mobile', ['basic']), [['view', 'subscriptions']]);
assert.deepEqual(launch('', ['mobile'], 'subscription_mobile'), [['subscription', 'mobile']]);
assert.deepEqual(launch('unknown', ['mobile']), []);
console.log('Happ → Mini App: 5 scenarios passed');
