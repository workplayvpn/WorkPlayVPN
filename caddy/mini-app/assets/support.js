"use strict";
const supportState = { articles: null, knowledgeLoading: false, ticketsLoading: false, key: null, fingerprint: null };
const supportStatuses = {new:"Новое",in_progress:"В работе",resolved:"Решено",closed:"Закрыто"};
const supportCategories = {connection:"Подключение",speed:"Скорость, видео или игры",device:"Устройства",payment:"Оплата",referral:"Рефералы",other:"Другой вопрос"};
function supportNode(tag, text, className) { const node=document.createElement(tag);node.textContent=text;if(className)node.className=className;return node; }
function renderKnowledge() {
  const list=document.querySelector("#knowledge-list");list.replaceChildren();
  const query=document.querySelector("#knowledge-search").value.trim().toLocaleLowerCase("ru");
  const matches=(supportState.articles||[]).filter(x=>[x.title,x.group,...x.paragraphs].join(" ").toLocaleLowerCase("ru").includes(query));
  for(const article of matches) {
    const details=document.createElement("details");details.className="knowledge-article";
    details.append(supportNode("summary",article.title),supportNode("span",article.group,"eyebrow"));
    for(const paragraph of article.paragraphs) details.append(supportNode("p",paragraph));
    list.append(details);
  }
  if(!matches.length) list.append(supportNode("p","Ответ не найден. Попробуй другой запрос или сообщи о проблеме."));
}
async function loadKnowledge() {
  if(supportState.articles){renderKnowledge();return;}
  if(supportState.knowledgeLoading)return;supportState.knowledgeLoading=true;
  const error=document.querySelector("#knowledge-error");error.textContent="Загружаем инструкции…";
  try {const response=await fetch("/app/assets/knowledge.json?v=20261003-2");if(!response.ok)throw new Error();supportState.articles=await response.json();error.textContent="";renderKnowledge();}
  catch {error.textContent="Не удалось загрузить инструкции. Открой раздел повторно или напиши в поддержку.";}
  finally {supportState.knowledgeLoading=false;}
}
function prepareSupportForm() {
  const select=document.querySelector("#support-device");const previous=select.value;
  select.replaceChildren(supportNode("option","Это устройство / не относится к вопросу"));select.firstChild.value="";
  for(const device of state.devices) {const option=supportNode("option",`${device.device_name} · ${device.public_id}`);option.value=device.id;select.append(option);}
  if([...select.options].some(x=>x.value===previous))select.value=previous;
}
async function loadSupportTickets() {
  if(supportState.ticketsLoading)return;supportState.ticketsLoading=true;
  const list=document.querySelector("#support-history"),error=document.querySelector("#support-history-error");error.textContent="Загружаем обращения…";
  try {
    const tickets=await api("/mini-app/support/tickets");list.replaceChildren();error.textContent="";
    if(!tickets.length)list.append(supportNode("p","Обращений пока нет. Если что-то не работает, заполни форму выше."));
    for(const ticket of tickets){
      const row=document.createElement("article");row.className="referral-history-row";
      row.append(supportNode("strong",`${supportCategories[ticket.category]||"Обращение"} · ${supportStatuses[ticket.status]||ticket.status}`),supportNode("span",`№ ${ticket.id}`),supportNode("span",new Date(ticket.created_at).toLocaleString("ru-RU")),supportNode("p",ticket.description));
      if(ticket.response)row.append(supportNode("strong","Ответ поддержки"),supportNode("p",ticket.response));
      const button=supportNode("button","Скопировать номер","button button-secondary");button.type="button";button.addEventListener("click",async()=>{try{await navigator.clipboard.writeText(ticket.id);showToast("Номер скопирован.");}catch{showToast("Не удалось скопировать номер.","error");}});row.append(button);list.append(row);
    }
  }catch(errorValue){error.textContent=humanError(errorValue);}
  finally{supportState.ticketsLoading=false;}
}
function supportPlatform() {
  const p=detectDevice().platform.toLowerCase();return ({ios:"ios",ipados:"ios",android:"android",windows:"windows",macos:"macos",linux:"linux"})[p]||"unknown";
}
document.querySelector("#knowledge-search").addEventListener("input",renderKnowledge);
document.querySelector("#support-refresh").addEventListener("click",loadSupportTickets);
document.querySelector("#support-form").addEventListener("submit",async(event)=>{
  event.preventDefault();const description=document.querySelector("#support-description").value.trim();
  const result=document.querySelector("#support-result");if(description.length<20||description.length>3000){result.textContent="Опиши проблему: от 20 до 3000 символов.";return;}
  const payload={category:document.querySelector("#support-category").value,tier:document.querySelector("#support-tier").value,network:document.querySelector("#support-network").value,description,platform:supportPlatform(),device_id:document.querySelector("#support-device").value?Number(document.querySelector("#support-device").value):null};
  const fingerprint=JSON.stringify(payload);if(supportState.fingerprint!==fingerprint){supportState.key=makeIdempotencyKey();supportState.fingerprint=fingerprint;}
  payload.idempotency_key=supportState.key;const button=document.querySelector("#support-submit");button.disabled=true;result.textContent="Отправляем обращение…";
  try {const ticket=await api("/mini-app/support/tickets",{method:"POST",body:JSON.stringify(payload)});result.textContent=`Обращение сохранено. Номер: ${ticket.id}. Статус и ответ — в базе знаний, раздел «Мои обращения».`;document.querySelector("#support-description").value="";supportState.key=null;supportState.fingerprint=null;}
  catch(error){result.textContent=humanError(error);if(error instanceof ApiError&&error.status>=400&&error.status<500){supportState.key=null;supportState.fingerprint=null;}}
  finally{button.disabled=false;}
});
