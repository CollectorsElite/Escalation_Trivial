'use strict';

function creationKey() {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, n => n.toString(16).padStart(2, '0')).join('');
}

function deckPayload() {
  const multipliers = Object.fromEntries(state.questions
    .filter(q => state.selected.has(q.id) && multiplier(q) > 1)
    .map(q => [q.id, multiplier(q)]));
  return {ids:[...state.selected], title:state.quizTitle, duration:state.duration, multipliers,
    bets:state.bets, shuffle:state.shuffle, revealOnComplete:state.revealOnComplete};
}

function setActions() {
  return `<div class="set-actions">
    ${act('name-set', state.activeSet ? 'Aggiorna set' : 'Salva come set', 'save', 'soft')}
    ${state.activeSet ? act('copy-draft','Salva come copia','copy','text-btn') : ''}
  </div>`;
}

function applySet(item) {
  const d = item.deck;
  const available = new Set(state.questions.map(q => q.id));
  if (d.ids.some(id => !available.has(id))) throw Error('Il catalogo è cambiato. Riapri il set per aggiornare la regia.');
  state.activeSet = {id:item.id, name:item.name, revision:item.revision};
  state.selected = new Set(d.ids);
  state.quizTitle = d.title;
  state.duration = d.duration;
  state.shuffle = d.shuffle;
  state.bets = d.bets;
  state.revealOnComplete = d.revealOnComplete;
  state.multipliers = Object.fromEntries(d.ids.map(id => [id, d.multipliers[id] || 1]));
  renderStudio();
}

function dialogError(message) {
  const element = $('#editor-error', dlg);
  if (element) {
    element.hidden=false; element.textContent=message;
    element.scrollIntoView({block:'nearest'});
  } else notice(message);
}

const editorErrorLine = '<p id="editor-error" role="alert" class="edit-error" hidden></p>';

async function savedSets(archived=false) {
  modal('Set salvati', `<div class="set-tabs" role="group" aria-label="Elenco dei set">
    ${act('sets','Disponibili',null,'soft',`aria-pressed="${!archived}"`)}
    ${act('sets-archived','Archiviati',null,'soft',`aria-pressed="${archived}"`)}
    </div>${archived?'<p class="edit-hint">Qui trovi i set archiviati dai docenti. Con «Ripristina» un set torna tra quelli disponibili. Le sue domande restano nel catalogo.</p>':''}
    <div id="set-list"><p class="muted" role="status">Caricamento…</p></div>${editorErrorLine}`);
  const list = $('#set-list');
  const items = await api('/api/admin/sets?archived=' + archived);
  if (!list.isConnected || !dlg.open) return;
  list.innerHTML = items.length ? items.map(s => {
    const attrs = `data-id="${esc(s.id)}" data-revision="${s.revision}"`;
    const updated = new Date(s.updatedAt * 1000).toLocaleString('it-IT',{dateStyle:'short',timeStyle:'short'});
    return `<article class="saved-card"><div class="saved-meta">${icon('cards')}
      ${fmt(s.count)} ${s.count===1?'domanda':'domande'} · ${esc(updated)}</div>
      <h3>${esc(s.name)}</h3><p>${s.categories.map(esc).join(' · ')}</p><div class="saved-actions">
      ${archived ? act('restore-set','Ripristina','back','soft',attrs) :
        act('open-set','Apri','arrow','primary',attrs) + act('duplicate-set','Duplica','copy','soft',attrs) +
        act('archive-set','Archivia',null,'text-btn',attrs)}</div></article>`;
  }).join('') : `<p class="empty">${archived?'Nessun set archiviato.':'Qui troverai i set condivisi. Seleziona le domande e scegli «Salva come set».'}</p>`;
}

// Opening a set refreshes the catalogue too: a second teacher may have just added questions.
async function openStoredSet(id, duplicate=false) {
  const origin = dlg.querySelector('#set-list') || dlg.querySelector('form');
  const [item] = await Promise.all([api('/api/admin/sets/' + encodeURIComponent(id)), overview()]);
  if (!dlg.open || !origin?.isConnected || document.body.dataset.view !== 'studio') return;
  if (item.archived) throw Error('Questo set è stato archiviato. Ripristinalo per aprirlo.');
  if (duplicate) return nameSet(true, item);
  dlg.close();
  applySet(item);
  notice(`Set «${item.name}» aperto.`);
}

