const dist=(a,b)=>Math.hypot((a.x-b.x)*4/3,a.y-b.y,((a.z||0)-(b.z||0))*.6);
export function pinchRatio(hand){if(!hand||hand.length<21)return Infinity;return dist(hand[4],hand[8])/Math.max(.025,dist(hand[0],hand[9]),dist(hand[5],hand[17]));}
export class FrontKeyboard{
 constructor(keyAt,onPress=()=>{}){this.keyAt=keyAt;this.onPress=onPress;this.reset();}
 reset(){this.hands=new Map();}
 update(id,p,ratio,now){
  let old=this.hands.get(id);if(old&&now-old.at>260)old=null;
  const s=old?{...old}:{armed:false,down:false,key:null,p:{...p}},moving=!old||Math.hypot(p.x-old.p.x,p.y-old.p.y)>180;
  if(moving){s.armed=false;s.down=false;s.key=null;s.closeAt=null;}
  s.p={...p};s.at=now;s.ratio=ratio;
  if(ratio>.48){s.armed=true;s.down=false;s.closeAt=null;s.key=this.keyAt(p);}
  else if(ratio<.30&&s.armed){
   if(s.closeAt==null)s.closeAt=now;
   if(now-s.closeAt>=35){if(s.key!==null)this.onPress(s.key);s.armed=false;s.down=true;}
  }else if(ratio>=.30)s.closeAt=null;
  this.hands.set(id,s);return s;
 }
 expire(now){for(const [id,h] of this.hands)if(now-h.at>260)this.hands.delete(id);}
}
