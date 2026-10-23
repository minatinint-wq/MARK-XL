// Visual interpolation only. Predictions never enter musical hit testing.
export class HandMotion{
 constructor(){this.points=new Map();}
 reset(){this.points.clear();}
 push(id,p,now){
  const old=this.points.get(id),gap=!old||now-old.at>260||Math.hypot(p.x-old.target.x,p.y-old.target.y)>180;
  const dt=old?Math.max(20,now-old.at):50;
  this.points.set(id,{target:{...p},display:gap?{...p}:old.display,at:now,drawAt:gap?now:old.drawAt,vx:gap?0:(p.x-old.target.x)/dt,vy:gap?0:(p.y-old.target.y)/dt});
 }
 sample(id,now){
  const s=this.points.get(id);if(!s||now-s.at>260){this.points.delete(id);return null;}
  const age=now-s.at,lead=Math.min(35,Math.max(0,age)),clamp=v=>Math.max(-8,Math.min(8,v));
  const target={x:s.target.x+clamp(s.vx*lead),y:s.target.y+clamp(s.vy*lead)},a=1-Math.exp(-Math.max(0,now-s.drawAt)/28);s.drawAt=now;
  s.display.x+=(target.x-s.display.x)*a;s.display.y+=(target.y-s.display.y)*a;
  return {...s.display,opacity:age<160?1:Math.max(0,(260-age)/100)};
 }
}
