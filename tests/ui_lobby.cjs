'use strict';
// Regression checks for the production browser controller using Node's standard library.
const assert = require('node:assert/strict');
const crypto = require('node:crypto').webcrypto;
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function storage() {
  const map=new Map();
  return {getItem:key=>map.get(key)??null,setItem:(key,value)=>map.set(key,value),removeItem:key=>map.delete(key)};
}
function tab(shared,pathname='/') {
  const handlers={}, timers=new Map();
  let timerId=0;
  const element=()=>({classList:{add(){},remove(){}},addEventListener(){},dataset:{},textContent:'',innerHTML:''});
  const dom=new Map(['#app','#site-header','#dialog','#notice','#phase-announce'].map(key=>[key,element()]));
  const document={
    body:{dataset:{}},querySelector:key=>dom.get(key)??null,querySelectorAll:()=>[],
    addEventListener:(name,fn)=>{handlers['doc:'+name]=fn;},hidden:false,
  };
  class Socket {
    static OPEN=1; static CLOSED=3;
    constructor(){this.readyState=0;this.messages=[];}
    send(raw){this.messages.push(JSON.parse(raw));}
    close(){this.readyState=3;if(this.onclose)this.onclose();}
  }
  const window={sessionStorage:storage(),localStorage:shared,scrollTo(){},
    addEventListener:(name,fn)=>{handlers[name]=fn;}};
  const context=vm.createContext({document,window,navigator:{onLine:true},crypto,URL,URLSearchParams,
    WebSocket:Socket,location:{pathname,search:'',host:'localhost',origin:'http://localhost',protocol:'http:'},
    setInterval(){},setTimeout:fn=>{timers.set(++timerId,fn);return timerId;},clearTimeout:id=>timers.delete(id)});
  for(const file of ['ui.js','question-media.js','studio.js','teacher.js','game.js','player.js','app.js']) {
    let source=fs.readFileSync(path.join(__dirname,'..','static',file),'utf8');
    if(file==='app.js') source=source.replace(/\nboot\(\);\s*$/,'');
    vm.runInContext(source,context,{filename:file});
  }
  return {run:code=>vm.runInContext(code,context),context,handlers,dom};
}

async function studioAndLobby() {
  const room={id:'classe',pin:'333333',created:2,status:'lobby',current:0,total:1,players:1,
    connected:1,duration:30,title:'Lezione A',areas:['Categoria iniziale']};
  for (const route of ['/docente','/schermo','/']) {
    const view=tab(storage(),route);
    if(route==='/') view.run("storePlayer({playerId:'sample',pin:'333333',nickname:'Nova'})");
    view.context.room=room;
    view.run('syncView({game:room})');
    assert.match(view.dom.get('#app').innerHTML,/Lezione A/);
    view.run("syncView({game:{...room,title:'Lezione B',areas:['Nuovo argomento']}})");
    assert.match(view.dom.get('#app').innerHTML,/Lezione B/);
    assert.match(view.dom.get('#app').innerHTML,/Nuovo argomento/);
    assert.doesNotMatch(view.dom.get('#app').innerHTML,/Categoria iniziale/);
  }
  const teacher=tab(storage(),'/docente');
  const data={game:room, selected:['a'], settings:{multipliers:{}}, questions:[
    {id:'a',category_id:'A',difficulty:'Avanzato'}, {id:'b',category_id:'B',difficulty:'Avanzato'}]};
  teacher.context.data=data;
  teacher.run('overview=async()=>data;renderGame=()=>{}');
  await teacher.run('goStudio(true)');
  assert.equal(teacher.run('multiplier(data.questions[0])'),1);
  assert.equal(teacher.run('multiplier(data.questions[1])'),2);
  teacher.run("state.questions=data.questions;state.drawCategories=new Set(['A']);state.category='B'");
  teacher.run("replaceStudioQuestions([data.questions[0],{id:'b',category_id:'C'}])");
  assert.equal(teacher.run("state.category"),'all');
  assert.deepEqual([...teacher.run('state.drawCategories')],['A']);
  teacher.run("state.drawCategories=new Set(['A','C']);replaceStudioQuestions([...state.questions,{id:'z',category_id:'Z'}])");
  assert.deepEqual([...teacher.run('state.drawCategories')],['A','C','Z']);
  data.game={...room,status:'question',current:1};
  data.snapshot={game:data.game};
  await teacher.run('goStudio(false)');
  assert.equal(teacher.run('state.studio || state.editing'),false);
  assert.equal(teacher.run('state.game.status'),'question');
  teacher.run("state.admin=true;handleMessage({type:'admin_signed_out'})");
  assert.equal(teacher.run('state.admin'),false);
  assert.match(teacher.dom.get('#app').innerHTML,/Password docente/);
  console.log('OK: titolo e categorie su tre viste, moltiplicatori in modifica, filtri, seconda regia e uscita');
}

