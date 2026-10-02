"use strict";
let knowledgeSiteLoading=false;
async function loadSiteKnowledge(){
 if(knowledgeSiteLoading)return;knowledgeSiteLoading=true;const error=document.querySelector('#knowledge-error');
 try{if(!await window.WorkPlayHelpAccess.ensure())return;const articles=await window.WorkPlayHelpAccess.request('/help-access/knowledge');window.WorkPlayKnowledge.mount(articles,'/assets');error.textContent='';}
 catch(e){if(e.status===403)window.WorkPlayHelpAccess.lock();else error.textContent='Не удалось загрузить инструкции. Обнови страницу или напиши в @workplayvpnteam.';}
 finally{knowledgeSiteLoading=false;}
}
document.addEventListener('help-access-unlocked',loadSiteKnowledge);
document.addEventListener('help-access-locked',()=>{document.querySelector('#knowledge-list').replaceChildren();});
loadSiteKnowledge();
