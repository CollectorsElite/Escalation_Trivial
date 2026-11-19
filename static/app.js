'use strict';
async function api(path,method='GET',body) {
  let r;try{r=await fetch(path,{method,credentials:'same-origin',headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});}catch{throw Error('Il server non è raggiungibile. Controlla la connessione e riprova.');}
  const data=await r.json().catch(()=>({}));if(!r.ok){const detail=data.detail;const err=Error(typeof detail==='string'?detail:detail?.message || `Richiesta non riuscita (${r.status}).`);err.status=r.status;err.code=detail?.code;throw err;}return data;
}
function stopSocket() {
  clearTimeout(state.reconnect); clearTimeout(state.syncTimer);
  state.syncTimer=null; state.reconnect=null;
  const ws=state.socket;
  state.socket=null; state.online=false;
  if(ws){ws.onopen=null;ws.onclose=null;ws.onmessage=null;ws.close();}
}
function resetPlayer(p=state.player) {
  stopSocket();
  if(dlg.open) dlg.close();
  forgetPlayer(p); rememberJoin(null);
  state.review=null; state.game=null; state.snap=null; state.pending=null; state.phaseKey='';
  state.tabLimit=false; state.retry=0;
  if(location.search) history.replaceState(null,'','/');
  showHome(); loadSummary();
}
async function loadSummary(){try{state.summary=await api('/api/catalogue-summary');if($('#entry-metrics'))$('#entry-metrics').innerHTML=homeMetrics();}catch{/* Entry form remains available. */}}
function paintLobby(g) {
  const metrics={players:fmt(g.players),connected:fmt(g.connected),total:fmt(g.total),duration:`${fmt(g.duration)} s`};
  for(const [name,value] of Object.entries(metrics)) all(`[data-${name}]`).forEach(el=>el.textContent=value);
  const start=$('[data-start]');
  if(start) start.disabled=g.players===0 || state.busy;
  const hint=$('#start-hint');
  if(hint) hint.textContent=startHint(g);
}
function updateCounters(msg) {
  const g=state.game;
  if(!g || g.id!==msg.gameId || g.current-1!==msg.index || g.status!==msg.status) return;
  g.players=msg.players; g.connected=msg.connected;
  if(state.snap) state.snap.answered=msg.answered;
  if(g.status==='lobby') paintLobby(g);
  else all('[data-players]').forEach(el=>el.textContent=fmt(g.players));
  all('[data-answered]').forEach(el=>el.textContent=fmt(msg.answered));
  all('[data-meter]').forEach(el=>el.style.width=`${Math.min(100,100*msg.answered/(msg.players||1))}%`);
}
function tone(phase){if(!state.sound||!state.audio||!['question','results','finished'].includes(phase))return;const ctx=state.audio;const notes=phase==='finished'?[392,494,587]:phase==='results'?[440,554]:[392,523];notes.forEach((f,i)=>{const osc=ctx.createOscillator(),amp=ctx.createGain(),t=ctx.currentTime+i*.13;osc.type='sine';osc.frequency.value=f;amp.gain.setValueAtTime(.0001,t);amp.gain.exponentialRampToValueAtTime(.06,t+.02);amp.gain.exponentialRampToValueAtTime(.0001,t+.19);osc.connect(amp);amp.connect(ctx.destination);osc.start(t);osc.stop(t+.2);});}
function syncView(s, reconnected=false) {
  const g = s.game, old = state.game, previous = state.phaseKey;
  if (g && old) {
    if (old.id !== g.id && g.created < old.created) return;
    const order = {lobby:0,question:1,results:2,finished:3,cancelled:3};
    if (old.id === g.id && (g.current < old.current || (g.current === old.current && order[g.status] < order[old.status]))) return;
  }
  const key = g ? `${g.id}/${g.current}/${g.status}` : 'empty';
  const phaseChanged = key !== previous;
  const priorAnswer = state.snap?.me;
  if (!phaseChanged && !reconnected && g?.status==='question' && priorAnswer?.answered && s.me && !s.me.answered) {
    s.me.answered = true;
    s.me.choice = priorAnswer.choice;
  }
  state.snap = s;
  state.game = g;
  if (phaseChanged || reconnected || s.me?.answered) state.pending = null;
  state.phaseKey = key;
  if (g?.server_now) state.offset = g.server_now*1000 - Date.now();
  if (g?.id !== old?.id) state.review = null;
  if (g?.status==='lobby' && old?.id!==g.id) { state.studio=false; state.editing=false; }
  if (g && g.status !== 'lobby') state.editing=false;
  if (phaseChanged) {
    state.wager=false;
    if (dlg.open && !(route==='player' && !state.player)) dlg.close();
    if (previous && g) {
      tone(g.status);
      const names = {lobby:'Lobby aperta',question:'Nuova domanda',results:'Soluzione disponibile',finished:'Classifica finale',cancelled:'Partita annullata'};
      announce(`${names[g.status]}${g.current?' · '+g.current+' di '+g.total:''}`);
      window.scrollTo(0,0);
    }
  } else {
    const view = document.body.dataset.view;
    if (g?.status==='lobby' && ['player-lobby','host-lobby','screen-lobby'].includes(view)) {
      paintLobby(g); updateLive(); return;
    }
    if (route==='player' && view==='player-round' && g?.status==='question') {
      updateLive(); updatePlayerAnswer(); tick(); return;
    }
    if (route==='player' && ((view==='player-result' && g?.status==='results') || (view==='player-final' && g?.status==='finished'))) {
      updateLive(); return;
    }
    if (route==='host' && (state.editing || state.studio || !g) && view==='studio') { updateLive(); return; }
  }
  renderGame();
  if (phaseChanged && previous && g && route==='player') $('[data-phase-focus]')?.focus({preventScroll:true});
}

