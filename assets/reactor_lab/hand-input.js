const dist=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y);
export const validHand=h=>Array.isArray(h)&&h.length>=21&&h.slice(0,21).every(p=>p&&Number.isFinite(p.x)&&Number.isFinite(p.y));
function fingerState(h,b){
 const base=h[b],pip=h[b+1],tip=h[b+3];
 const ax=base.x-pip.x,ay=base.y-pip.y,bx=tip.x-pip.x,by=tip.y-pip.y;
 const lengths=Math.hypot(ax,ay)*Math.hypot(bx,by);
 if(lengths<.000015)return 'unknown';
 const cosine=(ax*bx+ay*by)/lengths;
 const reach=dist(tip,h[0])/Math.max(.008,dist(pip,h[0]));
 const stretch=dist(tip,base)/Math.max(.008,dist(pip,base));
 if(cosine<-.25&&reach>1.01&&stretch>1.28)return 'extended';
 if(cosine>.15&&reach<1.06)return 'folded';
 return 'unknown';
}
export function handGesture(h){
 if(!validHand(h))return {pose:'uncertain',hint:'Mostre a mão inteira'};
 const size=Math.max(dist(h[0],h[9]),dist(h[5],h[17]));
 if(size<.045)return {pose:'uncertain',hint:'Aproxime um pouco a mão da câmera'};
 if([0,5,9,13,17,8,20].some(i=>h[i].x<-.06||h[i].x>1.06||h[i].y<-.06||h[i].y>1.06))return {pose:'uncertain',hint:'Mantenha a mão dentro da câmera'};
 const fingers=[5,9,13,17].map(b=>fingerState(h,b));
 if(fingers.filter(f=>f==='extended').length>=3)return {pose:'position'};
 if(fingers[0]==='extended'&&fingers.slice(1).filter(f=>f==='folded').length>=2&&!fingers.slice(1).includes('extended'))return {pose:'draw'};
 if(fingers[3]==='extended'&&fingers.slice(0,3).every(f=>'folded'===f))return {pose:'move'};
 const thumbFolded=dist(h[4],h[9])<size*.65;
 if(fingers.every(f=>f==='folded')&&thumbFolded)return {pose:'erase'};
 return {pose:'uncertain',hint:'Mostre o indicador ou abra a mão'};
}
export function sketchHandPose(h){const pose=handGesture(h).pose;return pose==='uncertain'?'position':pose;}

// Track identities, not left-to-right order, so crossing hands cannot swap brushes.
export class HandSlots{
 constructor(){this.reset();}
 reset(){this.slots=[];this.serial=0;}
 assign(hands,labels=[],now=performance.now()){
  const observations=(hands||[]).map((h,i)=>({h,label:labels[i]?.[0]?.score>=.8?labels[i][0].categoryName:''})).filter(o=>validHand(o.h)).slice(0,2);
  this.slots=this.slots.filter(s=>now-s.last<950);
  const cost=(o,s)=>{
   const dt=Math.min(180,Math.max(0,now-s.last));
   const predicted={x:s.wrist.x+Math.max(-.09,Math.min(.09,(s.vx||0)*dt)),y:s.wrist.y+Math.max(-.09,Math.min(.09,(s.vy||0)*dt))};
   return dist(o.h[0],predicted)+(o.label&&s.label&&o.label!==s.label?.045:0);
  };
  let best={cost:Infinity,slots:[]};
  const assign=(i,chosen,used,total)=>{
   if(i===observations.length){if(total<best.cost)best={cost:total,slots:chosen};return;}
   for(const slot of this.slots)if(!used.has(slot)){
    const c=cost(observations[i],slot);if(c>.30)continue;
    assign(i+1,[...chosen,slot],new Set([...used,slot]),total+c);
   }
   assign(i+1,[...chosen,null],used,total+.31);
  };assign(0,[],new Set(),0);
  return observations.map((o,i)=>{
   let s=best.slots[i];if(!s){s={id:'hand-'+(++this.serial),last:now,wrist:o.h[0],label:o.label};this.slots.push(s);}
   const dt=Math.max(40,now-s.last);
   s.vx=(o.h[0].x-s.wrist.x)/dt;s.vy=(o.h[0].y-s.wrist.y)/dt;
   if(o.label&&o.label!==s.label){s.proposed=s.proposed===o.label?s.proposed:o.label;s.votes=(s.voteLabel===o.label?s.votes:0)+1;s.voteLabel=o.label;if(s.votes>=3){s.label=o.label;s.votes=0;}}
   else{s.votes=0;s.voteLabel='';}
   Object.assign(s,{wrist:{...o.h[0]},last:now});return {id:s.id,hand:o.h,label:s.label||''};
  });
 }
}

export function mapHandPoint(p,area={left:.2,top:.2,right:.8,bottom:.8}){
 return {x:Math.max(0,Math.min(1024,((1-p.x)-area.left)/(area.right-area.left)*1024)),y:Math.max(0,Math.min(768,(p.y-area.top)/(area.bottom-area.top)*768))};
}
