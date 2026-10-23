import {HandMotion} from './hand-motion.js';
// A palm downstroke produces one hit; lifting rearms that hand independently.
export function padAt(p,pads){
 return pads.map(pad=>({pad,d:((p.x-pad.x)/pad.r)**2+((p.y-pad.y)/(pad.r*.75))**2})).filter(x=>x.d<=1).sort((a,b)=>a.d-b.d)[0]?.pad||null;
}
export class DrumStrokes{
 constructor(pads,onHit=()=>{}){this.pads=pads;this.onHit=onHit;this.reset();}
 reset(){this.hands=new Map();this.motion=new HandMotion();}
 update(id,p,now){
  if(!p||!Number.isFinite(p.x)||!Number.isFinite(p.y))return null;this.motion.push(id,p,now);
  let old=this.hands.get(id),gap=!old||now-old.at>280,jump=old&&Math.hypot(p.x-old.p.x,p.y-old.p.y)>200;
  if(gap||jump){this.hands.set(id,{p:{...p},at:now,peak:p.y,low:p.y,armed:!jump,trail:[{...p}]});return null;}
  const dt=Math.max(1,now-old.at),a=1-Math.exp(-dt/32),q={x:old.p.x+(p.x-old.p.x)*a,y:old.p.y+(p.y-old.p.y)*a};
  const velocity=(q.y-old.p.y)*1000/dt,state={...old,p:q,at:now,trail:[...old.trail,q].slice(-4)};
  let hit=null;
  if(!state.armed){state.low=Math.max(state.low,q.y);if(state.low-q.y>=24&&velocity<-20){state.armed=true;state.peak=q.y;}}
  else{
   state.peak=Math.min(state.peak,q.y);
   const pad=padAt(q,this.pads);
   if(pad&&q.y-state.peak>=22&&velocity>=100){
    hit={pad,velocity:Math.max(45,Math.min(115,Math.round(45+velocity*.085)))};
    this.onHit(pad,hit.velocity);state.armed=false;state.low=q.y;
   }
  }
  this.hands.set(id,state);return hit;
 }
 expire(now){for(const [id,h] of this.hands)if(now-h.at>280)this.hands.delete(id);}
 draw(c,now){
  this.expire(now);for(const [id,h] of this.hands){
   const p=this.motion.sample(id,now)||h.p;
   c.strokeStyle='#70e2eb55';c.lineWidth=3;c.beginPath();h.trail.forEach((p,i)=>i?c.lineTo(p.x,p.y):c.moveTo(p.x,p.y));c.stroke();
   c.strokeStyle='#e6c8a3';c.lineWidth=7;c.lineCap='round';c.beginPath();c.moveTo(p.x-26,p.y-66);c.lineTo(p.x,p.y);c.stroke();c.lineCap='butt';
   c.fillStyle=h.armed?'#9bfcf5':'#ffc47c';c.beginPath();c.arc(p.x,p.y,10,0,Math.PI*2);c.fill();
  }
 }
}
