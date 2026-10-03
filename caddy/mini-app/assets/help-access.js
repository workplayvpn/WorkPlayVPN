"use strict";
window.WorkPlayHelpAccess=(()=>{
 const mini=location.pathname.startsWith('/app/');let checking=null,unlocked=false,session=null;
 class AccessError extends Error{constructor(status,detail){super(detail);this.status=status;}}
 function applySession(headers,path){if(mini&&session&&path.startsWith('/mini-app/support/'))headers.set('X-Help-Session',session);}
 async function request(path,options={}){
  const headers=new Headers(options.headers||{});if(options.body)headers.set('Content-Type','application/json');
  if(mini)headers.set('X-Telegram-Init-Data',window.Telegram?.WebApp?.initData||'');applySession(headers,path);
  const response=await fetch(path,{...options,headers,credentials:'same-origin',cache:'no-store'});
  if(!response.ok){let detail='Не удалось выполнить запрос. Попробуй ещё раз.';try{const data=await response.json();if(typeof data.detail==='string')detail=data.detail;}catch{}throw new AccessError(response.status,detail);}
  return response.json();
 }
 function lock(){session=null;unlocked=false;document.querySelectorAll('[data-help-gate]').forEach(x=>x.hidden=false);document.querySelectorAll('[data-help-protected]').forEach(x=>x.hidden=true);document.dispatchEvent(new Event('help-access-locked'));}
 function show(){unlocked=true;document.querySelectorAll('[data-help-gate]').forEach(x=>x.hidden=true);document.querySelectorAll('[data-help-protected]').forEach(x=>x.hidden=false);}
 async function ensure(){
  if(checking)return checking;
  checking=(async()=>{try{await request(mini?'/mini-app/support/session':'/help-access/session');show();return true;}catch{lock();return false;}finally{checking=null;}})();return checking;
 }
 document.querySelectorAll('[data-help-login]').forEach(form=>form.addEventListener('submit',async event=>{
  event.preventDefault();const field=form.querySelector('[data-help-key]'),error=form.querySelector('[data-help-error]'),button=form.querySelector('button[type=submit]'),key=field.value.trim();
  if(!key){error.textContent='Введи ключ помощи.';field.focus();return;}if(button.disabled)return;button.disabled=true;error.textContent='Проверяем ключ…';
  try{if(checking)await checking;const result=await request(mini?'/mini-app/support/login':'/help-access/login',{method:'POST',body:JSON.stringify({key})});if(mini)session=result.session||null;
   // Mini App server verifies that the key belongs to the Telegram account.
   if(!await ensure())throw Error('Не удалось подтвердить вход. Закрой и снова открой Mini App, затем повтори вход.');
   document.querySelectorAll('[data-help-key]').forEach(x=>x.value='');error.textContent='';document.dispatchEvent(new Event('help-access-unlocked'));window.scrollTo({top:0,behavior:'instant'});
  }catch(e){error.textContent=e.message==='HELP_KEY_REQUIRED'?'Введи ключ помощи ещё раз.':e.message;}finally{button.disabled=false;}
 }));
 document.querySelectorAll('[data-help-logout]').forEach(button=>button.addEventListener('click',async()=>{
  button.disabled=true;try{await request('/help-access/logout',{method:'POST'});lock();document.querySelectorAll('[data-help-key]').forEach(x=>x.value='');document.querySelectorAll('[data-help-own-key]').forEach(x=>{x.hidden=true;x.querySelector('code').textContent='';});}catch{if(mini&&typeof showToast==='function')showToast('Не удалось выйти. Попробуй ещё раз.','error');else alert('Не удалось выйти. Попробуй ещё раз.');}finally{button.disabled=false;}
 }));
 document.querySelectorAll('[data-help-show-key]').forEach(button=>button.addEventListener('click',async()=>{
  const box=button.parentElement.querySelector('[data-help-own-key]');button.disabled=true;
  try{const data=await request('/mini-app/support/access-key');box.querySelector('code').textContent=data.key;box.hidden=false;}catch{const form=button.closest('[data-help-gate]').querySelector('[data-help-login]');form.querySelector('[data-help-error]').textContent='Не удалось получить ключ. Открой бота → «Помощь» или запусти Mini App заново.';}finally{button.disabled=false;}
 }));
 document.querySelectorAll('[data-help-copy-key]').forEach(button=>button.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(button.parentElement.querySelector('code').textContent);button.textContent='Скопировано ✓';}catch{button.textContent='Выдели и скопируй ключ вручную';}}));
 return {ensure,lock,request,applySession,isUnlocked:()=>unlocked};
})();