async function questionEditor() {
  for (const [id,revision,copy] of [['AUT-001',0,false],['AUT-001',2,false],['DOC-demo',1,false],['AUT-001',0,true]]) {
    const view=tab(storage(),'/docente');
    const q={id,revision,category_id:'AUT',category:'Password e autenticazione',difficulty:'Base',
      text:'Quale password usi?',options:['La precedente','Una nuova'],correct:1,explanation:'Ogni servizio ha la sua password.'};
    if (revision || copy) Object.assign(q,{image:'a'.repeat(64),imageAlt:'Traccia iniziale.'});
    view.context.question=q;
    view.run('state.questions=[question];state.selected.add(question.id);renderStudio=()=>{}');
    const dialog=view.dom.get('#dialog');
    dialog.showModal=()=>{dialog.open=true;};
    dialog.close=()=>{dialog.open=false;};
    dialog.querySelector=selector=>selector==='.dialog-head'?{isConnected:true}:null;
    await view.run("perform('preview',question.id)");
    assert.match(dialog.innerHTML,/data-action="edit-question"/);
    assert.match(dialog.innerHTML,/data-action="copy-question"/);

    const values={category:'AUT',newCategory:'',difficulty:'Base',text:'Quale password scegli?',
      format:'2',option0:q.options[0],option1:q.options[1],option2:'',option3:'',correct:'1',explanation:q.explanation};
    const elements=Object.fromEntries(Object.entries(values).map(([k,value])=>[k,{value}]));
    elements.imageFile={value:'',files:[], setCustomValidity(error){this.error=error;}};
    elements.imageAlt={value:q.imageAlt||''};
    const controls=new Map([['details',{open:false}],['[data-new-category]',{}],
      ['[data-editor-image]',{}],['[data-remove-image]',{}],['[data-image-description]',{}],['[data-image-feedback]',{hidden:true}]]);
    for (let i=0;i<4;i++) controls.set(`[data-option-row="${i}"]`,{querySelector:()=>({})});
    const form={elements,dataset:{},isConnected:true,querySelector:key=>controls.get(key)||null,querySelectorAll:()=>[]};
    view.dom.set('#question-form',form);
    let request;
    view.context.fetch=async (url,options)=>{
      if(options.method==='GET') return {ok:true,json:async()=>q};
      const body=JSON.parse(options.body);
      request={url,method:options.method,body};
      return {ok:true,json:async()=>({...q,id:copy?'DOC-copia':id,text:body.text,revision:revision+1})};
    };
    view.context.action=copy?'copy-question':'edit-question';
    await view.run("perform(action,question.id)");
    assert.ok(dialog.innerHTML.includes(copy?'Copia domanda':'Salva modifiche'));
    assert.ok(dialog.innerHTML.includes('Immagine della domanda'));
    const holder=controls.get('[data-editor-image]'), remove=controls.get('[data-remove-image]');
    if(q.image) assert.ok(holder.innerHTML.includes('/api/question-images/'+q.image));
    let expectedImage=q.image||null;
    if(revision===2) {
      elements.imageFile.files=[{type:'image/svg+xml',size:50,name:'test.svg'}];
      elements.imageFile.onchange();
      assert.match(elements.imageFile.error,/JPG/);
      assert.ok(holder.innerHTML.includes(q.image));
      view.context.URL=class extends URL {
        static createObjectURL(){return 'blob:anteprima';}
        static revokeObjectURL(){}
      };
      view.context.FileReader=class {
        readAsDataURL(){this.result='data:image/png;base64,QUJD';this.onload();}
      };
      elements.imageFile.files=[{type:'image/png',size:12,name:'nuova.png'}];
      elements.imageFile.onchange();
      assert.equal(elements.imageFile.error,'');
      assert.ok(holder.innerHTML.includes('blob:anteprima'));
      assert.equal(elements.imageAlt.value,'');
      elements.imageAlt.value='Nuova illustrazione.';
      expectedImage=null;
    } else if(id==='DOC-demo') {
      remove.onclick();
      assert.equal(holder.innerHTML,'');
      assert.equal(remove.hidden,true);
      assert.equal(elements.imageAlt.value,'');
      expectedImage=null;
    }
    await form.onsubmit({preventDefault(){},submitter:{value:'save'}});
    assert.equal(request.method,copy?'POST':'PUT');
    assert.equal(request.url,'/api/admin/catalogue'+(copy?'':'/'+id));
    assert.equal(request.body.expectedRevision,copy?undefined:revision);
    assert.equal(request.body.text,values.text);
    assert.equal(request.body.image,expectedImage);
    assert.equal(request.body.imageAlt,elements.imageAlt.value);
    assert.equal(request.body.imageUpload,revision===2?'QUJD':undefined);
    assert.equal(view.run('state.questions.length'),copy?2:1);
    assert.deepEqual([...view.run('state.selected')],[id]);
    assert.equal(view.run("state.questions.find(q=>q.id===question.id).text"),copy?q.text:values.text);
  }
  console.log('OK: editor docente, salvataggio sullo stesso codice e copia indipendente');
}

