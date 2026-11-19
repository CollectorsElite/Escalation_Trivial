'use strict';

function showHome() {
  header();
  const invite = new URLSearchParams(location.search).get('pin') || '';
  const hasPin = /^\d{6}$/.test(invite);
  const pin = hasPin ? invite : '';
  const instructions = hasPin ? 'Scegli il nome che vedrà la tua classe.' : 'Inserisci il PIN proiettato in aula e scegli un nickname.';
  show(`<div class="entry shell ${hasPin ? 'has-invite' : ''}">
    <div class="entry-grid">
      <section class="join-card join-first paper" aria-labelledby="join-title">
        <div class="card-kicker"><span class="tile-icon">${icon('key')}</span>Accesso giocatori</div>
        <h1 id="join-title">Entra in partita<em>.</em></h1><p id="join-intro">${instructions}</p>
        <form id="join-form">
          ${hasPin ? `<div id="invite-summary"><div><span>PIN dall’invito</span><b>${esc(pin.slice(0,3))} ${esc(pin.slice(3))}</b></div>${act('edit-pin','Cambia PIN',null,'text-btn')}</div>` : ''}
          <div class="pin-field" id="pin-field" ${hasPin ? 'hidden' : ''}>
            <label for="join-pin">PIN della partita</label>
            <input id="join-pin" name="pin" class="pin-input" type="text" inputmode="numeric" pattern="[0-9]{6}" placeholder="000000" value="${esc(pin)}" autocomplete="off" required>
          </div>
          <label for="join-nick">Nickname</label>
          <input id="join-nick" name="nickname" placeholder="Il tuo nome di gioco" autocomplete="nickname" spellcheck="false" minlength="2" maxlength="24" required>
          ${errorLine()}<button type="submit" class="btn primary cta">Entra nella lobby ${icon('arrow')}</button>
        </form>
        ${act('rules','Come si gioca','info','text-btn entry-rules')}
      </section>
      <aside class="poster" aria-label="Escalation Trivial, il quiz live per la tua aula">
        <img class="cover-photo" src="/static/assets/mazzo-trivial.webp" width="984" height="656" alt="" fetchpriority="low">
        <div class="poster-copy" aria-hidden="true">
          <img class="cover-word" src="/static/assets/escalation-nome.svg" alt="" width="230" height="29">
          <div class="cover-title">Trivial<span>.</span></div>
          <p>Il quiz in diretta per la tua aula.</p>
        </div>
      </aside>
    </div>
    <section id="entry-metrics" class="stats-strip" aria-label="Il gioco in numeri">${homeMetrics()}</section>
  </div>`, 'entry');
}

function editInvitePin() {
  const field = $('#pin-field');
  if (!field) return;
  field.hidden = false;
  $('#invite-summary')?.remove();
  $('#join-intro').textContent = 'Inserisci il PIN proiettato in aula e scegli un nickname.';
  history.replaceState(null, '', location.pathname);
  $('#join-pin').focus();
  $('#join-pin').select();
}

function waitingPlayer(g) {
  show(`<div class="shell narrow"><section class="panel player-wait paper">
    <div class="pass-head">
      <div class="eyeline"><i class="pip mint"></i>Lobby aperta</div>
      <h1 data-phase-focus tabindex="-1">Sei dentro, <em>${esc(state.player.nickname)}</em>.</h1>
    </div>
    <div class="pass-body">${lobbyTitle(g)}
    <div class="wait-status" role="status" aria-live="polite" aria-atomic="true">
      <span class="wait-light" aria-hidden="true"></span>
      <div><strong data-wait-title></strong><p data-wait-copy></p></div>
    </div>
    <div class="wait-ticket"><span>PIN della partita</span><b>${esc(g.pin.slice(0,3))} ${esc(g.pin.slice(3))}</b></div>
    ${gameMeta(g)}
    <div class="wait-actions">${act('rules','Come si gioca','info','soft')}${act('leave','Lascia la lobby','exit','text-btn')}</div></div>
  </section></div>`, 'player-lobby');
  updateWaitingStatus();
}
function updateWaitingStatus() {
  const title=$('[data-wait-title]');
  if(!title) return;
  const mode=state.online?'ready':navigator.onLine===false?'offline':'connecting';
  const box=title.closest('.wait-status');
  if(box.dataset.mode===mode) return;
  box.dataset.mode=mode;
  const messages={
    ready:['In attesa del via','La prima domanda apparirà qui appena il docente avvierà il quiz.'],
    offline:['Connessione interrotta','Il tuo posto è riservato. Ricollegati alla rete per seguire la partita.'],
    connecting:['Collegamento in corso','Il tuo posto è riservato. Stiamo recuperando lo stato della partita.']
  };
  title.textContent=messages[mode][0];
  $('[data-wait-copy]',box).textContent=messages[mode][1];
}

