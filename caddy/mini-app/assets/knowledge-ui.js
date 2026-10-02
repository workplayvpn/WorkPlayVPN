"use strict";
// Shared visual renderer. Article and ticket text is inserted using textContent.
window.WorkPlayKnowledge = (() => {
  const icons={"Подключение":"🚀","Подписки":"✨","Устройства":"📱","Проблемы":"🛟","Рефералы":"🤝","Поддержка":"💬"};
  function node(tag,text,cls){const el=document.createElement(tag);if(text!==null)el.textContent=text;if(cls)el.className=cls;return el;}
  function mount(articles,assets){
    const list=document.querySelector('#knowledge-list'),search=document.querySelector('#knowledge-search'),filters=document.querySelector('#knowledge-filters');
    let group='Все';
    const groups=['Все',...new Set(articles.map(a=>a.group))];
    filters.replaceChildren();
    for(const name of groups){const b=node('button',`${icons[name]||'✦'} ${name}`,'kb-filter');b.type='button';b.setAttribute('aria-pressed',String(name===group));b.addEventListener('click',()=>{group=name;for(const btn of filters.children)btn.setAttribute('aria-pressed',String(btn===b));render();});filters.append(b);}
    function render(){
      const query=search.value.trim().toLocaleLowerCase('ru');
      const matches=articles.filter(a=>(group==='Все'||a.group===group)&&[a.title,a.subtitle,a.group,...a.paragraphs].join(' ').toLocaleLowerCase('ru').includes(query));
      list.replaceChildren();document.querySelector('#knowledge-count').textContent=`${matches.length} из ${articles.length}`;
      for(const a of matches){
        const card=node('details',null,'kb-article'),summary=node('summary',null),cover=node('span',null,'kb-cover'),img=document.createElement('img');img.src=`${assets}/help/${a.art}.svg`;img.alt='';img.width=150;img.height=150;cover.append(img);
        const copy=node('span',null,'kb-card-copy'),meta=node('span',null,'kb-card-meta');meta.append(node('span',`${a.emoji} ${a.group}`),node('span',`${Math.max(1,Math.ceil(a.paragraphs.join(' ').length/850))} мин`));
        const read=node('span',null,'kb-read');read.append(node('span','Открыть инструкцию'),node('span','↗'));copy.append(meta,node('strong',a.title),node('small',a.subtitle),read);summary.append(cover,copy);
        const body=node('div',null,'kb-body'),steps=node('ol',null);for(const p of a.paragraphs)steps.append(node('li',p));body.append(steps,node('div','💡 Если вопрос остался, открой «Сообщить о проблеме» — подскажем, что проверить.','kb-note'));card.append(summary,body);
        card.addEventListener('toggle',()=>{read.firstChild.textContent=card.open?'Свернуть инструкцию':'Открыть инструкцию';if(card.open)for(const other of list.children)if(other!==card)other.open=false;});list.append(card);
      }
      if(!matches.length)list.append(node('div','🔎 Ничего не найдено. Попробуй другой запрос или выбери раздел «Все».','kb-empty'));
    }
    search.addEventListener('input',render);render();return {render};
  }
  return {mount,node};
})();
