'use strict';

function answerMark(index) {
  return `<span class="answer-mark opt-${index}"><span>${letters[index]}</span></span>`;
}

function optionRow(text, i, {correct=false, own=false, wrong=false, count=null, total=0}={}) {
  const marks = [correct ? 'Corretta' : '', own ? 'La tua scelta' : ''].filter(Boolean).join(' · ');
  const pct = total ? Math.round(100 * (count || 0) / total) : 0;
  const bar = count === null ? '' : `<span class="bar-track"><span style="width:${pct}%"></span></span>`;
  const votes = count === null ? '' : `<span class="votes"><b>${pct}%</b><small>${fmt(count)} ${count===1?'voto':'voti'}</small></span>`;
  return `<div class="option opt-${i} ${correct?'right':''} ${own?'chosen':''} ${wrong?'wrong':''}">
    ${answerMark(i)}<span class="option-body"><strong>${esc(text)}</strong>
    ${marks ? `<small class="option-mark">${icon(correct?'check':wrong?'x':'target')}${marks}</small>` : ''}${bar}</span>${votes}</div>`;
}

function gameMeta(g) {
  return `<div class="compact-stats lobby-metrics">${metric('users','Iscritti',`<span data-players>${fmt(g.players)}</span>`)}
    ${metric('net','Collegati',`<span data-connected>${fmt(g.connected)}</span>`)}
    ${metric('cards','Domande',`<span data-total>${fmt(g.total)}</span>`)}
    ${metric('timer','Per domanda',`<span data-duration>${fmt(g.duration)} s</span>`)}</div>`;
}
function startHint(g) {
  if (!g.players) return 'In attesa del primo giocatore.';
  if (!g.connected) return 'Nessun giocatore è collegato. Attendi il rientro prima di dare il via.';
  if (g.connected < g.players) return `${fmt(g.connected)} su ${fmt(g.players)} iscritti in linea.`;
  return g.players===1 ? 'Il giocatore è collegato. Puoi dare il via.' : 'Tutti gli iscritti sono collegati. Puoi dare il via.';
}

function qrImage(g) {
  return `<img src="/api/admin/qr?pin=${encodeURIComponent(g.pin)}" width="208" height="208" alt="QR per entrare nella partita ${esc(g.pin)}">`;
}

function enlargeLobbyQr() {
  const g=state.game;
  if (!state.admin || g?.status!=='lobby') return;
  const host=new URL(joinURL(g)).host;
  modal('Inquadra per entrare', `<div class="qr-zoom">${qrImage(g)}
    <p>Oppure apri <strong>${esc(host)}</strong> e inserisci il PIN</p>
    <b class="zoom-pin">${esc(g.pin.slice(0,3))} ${esc(g.pin.slice(3))}</b></div>`);
}

function showLobby(g) {
  const screen = route === 'screen';
  const address = new URL(joinURL(g));
  const display = address.host;
  const localOnly = /^(?:localhost|127(?:\.\d{1,3}){3}|0\.0\.0\.0|\[::1?\])$/.test(address.hostname)
    || address.hostname.endsWith('.localhost');
  const pin = `<div class="pin-block"><span class="eyeline">PIN della partita</span>
    <strong class="lobby-pin" aria-label="PIN ${esc(g.pin.split('').join(' '))}">${esc(g.pin.slice(0,3))}<span>${esc(g.pin.slice(3))}</span></strong></div>`;
  const qr = `<button type="button" class="qr-box" data-action="enlarge-qr" aria-label="Ingrandisci il QR della partita">${qrImage(g)}</button>`;
  show(`<div class="shell game-wrap ${screen?'projection':''}"><div class="page-title"><div>
    <div class="eyeline"><i class="pip mint"></i>Lobby aperta</div><h1>${screen?'Entra nella sfida':'Lobby della partita'}<em>.</em></h1>
    ${localOnly?'<p>Il PIN permette di partecipare dai browser aperti su questo computer.</p>':screen?`<p>Inquadra il QR oppure apri <strong>${esc(display)}</strong> e inserisci il PIN.</p>`:'<p>Condividi il codice con l’aula. Avvia la prima domanda quando tutti sono pronti.</p>'}</div></div>
    <div class="lobby-grid"><section class="panel ticket paper"><div class="ticket-body">${pin}<img class="ticket-stamp" src="/static/assets/escalation-segno.svg" width="56" height="54" alt=""></div><div class="ticket-foot">${gameMeta(g)}</div></section>
    ${localOnly?`<aside class="panel qr-panel local-invite"><span class="standby-mark" aria-hidden="true">${icon('screen')}</span><strong>Invito locale</strong><p>Per collegare i telefoni usa <b>Avvia-Aula</b> sul computer del docente oppure apri la regia dall’indirizzo di rete del servizio.</p></aside>`:
      `<aside class="panel qr-panel">${qr}<strong>Scansiona per entrare</strong><small class="qr-hint">Seleziona il QR per ingrandirlo</small>${screen?'':act('copy-link','Copia link di invito','copy','text-btn')}</aside>`}</div>
    ${screen?'':`<div class="command-bar"><div><strong>Comandi di regia</strong><p id="start-hint">${startHint(g)}</p></div><div class="actions">${act('cancel','Annulla','x','text-btn')}${act('edit','Modifica quiz','edit')}${act('start','Avvia partita','play','primary','data-start '+(g.players?'':'disabled'))}</div></div>`}
    </div>`, screen?'screen-lobby':'host-lobby');
}

