import {FrontKeyboard,pinchRatio} from './front-keyboard.js';
import {HandMotion} from './hand-motion.js';
import {DrumStrokes,padAt} from './drum-strokes.js';
import {StringBoard,visibleFingers,drawStringBoard,noteName} from './string-board.js';
import {MusicAudio} from './music-audio.js';
import {INSTRUMENTS} from './music-catalog.js';
import {HandSlots,handGesture,mapHandPoint} from './hand-input.js';
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const CHORDS={Livre:[40,45,50,55,59,64],Am:[45,45,52,57,60,64],C:[48,48,52,55,60,64],G:[43,47,50,55,59,67],D:[50,50,50,57,62,66],Em:[40,47,52,55,59,64],F:[41,48,53,57,60,65]};
const FAMILIES=['Pianos','Percussão afinada','Órgãos e acordeões','Guitarras e violões','Baixos','Cordas','Conjuntos e coros','Metais','Saxofones e palhetas','Flautas','Sintetizadores solo','Pads','Efeitos musicais','Étnicos','Percussão','Efeitos sonoros'];
export const PADS=[{name:'Bumbo',note:36,x:380,y:465,r:95},{name:'Caixa',note:38,x:165,y:325,r:84},{name:'Chimbal',note:42,x:135,y:125,r:73},{name:'Prato',note:49,x:760,y:120,r:95},{name:'Tom grave',note:45,x:750,y:385,r:87},{name:'Tom agudo',note:50,x:370,y:240,r:78},{name:'Tom médio',note:47,x:560,y:250,r:78},{name:'Ride',note:51,x:925,y:275,r:75}];
export function keyAt(p){
 if(p.x<40||p.x>984||p.y<170||p.y>555)return null;
 const step=944/14,whites=[0,2,4,5,7,9,11,12,14,16,17,19,21,23];
 if(p.y<390)for(let i=0;i<13;i++)if(whites[i+1]-whites[i]===2&&Math.abs(p.x-(40+(i+1)*step))<step*.30)return whites[i]+1;
 return whites[clamp(Math.floor((p.x-40)/step),0,13)];
}
export class MusicStudio{
 constructor({requestCamera,onToggle,notify}){
  Object.assign(this,{requestCamera,onToggle,notify});this.opened=false;this.audio=new MusicAudio();this.program=24;this.layout='strings';this.slots=new HandSlots();this.hands=new Map();this.flashes=new Map();this.lastHits=new Map();this.points=[];this.lastFrame=0;this.motion=new HandMotion();this.frontKeyboard=new FrontKeyboard(keyAt,key=>this.hit(60+key,'key'+key));this.drumStrokes=new DrumStrokes(PADS,(pad,velocity)=>this.hit(pad.note,'pad'+pad.note,velocity,true));this.stringNotes=new Map();this.stringBoard=new StringBoard((note,row,velocity)=>this.playString(note,row,velocity));
  this.panel=document.createElement('section');this.panel.id='music-studio';this.panel.hidden=true;
  this.panel.innerHTML=`<div class="music-heading"><div><small>JARVIS / SOUND LAB</small><h2>Estúdio de Música</h2></div><div><button id="music-expand">Ampliar</button><button id="music-close">Voltar ao 3D</button></div></div>
   <div class="music-tools"><select id="music-instrument" aria-label="Instrumento"></select><button id="music-enable">Ativar som</button><button id="music-camera">Usar mãos</button><button id="music-stop">Parar som</button><label>Volume <input id="music-volume" type="range" min="0" max="100" value="55"></label></div>
   <div class="music-tools"><label>Visual <select id="music-layout"><option value="strings">Cordas</option><option value="keys">Teclas / notas</option><option value="drums">Bateria</option></select></label><label id="music-chord-row">Acorde <select id="music-chord"></select></label><label>Oitava <select id="music-octave"><option value="-12">−1</option><option value="0" selected>Normal</option><option value="12">+1</option></select></label><label id="music-key-mode-row">Teclado <select id="music-key-mode"><option value="front">Frontal: pinça para tocar</option><option value="touch">Indicador: toque direto</option></select></label><label id="music-string-mode-row">Cordas <select id="music-string-mode"><option value="direct">Toque direto nas notas</option><option value="pick">2 mãos: casas + dedilhado</option></select></label><span id="music-note">Pronto para tocar</span></div>
   <div class="music-work"><canvas id="music-canvas" width="1024" height="620" aria-label="Instrumento interativo"></canvas><aside id="music-preview"><p>Use as mãos ou toque com o mouse.</p></aside></div>
   <div id="music-status" role="status">Ative o som uma vez para carregar os instrumentos locais.</div><p id="music-hint"></p><small class="music-credit">128 timbres General MIDI + bateria · amostras GeneralUser GS / S. Christian Collins · motor SpessaSynth · sem API para tocar</small>`;
  document.body.append(this.panel);this.canvas=this.$('canvas');this.ctx=this.canvas.getContext('2d');this.camera=document.getElementById('camera-panel');this.cameraParent=this.camera.parentNode;this.cameraNext=this.camera.nextSibling;
  for(let i=0;i<16;i++){const group=document.createElement('optgroup');group.label=FAMILIES[i];for(const row of INSTRUMENTS.slice(i*8,i*8+8)){const o=new Option(`${row.program+1}. ${{0:'Piano de cauda',24:'Violão nylon',25:'Violão aço',26:'Guitarra jazz',27:'Guitarra limpa',29:'Guitarra overdrive',30:'Guitarra distorcida',32:'Baixo acústico',33:'Baixo elétrico',40:'Violino',42:'Violoncelo',46:'Harpa',73:'Flauta',105:'Banjo'}[row.program]||row.name}`,row.program);group.append(o);}this.$('instrument').append(group);}this.$('instrument').add(new Option('Bateria / percussão','drums'));this.$('instrument').value='24';
  for(const name of Object.keys(CHORDS))this.$('chord').add(new Option(name,name));
  this.$('key-mode').onchange=()=>{this.cameraStopped();this.updateHint();};this.$('expand').onclick=()=>document.getElementById('expand-button').click();this.$('string-mode').onchange=()=>{this.cameraStopped();this.updateHint();};
  this.$('close').onclick=()=>this.toggle(false);this.$('enable').onclick=()=>this.enable();this.$('camera').onclick=()=>{this.enable();requestCamera();};this.$('stop').onclick=()=>this.cameraStopped();
  this.$('volume').oninput=()=>this.audio.setVolume(Number(this.$('volume').value)/100);
  this.$('instrument').onchange=()=>{const value=this.$('instrument').value;this.audio.stopNotes();if(value==='drums')this.layout='drums';else{this.program=Number(value);this.audio.select(this.program);this.layout=this.program>=24&&this.program<=39?'strings':'keys';}this.updateLayout();};
  this.$('layout').onchange=()=>{this.audio.stopNotes();this.layout=this.$('layout').value;this.updateLayout();};this.$('chord').onchange=this.$('octave').onchange=()=>{this.audio.stopNotes();this.updateLayout();};
  const pointer=e=>{const r=this.canvas.getBoundingClientRect();return {x:(e.clientX-r.left)*1024/r.width,y:(e.clientY-r.top)*620/r.height};};
  this.canvas.onpointerdown=e=>{if(e.button!==0)return;this.canvas.setPointerCapture(e.pointerId);this.mouse=e.pointerId;this.touch('mouse',pointer(e),performance.now());};this.canvas.onpointermove=e=>{if(e.pointerId===this.mouse)this.touch('mouse',pointer(e),performance.now());};this.canvas.onpointerup=this.canvas.onpointercancel=()=>{this.mouse=null;this.hands.delete('mouse');this.stringBoard.release('mouse');};
  this.keyHandler=e=>{if(!this.opened||e.repeat||e.ctrlKey||e.altKey||e.target.closest?.('input,select,textarea'))return;const i='asdfghjkl'.indexOf(e.key.toLowerCase());if(i<0)return;e.preventDefault();if(this.layout==='drums'){const pad=PADS[i%PADS.length];this.hit(pad.note,'pad'+pad.note,100,true);}else if(this.layout==='strings')this.playString(this.notes()[i%this.notes().length],i%this.notes().length);else this.hit(60+[0,2,4,5,7,9,11,12,14][i],'key'+[0,2,4,5,7,9,11,12,14][i]);};document.addEventListener('keydown',this.keyHandler);
  this.drawLoop=now=>{if(this.disposed)return;this.frame=requestAnimationFrame(this.drawLoop);if(!this.opened||document.hidden||now-this.lastFrame<16)return;this.lastFrame=now;for(const [id,h] of this.hands)if(now-h.at>220)this.hands.delete(id);this.draw(now);};this.frame=requestAnimationFrame(this.drawLoop);this.updateLayout();
 }
 $(id){return document.getElementById('music-'+id);}
 notes(){return this.stringBoard.notes();}
 updateHint(){this.$('hint').textContent=this.layout==='strings'?(this.$('string-mode').value==='direct'?'Use as pontas dos dedos nas notas do braço: cada dedo toca uma casa. ':'Uma mão escolhe as casas no braço; os dedos da outra cruzam as cordas no corpo para tocar. ')+'Polegar, indicador, médio, anelar e mindinho são rastreados separados. Feche a mão para reposicionar. Use Ampliar para ver as notas melhor.':this.layout==='drums'?'Baquetas seguem as mãos: desça a mão sobre o tambor para bater; levante para preparar o próximo golpe. Cada mão é independente. Descer mais rápido toca mais forte.':(this.$('key-mode').value==='front'?'De frente para a câmera: mire a tecla com o indicador, junte polegar e indicador para tocar e solte para repetir. Abra a pinça antes do primeiro toque. Duas mãos independentes.':'Indicador: toque nas teclas / notas. Mude de tecla ou retire o dedo para repetir.');this.$('hint').textContent+=' Mouse também funciona. A S D F G H J K L tocam notas.';}
 updateLayout(){this.$('layout').value=this.layout;this.hands.clear();this.lastHits.clear();this.frontKeyboard.reset();this.motion.reset();this.drumStrokes.reset();this.stringNotes.clear();this.points=[];
  const bass=this.program>=32&&this.program<=39,tuning=bass?[43,38,33,28]:[64,59,55,50,45,40],preset=bass?tuning:[...(CHORDS[this.$('chord').value]||CHORDS.Livre)].reverse();this.stringBoard.configure(tuning,preset);
  this.$('key-mode-row').hidden=this.layout!=='keys';this.$('chord-row').hidden=this.layout!=='strings'||bass;this.$('string-mode-row').hidden=this.layout!=='strings';this.updateHint();this.draw(performance.now());}
 playString(note,row,velocity=92){
  if(performance.now()-(this.lastHits.get('string'+row)||-Infinity)<70)return false;
  const previous=this.stringNotes.get(row);if(previous!==undefined)this.audio.stopNote(previous);
  if(!this.hit(note,'string'+row,velocity))return false;
  const actual=note+Number(this.$('octave').value);this.stringNotes.set(row,actual);
  const fret=note-this.stringBoard.tuning[row];this.$('note').textContent=`${row+1}ª corda · ${fret?'casa '+fret:'solta'} · ${noteName(actual)}`;return true;
 }
 async enable(){this.$('enable').disabled=true;this.$('status').textContent='Carregando banco local de instrumentos…';try{await this.audio.start();if(!this.opened){await this.audio.pause();return;}if(this.audio.context.state!=='running')throw Error('Clique em Ativar som para liberar o áudio.');this.$('status').textContent='Som ativo · toque no instrumento';this.$('enable').textContent='Som ativo';}catch(e){this.$('status').textContent='Não foi possível ativar o som: '+e.message;}finally{this.$('enable').disabled=false;}}
 toggle(on=!this.opened){this.opened=on;this.panel.hidden=!on;this.onToggle(on);if(on)this.$('preview').append(this.camera);else{this.cameraParent.insertBefore(this.camera,this.cameraNext);this.audio.pause();this.$('enable').textContent='Ativar som';this.cameraStopped();}document.body.classList.toggle('music-open',on);}
 hit(note,key,velocity=92,drum=false){const now=performance.now();if(now-(this.lastHits.get(key)||-Infinity)<70)return false;
  const actual=clamp(note+(drum?0:Number(this.$('octave').value)),0,127),played=this.audio.play(actual,velocity,drum,this.layout==='strings'?1600:500);if(!played)return false;
  this.lastHits.set(key,now);this.flashes.set(key,now);this.$('note').textContent=drum?PADS.find(p=>p.note===note)?.name||'Percussão':noteName(actual);return true;
 }
 touch(id,p,now){
  const old=this.hands.get(id),previous=old&&now-old.at<220?old:null;this.hands.set(id,{p,at:now});
  if(previous&&Math.hypot(p.x-previous.p.x,p.y-previous.p.y)>230)return;
  if(this.layout==='strings'){
   if(id==='mouse'&&!this.stringBoard.tracks.has(id))this.stringBoard.update([{id,p,finger:'Mouse',short:'•'}],now-70,{direct:false});
   this.stringBoard.update([{id,p,finger:'Mouse',short:'•'}],now,{direct:this.$('string-mode').value==='direct'});
  }else if(this.layout==='drums'){
   const pad=padAt(p,PADS);if(pad&&old?.zone!==pad.note)this.hit(pad.note,'pad'+pad.note,100,true);this.hands.get(id).zone=pad?.note;
  }else{const key=keyAt(p);if(key!==null&&key!==old?.zone)this.hit(60+key,'key'+key);this.hands.get(id).zone=key;}
 }
 consumeHands(hands,labels=[],now=performance.now()){
  if(!this.opened)return false;const rows=this.slots.assign(hands,labels,now),seen=new Set();this.points=[];
  if(this.layout==='keys'&&this.$('key-mode').value==='front'){
   for(const row of rows){const p=mapHandPoint(row.hand[8]);p.y=p.y/768*620;const state=this.frontKeyboard.update(row.id,p,pinchRatio(row.hand),now);this.motion.push(row.id,p,now);this.points.push({id:row.id,p,draw:state.down,short:state.down?'♪':'I'});}
   this.frontKeyboard.expire(now);document.getElementById('gesture-label').textContent=`TECLADO FRONTAL · ${rows.length} mão(s) · mire / feche a pinça / solte`;return true;
  }
  if(this.layout==='drums'){
   for(const row of rows){const center=[0,5,9,13,17].reduce((p,i)=>({x:p.x+row.hand[i].x/5,y:p.y+row.hand[i].y/5}),{x:0,y:0}),p=mapHandPoint(center);p.y=p.y/768*620;this.drumStrokes.update(row.id,p,now);}
   this.drumStrokes.expire(now);document.getElementById('gesture-label').textContent=`BATERIA · ${rows.length} mão(s) · desça para bater / levante para repetir`;return true;
  }
  if(this.layout==='strings'){
   const tips=[];for(const row of rows){const active=new Set();for(const finger of visibleFingers(row.hand)){
    const id=row.id+'-'+finger.tip,p=mapHandPoint(row.hand[finger.tip]);p.y=p.y/768*620;active.add(id);tips.push({id,p,finger:finger.name,short:finger.short,draw:true});
   }for(const id of this.stringBoard.tracks.keys())if(id.startsWith(row.id+'-')&&!active.has(id))this.stringBoard.release(id);}
   const result=this.stringBoard.update(tips,now,{direct:this.$('string-mode').value==='direct'});this.points=result.pointers;for(const point of this.points)this.motion.push(point.id,point.p,now);
   document.getElementById('gesture-label').textContent=`CORDAS · ${rows.length} mão(s) · ${tips.length} dedo(s) · ${result.contacts.length} casa(s)`;return true;
  }
  for(const r of rows){seen.add(r.id);const h=r.hand,pose=handGesture(h).pose,p=mapHandPoint(h[8]);p.y=p.y/768*620;this.points.push({id:r.id,p,draw:pose==='draw'});this.motion.push(r.id,p,now);
   if(pose==='draw')this.touch(r.id,p,now);else this.hands.delete(r.id);
  }for(const id of this.hands.keys())if(id!=='mouse'&&!seen.has(id))this.hands.delete(id);
  document.getElementById('gesture-label').textContent='MÚSICA · '+(rows.length?'indicador toca / mão aberta reposiciona':'mostre as mãos');return true;
 }
 cameraStopped(){this.hands.clear();this.points=[];this.frontKeyboard.reset();this.motion.reset();this.drumStrokes.reset();this.stringBoard.reset();this.stringNotes.clear();this.audio.stopNotes();}
 draw(now){
  const c=this.ctx,lit=key=>now-(this.flashes.get(key)||-Infinity)<180;c.clearRect(0,0,1024,620);const bg=c.createLinearGradient(0,0,1024,620);bg.addColorStop(0,'#132d3b');bg.addColorStop(1,'#060e18');c.fillStyle=bg;c.fillRect(0,0,1024,620);c.textAlign='center';c.font='22px Segoe UI';
  if(this.layout==='strings'){
   this.stringBoard.expire(now);drawStringBoard(c,this.stringBoard,now,{program:this.program,lit,octave:Number(this.$('octave').value)});
  }else if(this.layout==='drums'){
   for(const p of PADS){const active=lit('pad'+p.note),cymbal=[42,49,51].includes(p.note);c.fillStyle=active?'#63e4eb':cymbal?'#ae8b4e':'#d4dce4';c.strokeStyle=active?'#e0ffff':'#426477';c.lineWidth=8;c.beginPath();c.ellipse(p.x,p.y,p.r,p.r*.75,0,0,Math.PI*2);c.fill();c.stroke();c.fillStyle='#183040';c.fillText(p.name,p.x,p.y+6);}
  }else{
   this.frontKeyboard.expire(now);const hover=key=>this.$('key-mode').value==='front'&&[...this.frontKeyboard.hands.values()].some(h=>h.key===key);
   const whites=[0,2,4,5,7,9,11,12,14,16,17,19,21,23],w=944/14;c.font='16px Segoe UI';
   for(let i=0;i<14;i++){c.fillStyle=lit('key'+whites[i])?'#72e4e9':hover(whites[i])?'#f5d38c':'#eaf0f4';c.fillRect(40+i*w,170,w-2,385);c.fillStyle='#324858';c.fillText(['Dó','Ré','Mi','Fá','Sol','Lá','Si'][i%7],40+i*w+w/2,530);}
   for(let i=0;i<13;i++)if(whites[i+1]-whites[i]===2){c.fillStyle=lit('key'+(whites[i]+1))?'#2ebbd3':hover(whites[i]+1)?'#ad873b':'#10202c';c.fillRect(40+(i+1)*w-w*.3,170,w*.6,220);}
  }
  if(this.layout==='drums')this.drumStrokes.draw(c,now);
  for(const point of this.points){const {draw,short}=point,p=this.motion.sample(point.id,now)||point.p;c.beginPath();c.arc(p.x,p.y,draw?15:12,0,Math.PI*2);c.fillStyle=draw?'#6ceeffaa':'#ffffff22';c.fill();c.lineWidth=3;c.strokeStyle=draw?'#d5ffff':'#8197b3';c.stroke();if(short){c.font='bold 15px Segoe UI';c.fillStyle='#fff';c.fillText(short,p.x,p.y+5);}}
 }
 dispose(){this.disposed=true;cancelAnimationFrame(this.frame);document.removeEventListener('keydown',this.keyHandler);this.audio.dispose();}
}