function nameSet(copy=false, source=null) {
  const current=source || state.activeSet;
  const deck=source ? source.deck : deckPayload();
  if (!deck.ids.length) {notice('Seleziona almeno una domanda.');return;}
  const update=!!current && !copy;
  const initial=copy && current ? (current.name.slice(0,82)+' – copia') : current?.name || state.quizTitle;
  modal(update?'Aggiorna set':copy?'Duplica set':'Salva come set',
    `<form class="author-form" id="set-form">
      <label for="set-name">Nome del set</label>
      <input id="set-name" required maxlength="90" value="${esc(initial)}" placeholder="Es. Privacy – corso base" autofocus>
      <p class="edit-hint">${fmt(deck.ids.length)} domande · ${fmt(deck.duration)} secondi per domanda · Archivio condiviso</p>
      ${editorErrorLine}<div class="editor-actions">${act('close','Annulla',null,'text-btn')}
      <button class="btn primary" type="submit">${icon('save')}${update?'Aggiorna set':'Salva set'}</button></div></form>`);
  const form=$('#set-form');
  const key=creationKey();
  form.onsubmit=async event=>{
    event.preventDefault();
    await submitTeacherForm(form, async ()=>{
      const name=$('#set-name',form).value.trim();
      const path='/api/admin/sets' + (update ? '/' + encodeURIComponent(current.id) : '');
      const body={...deck, name, creationKey:key};
      if(update) body.expectedRevision=current.revision;
      const item=await api(path,update?'PATCH':'POST',body);
      if (!form.isConnected || !dlg.open) return;
      dlg.close(); applySet(item);
      notice(`Set «${item.name}» salvato.`);
    });
  };
}

async function changeArchive(id, revision, archived) {
  const change = await api('/api/admin/sets/' + encodeURIComponent(id),'PATCH',{archived,expectedRevision:revision});
  if (change.archived && state.activeSet?.id===id) {
    state.activeSet=null;
    if (document.body.dataset.view==='studio') renderStudio();
  }
  await savedSets(!archived);
  notice(archived?'Set archiviato.':'Set ripristinato.');
}

async function submitTeacherForm(form, job) {
  if (form.dataset.saving === 'true') return;
  form.dataset.saving='true';
  const buttons=[...form.querySelectorAll('button[type=submit]')];
  buttons.forEach(b => b.disabled=true);
  const error=$('#editor-error',form);
  if(error) error.hidden=true;
  try {
    await job();
  } catch(e) {
    if (!form.isConnected) return;
    if(e.status===401) {endAdminSession();return;}
    dialogError(e.message);
    if(e.code==='set_changed' && !form.querySelector('[data-action="copy-draft"]')) {
      error.insertAdjacentHTML('afterend', `<div class="saved-actions">${act('copy-draft','Salva la bozza come copia','copy','soft')}${act('sets','Riapri i set','cards','text-btn')}</div>`);
    }
    if(e.code==='question_changed' && !form.querySelector('[data-action="reload-question"]')) {
      error.insertAdjacentHTML('afterend', act('reload-question','Ricarica la versione salvata','back','soft',`data-id="${esc(form.dataset.questionId)}"`));
    }
  } finally {
    form.dataset.saving='false';
    buttons.forEach(b=>b.disabled=false);
  }
}

function questionCode(q) {
  return q.id.startsWith('DOC-') ? q.id.slice(0,12).toUpperCase() : q.id;
}

