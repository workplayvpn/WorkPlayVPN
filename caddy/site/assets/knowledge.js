"use strict";
(async()=>{const error=document.querySelector('#knowledge-error');try{const r=await fetch('/assets/knowledge.json?v=20261003-3');if(!r.ok)throw Error();window.WorkPlayKnowledge.mount(await r.json(),'/assets');}catch{error.textContent='Не удалось загрузить инструкции. Обнови страницу или напиши в @workplayvpnteam.';}})();