async function questionImages() {
  const q={id:'PCTO-003',image:'b'.repeat(64),imageAlt:'Mario <legge> il messaggio.',category_id:'PCTO',category:'PCTO',
    text:'Che cosa faresti?',options:['Apro','Verifico'],correct:1,type:'AB',difficulty:'Base',explanation:'Verifica il messaggio.'};
  for (const route of ['/docente','/schermo','/']) {
    const view=tab(storage(),route);
    view.context.snap={game:{id:'g',status:'question',current:1,total:2,duration:60,players:1,deadline:Date.now()/1000+60},
      question:q,me:{nickname:'Mario',score:0}};
    view.run("state.game=snap.game;state.snap=snap;route==='player'?renderPlayerRound(snap):renderGroupRound(snap)");
    const html=view.dom.get('#app').innerHTML;
    assert.ok(html.includes('/api/question-images/'+q.image) && html.includes('Ingrandisci immagine'));
    assert.ok(html.includes('Mario &lt;legge&gt; il messaggio.'));
    view.run("snap.game.status='results';route==='player'?renderPlayerResult(snap):renderGroupResult(snap)");
    assert.ok(view.dom.get('#app').innerHTML.includes('/api/question-images/'+q.image));
    assert.equal(view.run("questionImage({text:'Solo testo'})"),'');
    assert.equal(view.run("questionImage({image:'https://example.test/untrusted.jpg'})"),'');
  }
  const view=tab(storage()), original={src:'/api/question-images/'+q.image,alt:q.imageAlt};
  const enlarged={}, viewport={scrollLeft:10,scrollTop:10}, zoom={setAttribute(k,v){this[k]=v;}};
  const close={focus(){this.focused=true;}};
  const captionText={},caption={querySelector:()=>captionText};
  const widgets={img:enlarged,'.image-viewport':viewport,'.image-caption':caption,'[data-zoom-image]':zoom,'[data-close-image]':close};
  const viewer={open:false,querySelector:k=>widgets[k],
    classList:{remove(){},toggle(){return true;}},showModal(){this.open=true;},close(){this.open=false;}};
  view.dom.set('#question-image-viewer',viewer);
  const target={closest(k){return k==='.question-image'?{querySelector:()=>original}:k==='img, [data-expand-image]'?this:null;}};
  await view.handlers['doc:click']({target});
  assert.ok(viewer.open && close.focused && enlarged.src===original.src && enlarged.alt===original.alt);
  assert.equal(captionText.textContent,original.alt);
  assert.equal(caption.hidden,false);
  assert.equal(viewport.scrollLeft+viewport.scrollTop,0);
  await view.handlers['doc:click']({target:{closest:k=>k==='#question-image-viewer'?viewer:k==='[data-zoom-image]'?zoom:null}});
  assert.equal(zoom['aria-pressed'],'true');
  await view.handlers['doc:click']({target:{closest:k=>k==='#question-image-viewer'?viewer:k==='[data-close-image]'?close:null}});
  assert.equal(viewer.open,false);
  console.log('OK: immagini in regia, proiezione e telefono, zoom e chiusura del visualizzatore');
}