function progressTop(g,label) {
  return `<div class="round-head"><div><span class="eyeline"><i class="pip ${g.status==='results'?'mint':''}"></i>${label}</span>
  <span class="round-index">Domanda <b>${g.current}</b> di ${g.total}</span></div>
  <div class="round-progress" aria-hidden="true"><i style="width:${100*g.current/g.total}%"></i></div></div>`;
}

function timerBox() {
  return `<div class="round-clock" role="timer" aria-live="off">
    <span class="clock-label">Tempo rimasto</span><span class="clock-face">
    <svg viewBox="0 0 52 52" aria-hidden="true" focusable="false"><circle class="clock-base" cx="26" cy="26" r="23"></circle>
    <circle class="clock-ink" cx="26" cy="26" r="23" pathLength="100" stroke-dasharray="100" data-dial></circle></svg>
    <strong><span data-timer>–</span><small>s</small></strong></span></div>`;
}

function remaining() {
  return Math.max(0,((state.game?.deadline || 0)*1000 - Date.now() - state.offset)/1000);
}

function tick() {
  if (state.game?.status !== 'question') return;
  const clock = $('.round-clock');
  if (!clock) return;
  const left = remaining(), seconds = Math.ceil(left);
  const time = $('[data-timer]',clock);
  const changed = time.textContent !== String(seconds);
  if (changed) time.textContent = seconds;
  const quiet = route === 'player' && (state.snap?.me?.answered || state.pending);
  clock.classList.toggle('urgent', seconds <= 5 && !quiet);
  clock.classList.toggle('answered-clock', !!quiet);
  $('[data-dial]',clock).style.strokeDashoffset = String(100 - 100*Math.min(1,left/state.game.duration));
  if (changed && !seconds && route === 'player') updatePlayerAnswer();
}

function counter(s,g) {
  return `<div class="participation"><span>${icon('users')}Risposte ricevute</span>
  <strong><b data-answered>${fmt(s.answered)}</b> / <b data-players>${fmt(g.players)}</b></strong>
  <div class="thin-track"><i data-meter style="width:${100*(s.answered||0)/(g.players||1)}%"></i></div></div>`;
}

function playerFoot(me) {
  return `<div class="player-foot"><span>${icon('users')}${esc(me.nickname || state.player?.nickname)}</span><b>${icon('bolt')}${fmt(me.score)} pt</b></div>`;
}

function renderGroupRound(s) {
  const {game:g,question:q} = s;
  if (!q) return;
  const host = route === 'host';
  const hint = g.reveal_on_complete ? 'La soluzione apparirà quando tutti avranno risposto o allo scadere del tempo.' : 'Alla scadenza la soluzione apparirà a tutti.';
  show(`<div class="shell game-wrap ${host?'':'projection'}">${progressTop(g,'Round in corso')}
    <section class="panel round"><div class="round-line">${topic(q)}${timerBox()}</div>
    <h1 class="question">${esc(q.text)}</h1><div class="options ${q.options.length===2?'binary':''}">${q.options.map((t,i)=>optionRow(t,i)).join('')}</div>
    ${counter(s,g)}</section>
    ${host?`<div class="command-bar"><div><strong>Domanda aperta</strong><p>${hint}</p></div><div class="actions">${act('cancel','Annulla partita','x','text-btn')}${act('reveal','Chiudi le risposte','flag','primary')}</div></div>`:''}
    </div>`,host?'host-round':'screen-round');
  tick();
}

function renderGroupResult(s) {
  const {game:g,question:q} = s, total = s.answered || 0;
  if (!q) return;
  const host = route === 'host';
  const options = q.options.map((t,i)=>optionRow(t,i,{correct:i===q.correct,count:s.breakdown?.[i]||0,total})).join('');
  const next = g.current < g.total ? act('finish-early','Concludi qui','flag','text-btn') + act('next','Prossima domanda','arrow','primary') : act('finish','Mostra la classifica','award','primary');
  show(`<div class="shell game-wrap ${host?'':'projection'}">${progressTop(g,'Soluzione del round')}
    <section class="panel round results"><div class="round-line">${topic(q)}<span class="mono muted">${fmt(total)} / ${fmt(g.players)} risposte</span></div>
    <h1 class="question">${esc(q.text)}</h1><div class="options ${q.options.length===2?'binary':''}">${options}</div>
    <div class="explain">${icon('info')}<div><strong>Perché questa risposta?</strong><p>${esc(q.explanation)}</p></div></div></section>
    ${host?`<div class="command-bar"><div><strong>Confronto in aula</strong><p>${g.current===g.total?'Hai completato l’ultima domanda.':'La spiegazione resta visibile fino al prossimo round.'}</p></div><div class="actions">${next}</div></div>${ranking(s.leaderboard,'Classifica provvisoria')}`:''}
    </div>`,host?'host-result':'screen-result');
}