function handleMessage(m) {
  if (m.type==='snapshot') { const resumed=!state.online; clearTimeout(state.syncTimer);state.syncTimer=null;state.online=true; state.retry=0; syncView(m,resumed); return; }
  if (m.type==='counts') { updateCounters(m); return; }
  if (m.type==='answer_ack') {
    if (!state.game || m.questionIndex!==state.game.current-1 || state.game.status!=='question') return;
    state.pending=null;
    if ((m.ok || (m.alreadyAnswered && Number.isInteger(m.choice))) && state.snap?.me) {
      state.snap.me.answered=true;
      state.snap.me.choice=m.choice; if(Number.isInteger(m.remainingBets))state.snap.me.remainingBets=m.remainingBets;
    } else if (!m.ok && !state.snap?.me?.answered) {
      notice(m.message);
      state.socket?.close();
    }
    updatePlayerAnswer();
    tick();
  } else if (m.type==='session_invalid') { resetPlayer(); notice(m.message || 'La sessione è terminata.'); }
  else if (m.type==='error' && m.code==='tab_limit') {
    state.tabLimit=true; stopSocket(); header(); connectionHelp(m.message,'retry-socket');
  } else if (m.type==='error') notice(m.message);
}

function watchSocket(ws,delay) {
  clearTimeout(state.syncTimer);
  state.syncTimer=setTimeout(()=>{if(state.socket===ws) ws.close();},delay);
}
function showConnection() {
  updateLive();
  if(route==='player' && state.game?.status==='question') updatePlayerAnswer();
}
function connect() {
  stopSocket(); showConnection();
  const channel=route==='player'?'play':route, player=state.player;
  if(state.tabLimit || navigator.onLine===false || (channel==='play'?!player:!state.admin)) return;
  const ws=new WebSocket(`${location.protocol==='https:'?'wss:':'ws:'}//${location.host}/ws/${channel}`);
  state.socket=ws;
  watchSocket(ws,12000);
  ws.onopen=()=>{
    if(state.socket!==ws) return;
    if(channel==='play') ws.send(JSON.stringify({type:'hello',pin:player.pin,playerId:player.playerId,token:player.token}));
  };
  ws.onmessage=e=>{
    if(state.socket!==ws) return;
    let msg;try{msg=JSON.parse(e.data);}catch{return;}
    handleMessage(msg);
  };
  ws.onclose=()=>{
    if(state.socket!==ws) return;
    clearTimeout(state.syncTimer);state.syncTimer=null;state.online=false;showConnection();
    if(navigator.onLine===false || state.tabLimit) return;
    const delay=Math.min(900*1.65**state.retry++,9000);
    state.reconnect=setTimeout(async()=>{
      if(state.socket!==ws) return;
      if(channel!=='play') {
        try{await api('/api/screen');}
        catch(e){if(e.status===401 && state.socket===ws){stopSocket();state.admin=false;showLogin();return;}}
      }
      if(state.socket===ws) connect();
    },delay);
  };
}
function requestSync() {
  if(state.tabLimit || navigator.onLine===false || !(route==='player'?state.player:state.admin)) return;
  const ws=state.socket;
  if(ws?.readyState===WebSocket.OPEN && state.online) {
    if(state.syncTimer!==null) return;
    watchSocket(ws,4000);
    try{ws.send(JSON.stringify({type:'sync'}));}catch{ws.close();}
  } else if(!ws || ws.readyState===WebSocket.CLOSED) connect();
}
async function overview(){const o=await api('/api/admin/overview');state.questions=o.questions;return o;}
async function adminInit(){try{let snap;if(route==='screen')snap=await api('/api/screen');else{const o=await overview();snap=o.snapshot||{game:null};}
  state.admin=true;syncView(snap);connect();}catch(e){if(e.status===401){state.admin=false;showLogin();}else connectionHelp(e.message);}}
