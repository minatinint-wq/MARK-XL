const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const dist=(a,b)=>Math.hypot((a.x-b.x)*4/3,a.y-b.y);
const dead=(v,band)=>Math.abs(v)<=band?0:v-Math.sign(v)*band;
const lineDelta=a=>Math.atan2(Math.sin(a*2),Math.cos(a*2))/2;
const defaultPose=()=>({x:0,y:0,rx:0,ry:0,rz:0,scale:1});
const copyPose=p=>Object.fromEntries(Object.entries(defaultPose()).map(([k,v])=>[k,Number.isFinite(p?.[k])?p[k]:v]));
const validHand=h=>Array.isArray(h)&&h.length>=21&&h.slice(0,21).every(p=>p&&Number.isFinite(p.x)&&Number.isFinite(p.y));
function describeHand(h){
 const palm=[0,5,9,13,17].reduce((c,i)=>({x:c.x+h[i].x/5,y:c.y+h[i].y/5}),{x:0,y:0});
 const size=Math.max(.025,dist(h[0],h[9]));
 const curled=[8,12,16,20].map((tip,i)=>dist(h[tip],h[0])<dist(h[[6,10,14,18][i]],h[0])*1.1);
 const fist=curled[0]&&curled.filter(Boolean).length>=3;
 return {x:1-palm.x,y:palm.y,fist,pinch:dist(h[4],h[8])/size};
}
export function classifyHands(hands){
 const valid=(Array.isArray(hands)?hands:[]).filter(validHand).slice(0,2);
 if(!valid.length)return {kind:'none',count:0};
 const descriptions=valid.map(describeHand);
 if(descriptions.length===2){
  const [a,b]=descriptions;const distance=dist(a,b);
  if(distance<.085)return {kind:'close',count:2};
  return {kind:a.fist&&b.fist?'two-rotate':'two-hand',count:2,x:(a.x+b.x)/2,y:(a.y+b.y)/2,distance,angle:Math.atan2(b.y-a.y,(b.x-a.x)*4/3)};
 }
 const h=descriptions[0];return {...h,count:1,kind:h.fist?'rotate':h.pinch<.35?'move':'release'};
}
export class HandPoseTracker{
 constructor(getPose=defaultPose){this.getPose=getPose;this.reset();}
 reset(){this.anchor=null;this.pending=null;this.pose=copyPose(this.getPose());this.lastTime=0;}
 update(hands,now=performance.now()){
  const g=classifyHands(hands);
  if(['none','release','close'].includes(g.kind)){
   this.anchor=null;this.pending=null;this.lastTime=now;return {...g,active:false};
  }
  if(this.lastTime&&now-this.lastTime>400){this.anchor=null;this.pending=null;}
  const dt=clamp(now-(this.lastTime||now-85),10,200);this.lastTime=now;
  if(!this.anchor||this.anchor.kind!==g.kind){
   this.anchor=null;
   this.pending=this.pending?.kind===g.kind?{kind:g.kind,frames:this.pending.frames+1}:{kind:g.kind,frames:1};
   if(this.pending.frames<2)return {...g,active:false,settling:true};
   this.pose=copyPose(this.getPose());this.anchor={...g,pose:{...this.pose}};this.filtered={...g};this.angle=g.angle||0;this.previousAngle=g.angle||0;
   return {...g,active:true,pose:{...this.pose}};
  }
  const a=this.anchor,alpha=1-Math.exp(-dt/95);
  for(const k of ['x','y','distance'])if(Number.isFinite(g[k]))this.filtered[k]+=(g[k]-this.filtered[k])*alpha;
  if(Number.isFinite(g.angle)){
   this.angle+=lineDelta(g.angle-this.previousAngle);this.previousAngle=g.angle;
   this.filtered.angle+=(this.angle-this.filtered.angle)*alpha;
  }
  const dx=dead(this.filtered.x-a.x,.008),dy=dead(this.filtered.y-a.y,.008);
  const pose={...a.pose};
  if(g.kind==='move'||g.kind==='two-hand'){
   pose.x=clamp(a.pose.x+dx*3.2,-1.6,1.6);pose.y=clamp(a.pose.y-dy*3.2,-1.4,1.4);
  }
  if(g.kind==='rotate'||g.kind==='two-rotate'){
   pose.ry=a.pose.ry+dx*4.6;pose.rx=a.pose.rx+clamp(dy*3.4,-1.4,1.4);
  }
  if(g.kind==='two-hand')pose.scale=clamp(a.pose.scale*Math.exp(dead(Math.log(this.filtered.distance/a.distance),.025)),.4,2.6);
  if(g.count===2)pose.rz=a.pose.rz-dead(this.filtered.angle-a.angle,.035);
  this.pose=pose;return {...g,active:true,pose:{...pose}};
 }
}
export class GestureController{
 constructor({video,canvas,label,onGesture,onError,onStatus,onRelease=()=>{},getPose=defaultPose,onHands=()=>false}){
  Object.assign(this,{video,canvas,label,onGesture,onError,onStatus,onRelease,getPose,onHands});
  this.running=false;this.starting=false;this.worker=null;this.stream=null;this.generation=0;this.busy=false;this.active=false;this.blockedUntil=0;this.lastStatus='';this.tracker=new HandPoseTracker(getPose);
 }
 reset(){this.tracker.reset();this.release();}
 release(){if(this.active){this.active=false;this.onRelease();}}
 suspend(ms=300){this.blockedUntil=performance.now()+ms;this.reset();}
 status(text){if(text!==this.lastStatus){this.lastStatus=text;this.onStatus(text);}}
 async start(){
  if(this.running||this.starting)return this.running;
  this.starting=true;this.reset();const gen=++this.generation;this.status('Carregando controle local');
  try{
   this.worker=new Worker('./hand-worker.js');
   await new Promise((resolve,reject)=>{
    this.rejectInit=reject;this.initTimer=setTimeout(()=>reject(new Error('Modelo de mãos não iniciou.')),22000);
    this.worker.onmessage=e=>{if(e.data.type==='ready'){clearTimeout(this.initTimer);resolve();}else if(e.data.type==='error'){clearTimeout(this.initTimer);reject(new Error(e.data.message));}};
    this.worker.onerror=()=>{clearTimeout(this.initTimer);reject(new Error('Falha ao iniciar controle de mãos.'));};this.worker.postMessage({type:'init'});
   });
   this.rejectInit=null;if(gen!==this.generation)return false;
   const stream=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:640},height:{ideal:480},aspectRatio:{ideal:4/3},frameRate:{ideal:24,max:24}},audio:false});
   if(gen!==this.generation){stream.getTracks().forEach(t=>t.stop());return false;}
   this.stream=stream;this.video.srcObject=stream;await this.video.play();
   if(gen!==this.generation)return false;
   this.running=true;this.starting=false;this.lastVideoTime=-1;
   this.worker.onmessage=e=>{if(gen!==this.generation)return;this.busy=false;if(e.data.type==='landmarks')this.consume(e.data.hands,e.data.handedness);else if(e.data.type==='error')this.onError(e.data.message);};
   this.worker.onerror=()=>{if(gen===this.generation)this.onError('O controle de mãos foi interrompido.');};
   stream.getVideoTracks()[0].onended=()=>{if(this.running)this.onError('A câmera foi desconectada.');};
   this.timer=setInterval(()=>this.frame(),50);this.status('Mostre as duas mãos');return true;
  }catch(e){
   if(gen!==this.generation)return false;
   this.stop();this.onError(e.name==='NotAllowedError'?'A câmera não foi autorizada.':e.name==='NotReadableError'?'A câmera está sendo usada por outro aplicativo.':e.message||'Não foi possível abrir a câmera.');return false;
  }finally{if(gen===this.generation)this.starting=false;}
 }
 async frame(){
  if(!this.running||this.inferencePaused||this.busy||this.video.readyState<2)return;
  if(this.lastVideoTime===this.video.currentTime)return;this.lastVideoTime=this.video.currentTime;
  this.busy=true;const gen=this.generation;
  try{
   const bitmap=await createImageBitmap(this.video,{resizeWidth:640,resizeHeight:480,resizeQuality:'high'});
   if(!this.running||gen!==this.generation){bitmap.close();return;}
   try{this.worker.postMessage({type:'frame',bitmap,time:performance.now()},[bitmap]);}catch(e){bitmap.close();throw e;}
  }catch(e){if(gen===this.generation)this.busy=false;}
 }
 consume(hands,handedness=[]){
  if(!this.running)return;this.draw(hands);if(this.onHands(hands,handedness)){this.tracker.reset();this.active=false;return;}
  if(performance.now()<this.blockedUntil){this.tracker.reset();this.release();this.status('Comando em andamento · aguarde');return;}
  const g=this.tracker.update(hands);
  if(!g.active){this.release();this.status(g.settling?'Segure o gesto…':g.kind==='none'?'Mostre uma ou duas mãos':g.kind==='close'?'Separe um pouco as mãos':'Mão aberta · posição mantida');return;}
  this.active=true;
  this.status({'move':'Pinça · mover','rotate':'Punho · girar','two-hand':`2 mãos · zoom ${Math.round(g.pose.scale*100)}% / mover / inclinar`,'two-rotate':'2 punhos · girar / inclinar'}[g.kind]);
  this.onGesture(g.pose);
 }
 draw(hands){
  if(this.canvas.width!==480)this.canvas.width=480;if(this.canvas.height!==360)this.canvas.height=360;
  const c=this.canvas.getContext('2d');c.clearRect(0,0,480,360);
  const valid=(Array.isArray(hands)?hands:[]).filter(validHand).slice(0,2);
  if(valid.length===2){c.strokeStyle='#f7cf73';c.lineWidth=1;c.setLineDash([5,5]);c.beginPath();c.moveTo(valid[0][9].x*480,valid[0][9].y*360);c.lineTo(valid[1][9].x*480,valid[1][9].y*360);c.stroke();c.setLineDash([]);}
  valid.forEach((h,index)=>{
   c.strokeStyle=index?'#ffca75':'#7ce6ff';c.fillStyle=index?'#ffe6b4':'#c9fbff';c.lineWidth=2;
   for(const path of [[0,1,2,3,4],[0,5,6,7,8],[5,9,10,11,12],[9,13,14,15,16],[13,17,18,19,20],[0,17]]){c.beginPath();path.forEach((idx,j)=>{const p=h[idx];j?c.lineTo(p.x*480,p.y*360):c.moveTo(p.x*480,p.y*360);});c.stroke();}
   for(const p of h){c.beginPath();c.arc(p.x*480,p.y*360,2,0,Math.PI*2);c.fill();}
  });
 }
 stop(){
  this.generation++;clearTimeout(this.initTimer);const reject=this.rejectInit;this.rejectInit=null;reject?.(new Error('Controle cancelado'));
  this.running=false;this.starting=false;this.busy=false;clearInterval(this.timer);this.timer=null;
  this.worker?.terminate();this.worker=null;this.stream?.getTracks().forEach(t=>{t.onended=null;t.stop();});this.stream=null;this.video.srcObject=null;this.reset();
 }
}
