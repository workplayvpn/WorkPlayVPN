const {readFileSync}=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const path=require('node:path');
const nodes=new Map();
function node(){return {textContent:'',children:[],dataset:{},classList:{add(){},remove(){},toggle(){}},append(...v){this.children.push(...v);},replaceChildren(...v){this.children=v;},setAttribute(){},addEventListener(name,fn){this[name]=fn;}};}
let external=[],toasts=[],confirmAnswer=false;
const context=vm.createContext({document:{getElementById(id){if(!nodes.has(id))nodes.set(id,node());return nodes.get(id);},createElement:node,querySelectorAll(){return[];}},window:{location:{search:'',pathname:'/app/'},confirm(){return confirmAnswer;}},history:{replaceState(){}},telegram:{showConfirm(msg,cb){cb(confirmAnswer);},isVersionAtLeast(){return true;}},state:{view:'home'},Intl,URLSearchParams,ApiError:class extends Error{},humanError:e=>e.message,openExternal:u=>external.push(u),showToast:m=>toasts.push(m),setTimeout(){},clearTimeout(){},makeIdempotencyKey:()=>"new-key",navigator:{},console});
vm.runInContext(readFileSync(path.join(__dirname,'../../caddy/mini-app/assets/gifts.js'),'utf8'),context);
const run=s=>vm.runInContext(s,context);
(async()=>{
 const plan={code:'basic30',access_tier:'basic',duration_days:30,device_limit:3,amount:'199',currency:'RUB'};
 let purchased=[{id:1,payment_id:25,state:'obsolete',access_tier:'basic',duration_days:30,amount:'199',currency:'RUB'}],calls=0;
 context.api=async(url,options)=>{if(url.endsWith('/catalog'))return[plan];if(options){calls++;return{id:26,status:'pending',amount:'199',currency:'RUB',confirmation_url:'https://example.com/pay'};}return{purchased,activated:[]};};
 await run('loadGifts()');
 assert.equal(nodes.get('gift-types').children.length,1);
 assert.equal(nodes.get('gift-offers').children.length,0);
 await nodes.get('gift-types').children[0].children.at(-1).click();
 assert.equal(run('giftUI.pane'),'catalog');
 assert.equal(nodes.get('gift-offers').children.length,1);
 await run('buyGift(giftUI.catalog[0])');
 assert.equal(calls,1);assert.equal(run('giftUI.pane'),'invoice');assert.equal(external.length,0);
 await run('openGiftPayment("https://example.com/pay")');assert.equal(external.length,0);
 confirmAnswer=true;await run('openGiftPayment("https://example.com/pay")');assert.equal(external.length,1);
 purchased=[{payment_id:26,state:'pending',amount:'199',currency:'RUB',confirmation_url:'https://example.com/pay'}];
 await run('checkGiftPayment()');assert.match(toasts.at(-1),/пока не подтверждена/);
 purchased[0].state='ready';await run('checkGiftPayment()');assert.match(toasts.at(-1),/Подарок готов/);
 console.log('Gift UI: tier selection, fresh invoice, no automatic navigation, confirm/cancel, payment feedback passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