function enterPlayer(pin,data) {
  clearNotice();
  storePlayer({pin,playerId:data.playerId,token:data.token,nickname:data.nickname});
  rememberJoin(null); state.game=data.game; state.snap=null; state.phaseKey=''; state.pending=null;
  state.tabLimit=false; state.retry=0;
  renderGame(); connect();
}
async function registerPlayer(draft) {
  rememberJoin(draft);
  try {const data=await api('/api/join','POST',draft);enterPlayer(draft.pin,data);}
  catch(e){if(e.status>=400 && e.status<500) rememberJoin(null);throw e;}
}
async function playerInit() {
  const pin=new URLSearchParams(location.search).get('pin');
  const draft=state.joinDraft || readSaved('sessionStorage','esc_join_pending');
  if(draft?.joinKey && (!pin || pin===draft.pin)) {
    try {await registerPlayer(draft);return;}
    catch(e){
      if(!e.status || e.status>=500) {connectionHelp(e.message);return;}
      showHome(); loadSummary(); formError(e.message); return;
    }
  }
  const saved=localGet(pin);
  if(saved) {
    try {
      const data=await api('/api/join','POST',{pin:saved.pin,playerId:saved.playerId,token:saved.token});
      enterPlayer(saved.pin,data); return;
    } catch(e){
      if(![400,401,404].includes(e.status)){connectionHelp(e.message);return;}
      forgetPlayer(saved);
    }
  }
  showHome(); loadSummary();
}
function sendAnswer(i){if(state.game?.status!=='question'||state.pending||state.snap?.me?.answered||!state.online||state.socket?.readyState!==WebSocket.OPEN||remaining()<=0)return;
  const g=state.game, ws=state.socket;const pending={wager:state.wager,choice:i,questionId:state.snap.question.id,questionIndex:g.current-1};state.pending=pending;
  try{ws.send(JSON.stringify({type:'answer',...pending}));updatePlayerAnswer();tick();setTimeout(()=>{if(state.pending===pending && state.socket===ws)ws.close();},6500);}catch{state.pending=null;state.online=false;updateLive();updatePlayerAnswer();state.socket?.close();}
}
async function saveDeck(){const edit=state.editing;const payload={title:state.quizTitle,bets:state.bets,multipliers:Object.fromEntries(state.questions.filter(q=>state.selected.has(q.id)&&multiplier(q)>1).map(q=>[q.id,multiplier(q)])),ids:[...state.selected],duration:state.duration,shuffle:state.shuffle,revealOnComplete:state.revealOnComplete};if(edit){payload.gameId=state.game.id;payload.expectedRevision=state.deckRevision;}
  await api(edit?'/api/admin/questions':'/api/admin/create',edit?'PATCH':'POST',payload);state.editing=false;state.studio=false;const o=await overview();if(!state.snap?.game||state.snap.game.id!==o.game?.id||!state.online)syncView(o.snapshot);else renderGame();window.scrollTo(0,0);
}
async function hostAction(action){const g=state.game;if(!g)return;await api('/api/admin/action','POST',{action,gameId:g.id,index:g.current-1,status:g.status});if(!state.online){const o=await overview();syncView(o.snapshot);} }
async function goStudio(edit){const o=await overview();if(edit&&o.game?.status!=='lobby'){syncView(o.snapshot);return;}state.game=o.game;state.snap=o.snapshot;state.quizTitle=edit?(o.settings?.title||''):'';state.bets=edit?!!o.settings?.bets:true;state.multipliers=edit?Object.fromEntries(o.questions.map(q=>[q.id,o.settings?.multipliers?.[q.id]||1])):{};state.deckRevision=edit?o.configurationRevision:null;state.duration=edit?o.game.duration:30;state.selected=new Set(edit?o.selected:[]);state.search='';state.category='all';state.level='all';state.shuffle=false;state.revealOnComplete=edit?o.game.reveal_on_complete:true;state.editing=edit;state.studio=!edit;renderGame();window.scrollTo(0,0);}
document.addEventListener('input',e=>{if(e.target.id==='quiz-title')state.quizTitle=e.target.value;});
function confirmAction(title,description,action,label){modal(title,`<p>${esc(description)}</p>`,act('close','Indietro',null,'soft')+act(`confirm-${action}`,label,'check','primary'));}
async function perform(action,id){switch(action){
  case 'retry-socket':
    state.tabLimit=false;state.retry=0;renderGame();connect();return;
  case 'reload-deck':dlg.close();return goStudio(true);
  case 'wager': if(state.game?.bets && !state.snap.me.answered && !state.pending && state.snap.me.remainingBets>0){state.wager=!state.wager;updatePlayerAnswer();}return;
  case 'edit-pin':return editInvitePin();
  case 'enlarge-qr':return enlargeLobbyQr();
  case 'review':return openReview();
  case 'review-all':case 'review-missed':{
    const body=$('#review-content');
    if(body){fillReview(body,action==='review-all');$(`[data-action="${action}"]`,body)?.focus({preventScroll:true});}
    return;
  }
  case 'rules':return rules();case 'close':return dlg.close();case 'retry':return boot();case 'preview':return previewQuestion(id);
  case 'category':{const rows=state.questions.filter(q=>q.category_id===id),remove=rows.every(q=>state.selected.has(q.id));rows.forEach(q=>remove?state.selected.delete(q.id):state.selected.add(q.id));return refreshStudio();}
  case 'browse-category':state.category=id;state.search='';state.level='all';renderStudio();$('#category-filter').focus();return;
  case 'mix':return balancedDraw();case 'select-visible':filtered().forEach(q=>state.selected.add(q.id));return refreshStudio();case 'clear':state.selected.clear();return refreshStudio();
  case 'save-deck':return saveDeck();case 'edit':return goStudio(true);case 'new':return goStudio(false);
  case 'back-lobby':{state.editing=false;const o=await overview();return syncView(o.snapshot);}
  case 'start':case 'next':case 'finish':return hostAction(action);
  case 'reveal':if((state.snap?.answered||0)<state.game.players)return confirmAction('Chiudere le risposte?',`Hanno risposto ${state.snap?.answered||0} giocatori su ${state.game.players}. La soluzione apparirà subito su tutti gli schermi.`,action,'Mostra la soluzione');return hostAction('reveal');
  case 'finish-early':return confirmAction('Concludere la partita?',`Hai completato ${state.game.current} round su ${state.game.total}. Verrà mostrata la classifica finale.`,'finish','Concludi partita');
  case 'cancel':return confirmAction('Annullare la partita?','La sessione verrà interrotta per tutti i partecipanti.','cancel','Annulla partita');
  case 'confirm-cancel':case 'confirm-finish':case 'confirm-reveal':dlg.close();return hostAction(action.slice(8));
  case 'leave':return confirmAction('Lasciare la lobby?','Il posto e il nickname torneranno disponibili. Potrai rientrare finché la lobby è aperta.','leave','Lascia la lobby');
  case 'confirm-leave':{dlg.close();const p=state.player;await api('/api/leave','POST',{pin:p.pin,playerId:p.playerId,token:p.token});if(state.player?.playerId===p.playerId)resetPlayer(p);return;}
  case 'exit-player':return resetPlayer();
  case 'copy-link':{const u=joinURL(state.game);try{await navigator.clipboard.writeText(u);notice('Link di invito copiato.');}catch{modal('Link di invito',`<p>Seleziona il link per copiarlo.</p><input aria-label="Link di invito" id="invite-url" readonly value="${esc(u)}">`);$('#invite-url').select();}return;}
  case 'logout':await api('/api/admin/logout','POST');stopSocket();state.admin=false;state.editing=false;state.studio=false;state.phaseKey='';showLogin();return;
  case 'fullscreen':if(document.fullscreenElement)await document.exitFullscreen();else if(document.documentElement.requestFullscreen)await document.documentElement.requestFullscreen();else notice('Usa la modalità a schermo intero del browser.');return;
  case 'sound':{if(!state.audio){const Audio=window.AudioContext||window.webkitAudioContext;if(!Audio){notice('Audio non disponibile su questo dispositivo.');return;}state.audio=new Audio();}await state.audio.resume();state.sound=!state.sound;if(state.sound)tone('question');header();return;}
}}
const mutations=new Set(['save-deck','start','next','finish','confirm-finish','confirm-cancel','confirm-reveal','confirm-leave','logout','reveal']);
document.addEventListener('click',async e=>{const choice=e.target.closest('[data-choice]');if(choice){sendAnswer(Number(choice.dataset.choice));return;}const btn=e.target.closest('[data-action]');if(!btn)return;const action=btn.dataset.action;const lock=mutations.has(action);if(lock&&state.busy)return;if(lock){state.busy=true;btn.disabled=true;}
  try{await perform(action,btn.dataset.id);}catch(err){if(err.status===401&&route!=='player'){stopSocket();state.admin=false;showLogin();}else if(err.code==='deck_changed' && state.editing) {
    modal('La selezione è cambiata',`<p>${esc(err.message)} La tua bozza è ancora visibile.</p>`,
      act('close','Mantieni la bozza',null,'soft')+act('reload-deck','Ricarica selezione','cards','primary'));
  } else {notice(err.message);if(err.status===409&&route==='host'&&!state.editing){const o=await overview().catch(()=>null);if(o?.snapshot)syncView(o.snapshot);}}}finally{if(lock){state.busy=false;if(btn.isConnected)btn.disabled=false;if(state.game?.status==='lobby')paintLobby(state.game);if($('#selected-count'))refreshStudio({cats:false,rows:false});}}});
