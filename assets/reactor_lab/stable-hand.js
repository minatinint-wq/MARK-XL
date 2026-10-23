import {handGesture} from './hand-input.js';
const distance=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y);
export const HAND_LOSS_GRACE=320;

// Time-based confirmation and adaptive smoothing; no synthetic motion during loss.
export class StableHand{
 constructor(){this.reset();}
 reset(){this.pose='position';this.candidate=null;this.lastSeen=null;this.lastInk=null;this.raw=null;this.filtered=null;this.jump=null;this.uncertainAt=null;}
 update(hand,now=performance.now()){
  const detection=handGesture(hand),wanted=detection.pose;
  const gap=this.lastSeen===null?0:now-this.lastSeen;this.lastSeen=now;
  let breakStroke=gap>HAND_LOSS_GRACE,changed=false;
  if(breakStroke){this.pose='position';this.candidate=null;this.raw=this.filtered=null;}
  if(wanted==='uncertain'){
   this.candidate=null;this.uncertainAt??=now;
   if(now-this.uncertainAt>HAND_LOSS_GRACE){changed=this.pose!=='position';this.pose='position';breakStroke=true;}
   return {pose:this.pose,ink:false,point:this.filtered,breakStroke,changed,uncertain:true,hint:detection.hint};
  }
  this.uncertainAt=null;
  if(wanted!==this.pose){
   if(this.candidate?.pose!==wanted)this.candidate={pose:wanted,since:now,frames:1};else this.candidate.frames++;
   const hold=wanted==='erase'?340:wanted==='draw'?100:wanted==='move'?160:75,minFrames=wanted==='erase'?3:2;
   if(now-this.candidate.since>=hold&&this.candidate.frames>=minFrames){
    this.pose=wanted;this.candidate=null;changed=true;this.raw=this.filtered=null;this.jump=null;
   }
  }else this.candidate=null;
  // Do not paint through a possible release or fist; retain the stroke for recovery.
  if(wanted!==this.pose)return {pose:this.pose,ink:false,point:this.filtered,changed,breakStroke,settling:true,hint:wanted==='erase'?'Segure o punho para apagar':'Confirmando gesto'};
  const p=hand[this.pose==='erase'?9:this.pose==='move'?20:8];
  const dt=this.raw?Math.max(16,Math.min(300,now-this.raw.at)):85;
  if(this.raw){
   const maxStep=gap>120?.075:Math.max(.065,dt*.0007);
   if(distance(p,this.raw)>maxStep){
    if(this.jump&&distance(p,this.jump)<.035&&now-this.jump.at<300){
     breakStroke=true;this.raw=this.filtered=null;this.jump=null;
    }else{this.jump={x:p.x,y:p.y,at:now};return {pose:this.pose,ink:false,point:this.filtered,breakStroke,changed,uncertain:true,hint:'Estabilizando a mão'};}
   }else this.jump=null;
  }
  if(!this.filtered)this.filtered={x:p.x,y:p.y};
  else{
   const delta=distance(p,this.filtered);
   if(delta>.0018){
    const speed=Math.min(1.5,delta/(dt/1000)),cutoff=1.1+speed*7;
    const alpha=1-Math.exp(-2*Math.PI*cutoff*dt/1000);
    this.filtered={x:this.filtered.x+(p.x-this.filtered.x)*alpha,y:this.filtered.y+(p.y-this.filtered.y)*alpha};
   }
  }
  this.raw={x:p.x,y:p.y,at:now};
  const ink=this.pose==='draw'||this.pose==='erase';if(ink)this.lastInk=now;
  return {pose:this.pose,ink,move:this.pose==='move',point:{...this.filtered},changed,breakStroke,hint:''};
 }
 lost(now=performance.now()){
  this.candidate=null;this.jump=null;
  if(this.lastSeen===null||now-this.lastSeen<=HAND_LOSS_GRACE)return false;
  this.reset();return true;
 }
}
