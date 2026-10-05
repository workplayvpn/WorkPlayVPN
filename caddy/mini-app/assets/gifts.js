/* Gifts use authenticated server prices and explicit, one-time redemption. */
const giftUI = {pane:"home", tab:"purchased", data:{purchased:[],activated:[]}, loading:false, buying:false, keys:new Map(), order:null, timer:null, generation:0};
const giftElement = (id) => document.getElementById(id);
function giftNode(tag, text, className="") {const node=document.createElement(tag);node.textContent=text;node.className=className;return node;}
function giftError(error) {const node=giftElement("gift-error");node.textContent=error instanceof ApiError && error.status<500 && /[А-Яа-я]/.test(error.detail) ? error.detail : humanError(error);node.classList.remove("hidden");}
function giftButton(text, action) {const button=giftNode("button",text,"button button-secondary");button.type="button";button.addEventListener("click",async()=>{button.disabled=true;try{await action(button);}catch(error){giftError(error);}finally{button.disabled=false;}});return button;}
function giftPane(name) {giftUI.pane=name;giftElement("gift-error").classList.add("hidden");document.querySelectorAll("[data-gift-pane]").forEach(node=>node.classList.toggle("hidden",node.dataset.giftPane!==name));if(name==="mine")renderGiftList();}
function giftTier(tier) {return tier==="mobile"?"Mobile":"Basic";}
function giftMoney(row) {return new Intl.NumberFormat("ru-RU",{style:"currency",currency:row.currency}).format(Number(row.amount));}
async function giftCopy(value, button) {try{await navigator.clipboard.writeText(value);button.textContent="✓ Скопировано";}catch{showToast("Не удалось скопировать. Нажмите на код и выделите его вручную.","error");}}
function renderGiftOffers(rows) {
  const root=giftElement("gift-offers");root.replaceChildren();
  for(const tier of ["basic","mobile"]){const offers=rows.filter(row=>row.access_tier===tier);if(!offers.length)continue;root.append(giftNode("h2",giftTier(tier)));for(const row of offers){const card=giftNode("article","","gift-card");card.append(giftNode("h3",`${row.duration_days} дней · ${row.device_limit} устройства`),giftNode("strong",giftMoney(row),"gift-price"),giftButton("Купить подарок",()=>buyGift(row)));root.append(card);}}
  if(!rows.length)root.append(giftNode("p","Доступных подарков пока нет."));
}
function renderGiftList() {
  const root=giftElement("gift-list");root.replaceChildren();
  giftElement("gift-purchased-tab").setAttribute("aria-pressed",String(giftUI.tab==="purchased"));giftElement("gift-activated-tab").setAttribute("aria-pressed",String(giftUI.tab==="activated"));
  const labels={ready:"Готов к передаче",pending:"Ожидает оплаты",redeemed:"Активирован",canceled:"Отменён",expired:"Счёт истёк",failed:"Ошибка оплаты"};
  for(const row of giftUI.data[giftUI.tab]) {const card=giftNode("article","","gift-card");card.append(giftNode("h3",`${giftTier(row.access_tier)} · ${row.duration_days} дней`),giftNode("p",`${row.is_test?"🧪 Тестовый подарок · ":""}${labels[row.state]||row.state}`,"gift-status"));
    if(row.code){card.append(giftNode("code",row.code,"gift-code-value"),giftButton("Скопировать код",button=>giftCopy(row.code,button)),giftButton("Поделиться подарком",()=>openBotLink(`https://t.me/share/url?url=${encodeURIComponent(row.share_url)}&text=${encodeURIComponent(`Дарю Work&PlayVPN ${giftTier(row.access_tier)} на ${row.duration_days} дней!`)}`)));}
    if(row.state==="pending")card.append(giftButton("Продолжить оплату",()=>{giftUI.order=row;giftPane("invoice");renderGiftInvoice();if(row.confirmation_url)openExternal(row.confirmation_url);}));root.append(card);
  }
  if(!giftUI.data[giftUI.tab].length)root.append(giftNode("p","Подарков пока нет.","gift-loading"));
  if(giftUI.data.next_offset!==null && giftUI.data.next_offset!==undefined)root.append(giftButton("Загрузить более ранние подарки",async()=>{const more=await api(`/mini-app/gifts?offset=${giftUI.data.next_offset}`);for(const tab of ["purchased","activated"]){const known=new Set(giftUI.data[tab].map(row=>row.id));giftUI.data[tab].push(...more[tab].filter(row=>!known.has(row.id)));}giftUI.data.next_offset=more.next_offset;renderGiftList();}));
}
function renderGiftInvoice() {
  if(!giftUI.order)return;const root=giftElement("gift-invoice");root.replaceChildren();const id=giftUI.order.payment_id||giftUI.order.id;const row=giftUI.data.purchased.find(item=>item.payment_id===id)||giftUI.order;
  if(row.state && row.state!=="pending") {root.append(giftNode("h2",row.state==="ready"?"Подарок готов 🎁":"Счёт завершён"),giftButton("К моим подаркам",()=>{giftUI.tab="purchased";giftPane("mine");}));giftUI.keys.clear();return;}
  root.append(giftNode("h2","Ожидаем оплату"),giftNode("p",`Заказ #${id} · ${giftMoney(row)}`),giftNode("p","После подтверждения оплаты код появится в «Моих подарках». Страница проверяет оплату автоматически."));
  if(row.confirmation_url)root.append(giftButton("Перейти к оплате",()=>openExternal(row.confirmation_url)));root.append(giftButton("Проверить оплату",()=>loadGifts()));
}
async function loadGifts() {
  if(giftUI.loading)return;giftUI.loading=true;clearTimeout(giftUI.timer);
  try{const [catalog,data]=await Promise.all([api("/mini-app/gifts/catalog"),api("/mini-app/gifts")]);giftUI.data=data;renderGiftOffers(catalog);renderGiftList();renderGiftInvoice();}catch(error){giftError(error);}finally{giftUI.loading=false;if(state.view==="gifts"&&giftUI.data.purchased.some(row=>row.state==="pending"))giftUI.timer=setTimeout(()=>{if(state.view==="gifts")loadGifts();},10000);}
}
async function buyGift(plan) {
  if(giftUI.buying)return;giftUI.buying=true;
  try{let order=giftUI.data.purchased.find(row=>row.state==="pending"&&row.access_tier===plan.access_tier&&row.duration_days===plan.duration_days);if(!order){if(!giftUI.keys.has(plan.code))giftUI.keys.set(plan.code,makeIdempotencyKey());order=await api("/mini-app/gifts/payments",{method:"POST",body:JSON.stringify({plan_code:plan.code,idempotency_key:giftUI.keys.get(plan.code)})});}giftUI.order=order;giftPane("invoice");renderGiftInvoice();await loadGifts();if(order.confirmation_url)openExternal(order.confirmation_url);}finally{giftUI.buying=false;}
}
document.querySelectorAll("[data-gift-open]").forEach(node=>node.addEventListener("click",()=>giftPane(node.dataset.giftOpen)));
giftElement("gift-back").addEventListener("click",()=>giftUI.pane==="home"?setView("home"):giftPane("home"));
giftElement("gift-refresh").addEventListener("click",()=>loadGifts());
for(const tab of ["purchased","activated"])giftElement(`gift-${tab}-tab`).addEventListener("click",()=>{giftUI.tab=tab;renderGiftList();});
giftElement("gift-code").addEventListener("input",()=>{giftUI.generation++;giftElement("gift-preview").classList.add("hidden");});
giftElement("gift-redeem-form").addEventListener("submit",async(event)=>{
  event.preventDefault();const submit=event.currentTarget.querySelector("button");submit.disabled=true;const code=giftElement("gift-code").value;const generation=giftUI.generation;giftElement("gift-error").classList.add("hidden");
  try{const details=await api("/mini-app/gifts/preview",{method:"POST",body:JSON.stringify({code})});if(generation!==giftUI.generation)return;const preview=giftElement("gift-preview");preview.replaceChildren(giftNode("h2",`${giftTier(details.access_tier)} · ${details.duration_days} дней`),giftNode("p",details.already_activated?"Этот подарок уже активирован на вашем аккаунте.":"Подтвердите активацию на вашем аккаунте. Действующая подписка того же типа продлится."));
    if(!details.already_activated)preview.append(giftButton("Активировать на моём аккаунте",async()=>{if(generation!==giftUI.generation)return;const result=await api("/mini-app/gifts/redeem",{method:"POST",body:JSON.stringify({code})});showToast(result.already_activated?"Подарок уже активирован.":"Подарок активирован 🎁");giftElement("gift-code").value="";giftElement("gift-preview").classList.add("hidden");giftUI.generation++;giftUI.tab="activated";giftPane("mine");await loadGifts();await loadData();}));preview.classList.remove("hidden");
  }catch(error){giftError(error);}finally{submit.disabled=false;}
});
const incomingGift=new URLSearchParams(window.location.search).get("gift_code");
if(incomingGift&&/^[A-Z2-7]{24}$/.test(incomingGift)){giftElement("gift-code").value=incomingGift;giftPane("redeem");history.replaceState(null,"",window.location.pathname+"?view=gifts");}