function ranking(list=[], title='Classifica') {
  const rows = list.map(p=>`<li><span class="rank-pos">${fmt(p.rank)}ª</span><span class="rank-name">${esc(p.nickname)}${p.tied>1?'<small>Pari merito</small>':''}</span><b>${fmt(p.score)}</b></li>`).join('');
  return `<section class="panel rank-panel"><div class="section-head"><h2>${esc(title)}</h2><span class="eyeline">Punti</span></div>
  ${rows?`<ol class="rank-list">${rows}</ol>`:'<p class="muted">Nessun giocatore in classifica.</p>'}</section>`;
}

function podium(list) {
  const medalists = list.filter(p=>p.rank<=3 && p.score>0);
  if (!medalists.length) return `<section class="panel podium-empty"><span class="standby-mark">${icon('flag')}</span><h2>Nessuna risposta corretta</h2><p>La classe ha concluso a zero punti.</p></section>`;
  const ranks = [...new Set(medalists.map(p=>p.rank))];
  const tiers = ranks.map(rank=>{
    const people=medalists.filter(p=>p.rank===rank);
    const shown=people.slice(0,2), tied=people[0].tied || people.length;
    const rest=tied-shown.length;
    const shared=tied>1?`<small class="tie-caption">Pari merito${rest>0?` · altri ${fmt(rest)}`:''}</small>`:'';
    return `<li class="podium-tier place-${rank}"><div class="podium-medal">${icon(rank===1?'award':'flag')}<span>${rank}° posto</span></div>
      <div class="podium-names">${shown.map(p=>`<strong>${esc(p.nickname)}</strong>`).join('')}${shared}</div>
      <div class="tier-points">${fmt(people[0].score)} <small>pt</small></div></li>`;
  }).join('');
  return `<section class="podium-panel" aria-label="Podio"><ol class="podium" data-tiers="${ranks.length}">${tiers}</ol></section>`;
}

function finishScreen(s) {
  const {game:g} = s, teacher=route==='host', player=route==='player';
  if (g.status==='cancelled') {
    show(`<div class="shell narrow"><section class="panel waiting"><span class="big-symbol">${icon('flag')}</span><div class="eyeline">Sessione chiusa</div>
      <h1 data-phase-focus tabindex="-1">Partita annullata<em>.</em></h1><p>Il docente ha interrotto questa partita.</p>
      ${teacher?act('new','Prepara una partita','arrow','primary'):player?act('exit-player','Torna all’ingresso','back','soft'):'<p class="muted">In attesa della prossima lobby.</p>'}</section></div>`,'cancelled');
    return;
  }
  if (player) { renderPlayerFinal(s); return; }
  const list=s.leaderboard || [];
  show(`<div class="shell game-wrap ${teacher?'':'projection'}"><div class="page-title"><div><div class="eyeline"><i class="pip mint"></i>Partita conclusa</div>
    <h1>Classifica finale<em>.</em></h1><p>${fmt(g.players)} ${g.players===1?'partecipante':'partecipanti'} · ${g.current} ${g.current===1?'round disputato':'round disputati'}</p></div>
    ${teacher?`<div class="actions">${link(`/api/admin/export?gameId=${encodeURIComponent(g.id)}`,'Esporta CSV','save','soft')}${act('new','Nuova partita','arrow','primary')}</div>`:''}</div>
    <div class="final-grid award-layout">${podium(list)}${ranking(list,list.length<g.players?`Classifica · primi ${fmt(list.length)}`:'Classifica')}</div></div>`,'final');
}

function screenIdle() {
  show(`<div class="shell narrow"><section class="panel waiting"><div class="radar" aria-hidden="true"><i></i><b></b></div><div class="eyeline">Schermo di sala</div>
    <h1>In attesa della lobby<em>.</em></h1><p>Il PIN apparirà qui quando il docente aprirà la partita.</p></section></div>`,'standby');
}

function renderGame() {
  const g=state.game,s=state.snap;
  header();
  if (route==='host' && (state.editing || state.studio || !g)) { renderStudio(); return; }
  if (route==='player' && !state.player) { showHome(); return; }
  if (!g) { screenIdle(); return; }
  if (g.status==='lobby') { if (route==='player') waitingPlayer(g); else showLobby(g); return; }
  if (!s?.game || s.game.id!==g.id) { show('<p class="boot">Recupero della partita…</p>','loading'); return; }
  if (g.status==='question') { if (route==='player') renderPlayerRound(s); else renderGroupRound(s); }
  else if (g.status==='results') { if (route==='player') renderPlayerResult(s); else renderGroupResult(s); }
  else finishScreen(s);
}