document.addEventListener('submit',async e=>{const f=e.target;if(!['login','join-form'].includes(f.id))return;e.preventDefault();const b=$('button[type=submit]',f);if(b.disabled)return;b.disabled=true;const err=$('#form-error');if(err)err.hidden=true;
  try{if(f.id==='login'){await api('/api/admin/login','POST',{password:$('#admin-password').value});await adminInit();}else{const pin=$('#join-pin').value.trim();await registerPlayer(draftFor(pin,$('#join-nick').value.trim()));}}catch(error){formError(error.message);}finally{if(b.isConnected)b.disabled=false;}});
document.addEventListener('input',e=>{if(e.target.id==='question-search'){state.search=e.target.value;refreshStudio({cats:false});}if(e.target.id==='join-pin')e.target.value=e.target.value.replace(/\D/g,'').slice(0,6);});
document.addEventListener('change',e=>{const t=e.target;if(t.dataset.bonus){state.multipliers[t.dataset.bonus]=Number(t.value);}else if(t.id==='bets'){state.bets=t.checked;}else if(t.dataset.area){if(t.checked)state.drawAreas.add(t.dataset.area);else state.drawAreas.delete(t.dataset.area);}else if(t.dataset.question){t.checked?state.selected.add(t.dataset.question):state.selected.delete(t.dataset.question);refreshStudio({rows:false});}else if(t.id==='duration'){state.duration=Number(t.value);refreshStudio({rows:false,cats:false});}else if(t.id==='shuffle'){state.shuffle=t.checked;}else if(t.id==='reveal-complete'){state.revealOnComplete=t.checked;}else if(t.id==='category-filter'||t.id==='level-filter'){state[t.id==='level-filter'?'level':'category']=t.value;refreshStudio({cats:false});}});
dlg.addEventListener('click',e=>{if(e.target===dlg){const r=dlg.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dlg.close();}});
document.addEventListener('fullscreenchange',header);
document.addEventListener('visibilitychange',()=>{if(!document.hidden) requestSync();});
window.addEventListener('pageshow',e=>{if(e.persisted) requestSync();});
window.addEventListener('online',()=>{
  if(state.player || state.admin) requestSync();
  else if(document.body.dataset.view==='error') boot();
});
window.addEventListener('offline',()=>{if(state.player||state.admin){stopSocket();showConnection();}});
setInterval(tick,150);
async function boot() {
  if(state.authenticating) return;
  state.authenticating=true;
  try {
    header();
    document.title=`${route==='host'?'Regia docente':route==='screen'?'Proiettore':'Gioca'} · Escalation Trivial`;
    await (route==='player'?playerInit():adminInit());
  } finally {state.authenticating=false;}
}
boot();