function renderPlayerRound(s) {
  const q = s.question;
  if (!q) return;
  const short = q.options.every(item => [...item].length <= 36);
  const choices = q.options.map((answer, i) => `<button class="answer-key opt-${i}" type="button" data-choice="${i}" aria-pressed="false">
    ${answerMark(i)}<span class="answer-text">${esc(answer)}</span><span class="choice-flag" aria-hidden="true"></span>
  </button>`).join('');
  show(`<div class="shell narrow player-stage">${progressTop(s.game, 'Round in corso')}
    <section class="panel round player-card paper">
      <div class="round-line">${topic(q)}${timerBox()}</div>
      <h1 class="question" id="current-question" data-phase-focus tabindex="-1">${esc(q.text)}</h1>
       ${s.game.bets?`<div class="stake-box"><button class="btn soft" type="button" data-action="wager" aria-pressed="false">Raddoppio</button><small>Se indovini aggiungi i punti base. Se sbagli perdi fino a 500 punti.</small></div>`:''}<div class="answer-keys ${short ? 'short-keys' : 'long-keys'} ${q.options.length===2 ? 'two-keys' : 'four-keys'}" role="group" aria-labelledby="current-question">${choices}</div>
      <div class="receipt" data-receipt role="status" aria-live="polite" aria-atomic="true"><span class="receipt-sign" aria-hidden="true"></span><span data-receipt-text></span></div>
    </section>${playerFoot(s.me || {})}</div>`, 'player-round');
  updatePlayerAnswer();
  tick();
}

function updatePlayerAnswer() {
  const receipt = $('[data-receipt]');
  if (!receipt || !state.snap?.me) return;
  const me = state.snap.me;
  const choice = me.answered ? me.choice : state.pending?.choice;
  const mode = me.answered ? 'received' : !state.online ? 'offline' : state.pending ? 'sending' : remaining() <= 0 ? 'elapsed' : 'open';
  const button=$('[data-action="wager"]');
  if(button){button.disabled=mode!=='open'||me.remainingBets<1;button.setAttribute('aria-pressed',String(state.wager));button.textContent=(state.wager?'Raddoppio attivo':'Raddoppio')+' · '+me.remainingBets+' disponibili';}
  for (const key of all('[data-choice]')) {
    const selected = Number(key.dataset.choice) === choice;
    key.classList.toggle('selected', selected);
    key.setAttribute('aria-pressed', String(selected));
    key.setAttribute('aria-disabled', String(mode !== 'open'));
    if (selected && key.dataset.confirmation !== mode) {
      key.dataset.confirmation = mode;
      $('.choice-flag', key).innerHTML = icon(mode === 'received' ? 'check' : mode === 'offline' ? 'net' : 'timer');
    }
  }
  const name = Number.isInteger(choice) ? letters[choice] : '';
  const messages = {
    open: ['target','Scegli una risposta. La prima scelta è definitiva.'],
    sending: ['timer',`Invio della risposta ${name}…`],
    received: ['check',`Risposta ${name} registrata. Attendi la soluzione.`],
    offline: ['net',state.pending ? 'Connessione interrotta. Al rientro verificheremo se la risposta è arrivata.' : 'Riconnessione in corso. Potrai rispondere se il round è ancora aperto.'],
    elapsed: ['timer','Tempo terminato. Tra poco vedrai la soluzione.']
  };
  const [symbol, message] = messages[mode];
  receipt.dataset.mode = mode;
  const caption = $('[data-receipt-text]', receipt);
  if (caption.textContent !== message) {
    $('.receipt-sign', receipt).innerHTML = icon(symbol);
    caption.textContent = message;
  }
}

function outcomeInfo(outcome) {
  if (outcome === 'correct') return ['Risposta corretta','check'];
  if (outcome === 'wrong') return ['Risposta errata','x'];
  return ['Nessuna risposta','timer'];
}

function solutionContent(q, choice) {
  const own = Number.isInteger(choice) && choice !== q.correct;
  return `<div class="solution-content">
    <div class="solution-answer"><span>Risposta corretta</span><strong>${answerMark(q.correct)}<span>${esc(q.options[q.correct])}</span></strong></div>
    <div class="solution-why"><h3>Perché?</h3><p>${esc(q.explanation)}</p></div>
    ${own ? `<p class="previous-choice"><b>La tua scelta</b> ${letters[choice]} · ${esc(q.options[choice])}</p>` : ''}
  </div>`;
}

function rankText(me, full=false) {
  return me.rank ? `${fmt(me.rank)}ª${full ? ' posizione' : ''}${me.tied > 1 ? ' a pari merito' : ''}` : '–';
}

function outcomeMark(outcome) {
  if (outcome==='missed') return icon('timer');
  const strokes = outcome==='correct' ? ['M11 24l8 8 18-19'] : ['M14 14l20 20','M34 14L14 34'];
  return `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="4"
    stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    ${strokes.map(d=>`<path pathLength="1" d="${d}"/>`).join('')}</svg>`;
}

