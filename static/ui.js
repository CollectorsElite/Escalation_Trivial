'use strict';
const $ = (selector, root = document) => root.querySelector(selector);
const all = selector => [...document.querySelectorAll(selector)];
const app = $('#app');
const route = ({'/docente':'host', '/schermo':'screen'})[location.pathname.replace(/\/$/, '')] || 'player';
const state = {
  questions: [], selected: new Set(), category:'all', level:'all', search:'', duration:30, shuffle:false, revealOnComplete:true,
  editing:false, studio:false, admin:false, game:null, snap:null, player:null, socket:null, reconnect:null,
  retry:0, online:false, phaseKey:'', offset:0, pending:null, busy:false, authenticating:false,
  activeSet:null,drawCount:10,quizTitle:'', bets:true, wager:false, multipliers:{}, drawCategories:null, audio:null, sound:false, summary:null, review:null, joinDraft:null, deckRevision:null, syncTimer:null, tabLimit:false
};
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = value => Number(value || 0).toLocaleString('it-IT');
const letters = 'ABCD';
const glyphs = {
  arrow:'M4 12h15m-6-6 6 6-6 6', out:'M7 17 18 6M8 6h10v10', back:'m14 6-6 6 6 6',
  key:'M13.5 14.5a5.5 5.5 0 1 0-4-4L3 17v4h4v-3h3l3.5-3.5Z M16.5 7.5h.01',
  users:'M4 20v-2a4 4 0 0 1 4-4h3a4 4 0 0 1 4 4v2M17 14a4 4 0 0 1 4 4v2 M13 7a3.5 3.5 0 1 1-7 0 3.5 3.5 0 1 1 7 0ZM16 4a3.5 3.5 0 0 1 0 6.5',
  layers:'m3 8 9-5 9 5-9 5-9-5Zm0 4.5 9 5 9-5M3 17l9 5 9-5', cards:'M6 7V4h14v12h-3M3 9h13v12H3z',
  shield:'m12 3 8 3v5c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6l8-3Z M8.5 11.5l2.3 2.4 4.6-5',
  timer:'M20 13a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-8 0 3-3M10 2h4m4 4 2-2',
  screen:'M3 4h18v13H3zM8 21h8m-4-4v4', full:'M8 3H3v5m13-5h5v5m0 8v5h-5M3 16v5h5',
  sound:'M3 9h4l5-4v14l-5-4H3zM16 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14',
  mute:'M3 9h4l5-4v14l-5-4H3zM16 9l5 6m0-6-5 6',
  play:'m8 4 12 8-12 8V4Z', check:'m4 12 5 5L20 6', x:'m6 6 12 12M18 6 6 18',
  award:'M7 3h10v4a5 5 0 0 1-10 0V3Zm0 2H3v2a4 4 0 0 0 5 4m9-6h4v2a4 4 0 0 1-5 4m-4 1v5m-5 4h10m-8-3h6',
  copy:'M8 8h12v13H8zM16 5V3H4v13h2', qr:'M3 3h6v6H3zm12 0h6v6h-6zM3 15h6v6H3zm12 0h3v3h3v3h-6z',
  info:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0ZM12 11v5m0-9v.1',
  exit:'M9 4H4v16h5m2-8h10m-4-4 4 4-4 4', search:'M16 10a6 6 0 1 1-12 0 6 6 0 1 1 12 0Zm-2 5 6 6',
  mix:'M3 6h3c5 0 7 12 12 12h3m-4-4 4 4-4 4M3 18h3c2 0 3-2 5-4m3-5c1-2 3-3 5-3h2m-4-4 4 4-4 4',
  lock:'M5 10h14v11H5zM8 10V7a4 4 0 0 1 8 0v3m-4 4v3', mail:'M3 5h18v14H3Zm0 1 9 7 9-7',
  bug:'M8 8h8v7a4 4 0 0 1-8 0V8Zm2-2 4-1M5 9l3 2m8 0 3-2M4 14h4m8 0h4M5 20l4-3m6 0 4 3',
  net:'M9 3h6v5H9zM2 16h6v5H2zm14 0h6v5h-6zM12 8v4m-7 4v-4h14v4',
  file:'M5 3h9l5 5v13H5zM14 3v6h5M8 13h8m-8 4h6', activity:'M2 13h5l3-8 4 14 3-7h5',
  cloud:'M6 18a4 4 0 0 1-1-7.8A6.3 6.3 0 0 1 17 9a4.5 4.5 0 1 1 1 9H6Z',
  list:'M8 6h13M8 12h13M8 18h13M3 6h.1M3 12h.1M3 18h.1', edit:'m4 16 11-11 4 4L8 20l-5 1 1-5Zm9-9 4 4',
  save:'M12 3v12m-5-5 5 5 5-5M3 17v4h18v-4', visible:'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Zm13 0a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z',
  bolt:'m13 2-9 13h7l-1 7 10-14h-7l1-6Z', target:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-5 0a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z',
  flag:'M5 21V4m0 0c4-4 9 3 14-1v10c-5 4-10-3-14 1', grid:'M3 3h7v7H3zm11 0h7v7h-7zM3 14h7v7H3zm11 0h7v7h-7z'
};
function icon(name, cls='') {
  return `<svg class="ico ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${glyphs[name] || glyphs.grid}"/></svg>`;
}
const topics = {
  SSL:['shield','Sicurezza sul lavoro','#f6c772'], PHI:['mail','Phishing','#ffb183'], AUT:['key','Autenticazione','#ffce62'], MAL:['bug','Malware','#f1a6a1'],
  NET:['net','Reti e web','#96c9ff'], PRI:['lock','Privacy','#c8adf4'], OPS:['shield','Pratiche sicure','#a5d99d'],
  SOC:['activity','SOC e incidenti','#91d8d0'], BCP:['cloud','Cloud e backup','#a5baff'],
  PCTO:['cards','PCTO','#a6ddc9']
};
function topic(q) {const t=topics[q?.category_id] || ['layers',q?.category || 'Quiz','#b8c6bd'];return `<span class="topic" style="--t:${t[2]}">${icon(t[0])}${esc(t[1])}${q?.multiplier>1?' · Bonus ×'+q.multiplier:''}</span>`;}
function act(name, label, sym, variant='soft', attrs='') {
  return `<button type="button" class="btn ${variant}" data-action="${name}" ${attrs}>${sym?icon(sym):''}<span>${label}</span></button>`;
}
function link(href,label,sym,variant='link',newTab=false) {
  return `<a class="btn ${variant}" href="${esc(href)}" ${newTab?'target="_blank" rel="noopener"':''}>${sym?icon(sym):''}<span>${label}</span>${newTab?icon('out','small-icon'):''}</a>`;
}
function live() {return `<span class="live" data-connection><i></i><span>${state.online?'In diretta':'Collegamento…'}</span></span>`;}
function header() {
  const inPlay=route==='player'&&state.player;
  const brand=`<span class="brand"><img src="/static/assets/escalation-trivial.svg" alt="Escalation Trivial" width="299" height="54"></span>`;
  const studioNav=state.admin?`${live()}${link('/schermo','Proiettore','screen','nav-btn',true)}${act('logout','Esci','exit','nav-btn')}`:link('/','Area giocatori','back','nav-btn');
  let nav=route==='host'?studioNav:route==='screen'&&state.admin?`${live()}${act('sound',state.sound?'Audio attivo':'Audio spento',state.sound?'sound':'mute','nav-btn','aria-pressed="'+state.sound+'"')}${act('fullscreen',document.fullscreenElement?'Riduci':'Schermo intero','full','nav-btn')}`:inPlay?live():link('/docente','Area docente','key','nav-btn');
  $('#site-header').innerHTML=`<div class="shell topbar">${brand}<nav aria-label="Comandi ${route==='screen'?'proiezione':'principali'}">${nav}</nav></div>`;
  updateLive();
}
function updateLive(){
  const label = state.online ? 'In diretta' : navigator.onLine === false ? 'Offline' : 'Collegamento…';
  all('[data-connection]').forEach(el=>{el.classList.toggle('is-live',state.online);$('span',el).textContent=label;});
  if (route === 'player') updateWaitingStatus();
}
function announce(text){$('#phase-announce').textContent=text;}
let noticeTimer;
function clearNotice() {
  clearTimeout(noticeTimer);
  const el=$('#notice');
  el.classList.remove('show'); el.textContent='';
}
function notice(text) {
  clearTimeout(noticeTimer);
  const el=$('#notice');
  el.textContent=text; el.classList.add('show');
  noticeTimer=setTimeout(clearNotice,4800);
}
const dlg=$('#dialog');
function modal(title,body,actions='') {
  if(dlg.open)dlg.close();
  dlg.innerHTML=`<div class="dialog-head"><h2 id="dialog-title">${esc(title)}</h2><button type="button" class="square-btn" data-action="close" aria-label="Chiudi">${icon('x')}</button></div>${body}${actions?`<div class="actions modal-actions">${actions}</div>`:''}`;
  dlg.showModal();
}
function rules(){modal('Come si gioca',`<ol class="rules"><li><b>Entra nella lobby</b><p>Inserisci il PIN proiettato in aula e scegli un nickname, oppure inquadra il QR della partita.</p></li><li><b>Scegli una risposta</b><p>Ogni round ha due o quattro opzioni. La prima scelta ricevuta dal server è definitiva.</p></li><li><b>Guadagna punti</b><p>Una risposta esatta vale da 500 a 1.000 punti in base al tempo rimasto. Il bonus ×2 o ×3 moltiplica i punti base. Se attivo, il Raddoppio personale aggiunge un’altra quota base per una risposta esatta. Una puntata errata costa fino a 500 punti, senza scendere sotto zero. Hai due puntate: si consumano solo alla registrazione della risposta. A parità di punti si condivide la posizione.</p></li></ol>`,act('close','Ho capito','check','primary'));}
function show(html,view) {document.body.dataset.view=view;app.innerHTML=html;}
function connectionHelp(message,action='retry') {show(`<section class="single panel"><span class="eyeline">Connessione</span><h1>Collegamento interrotto</h1><p>${esc(message)}</p>${act(action,action==='retry-socket'?'Ricollega':'Riprova','arrow','primary')}</section>`,'error');}
function readSaved(storage,key) {
  try {return JSON.parse(window[storage].getItem(key) || 'null');} catch {return null;}
}
function writeSaved(storage,key,value) {
  try {
    if(value) window[storage].setItem(key,JSON.stringify(value));
    else window[storage].removeItem(key);
  } catch {
    // The current tab can keep playing using its in-memory state.
  }
}
function localGet(pin) {
  return [readSaved('sessionStorage','esc_player_tab'),readSaved('localStorage','esc_player')]
    .find(p=>p?.playerId && p.token && (!pin || p.pin===pin)) || null;
}
function storePlayer(p) {
  state.player=p;
  writeSaved('sessionStorage','esc_player_tab',p);
  writeSaved('localStorage','esc_player',p);
}
function forgetPlayer(p) {
  if(!p) return;
  for(const [storage,key] of [['sessionStorage','esc_player_tab'],['localStorage','esc_player']]) {
    if(readSaved(storage,key)?.playerId===p.playerId) writeSaved(storage,key,null);
  }
  if(state.player?.playerId===p.playerId) state.player=null;
}
function rememberJoin(draft) {
  state.joinDraft=draft;
  writeSaved('sessionStorage','esc_join_pending',draft);
}
function draftFor(pin,nickname) {
  const last=state.joinDraft || readSaved('sessionStorage','esc_join_pending');
  if(last?.pin===pin && last.joinKey) return {...last,nickname};
  const bytes=crypto.getRandomValues(new Uint8Array(32));
  const joinKey=Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');
  return {pin,nickname,joinKey};
}
function joinURL(g){return `${g.public_url || location.origin}/?pin=${encodeURIComponent(g.pin)}`;}
function metric(sym,label,value){return `<div class="metric">${icon(sym)}<div><strong>${value}</strong><span>${label}</span></div></div>`;}
function errorLine(){return '<p id="form-error" role="alert" class="form-error" hidden></p>';}
function formError(message){const e=$('#form-error');if(e){e.hidden=false;e.textContent=message;}else notice(message);}
function homeMetrics(){const s=state.summary;return `${metric('layers','Categorie',s?fmt(s.categories):'–')}${metric('cards','Domande nel catalogo',s?fmt(s.questions):'–')}${metric('users','Giocatori per partita',s?fmt(s.capacity):'–')}`;}
function showLogin(){header();const screen=route==='screen';show(`<div class="shell login-layout"><section class="login-intro"><div class="eyeline"><i class="pip"></i>Accesso riservato</div><h1>${screen?'Schermo di sala':'Regia docente'}<em>.</em></h1><p>${screen?'Accedi per proiettare lobby, domande e classifica.':'Prepara il quiz, apri la lobby e conduci la partita.'}</p><img class="login-art" src="/static/assets/mazzo-trivial.webp" alt="" width="984" height="656"></section><section class="join-card paper"><div class="card-kicker"><span class="tile-icon">${icon('lock')}</span><span>${screen?'Proiezione':'Area docente'}</span></div><h2>Accedi<span>.</span></h2><form id="login"><label for="admin-password">Password docente</label><input type="password" id="admin-password" required autocomplete="current-password">${errorLine()}<button type="submit" class="btn primary cta">${screen?'Apri il proiettore':'Entra in regia'} ${icon('arrow')}</button></form></section></div>`,'login');}
