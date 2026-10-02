"use strict";
const knowledgeSearch=document.querySelector("#knowledge-search");
knowledgeSearch.addEventListener("input",()=>{const query=knowledgeSearch.value.trim().toLocaleLowerCase("ru");let visible=0;document.querySelectorAll(".knowledge-article").forEach(article=>{const match=article.textContent.toLocaleLowerCase("ru").includes(query);article.hidden=!match;if(match)visible++;});document.querySelector("#knowledge-empty").hidden=visible>0;});