async function openQuestionEditor(id, copy=false) {
  let q;
  if(id) {
    const old=dlg.querySelector('.dialog-head');
    q=await api('/api/admin/catalogue/'+encodeURIComponent(id));
    if (!dlg.open || !old?.isConnected) return;
  }
  const existing=Boolean(q) && !copy;
  const category=q?.category_id || (state.category==='all'?'':state.category);
  const choices=new Map(categoryList());
  if(q) choices.set(q.category_id,q.category);
  const options=q?.options || ['', ''];
  const size=options.length;
  modal(existing?'Modifica domanda':copy?'Copia domanda':'Nuova domanda',
    `<form id="question-form" class="author-form">
      <div class="editor-pair"><label>Categoria<select name="category" required>
        <option value="">Scegli categoria</option>${[...choices].map(([k,n])=>`<option value="${esc(k)}" ${category===k?'selected':''}>${esc(n)}</option>`).join('')}
        <option value="__new">Crea categoria…</option></select></label>
      <label>Difficoltà<select name="difficulty">${['Base','Intermedio','Avanzato'].map(level=>`<option ${q?.difficulty===level?'selected':''}>${level}</option>`).join('')}</select></label></div>
      <label data-new-category hidden>Nome della nuova categoria<input name="newCategory" maxlength="80"></label>
      <label>Testo della domanda<textarea name="text" rows="2" required maxlength="600">${esc(q?.text)}</textarea></label>
      ${questionImageFields(q)}
      <fieldset class="answer-editor"><legend>Alternative e risposta corretta</legend>
      <label class="format-field">Formato <select name="format"><option value="2">2 alternative</option><option value="4" ${size===4?'selected':''}>4 alternative</option></select></label>
      ${[0,1,2,3].map(i=>`<div class="edit-option" data-option-row="${i}">
        <input type="radio" name="correct" value="${i}" aria-label="Segna ${letters[i]} come corretta" ${i===q?.correct?'checked':''} required>
        <label><span>${letters[i]}</span><input name="option${i}" aria-label="Testo alternativa ${letters[i]}" maxlength="240" value="${esc(options[i])}"></label></div>`).join('')}
      <p class="edit-hint">Seleziona il cerchio accanto all’alternativa corretta.</p></fieldset>
      <label>Spiegazione<textarea name="explanation" rows="2" required maxlength="1200">${esc(q?.explanation)}</textarea></label>
      ${copy?'<p class="edit-hint">Personalizza il testo, le alternative, la spiegazione o l’immagine per salvare la copia.</p>':''}
      ${existing?'<p class="edit-hint">La modifica si applica a tutti i set che contengono questa domanda.</p>':''}
      <details class="phone-preview"><summary>Anteprima sul telefono</summary><div data-phone-preview></div></details>
      ${editorErrorLine}<div class="editor-actions"><button type="submit" class="btn ${existing?'primary':'soft'}" value="save">${existing?'Salva modifiche':'Salva domanda'}</button>
      <button type="submit" class="btn ${existing?'soft':'primary'}" value="add">${icon('check')}Salva e aggiungi al set</button></div></form>`);
  const form=$('#question-form'), fields=form.elements, creation=creationKey();
  if (existing) form.dataset.questionId=q.id;
  const preview=$('details',form);
  const refresh=()=>{
    const count=Number(fields.format.value);
    const create=fields.category.value==='__new';
    $('[data-new-category]',form).hidden=!create;
    fields.newCategory.required=create;
    for(let i=0;i<4;i++){
      const row=$(`[data-option-row="${i}"]`,form);
      row.hidden=i>=count;
      const radio=$('[type="radio"]',row);
      radio.disabled=row.hidden;
      if(row.hidden) radio.checked=false;
      fields['option'+i].disabled=row.hidden;
      fields['option'+i].required=!row.hidden;
    }
    if(preview.open) {
      const categoryName=create?fields.newCategory.value:fields.category.selectedOptions[0].text;
      $('[data-phone-preview]',form).innerHTML=`<div class="sample-phone"><div class="sample-category">${esc(categoryName)}</div>
        <strong>${esc(fields.text.value.trim() || 'Testo della domanda')}</strong>${media.preview()}
        <div>${Array.from({length:count},(_,i)=>`<p>${answerMark(i)}<span>${esc(fields['option'+i].value || 'Alternativa '+letters[i])}</span></p>`).join('')}</div></div>`;
    }
  };
  const media=bindQuestionImageEditor(form,q,refresh);
  form.oninput=refresh; form.onchange=refresh; preview.ontoggle=refresh; refresh();
  form.onsubmit=async event=>{
    event.preventDefault();
    const add=event.submitter?.value==='add';
    await submitTeacherForm(form,async()=>{
      const count=Number(fields.format.value),create=fields.category.value==='__new';
      const payload={categoryId:create?'':fields.category.value,newCategory:create?fields.newCategory.value:'',
        difficulty:fields.difficulty.value,text:fields.text.value,
        options:Array.from({length:count},(_,i)=>fields['option'+i].value),correct:Number(fields.correct.value),
        explanation:fields.explanation.value,creationKey:creation,...await media.payload()};
      if(existing) payload.expectedRevision=q.revision;
      const saved=await api('/api/admin/catalogue'+(existing?'/'+encodeURIComponent(q.id):''),existing?'PUT':'POST',payload);
      if (!form.isConnected || !dlg.open) return;
      const index=state.questions.findIndex(item=>item.id===saved.id);
      const frozen=index>=0 && state.questions[index].frozen;
      if(!frozen) replaceStudioQuestions(index<0 ? [...state.questions,saved] :
        state.questions.map(item=>item.id===saved.id ? saved : item));
      if(add) state.selected.add(saved.id);
      dlg.close(); renderStudio();
      notice(frozen?'Correzione salvata per le prossime partite. La lobby conserva la sua versione.':
        add && state.activeSet?'Domanda aggiunta alla selezione. Premi «Aggiorna set» per salvare la composizione.':
        add?'Domanda salvata e aggiunta alla selezione.':'Domanda salvata nel catalogo.');
    });
  };
}
