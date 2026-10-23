import {ObjectEditor} from './object-editor.js';
import {SquareGesture} from './square-gesture.js';
import {StableHand,HAND_LOSS_GRACE} from './stable-hand.js';
import {HandSlots,sketchHandPose,mapHandPoint} from './hand-input.js';
export {sketchHandPose};
const distance=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y);
const point=(x,y)=>({x:Math.max(0,Math.min(1024,x)),y:Math.max(0,Math.min(768,y))});
export function snapStroke(points,color='#172a3a',width=5,enabled=true){
 const raw={type:'stroke',points:points.map(p=>({...p})),color,width};if(!enabled||points.length<8)return raw;
 const xs=points.map(p=>p.x),ys=points.map(p=>p.y),x=Math.min(...xs),y=Math.min(...ys),w=Math.max(...xs)-x,h=Math.max(...ys)-y;
 const closed=Math.min(w,h)>25&&distance(points[0],points.at(-1))<Math.min(w,h)*.18;
 if(closed){
  const edges=points.map(p=>Math.min(p.x-x,x+w-p.x,p.y-y,y+h-p.y)/Math.min(w,h));
  const corners=[{x,y},{x:x+w,y},{x:x+w,y:y+h},{x,y:y+h}];
  if(edges.filter(e=>e<.11).length/edges.length>.86&&corners.every(c=>points.some(p=>distance(c,p)<Math.min(w,h)*.2))){
   const square=Math.abs(w/h-1)<.18,s=square?(w+h)/2:0;
   return {type:'rectangle',points:[{x:x+(w-(s||w))/2,y:y+(h-(s||h))/2},{x:x+(w+(s||w))/2,y:y+(h+(s||h))/2}],color,width};
  }
  const radial=points.map(p=>Math.abs(Math.hypot((p.x-x-w/2)/(w/2),(p.y-y-h/2)/(h/2))-1));
  if(radial.reduce((a,b)=>a+b,0)/radial.length<.13)return {type:'ellipse',points:[{x,y},{x:x+w,y:y+h}],color,width};
 }
 const a=points[0],b=points.at(-1),length=distance(a,b);
 if(length>45&&points.every(p=>Math.abs((b.x-a.x)*(a.y-p.y)-(a.x-p.x)*(b.y-a.y))/length<7))return {type:'line',points:[a,b],color,width};
 return raw;
}
export class Sketchbook{
 constructor({send,requestCamera,onToggle,notify}){
  Object.assign(this,{send,requestCamera,onToggle,notify});this.opened=false;this.shapes=[];this.redoStack=[];this.current=[];this.revision=0;this.request=0;this.callbacks=new Map();this.aiBusy=false;this.lastAnalysis=0;this.autoName=true;this.handDown=false;this.waitRelease=false;this.lastHand=0;this.hands=new Map();this.slots=new HandSlots();this.active=new Map();this.groupSerial=0;this.editor=new ObjectEditor(this);this.squareGesture=new SquareGesture();this.gestureShape=null;this.area={left:.2,top:.2,right:.8,bottom:.8};this.calibration=null;
  const panel=document.createElement('section');panel.id='sketchbook';panel.hidden=true;
  panel.innerHTML=`<div class="sketch-title"><div><b>SKETCHBOOK</b><small>Do gesto à imagem</small></div><button id="sketch-close">Voltar ao 3D</button></div>
  <div class="sketch-tools"><button id="sketch-camera">Usar mãos</button><input id="sketch-color" type="color" value="#172a3a" aria-label="Cor do pincel"><select id="sketch-width" aria-label="Espessura"><option value="5">Fino</option><option value="10">Médio</option><option value="20">Grosso</option></select><select id="sketch-eraser" aria-label="Tamanho da borracha"><option value="40">Borracha pequena</option><option value="64" selected>Borracha média</option><option value="96">Borracha grande</option></select><select id="sketch-tool" aria-label="Ferramenta do mouse"><option value="draw">Pincel</option><option value="move">Mover objetos</option></select><button id="sketch-duplicate" disabled>Duplicar</button><button id="sketch-delete" disabled>Excluir</button><button id="sketch-undo">Desfazer</button><button id="sketch-redo">Refazer</button><button id="sketch-reset">Resetar</button></div>
  <div class="sketch-reach"><label>Alcance <input id="sketch-reach" type="range" min="30" max="100" value="60" aria-label="Área da câmera usada para cobrir todo o desenho"><output id="sketch-reach-label">60% da câmera</output></label><button id="sketch-calibrate">Calibrar cantos</button><button id="sketch-cancel-calibration" hidden>Cancelar calibração</button></div><div class="sketch-options"><span class="sketch-stability">Webcam estabilizada · segure o punho para apagar</span><label><input id="sketch-snap" type="checkbox" checked>Ajustar formas</label><label><input id="sketch-ai" type="checkbox" checked>IA nas pausas</label></div>
  <div class="sketch-workspace"><div class="sketch-paper"><canvas id="sketch-canvas" width="1024" height="768" aria-label="Tela de desenho"></canvas><svg id="sketch-selection" viewBox="0 0 1024 768" aria-hidden="true"></svg><span id="sketch-cursor" hidden></span></div><aside id="sketch-camera-preview"><p>Ative “Usar mãos” para ver sua mão aqui.</p></aside></div>
  <div id="sketch-hint">Duas mãos independentes: indicador desenha · mão aberta reposiciona · punho fechado apaga · mindinho arrasta o objeto. Levante uma mão sem interromper a outra. 👉👈, afastando = quadrado · duas mãos em C, afastando = círculo · duas mãos em L (arma) = retângulo. Segure um instante; solte para fixar.</div>
  <div id="sketch-selection-status" role="status">Mindinho esticado: arrastar objeto · abra a mão para soltar.</div><div id="sketch-ai-status" role="status">A IA sugere o que você desenhou; você pode corrigir abaixo.</div>
  <input id="sketch-name" maxlength="100" placeholder="O que você desenhou? / Nome do modelo" aria-label="Objeto desenhado ou nome do modelo">
  <textarea id="sketch-prompt" maxlength="2500" rows="2" placeholder="Prompt opcional: estilo, cores, materiais, cenário…" aria-label="Complemento do prompt"></textarea>
  <div class="sketch-actions"><button id="sketch-save">Salvar modelo</button><button id="sketch-generate">Gerar imagem no Studio</button></div>
  <small class="sketch-note">IA: envia somente o desenho ao Gemini. Geração: usa sua cota ZeroGPU ao clicar.</small>
  <details id="sketch-library"><summary>Meus modelos salvos</summary><div id="sketch-models"></div></details>`;
  document.body.append(panel);this.panel=panel;this.cameraPanel=document.getElementById('camera-panel');this.cameraParent=this.cameraPanel.parentNode;this.cameraNext=this.cameraPanel.nextSibling;this.canvas=this.$('canvas');this.ctx=this.canvas.getContext('2d');
  this.$('close').onclick=()=>this.toggle(false);this.$('camera').onclick=()=>requestCamera();
  this.$('undo').onclick=()=>{this.finishEdits();this.editor.undo();};
  this.$('redo').onclick=()=>{this.finishEdits();this.editor.redo();};
  this.$('duplicate').onclick=()=>{this.finishEdits();this.editor.duplicate();};
  this.$('delete').onclick=()=>{this.finishEdits();this.editor.remove();};
  this.$('tool').onchange=()=>{this.finishEdits();this.canvas.style.cursor=this.$('tool').value==='move'?'grab':'crosshair';};
  this.$('reset').onclick=()=>this.reset();this.$('save').onclick=()=>this.save(false);this.$('generate').onclick=()=>this.save(true);
  this.$('reach').oninput=()=>{this.finish();this.pauseHands();this.calibration=null;this.$('cancel-calibration').hidden=true;const a=Number(this.$('reach').value)/100,m=(1-a)/2;this.area={left:m,top:m,right:1-m,bottom:1-m};this.$('reach-label').textContent=`${Math.round(a*100)}% da câmera`;this.$('hint').textContent='Área menor = menos movimento para alcançar todas as bordas. Abra a mão e volte a apontar.';};
  this.$('calibrate').onclick=()=>{this.finishEdits();this.calibration={step:0,points:[],hand:null};this.$('cancel-calibration').hidden=false;this.$('hint').textContent='1/2: aponte para o canto superior esquerdo do seu alcance confortável e segure por 1 segundo.';requestCamera();};
  this.$('cancel-calibration').onclick=()=>{this.calibration=null;this.$('cancel-calibration').hidden=true;this.pauseHands();this.$('hint').textContent='Calibração cancelada. Alcance anterior mantido.';};
  this.$('name').oninput=()=>{this.autoName=false;};this.$('prompt').oninput=()=>{this.revision++;clearTimeout(this.analysisTimer);this.scheduleAnalysis();};
  this.$('ai').onchange=()=>{this.revision++;clearTimeout(this.analysisTimer);if(this.$('ai').checked)this.scheduleAnalysis();else this.$('ai-status').textContent='Interpretação pausada. Seu desenho continua disponível.';};
  const position=e=>{const r=this.canvas.getBoundingClientRect();return point((e.clientX-r.left)/r.width*1024,(e.clientY-r.top)/r.height*768);};
  this.canvas.onpointerdown=e=>{if(e.button!==0)return;this.canvas.setPointerCapture(e.pointerId);this.pointer=e.pointerId;this.mouseMoving=this.$('tool').value==='move';if(this.mouseMoving)this.editor.begin('mouse',position(e));else this.begin(position(e));};
  this.canvas.onpointermove=e=>{const p=position(e);if(this.pointer===e.pointerId){if(this.mouseMoving)this.editor.move('mouse',p);else this.append(p);}else if(this.$('tool').value==='move')this.editor.hover('mouse',p);};
  this.canvas.onpointerup=this.canvas.onpointercancel=e=>{if(this.pointer===e.pointerId){this.pointer=null;this.editor.end('mouse',e.type==='pointercancel');this.finish();}};
  this.canvas.onpointerleave=()=>this.editor.hover('mouse',null);
  this.keyHandler=e=>{if(!this.opened||e.target.closest?.('input,textarea,select,[contenteditable="true"]'))return;
   if((e.ctrlKey||e.metaKey)&&['z','y'].includes(e.key.toLowerCase())){e.preventDefault();this.$(e.key.toLowerCase()==='y'||e.shiftKey?'redo':'undo').click();}
   else if(e.key==='Delete'){e.preventDefault();this.$('delete').click();}
   else if(e.key==='Escape'){e.preventDefault();this.editor.endAll(true);this.pauseHands();this.editor.selected=null;this.renderSelection();}
  };document.addEventListener('keydown',this.keyHandler);
  this.watch=setInterval(()=>{if(this.squareGesture.since!==null&&performance.now()-this.lastHand>HAND_LOSS_GRACE)this.endShapeGesture();for(const [id,h] of this.hands)if(performance.now()-h.last>HAND_LOSS_GRACE)this.missingHand(id,h,performance.now());},100);
  this.resizeObserver=new ResizeObserver(()=>{const paper=this.canvas.parentElement,w=Math.min(paper.clientWidth,paper.clientHeight*4/3);this.canvas.style.width=w+'px';this.canvas.style.height=(w*.75)+'px';this.renderSelection();});this.resizeObserver.observe(this.canvas.parentElement);
  this.render();
 }
 $(id){return document.getElementById('sketch-'+id);}
 toggle(on=!this.opened){this.finish();this.pauseHands();this.opened=on;this.panel.hidden=!on;this.onToggle(on);if(on)this.$('camera-preview').append(this.cameraPanel);else this.cameraParent.insertBefore(this.cameraPanel,this.cameraNext);document.body.classList.toggle('sketch-open',on);if(on){this.refreshLibrary();this.scheduleAnalysis();}else{this.calibration=null;this.$('cancel-calibration').hidden=true;clearTimeout(this.analysisTimer);this.$('cursor').hidden=true;for(const h of this.hands.values())h.cursor.hidden=true;}}
 reset(){this.editor.endAll();this.editor.reset();this.squareGesture.reset();this.gestureShape=null;this.calibration=null;this.$('cancel-calibration').hidden=true;this.active.clear();this.current=[];this.shapes=[];this.redoStack=[];this.pauseHands();this.autoName=true;this.$('name').value='';this.$('prompt').value='';this.changed();this.$('ai-status').textContent='Tela limpa. Abra as mãos para retomar.';}
 pauseHands(){this.editor.endAll();this.endShapeGesture();for(const h of this.hands.values())h.waitRelease=true;}
 begin(p){this.beginBrush('mouse',p,'draw');this.current=this.active.get('mouse').points;}
 append(p){this.appendBrush('mouse',p);}
 beginBrush(id,p,mode){
  clearTimeout(this.analysisTimer);this.finishBrush(id);
  const group='g'+(++this.groupSerial),brush={mode,points:[p],color:mode==='erase'?'#ffffff':this.$('color').value,width:Number(this.$(mode==='erase'?'eraser':'width').value),group,ops:[],start:this.shapes.length};
  this.active.set(id,brush);this.redoStack=[];this.addSegment(brush,[p]);this.revision++;this.render();
 }
 addSegment(brush,points){
  const last=this.shapes.at(-1);
  if(last&&last.group===brush.group&&last.type===(brush.mode==='erase'?'erase':'stroke'))last.points.push(...points.slice(1));
  else{const shape={type:brush.mode==='erase'?'erase':'stroke',points:points.map(p=>({...p})),color:brush.color,width:brush.width,group:brush.group};this.shapes.push(shape);brush.ops.push(shape);}
 }
 appendBrush(id,p){
  const brush=this.active.get(id);if(!brush)return;const prev=brush.points.at(-1);if(distance(prev,p)<2)return;
  if(brush.points.length>=4000||this.shapes.length>=4500){this.finishBrush(id);const h=this.hands.get(id);if(h)h.waitRelease=true;this.notify('Levante a mão para iniciar outro traço.');return;}
  brush.points.push(p);this.addSegment(brush,[prev,p]);this.revision++;this.render();
 }
 finishBrush(id,snap=true){
  const brush=this.active.get(id);if(!brush)return;this.active.delete(id);if(id==='mouse')this.current=[];
  // Closing a shape never stops a pointing hand. Snap only after this hand releases.
  const first=this.shapes.indexOf(brush.ops[0]);
  const interleavedErase=this.shapes.slice(Math.max(0,first)).some(o=>o.type==='erase'&&o.group!==brush.group);
  if(brush.mode==='draw'&&!interleavedErase&&first>=0){
   const shape={...snapStroke(brush.points,brush.color,brush.width,snap&&this.$('snap').checked),group:brush.group};
   this.shapes=this.shapes.filter(o=>o.group!==brush.group);this.shapes.splice(first,0,shape);
  }
  this.editor.recordAdd(brush.group);this.changed();
 }
 finish(){for(const id of [...this.active.keys()])this.finishBrush(id);}
 changed(){this.revision++;this.render();this.scheduleAnalysis();}
 render(){const c=this.ctx;c.fillStyle='#ffffff';c.fillRect(0,0,1024,768);
  const draw=s=>{const ps=s.points;if(!ps.length)return;c.strokeStyle=s.type==='erase'?'#ffffff':s.color;c.fillStyle=c.strokeStyle;c.lineWidth=s.width;c.lineCap='round';c.lineJoin='round';c.beginPath();
   if(s.type==='rectangle')c.rect(ps[0].x,ps[0].y,ps[1].x-ps[0].x,ps[1].y-ps[0].y);
   else if(s.type==='ellipse')c.ellipse((ps[0].x+ps[1].x)/2,(ps[0].y+ps[1].y)/2,Math.abs(ps[1].x-ps[0].x)/2,Math.abs(ps[1].y-ps[0].y)/2,0,0,Math.PI*2);
   else if(ps.length===1){c.arc(ps[0].x,ps[0].y,s.width/2,0,Math.PI*2);c.fill();return;}
   else{ps.forEach((p,i)=>i?c.lineTo(p.x,p.y):c.moveTo(p.x,p.y));if(s.type==='polygon')c.closePath();}c.stroke();};
  this.shapes.forEach(draw);
  this.$('undo').disabled=!this.editor.history.length&&!this.active.size&&!this.gestureShape&&!this.editor.busy;this.$('redo').disabled=!this.editor.future.length;this.renderSelection();
 }
 drawReach(){
  const canvas=document.getElementById('landmarks'),c=canvas.getContext('2d'),a=this.area;c.save();c.strokeStyle='#ffd270';c.lineWidth=2;c.setLineDash([5,4]);c.strokeRect((1-a.right)*canvas.width,a.top*canvas.height,(a.right-a.left)*canvas.width,(a.bottom-a.top)*canvas.height);c.restore();
 }
 calibrate(tracked,now){
  const cal=this.calibration;if(!cal)return false;
  const row=tracked.find(r=>!cal.hand||r.id===cal.hand)||((tracked.length===1)?tracked[0]:null);
  if(!row||sketchHandPose(row.hand)!=='draw'){cal.points=[];cal.since=now;return true;}
  cal.hand=row.id;const p={x:1-row.hand[8].x,y:row.hand[8].y};
  if(cal.step===1&&(p.x<cal.first.x+.15||p.y<cal.first.y+.12)){cal.points=[];cal.since=now;return true;}
  if(!cal.points.length||distance(p,cal.points[0])>.025){cal.points=[p];cal.since=now;return true;}
  cal.points.push(p);if(now-cal.since<1000)return true;
  if(cal.step===0){cal.first=p;cal.step=1;cal.points=[];this.$('hint').textContent='2/2: aponte para o canto inferior direito do seu alcance confortável e segure por 1 segundo.';}
  else{this.area={left:Math.max(0,cal.first.x),top:Math.max(0,cal.first.y),right:Math.min(1,p.x),bottom:Math.min(1,p.y)};this.calibration=null;this.$('cancel-calibration').hidden=true;this.$('reach-label').textContent='Personalizado';this.pauseHands();this.$('hint').textContent='Alcance calibrado para o quadro inteiro. Abra as mãos e volte a apontar.';}
  return true;
 }
 missingHand(id,state,now){
  state.cursor.dataset.mode='uncertain';
  if(state.tracker.lost(now)){this.editor.end(id);this.editor.hover(id,null);this.finishBrush(id,false);state.cursor.hidden=true;state.filtered=null;state.pose='position';state.waitRelease=false;}
  if(now-state.last>1600){state.cursor.remove();this.hands.delete(id);}
 }
 releaseHands(){this.editor.endAll();this.endShapeGesture();this.finish();for(const state of this.hands.values()){state.tracker.reset();state.cursor.hidden=true;state.filtered=null;state.pose='position';state.waitRelease=false;}}
 consumeHands(hands,labels=[],now=performance.now()){if(!this.opened)return false;this.lastHand=now;
  const tracked=this.slots.assign(hands,labels,now),seen=new Set(),states=[];this.drawReach();if(this.calibrate(tracked,now))return true;
  const square=this.squareGesture.update(tracked.map(row=>row.hand),now);
  if(square.ended)this.endShapeGesture();
  if(square.engaged){
   this.editor.endAll();this.finish();clearTimeout(this.analysisTimer);
   for(const state of this.hands.values()){state.tracker.reset();state.cursor.hidden=true;state.waitRelease=true;state.last=now;}
   if(square.insert&&this.shapes.length<4500){
    this.gestureShape={type:square.kind==='circle'?'ellipse':'rectangle',points:[],color:this.$('color').value,width:Number(this.$('width').value),group:'g'+(++this.groupSerial)};
    this.shapes.push(this.gestureShape);this.redoStack=[];
   }
   if(this.gestureShape&&square.center&&(square.insert||square.resize))this.resizeGesture(square);
   const name={square:'Quadrado',circle:'Círculo',rectangle:'Retângulo'}[square.kind]||'Forma';
   document.getElementById('gesture-label').textContent=square.latched?name+' criado · solte o gesto para fixar':name+' · segure'+(square.kind==='circle'?' e afaste as mãos':' por um instante');return true;
  }
  for(const row of tracked){
   const {id,hand:h}=row;seen.add(id);let state=this.hands.get(id);
   if(!state){const cursor=document.createElement('span');cursor.className='sketch-hand-cursor';cursor.textContent=id.replace('hand-','');this.canvas.parentElement.append(cursor);state={cursor,pose:'position',waitRelease:false,tracker:new StableHand()};this.hands.set(id,state);}
   state.last=now;const result=state.tracker.update(h,now),pose=result.pose;
   if(result.breakStroke||result.changed){
    this.finishBrush(id,!result.breakStroke);
    if(result.breakStroke&&this.editor.drags.has(id))state.waitRelease=true;
    this.editor.end(id);this.editor.hover(id,null);
   }
   state.pose=pose;
   if(result.point)state.filtered=mapHandPoint(result.point,this.area);
   const cursor=state.cursor;cursor.hidden=!state.filtered;cursor.dataset.mode=result.ink||result.move?pose:(result.settling||result.uncertain?'uncertain':pose);
   if(state.filtered){cursor.style.left=(this.canvas.offsetLeft+state.filtered.x/1024*this.canvas.clientWidth)+'px';cursor.style.top=(this.canvas.offsetTop+state.filtered.y/768*this.canvas.clientHeight)+'px';}
   cursor.style.setProperty('--eraser-size',(Number(this.$('eraser').value)/1024*this.canvas.clientWidth)+'px');
   states.push(`${cursor.textContent}: ${result.hint||(pose==='draw'?'pincel':pose==='erase'?'borracha':pose==='move'?'mover objeto':'reposicionar')}`);
   if(pose==='position'&&!result.settling&&!result.uncertain){this.finishBrush(id);state.waitRelease=false;}
   if(result.move&&state.filtered&&!state.waitRelease&&this.pointer==null){
    this.editor.hover(id,state.filtered);if(!this.editor.drags.has(id))this.editor.begin(id,state.filtered);this.editor.move(id,state.filtered);continue;
   }
   if(!result.ink||this.pointer!=null||state.waitRelease||!state.filtered)continue;
   if(this.active.has(id))this.appendBrush(id,{...state.filtered});else this.beginBrush(id,{...state.filtered},pose);
  }
  for(const [id,state] of this.hands)if(!seen.has(id))this.missingHand(id,state,now);
  this.handDown=this.active.size>0;document.getElementById('gesture-label').textContent=states.join(' · ')||(this.handDown?'Reconectando a mão · traço preservado':'Mostre uma ou duas mãos');return true;
 }
 finishEdits(){this.editor.endAll();this.endShapeGesture();this.finish();this.pauseHands();}
 renderSelection(){
  const svg=this.$('selection');if(!svg)return;svg.style.left=this.canvas.offsetLeft+'px';svg.style.top=this.canvas.offsetTop+'px';svg.style.width=this.canvas.clientWidth+'px';svg.style.height=this.canvas.clientHeight+'px';svg.replaceChildren();
  const elements=this.editor.selections();
  for(const {box,moving,selected} of elements){const rect=document.createElementNS('http://www.w3.org/2000/svg','rect');for(const [k,v] of Object.entries({x:box.left-6,y:box.top-6,width:box.right-box.left+12,height:box.bottom-box.top+12,rx:3,fill:'none',stroke:moving?'#e69b13':selected?'#9051db':'#2795b3','stroke-width':2,'stroke-dasharray':moving?'0':'7 5','vector-effect':'non-scaling-stroke'}))rect.setAttribute(k,v);svg.append(rect);}
  const selected=elements.find(e=>e.selected);this.$('duplicate').disabled=this.$('delete').disabled=!selected;
  this.$('selection-status').textContent=this.editor.busy?'Movendo objeto · abra a mão para soltar · Esc cancela':selected?`Objeto selecionado · ${Math.round(selected.box.right-selected.box.left)} × ${Math.round(selected.box.bottom-selected.box.top)} · Duplicar / Excluir / Desfazer`:'Mindinho esticado: arrastar objeto · abra a mão para soltar.';
 }
 endShapeGesture(){const changed=!!this.gestureShape;if(changed)this.editor.recordAdd(this.gestureShape.group);this.gestureShape=null;this.squareGesture.reset();if(changed)this.changed();}
 resizeGesture(g){
  const center=mapHandPoint(g.center,this.area),clamp=(v,a,b)=>Math.max(a,Math.min(b,v));let w=220,h=220;
  if(g.kind==='circle'||g.kind==='square')w=h=clamp(g.span/(this.area.right-this.area.left)*1024,96,680);
  if(g.kind==='rectangle'){w=clamp((g.bounds.right-g.bounds.left)/(this.area.right-this.area.left)*1024,100,950);h=clamp((g.bounds.bottom-g.bounds.top)/(this.area.bottom-this.area.top)*768,70,700);}
  const x=clamp(center.x-w/2,0,1024-w),y=clamp(center.y-h/2,0,768-h),target=[{x,y},{x:x+w,y:y+h}],old=this.gestureShape.points;
  this.gestureShape.points=old.length?target.map((p,i)=>({x:old[i].x+(p.x-old[i].x)*.3,y:old[i].y+(p.y-old[i].y)*.3})):target;
  this.revision++;this.render();
 }
 payload(){return {name:this.$('name').value||'Meu desenho',prompt:this.$('prompt').value,image:this.canvas.toDataURL('image/png'),document:{version:1,width:1024,height:768,shapes:this.shapes}};}
 call(action,payload){return new Promise((resolve,reject)=>{const id='sketch-'+(++this.request);const timer=setTimeout(()=>{this.callbacks.delete(id);reject(Error('O pedido demorou demais. Tente novamente.'));},38000);this.callbacks.set(id,{resolve,reject,timer});if(!this.send(id,action,JSON.stringify(payload))){clearTimeout(timer);this.callbacks.delete(id);reject(Error('Conexão com o Jarvis ainda não está pronta.'));}});}
 receive(result){const cb=this.callbacks.get(result.requestId);if(!cb)return;clearTimeout(cb.timer);this.callbacks.delete(result.requestId);result.ok?cb.resolve(result):cb.reject(Error(result.message||'Não foi possível concluir.'));}
 scheduleAnalysis(){clearTimeout(this.analysisTimer);if(!this.opened||this.squareGesture.latched||this.editor.busy||this.active.size||!this.shapes.length||!this.$('ai').checked)return;this.analysisTimer=setTimeout(()=>this.analyze(),Math.max(1300,5000-(performance.now()-this.lastAnalysis)));}
 async analyze(){if(this.aiBusy||this.squareGesture.latched||this.editor.busy||this.active.size||!this.opened||document.hidden||!this.$('ai').checked||!this.shapes.length)return;
  const revision=this.revision;this.aiBusy=true;this.lastAnalysis=performance.now();this.$('ai-status').textContent='IA observando seu desenho…';
  try{const result=await this.call('analyze',{image:this.canvas.toDataURL('image/png'),prompt:this.$('prompt').value});
   if(this.revision!==revision||!this.opened||!this.$('ai').checked)return;
   this.$('ai-status').textContent=`Parece: ${result.label} · confiança ${result.confidence}. ${result.description}`+(result.alternatives?.length?' Alternativas: '+result.alternatives.join(', ')+'.':'');
   if(this.autoName)this.$('name').value=result.label;
  }catch(e){if(this.revision===revision)this.$('ai-status').textContent=e.message+' Você pode nomear o desenho e gerar mesmo assim.';}
  finally{this.aiBusy=false;if(this.revision!==revision)this.scheduleAnalysis();}
 }
 async save(generate){this.endShapeGesture();this.finish();this.pauseHands();if(!this.shapes.length){this.notify('Desenhe algo primeiro.');return;}if(this.saving)return;this.saving=true;this.$('save').disabled=true;this.$('generate').disabled=true;
  try{const result=await this.call(generate?'generate':'save',this.payload());this.notify(result.message||'Modelo salvo em PNG e formato editável.');await this.refreshLibrary();}
  catch(e){this.notify(e.message);}finally{this.saving=false;this.$('save').disabled=false;this.$('generate').disabled=false;}
 }
 async refreshLibrary(){try{const result=await this.call('list',{});const list=this.$('models');list.replaceChildren();if(!result.items.length){list.textContent='Seus desenhos salvos aparecem aqui.';return;}
  for(const row of result.items){const b=document.createElement('button');b.textContent=row.name;b.title=row.created_at;b.onclick=async()=>{try{const model=await this.call('load',{key:row.id});this.finish();this.pauseHands();this.editor.reset();this.shapes=model.document.shapes;this.groupSerial=Math.max(this.groupSerial,...this.shapes.map(s=>Number(String(s.group||'').slice(1))||0));for(const shape of this.shapes)if(!shape.group)shape.group='g'+(++this.groupSerial);this.current=[];this.redoStack=[];this.$('name').value=model.name;this.$('prompt').value=model.prompt;this.autoName=false;this.changed();}catch(e){this.notify(e.message);}};list.append(b);}
 }catch(e){this.$('models').textContent=e.message;}}
 dispose(){document.removeEventListener('keydown',this.keyHandler);this.editor.endAll();this.resizeObserver.disconnect();clearInterval(this.watch);clearTimeout(this.analysisTimer);for(const cb of this.callbacks.values())clearTimeout(cb.timer);this.callbacks.clear();}
}
