import {handGesture,validHand} from './hand-input.js';
const dist=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y);
const center=h=>({x:(h[0].x+h[9].x)/2,y:(h[0].y+h[9].y)/2});
const size=h=>Math.max(dist(h[0],h[9]),dist(h[5],h[17]));
export function gunHand(h){
 if(!validHand(h)||handGesture(h).pose!=='draw')return false;
 const s=size(h),tx=h[4].x-h[2].x,ty=h[4].y-h[2].y,ix=h[8].x-h[5].x,iy=h[8].y-h[5].y;
 return dist(h[4],h[9])>s*.9&&Math.hypot(tx,ty)>s*.55&&Math.abs(tx*ix+ty*iy)/Math.max(.0001,Math.hypot(tx,ty)*Math.hypot(ix,iy))<.65;
}
export function inwardPointers(hands,active=false){
 if(!Array.isArray(hands)||hands.length!==2||!hands.every(validHand))return false;
 const [a,b]=hands;if(hands.some(h=>handGesture(h).pose!=='draw'||gunHand(h)))return false;
 const c=hands.map(center),dx=c[1].x-c[0].x,dy=c[1].y-c[0].y,span=Math.hypot(dx,dy);
 if(span<.13||Math.abs(dy)>span*.6)return false;
 const facing=(h,sign)=>{const vx=h[8].x-h[5].x,vy=h[8].y-h[5].y;return (vx*dx+vy*dy)*sign/(Math.max(.001,Math.hypot(vx,vy))*span)>.78;};
 const gap=dist(a[8],b[8]);return facing(a,1)&&facing(b,-1)&&(active||gap<span*.75&&gap<.28);
}
export function curvedPair(hands){
 if(!Array.isArray(hands)||hands.length!==2||!hands.every(validHand))return false;
 const c=hands.map(center),dx=c[1].x-c[0].x,dy=c[1].y-c[0].y,span=Math.hypot(dx,dy);
 if(span<.09||Math.abs(dy)>span*.7)return false;
 return hands.every((h,i)=>{
  if(handGesture(h).pose!=='uncertain')return false;
  const s=size(h),gap=dist(h[4],h[8]),vx=h[8].x-c[i].x,vy=h[8].y-c[i].y;
  return s>=.045&&gap>s*.55&&gap<s*1.8&&[12,16,20].every(j=>dist(h[j],h[8])<s*.8)&&(vx*dx+vy*dy)*(i===0?1:-1)/Math.max(.0001,Math.hypot(vx,vy)*span)>.35;
 });
}
export function shapePose(hands){
 if(!Array.isArray(hands)||hands.length!==2)return null;
 if(hands.every(gunHand))return 'rectangle';
 if(curvedPair(hands))return 'circle';
 if(inwardPointers(hands))return 'square';return null;
}
// One shape per held two-hand gesture. Brief tracking gaps never duplicate it.
export class SquareGesture{
 constructor(){this.reset();}
 reset(){this.since=null;this.frames=0;this.latched=false;this.releasedAt=null;this.kind=null;this.initialSpan=0;}
 update(hands,now=performance.now()){
  const kind=this.latched&&this.kind==='square'&&inwardPointers(hands,true)?'square':shapePose(hands);
  if(!kind||this.kind&&kind!==this.kind){
   if(this.since===null)return {engaged:false,insert:false};
   this.releasedAt??=now;
   if(now-this.releasedAt>420){const ended=this.latched;this.reset();return {engaged:false,insert:false,ended};}
   return {engaged:true,insert:false,latched:this.latched,kind:this.kind};
  }
  const c=hands.map(center),span=dist(c[0],c[1]);
  if(this.since===null){this.since=now;this.initialSpan=span;this.kind=kind;}
  this.releasedAt=null;this.frames++;
  const insert=!this.latched&&now-this.since>=600&&this.frames>=4&&(kind!=='circle'||span>this.initialSpan*1.16);
  if(insert)this.latched=true;
  const points=hands.flatMap(h=>[h[4],h[8],h[9]]);
  return {engaged:true,insert,kind,latched:this.latched,resize:this.latched,span,
   center:{x:(c[0].x+c[1].x)/2,y:(c[0].y+c[1].y)/2},
   bounds:{left:Math.min(...points.map(p=>p.x)),right:Math.max(...points.map(p=>p.x)),top:Math.min(...points.map(p=>p.y)),bottom:Math.max(...points.map(p=>p.y))}};
 }
}
