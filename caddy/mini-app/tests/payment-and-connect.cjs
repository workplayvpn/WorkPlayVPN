// No dependencies: execute the real UI functions in an isolated DOM/API harness.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(require('node:path').join(__dirname, '../assets/app.js'), 'utf8');
function harness() {
  const nodes = new Map(), calls = [], opened = [], navigation = [];
  const node = id => {
    if (!nodes.has(id)) nodes.set(id, {textContent:'', innerHTML:'Buy', disabled:false, dataset:{},
      classList:{toggle(){},add(){},remove(){}}, value:''});
    return nodes.get(id);
  };
  const order = {id:42,status:'pending',amount:'199.00',currency:'RUB',access_tier:'basic',
    plan_code:'standard_30d',duration_days:30,confirmation_url:'https://pay.example/42',expires_at:new Date(Date.now()+60000).toISOString()};
  const location = {origin:'https://connect.workplayvpn.ru',hash:'#tgWebAppData=test',assign:url=>navigation.push(url),set href(url){navigation.push(url);}};
  const context = vm.createContext({Map,URL,Date,Promise,Error,ApiError:Error,
    state:{view:'terms',detailTier:'basic',payment:null}, keyGeneration:0,
    document:{hidden:false,querySelector:node}, window:{location,confirm:()=>false},
    telegram:{isVersionAtLeast:()=>true,showPopup:(popup,cb)=>{context.popup=popup;context.finishPopup=cb;}},
    setTimeout:()=>1,clearTimeout(){},showToast(){},humanError:e=>e.message,haptic(){},
    closeSheet(){},elements:{slotSheet:{}},renderPayment(){},loadData:async()=>{context.reloads++;},reloads:0,
    setView:name=>{context.state.view=name;},tierLabel:tier=>tier==='mobile'?'Mobile':'Basic',
    activeSubscriptions:()=>[{access_tier:'basic'},{access_tier:'mobile'}],subscriptionTier:e=>e.access_tier,
    formatMoney:(amount,currency)=>`${amount} ${currency}`,makeIdempotencyKey:()=> 'test-idempotency-key',
    openExternal:url=>opened.push(url),
    api:async(path,options)=>{calls.push({path,options});return path.startsWith('/mini-app/keys/')?
      {url:'happ://crypt5/'+path.split('/').pop(),launch_url:'https://connect.workplayvpn.ru/connect/happ/launch/key/'+path.split('/').pop(),instruction_url:'https://connect.workplayvpn.ru/connect/happ/'+path.split('/').pop()}: {...order};},
  });
  vm.runInContext(source.slice(source.indexOf('// Payment links are'), source.indexOf('function renderProfile()')),context);
  vm.runInContext(source.slice(source.indexOf('const subscriptionKeys ='),source.indexOf('function clearKeyOutput()')),context);
  vm.runInContext(source.slice(source.indexOf('async function startPayment('),source.indexOf('async function changeAccountRegion(')),context);
  return {context,order,node,calls,opened,navigation,run:s=>vm.runInContext(s,context)};
}
(async()=>{
  const h=harness(); h.context.buy=h.node('buy');
  await h.run('startPayment({code:"standard_30d"},buy)');
  assert.equal(h.context.state.view,'checkout');assert.equal(h.opened.length,0);
  assert.equal(h.calls.filter(c=>c.options?.method==='POST').length,1);
  h.run('renderCheckout()');assert.equal(h.node('#checkout-order').textContent,'№ 42');
  assert.equal(h.node('#checkout-amount').textContent,'199.00 RUB');
  let pending=h.run('confirmPaymentLink(state.payment.confirmation_url)');
  assert.equal(h.context.popup.title,'Открыть ссылку?');h.context.finishPopup('cancel');
  assert.equal(await pending,false);assert.equal(h.opened.length,0);
  pending=h.run('confirmPaymentLink(state.payment.confirmation_url)');h.context.finishPopup('open');
  assert.equal(await pending,true);assert.deepEqual(h.opened,['https://pay.example/42']);
  await h.run('startPayment({code:"standard_30d"},buy)');
  assert.equal(h.calls.filter(c=>c.options?.method==='POST').length,2);
  await h.run('startPayment({code:"another"},buy)');
  assert.equal(h.calls.filter(c=>c.options?.method==='POST').length,3);
  assert.equal(JSON.parse(h.calls.at(-1).options.body).plan_code,'another');
  for (const tier of ['basic','mobile']) {
    const choice=harness(); choice.context.buy=choice.node('buy');
    choice.run(`state.payment={...${JSON.stringify(h.order)},access_tier:${JSON.stringify(tier)},plan_code:${JSON.stringify(tier+'_7d')},amount:'99.00',duration_days:7}`);
    await choice.run(`startPayment({code:${JSON.stringify(tier+'_30d')}},buy)`);
    assert.equal(choice.calls.filter(c=>c.options?.method==='POST').length,1);
    assert.equal(JSON.parse(choice.calls[0].options.body).plan_code,tier+'_30d');
  }
  const expired=harness(); expired.context.buy=expired.node('buy');
  expired.run(`state.payment={...${JSON.stringify(h.order)},expires_at:'2000-01-01T00:00:00Z'}`);
  await expired.run('startPayment({code:"standard_30d"},buy)');
  assert.equal(expired.calls.filter(c=>c.options?.method==='POST').length,1);
  assert.equal(await h.run('confirmPaymentLink("javascript:alert(1)")'),false);
  await h.run('refreshCheckout()');assert.equal(h.context.state.payment.id,42);
  assert.equal(h.context.reloads,0);assert.equal(h.calls.at(-1).path,'/mini-app/payments/42');
  h.context.api=async()=>{throw Error('offline');};await h.run('refreshCheckout()');
  assert.equal(h.context.state.payment.status,'pending');assert.match(h.context.state.checkoutError,/не подтверждён/);
  h.context.api=async()=>({...h.order,status:'succeeded',confirmation_url:null});await h.run('refreshCheckout()');
  assert.equal(h.context.reloads,1);assert.equal(h.node('#checkout-pay').disabled,true);
  h.run('state.payment.status="pending"; state.payment.expires_at="2000-01-01T00:00:00Z";renderCheckout()');
  assert.equal(h.node('#checkout-status').textContent,'Срок оплаты истёк');assert.equal(h.node('#checkout-pay').disabled,true);
  const k=harness();k.run('state.view="devices"');
  await k.run('prepareSubscriptionKey("basic")');await k.run('connectSubscriptionInHapp()');
  k.run('state.detailTier="mobile"');await k.run('prepareSubscriptionKey("mobile")');await k.run('connectSubscriptionInHapp()');
  assert.deepEqual(k.opened,['https://connect.workplayvpn.ru/connect/happ/launch/key/basic','https://connect.workplayvpn.ru/connect/happ/launch/key/mobile']);
  await k.run('openConnectionInstructions()');
  assert.equal(k.navigation[0],'https://connect.workplayvpn.ru/connect/happ/mobile?return_tier=mobile#tgWebAppData=test');
  assert.deepEqual(k.calls.map(c=>c.path),['/mini-app/keys/basic','/mini-app/keys/mobile']);
  assert.equal(k.calls.filter(c=>c.options?.method==='POST').length,0);
  k.context.supportState={checkIndex:4,tried:['old']};k.context.supportStage=stage=>{k.context.stage=stage;};
  k.run('openConnectionCheck()');
  assert.equal(k.context.state.view,'support');assert.equal(k.context.stage,'context');
  assert.equal(k.node('#support-title').textContent,'Проверить подключение');
  assert.equal(k.node('#support-category').value,'connection');assert.equal(k.node('#support-tier').value,'mobile');
  const stale=harness();stale.run('state.view="devices"');
  stale.context.api=()=>new Promise(resolve=>{stale.context.resolveKey=resolve;});
  const launch=stale.run('connectSubscriptionInHapp()');stale.run('state.detailTier="mobile"');
  stale.context.resolveKey({url:'happ://crypt5/basic'});await launch;assert.equal(stale.navigation.length,0);
  const fallback=harness();fallback.context.telegram=null;fallback.context.window.confirm=()=>true;
  assert.equal(await fallback.run('confirmPaymentLink("https://pay.example/42")'),true);
  assert.deepEqual(fallback.opened,['https://pay.example/42']);
  const connectSource=fs.readFileSync(require('node:path').join(__dirname,'../../../backend/app/static/happ_connect.js'),'utf8');
  const backCalls=[];
  const back=vm.createContext({URLSearchParams,telegramApp:{BackButton:{hide(){}},close(){backCalls.push('close');}},
    window:{history:{length:2,back(){backCalls.push('back');}},location:{search:'?return_tier=mobile',hash:'#tgWebAppData=test',assign:url=>backCalls.push(url)}}});
  vm.runInContext(connectSource.slice(connectSource.indexOf('function navigateBack()'),connectSource.indexOf('function initializeBackNavigation()')),back);
  vm.runInContext('navigateBack();window.history.length=1;navigateBack()',back);
  assert.deepEqual(backCalls,['back','/app/?view=devices&detail_tier=mobile#tgWebAppData=test']);
  console.log('PASS: payment regressions, HTTPS Happ launch, tier separation, same-WebView instructions with return tier, stale key and fallback');
})().catch(error=>{console.error(error);process.exitCode=1;});
