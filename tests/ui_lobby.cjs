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
function tab(shared) {
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
    WebSocket:Socket,location:{pathname:'/',search:'',host:'localhost',origin:'http://localhost',protocol:'http:'},
    setInterval(){},setTimeout:fn=>{timers.set(++timerId,fn);return timerId;},clearTimeout:id=>timers.delete(id)});
  for(const file of ['ui.js','game.js','player.js','app.js']) {
    let source=fs.readFileSync(path.join(__dirname,'..','static',file),'utf8');
    if(file==='app.js') source=source.replace(/\nboot\(\);\s*$/,'');
    vm.runInContext(source,context,{filename:file});
  }
  return {run:code=>vm.runInContext(code,context),context,handlers,dom};
}

async function main() {
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
  console.log('OK: independent tabs, confirmed join retry, lost response, foreground sync, third-tab recovery, offline/online and notice cleanup');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