function renderPlayerResult(s) {
  const {game:g, question:q, me} = s;
  if (!q || !me) return;
  const a = me.answer;
  const outcome = !a ? 'missed' : a.correct ? 'correct' : 'wrong';
  const [title] = outcomeInfo(outcome);
  const effectKey=`${g.id}/${g.current}/${state.player?.playerId || ''}`;
  const fresh=readSaved('sessionStorage','esc_last_outcome')!==effectKey;
  if(fresh) writeSaved('sessionStorage','esc_last_outcome',effectKey);
  const options = q.options.map((t,i) => optionRow(t,i,{correct:i===q.correct,own:a?.choice===i,wrong:a?.choice===i && !a.correct})).join('');
  show(`<div class="shell narrow player-stage">${progressTop(g,'Soluzione del round')}
    <article class="panel debrief paper" data-outcome="${outcome}" data-reveal="${fresh}">
      <div class="outcome-head"><span class="outcome-icon">${outcomeMark(outcome)}</span>
        <h1 data-phase-focus tabindex="-1">${title}</h1><strong class="round-points">${(a?.points||0)>=0?'+':''}${fmt(a?.points)} <small>pt</small></strong>
      </div>
      ${solutionContent(q, a?.choice)}
      <details class="details-box"><summary>Rivedi domanda e opzioni</summary>
        <div class="details-body">${topic(q)}<p class="detail-question">${esc(q.text)}</p><div class="options preview-options">${options}</div></div>
      </details>
    </article>
    <div class="personal-strip"><div><span>Posizione</span><b>${rankText(me)}</b></div><div><span>Punti totali</span><b>${fmt(me.score)} pt</b></div></div>
    <p class="round-wait">${icon('timer')}${g.current===g.total ? 'Il docente mostrerà la classifica finale.' : 'La prossima domanda partirà al via del docente.'}</p>
  </div>`, 'player-result');
}

function renderPlayerFinal(s) {
  const {me, game:g} = s;
  if (!me) return;
  const counts = me.summary;
  const names = {correct:'Corrette',wrong:'Errate',missed:'Senza risposta'};
  const metrics = counts ? `<div class="final-metrics">${Object.entries(names).map(([key,label])=>`<div data-outcome="${key}"><strong>${fmt(counts[key])}</strong><span>${label}</span></div>`).join('')}</div>` : '';
  show(`<div class="shell narrow player-stage"><section class="panel personal-finish paper">
    <div class="eyeline"><i class="pip mint"></i>Partita conclusa</div><h1 data-phase-focus tabindex="-1">${esc(me.nickname)}<em>.</em></h1>
    <div class="finish-numbers"><div><span>Posizione finale</span><b>${me.rank?fmt(me.rank)+'ª':'–'}</b>
    <small>${me.tied>1?'Pari merito · ':''}su ${fmt(g.players)}</small></div><div><span>Punteggio</span>
    <b>${fmt(me.score)}</b><small>punti totali</small></div></div>
    ${metrics}${counts?`<p class="finish-standing">Velocità <b>${fmt(counts.base)} pt</b> · Bonus <b>${fmt(counts.bonus)} pt</b> · Puntate <b>${fmt(counts.stake)} pt</b></p>`:''}<div class="finish-actions">${act('review','Ripassa le domande','cards','primary')}${act('exit-player','Torna all’ingresso','back','text-btn')}</div>
  </section></div>`, 'player-final');
}

async function openReview() {
  const g = state.game, p = state.player;
  if (!p || g?.status !== 'finished') return;
  modal('Ripassa la partita','<div id="review-content"><p class="muted" role="status">Apertura delle domande…</p></div>');
  const body = $('#review-content');
  try {
    const cached = state.review;
    const data = cached?.gameId === g.id ? cached : await api('/api/player/review','POST',{pin:p.pin,playerId:p.playerId,token:p.token});
    if (state.player !== p || state.game?.id !== g.id || data.gameId !== g.id) return;
    state.review = data;
    if (dlg.open && body.isConnected) {
      const selectAll = data.rounds.every(r => r.outcome === 'correct');
      fillReview(body, selectAll);
    }
  } catch (err) {
    if (dlg.open && body.isConnected) body.innerHTML = `<p role="alert">${esc(err.message)}</p>${act('review','Riprova','arrow','soft')}`;
  }
}

function fillReview(body, allRounds) {
  if (!body || state.review?.gameId !== state.game?.id) return;
  const rounds = state.review.rounds;
  const missed = rounds.filter(r => r.outcome !== 'correct');
  const visible = allRounds ? rounds : missed;
  const items = visible.map(r => {
    const [label, sym] = outcomeInfo(r.outcome);
    return `<details class="review-row details-box" data-outcome="${esc(r.outcome)}">
      <summary><span class="review-meta">${icon(sym)}${label} · Domanda ${r.number}</span><strong>${esc(r.text)}</strong></summary>
      <div class="details-body"><p class="review-category">${esc(r.category)}</p>${solutionContent(r,r.choice)}</div>
    </details>`;
  }).join('');
  body.innerHTML = `<div class="review-filters" role="group" aria-label="Domande da visualizzare">
    ${act('review-missed',`Da ripassare (${fmt(missed.length)})`,null,'soft',`aria-pressed="${!allRounds}"`)}
    ${act('review-all',`Tutte (${fmt(rounds.length)})`,null,'soft',`aria-pressed="${allRounds}"`)}
  </div><div class="review-list">${items || '<p class="review-empty">Hai risposto correttamente a tutte le domande giocate.</p>'}</div>`;
}
