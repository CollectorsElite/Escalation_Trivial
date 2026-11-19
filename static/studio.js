'use strict';
function categoryList(){const names=new Map(state.questions.map(q=>[q.category_id,q.category]));return [...new Set([...Object.keys(topics),...names.keys()])].filter(id=>names.has(id)).map(id=>[id,names.get(id)]);}
function categoryCards(){return categoryList().map(([id,name])=>{
  const qs=state.questions.filter(q=>q.category_id===id), n=qs.filter(q=>state.selected.has(q.id)).length;
  const [sym,,color]=topics[id]||['layers',name,'#b8c6bd'];
  return `<div class="category-group"><button type="button" class="category ${n===qs.length?'active':n?'partial':''}" style="--t:${color}" data-action="category" data-id="${esc(id)}" aria-pressed="${n===qs.length?'true':n?'mixed':'false'}"><span class="cat-top"><span class="cat-icon">${icon(sym)}</span><span class="cat-check">${n===qs.length?icon('check'):n?'−':'+'}</span></span><strong>${esc(name)}</strong><small>${n?`${n} di ${qs.length} selezionate`:`${qs.length} domande`}</small></button><button type="button" class="text-btn btn" data-action="browse-category" data-id="${esc(id)}" aria-label="Scegli singole domande di ${esc(name)}">Scegli domande</button></div>`;
}).join('');}
function filtered(){const text=state.search.trim().toLocaleLowerCase('it');return state.questions.filter(q=>(state.category==='all'||q.category_id===state.category)&&(state.level==='all'||q.difficulty===state.level)&&(!text||[q.text,q.category,q.id].some(v=>v.toLocaleLowerCase('it').includes(text))));}
function drawControls() {
  const categories=categoryList();
  if (state.drawCategories === null) state.drawCategories=new Set(categories.map(([id])=>id));
  const choices=categories.map(([id,name])=>`<label class="draw-choice">
    <input type="checkbox" data-draw-category="${esc(id)}" ${state.drawCategories.has(id)?'checked':''}>
    <span>${esc(name)}</span></label>`).join('');
  return `<fieldset class="draw-panel"><legend>Categorie per la pesca automatica</legend>
    <div class="draw-choices">${choices}</div>
    <div class="draw-footer"><label for="draw-count">Numero di domande</label>
      <input id="draw-count" type="number" min="1" max="${state.questions.length}" value="${state.drawCount}" required>
      ${act('mix','Pesca domande','mix','soft')}</div></fieldset>`;
}
function multiplier(q){return state.multipliers[q.id] ?? (q.difficulty==='Avanzato'?2:1);}
function questionRows(qs){return qs.map(q=>`<div class="qrow"><label><input type="checkbox" data-question="${esc(q.id)}" ${state.selected.has(q.id)?'checked':''}><span><strong>${esc(q.text)}</strong><small>${esc(questionCode(q))} · ${esc(q.difficulty)} · ${q.options.length} opzioni</small></span></label><select class="bonus-select" data-bonus="${esc(q.id)}" aria-label="Moltiplicatore per ${esc(q.id)}">${[1,2,3].map(n=>`<option value="${n}" ${multiplier(q)===n?'selected':''}>${n===1?'Standard':'Bonus ×'+n}</option>`).join('')}</select>${act('preview','Dettagli' ,'visible','text-btn',`data-id="${esc(q.id)}"`)}</div>`).join('')||'<p class="empty">Nessuna domanda corrisponde ai filtri.</p>';}
function renderStudio(){const ages=['Base','Intermedio','Avanzato'];
  show(`<div class="shell studio"><div class="page-title"><div><div class="eyeline"><i class="pip"></i>Regia docente</div><h1>${state.editing?'Modifica la selezione':'Prepara la partita'}<em>.</em></h1><p>${state.activeSet?'Set aperto · <strong>'+esc(state.activeSet.name)+'</strong>':'Scegli le domande per questa classe o riprendi un set salvato.'}</p></div><div class="studio-actions">${act('sets','Set salvati','cards','soft')}${act('new-question','Nuova domanda','edit','soft')}</div></div><div class="studio-layout"><div class="studio-main"><section class="panel"><div class="section-head"><h2>Componi il quiz</h2></div>${drawControls()}<h3 class="manual-title">Selezione manuale</h3><div class="cats" id="category-tiles">${categoryCards()}</div></section><section class="panel"><div class="section-head"><h2>Catalogo domande</h2><span class="mono muted" id="filter-count"></span></div><div class="filters"><label class="searchbar">${icon('search')}<input id="question-search" placeholder="Cerca per testo o codice" aria-label="Cerca le domande" value="${esc(state.search)}"></label><label><span class="sr">Categoria</span><select id="category-filter"><option value="all">Tutte le categorie</option>${categoryList().map(([id,name])=>`<option value="${esc(id)}" ${id===state.category?'selected':''}>${esc(name)}</option>`).join('')}</select></label><label><span class="sr">Difficoltà</span><select id="level-filter"><option value="all">Tutti i livelli</option>${ages.map(a=>`<option ${a===state.level?'selected':''}>${a}</option>`).join('')}</select></label></div><div class="section-tools">${act('select-visible','Seleziona visibili','check','text-btn')}${act('clear','Svuota selezione','x','text-btn')}</div><div class="qscroll" id="question-list"></div></section></div><aside class="panel deck paper"><div class="deck-head"><div class="eyeline">Il tuo quiz</div><div class="deck-count"><strong id="selected-count">0</strong><span>domande<br>selezionate</span></div><div class="deck-rule"></div></div><div class="deck-controls"><label for="quiz-title">Titolo della partita</label><input id="quiz-title" maxlength="90" placeholder="Es. Formazione del personale" value="${esc(state.quizTitle)}"><label class="toggle"><input type="checkbox" id="bets" ${state.bets?'checked':''}>Consenti due Raddoppi personali</label><div class="deck-breakdown" id="deck-breakdown"></div><label for="duration">Tempo per domanda</label><select id="duration">${[...new Set([10,15,20,30,45,60,90,120,state.duration])].sort((a,b)=>a-b).map(v=>`<option value="${v}" ${v===state.duration?'selected':''}>${v} secondi</option>`).join('')}</select><label class="toggle"><input id="shuffle" type="checkbox" ${state.shuffle?'checked':''}><span>Mescola l’ordine delle domande</span></label><label class="toggle"><input id="reveal-complete" type="checkbox" ${state.revealOnComplete?'checked':''}><span>Mostra la soluzione quando tutti hanno risposto</span></label><p class="small muted" id="estimate"></p><p class="reading-hint" id="reading-hint" hidden></p><button class="btn primary cta" type="button" data-action="save-deck">${state.editing?'Salva modifiche':'Apri la lobby'} ${icon('arrow')}</button>${setActions()}${state.editing?act('back-lobby','Torna alla lobby','back','text-btn wide'):''}</div></aside></div></div>`,'studio');
  refreshStudio();
}
function refreshStudio({rows=true,cats=true}={}){
  if(!$('#selected-count'))return;
  const n=state.selected.size, q=state.questions.filter(x=>state.selected.has(x.id)), ab=q.filter(x=>x.type==='AB').length;
  $('#selected-count').textContent=fmt(n);
  $('#deck-breakdown').innerHTML=`<span><b>${ab}</b> a 2 opzioni</span><span><b>${n-ab}</b> a 4 opzioni</span>`;
  const minutes=Math.ceil(n*state.duration/60);$('#estimate').textContent=n?`Tempo massimo di risposta complessivo: ${minutes} min. Discussione esclusa.`:'Scegli almeno una domanda per aprire la lobby.';
  const readingHint = $('#reading-hint');
  const longer = state.duration < 45 ? q.filter(item => [item.text,...item.options].join(' ').trim().split(/\s+/u).length >= 45).length : 0;
  readingHint.hidden = longer === 0;
  if (longer) readingHint.textContent = `${longer === 1 ? 'Un quesito raggiunge' : longer+' quesiti raggiungono'} 45 parole fra domanda e opzioni. Per dare tempo alla lettura, valuta 45–60 secondi.`;
  $('[data-action="save-deck"]').disabled=n===0||state.busy;
  for(const button of all('.set-actions button')) button.disabled=n===0||state.busy;
  if(cats){const focus=document.activeElement?.dataset;const id=focus?.action==='category'?focus.id:null;$('#category-tiles').innerHTML=categoryCards();if(id)all('[data-action="category"]').find(el=>el.dataset.id===id)?.focus({preventScroll:true});}
  const items=filtered();$('#filter-count').textContent=`${items.length} / ${state.questions.length}`;
  if(rows)$('#question-list').innerHTML=questionRows(items);
  $('[data-action="select-visible"]').disabled=!items.length||items.every(x=>state.selected.has(x.id));
  $('[data-action="clear"]').disabled=n===0;
}
function previewQuestion(id) {
  const q=state.questions.find(item=>item.id===id);
  if(!q) return;
  modal('Dettaglio domanda',`${topic(q)}
    <div class="muted small gap-top">${esc(questionCode(q))} · ${esc(q.difficulty)} · ${q.revision?'Docente':'Catalogo di base'}</div>
    <h3 class="preview-title">${esc(q.text)}</h3><div class="options preview-options">${q.options.map((v,i)=>optionRow(v,i,{correct:i===q.correct})).join('')}</div>
    <div class="explain">${icon('info')}<p>${esc(q.explanation)}</p></div>`,
    q.revision ? act('edit-question','Modifica domanda','edit','soft',`data-id="${esc(id)}"`):
      act('copy-question','Crea una copia','copy','soft',`data-id="${esc(id)}"`));
}
function balancedDraw(){
  const input=$('#draw-count');
  if(!input.reportValidity())return;
  if(!state.drawCategories.size){notice('Seleziona almeno una categoria per la pesca.');return;}
  const count=input.valueAsNumber;
  const groups=[...state.drawCategories].map(id=>shuffled(state.questions.filter(q=>q.category_id===id))).filter(group=>group.length);
  const available=groups.reduce((total, group)=>total+group.length,0);
  if(count>available){notice(`Le categorie scelte contengono ${available} domande. Riduci il numero richiesto.`);input.focus();return;}
  const deck=[];
  while(deck.length<count){
    for(const group of shuffled(groups.filter(group=>group.length))){
      deck.push(group.pop().id);
      if(deck.length===count)break;
    }
  }
  state.drawCount=count;
  state.selected=new Set(deck);
  refreshStudio();
  notice(`Estratte ${count} domande da ${Math.min(groups.length,count)} categorie.`);
}
function shuffled(values){const arr=[...values];for(let i=arr.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[arr[i],arr[j]]=[arr[j],arr[i]];}return arr;}