async function presentationControls() {
  const view=tab(storage(),'/schermo');
  const {document,navigator,window}=view.context;
  const dialog=view.dom.get('#dialog');
  dialog.close=()=>{dialog.open=false;};
  dialog.showModal=()=>{dialog.open=true;};
  view.run("state.admin=true;state.game={pin:'123456',status:'lobby',public_url:'https://aula.example.test'}");
  let copied, selected=false;
  navigator.clipboard={writeText:async value=>{copied=value;}};
  await view.run("perform('copy-link')");
  assert.equal(copied,'https://aula.example.test/?pin=123456');
  navigator.clipboard.writeText=async()=>{throw new Error('Clipboard non disponibile');};
  view.dom.set('#invite-url',{select(){selected=true;}});
  await view.run("perform('copy-link')");
  assert.ok(dialog.open && selected && dialog.innerHTML.includes(copied));
  await view.run("perform('enlarge-qr')");
  assert.match(dialog.innerHTML,/api\/admin\/qr\?pin=123456/);
  assert.match(dialog.innerHTML,/123 456/);
  await view.run("perform('rules')");
  assert.match(dialog.innerHTML,/bonus ×2 o ×3/);
  await view.run("perform('close')");
  assert.equal(dialog.open,false);

  document.documentElement={async requestFullscreen(){document.fullscreenElement=this;}};
  document.exitFullscreen=async()=>{document.fullscreenElement=null;};
  await view.run("perform('fullscreen')");
  assert.equal(document.fullscreenElement,document.documentElement);
  await view.run("perform('fullscreen')");
  assert.equal(document.fullscreenElement,null);
  let notes=0;
  window.AudioContext=class {
    constructor(){this.currentTime=0;this.destination={};}
    async resume(){}
    createOscillator(){return {frequency:{},connect(){},start(){notes++;},stop(){}};}
    createGain(){return {gain:{setValueAtTime(){},exponentialRampToValueAtTime(){}},connect(){}};}
  };
  await view.run("perform('sound')");
  assert.equal(notes,2);
  view.run("tone('results');tone('finished')");
  assert.equal(notes,7);
  await view.run("perform('sound')");
  view.run("tone('finished')");
  assert.equal(notes,7);
  console.log('OK: invito copiato e selezionabile, QR ingrandito, regole, schermo intero e segnali sonori');
}

async function main() {
  await presentationControls();
  await studioAndLobby();
  await questionEditor();
  await questionImages();
  const shared=storage(), first=tab(shared), second=tab(shared);
  first.run("storePlayer({playerId:'old',token:'first',nickname:'Vega',pin:'222222'})");
  second.run("storePlayer({playerId:'new',token:'second',nickname:'Nova',pin:'333333'})");
  assert.equal(first.run("localGet('222222').playerId"),'old');
  first.run("forgetPlayer(localGet('222222'))");
  assert.equal(first.run("localGet('333333').playerId"),'new');
  assert.equal(second.run('localGet().playerId'),'new');

  first.context.fetch=async()=>{throw new Error('temporary network loss');};
  await assert.rejects(first.run("registerPlayer(draftFor('111111','Nova'))"));
  const key=first.run("readSaved('sessionStorage','esc_join_pending').joinKey");
  assert.match(key,/^[0-9a-f]{64}$/);
  first.run('state.joinDraft=null');
  assert.equal(first.run("draftFor('111111','Nova').joinKey"),key);
  assert.notEqual(first.run("draftFor('555555','Nova').joinKey"),key);

  const game={id:'sample',pin:'111111',created:1,status:'lobby',players:1,connected:0,current:0,total:2,duration:30};
  first.context.preview=game;
  first.run('showLobby(preview)');
  assert.match(first.dom.get('#app').innerHTML,/Invito locale/);
  assert.doesNotMatch(first.dom.get('#app').innerHTML,/class="qr-box"/);
  first.context.preview={...game,public_url:'http://192.168.30.10:8000'};
  first.run('showLobby(preview)');
  assert.match(first.dom.get('#app').innerHTML,/class="qr-box"/);
  const result={playerId:'p',token:'t',nickname:'Nova',game};
  let submissions=0;
  first.context.fetch=async(_url,options)=>{
    const body=JSON.parse(options.body);
    assert.equal(body.joinKey,key);submissions++;
    return {ok:true,json:async()=>result};
  };
  first.run("notice('Hai lasciato la lobby.')");
  await first.run('playerInit()');
  assert.equal(submissions,1);
  assert.equal(first.dom.get('#notice').textContent,'');
  assert.equal(first.run("readSaved('sessionStorage','esc_join_pending')"),null);
  assert.equal(first.run('state.player.nickname'),'Nova');

  first.context.snapshot={type:'snapshot',game:{...game,connected:1},me:{nickname:'Nova',score:0}};
  first.run("state.socket.readyState=WebSocket.OPEN;state.socket.onopen();handleMessage(snapshot)");
  assert.equal(first.run("state.socket.messages[0].type"),'hello');
  first.handlers['doc:visibilitychange']();
  assert.equal(first.run("state.socket.messages.at(-1).type"),'sync');
  first.run('handleMessage(snapshot)');
  assert.equal(first.run('state.syncTimer'),null);

  first.run("handleMessage({type:'error',code:'tab_limit',message:'Chiudi una scheda e premi Ricollega.'})");
  first.handlers['doc:visibilitychange']();
  assert.equal(first.run('state.socket'),null);
  assert.match(first.dom.get('#app').innerHTML,/Ricollega/);
  await first.run("perform('retry-socket')");
  assert.ok(first.run('state.socket'));
  first.context.navigator.onLine=false;
  first.handlers.offline();
  assert.equal(first.run('state.online'),false);
  assert.equal(first.run('state.socket'),null);
  assert.equal(first.run('state.player.playerId'),'p');
  first.context.navigator.onLine=true;
  first.handlers.online();
  assert.ok(first.run('state.socket'));
  const demoQuestion={id:'one',number:1,category_id:'PRI',category:'Privacy',text:'Una prova?',options:['Sì','No'],correct:0,explanation:'Spiegazione.'};
  for (const [i,outcome] of ['correct','wrong','missed'].entries()) {
    const answer=outcome==='missed' ? undefined : {points:outcome==='wrong'?-500:900,correct:outcome==='correct',choice:i};
    first.context.round={game:{...game,current:i+1,total:3},question:demoQuestion,me:{nickname:'Nova',rank:1,score:900,tied:1,answer}};
    first.run('renderPlayerResult(round)');
    const html=first.dom.get('#app').innerHTML;
    assert.ok(html.includes('data-outcome="'+outcome+'" data-reveal="true"'));
    assert.ok(html.includes('Spiegazione.'));
    first.run('renderPlayerResult(round)');
    assert.match(first.dom.get('#app').innerHTML,/data-reveal="false"/);
  }
  first.context.ties=[{rank:1,tied:2,score:900,nickname:'Nova'},{rank:1,tied:2,score:900,nickname:'Mira'},
                       {rank:3,tied:1,score:600,nickname:'Vega'}];
  assert.equal((first.run('ranking(ties)').match(/data-place="1"/g)||[]).length,2);
  assert.match(first.run('podium(ties)'),/Pari merito/);
  assert.doesNotMatch(first.run('podium(ties)'),/2° posto/);
  assert.match(first.run('podium([{rank:1,tied:1,score:0}])'),/Punteggi a zero/);
  console.log('OK: riscontri distinti e riproduzione singola, classifica con pari merito e punteggi a zero');
  console.log('OK: independent tabs, confirmed join retry, lost response, foreground sync, third-tab recovery, offline/online and notice cleanup');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
