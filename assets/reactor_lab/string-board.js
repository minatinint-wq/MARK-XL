// Shared geometry for drawing and hit testing: each fret is one semitone.
export const NECK={left:92,right:604,top:190,bottom:425,frets:8,pluckLeft:640,pluckRight:958};
export const FINGERS=[{tip:4,pip:3,base:2,name:'Polegar',short:'P'},{tip:8,pip:6,base:5,name:'Indicador',short:'I'},{tip:12,pip:10,base:9,name:'Médio',short:'M'},{tip:16,pip:14,base:13,name:'Anelar',short:'A'},{tip:20,pip:18,base:17,name:'Mindinho',short:'m'}];
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v)),distance=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y);
export const noteName=n=>['Dó','Dó♯','Ré','Ré♯','Mi','Fá','Fá♯','Sol','Sol♯','Lá','Lá♯','Si'][((n%12)+12)%12]+(Math.floor(n/12)-1);
export function visibleFingers(hand){
 if(!hand||hand.length<21||hand.some(p=>!p||!Number.isFinite(p.x)||!Number.isFinite(p.y)))return [];
 const size=distance(hand[0],hand[9]);if(size<.045)return [];
 return FINGERS.filter(f=>{
  const reach=distance(hand[f.tip],hand[0])/Math.max(.008,distance(hand[f.pip],hand[0]));
  if(f.tip===4)return reach>1.03&&distance(hand[4],hand[5])>size*.42;
  return reach>1.02&&distance(hand[f.tip],hand[f.base])>distance(hand[f.pip],hand[f.base])*1.10;
 });
}

export class StringBoard{
 constructor(onNote=()=>{}){this.onNote=onNote;this.configure([64,59,55,50,45,40]);}
 configure(tuning,preset=tuning){this.tuning=[...tuning];this.preset=[...preset];this.reset();}
 reset(){this.tracks=new Map();this.contacts=new Map();this.pointers=[];}
 y(row){return NECK.top+row*(NECK.bottom-NECK.top)/(this.tuning.length-1);}
 cell(row,fret){return {x:NECK.left+(fret-.5)*(NECK.right-NECK.left)/NECK.frets,y:this.y(row)};}
 expire(now){for(const [id,t] of this.tracks)if(now-t.at>240)this.release(id);}
 release(id){this.tracks.delete(id);this.contacts.delete(id);}
 notes(){const notes=[...this.preset];for(let row=0;row<notes.length;row++){const held=[...this.contacts.values()].filter(c=>c.row===row);if(held.length)notes[row]=this.tuning[row]+Math.max(...held.map(c=>c.fret));}return notes;}
 update(points,now,{direct=true}={}){
  this.expire(now);const seen=new Set(),prepared=[];this.pointers=[];
  for(const point of points){
   const {id,p}=point;if(!p||!Number.isFinite(p.x)||!Number.isFinite(p.y))continue;seen.add(id);
   let old=this.tracks.get(id),jump=old&&distance(p,old.p)>175;
   if(jump){this.release(id);old=null;}
   const dt=old?now-old.at:0,alpha=old?1-Math.exp(-Math.max(1,dt)/38):1;
   const q={x:old?old.p.x+(p.x-old.p.x)*alpha:p.x,y:old?old.p.y+(p.y-old.p.y)*alpha:p.y};
   const t={...old,p:q,raw:{...p},at:now,frames:old?old.frames+1:1,latches:old?.latches||new Set()};
   this.tracks.set(id,t);this.pointers.push({...point,p:q});prepared.push({point,t,old});
  }
  // A lost hand holds its frets briefly, but cannot create notes from stale frames.
  // Update all fretting fingers before any picking finger, independent of hand order.
  const changed=[];
  for(const {point,t} of prepared){
   const {id}=point,p=t.p,previous=this.contacts.get(id),spacing=(NECK.bottom-NECK.top)/(this.tuning.length-1);
   if(p.x<NECK.left||p.x>NECK.right||p.y<NECK.top-spacing*.45||p.y>NECK.bottom+spacing*.45){this.contacts.delete(id);t.candidate=null;continue;}
   let row=clamp(Math.round((p.y-NECK.top)/spacing),0,this.tuning.length-1),fret=clamp(Math.floor((p.x-NECK.left)/(NECK.right-NECK.left)*NECK.frets)+1,1,NECK.frets);
   if(previous){
    if(Math.abs(p.y-this.y(previous.row))<spacing*.5+5)row=previous.row;
    const center=this.cell(row,previous.fret).x,half=(NECK.right-NECK.left)/NECK.frets/2;
    if(Math.abs(p.x-center)<half+6)fret=previous.fret;
   }
   const key=row+':'+fret;
   if(t.candidate!==key){t.candidate=key;t.since=now;}
   if(t.frames<2||now-t.since<55)continue;
   const contact={id,row,fret,finger:point.finger||'Dedo',short:point.short||'•',p};
   if(!previous||previous.row!==row||previous.fret!==fret)changed.push(contact);
   this.contacts.set(id,contact);
  }
  const notes=this.notes();
  if(direct){const rows=new Set(changed.map(c=>c.row));for(const row of rows)this.onNote(notes[row],row,88);}
  for(const {point,t,old} of prepared){
   const p=point.p;if(p.x<NECK.pluckLeft||p.x>NECK.pluckRight||t.frames<2){t.latches.clear();continue;}
   for(let row=0;row<this.tuning.length;row++){
    const y=this.y(row),near=Math.abs(p.y-y)<=11;
    if(Math.abs(p.y-y)>21)t.latches.delete(row);
    const cross=old&&old.raw.x>=NECK.pluckLeft&&old.raw.x<=NECK.pluckRight&&(p.y-y)*(old.raw.y-y)<0;
    if((near||cross)&&!t.latches.has(row)){this.onNote(notes[row],row,clamp(70+(old?Math.abs(p.y-old.raw.y)*.8:0),60,112));t.latches.add(row);}
   }
  }
  return {notes,contacts:[...this.contacts.values()],pointers:this.pointers};
 }
}

export function drawStringBoard(c,board,now,{program,lit,octave=0}){
 const bass=program>=32&&program<=39,electric=program>=26&&program<=39;
 c.fillStyle=electric?'#793b69':'#895e37';c.beginPath();c.ellipse(775,310,205,237,0,0,Math.PI*2);c.fill();
 c.fillStyle='#382a28';c.fillRect(NECK.left,164,NECK.right-NECK.left,285);
 c.fillStyle='#08131c';c.beginPath();c.arc(788,307,76,0,Math.PI*2);c.fill();c.strokeStyle='#e0ba79';c.lineWidth=4;c.stroke();
 const notes=board.notes();c.textAlign='center';
 for(let fret=0;fret<=NECK.frets;fret++){
  const x=NECK.left+fret*(NECK.right-NECK.left)/NECK.frets;c.strokeStyle=fret?'#8e8585':'#f3dfb7';c.lineWidth=fret?2:7;c.beginPath();c.moveTo(x,164);c.lineTo(x,449);c.stroke();
  if(fret){c.font='20px Segoe UI';c.fillStyle='#d3bc93';c.fillText(String(fret),board.cell(0,fret).x,152);}
 }
 for(let row=0;row<notes.length;row++){
  const y=board.y(row),active=lit('string'+row),held=[...board.contacts.values()].filter(t=>t.row===row);
  c.lineWidth=active?5:1.6+row*.5;c.strokeStyle=active?'#77f5ff':held.length?'#ffd782':'#d5c7af';c.beginPath();c.moveTo(55,y);c.quadraticCurveTo(780,y+(active?Math.sin(now*.06)*7:0),958,y);c.stroke();
  c.font='16px Segoe UI';c.fillStyle='#d9edf4';c.fillText(noteName(board.tuning[row]+octave),48,y-9);
  for(let fret=1;fret<=NECK.frets;fret++){const p=board.cell(row,fret);c.font='17px Segoe UI';c.fillStyle='#eddfc8';c.fillText(noteName(board.tuning[row]+fret+octave),p.x,p.y-8);}
  c.font='bold 19px Segoe UI';c.fillStyle=held.length?'#ffdc83':'#e0f7fc';c.fillText(noteName(notes[row]+octave),910,y-12);
 }
 for(const hit of board.contacts.values()){
  const p=board.cell(hit.row,hit.fret);c.fillStyle='#0ba5ad';c.beginPath();c.arc(p.x,p.y,17,0,Math.PI*2);c.fill();c.strokeStyle='#b4ffff';c.lineWidth=2;c.stroke();c.fillStyle='#fff';c.font='bold 17px Segoe UI';c.fillText(hit.short,p.x,p.y+6);
 }
 c.fillStyle='#b6d9e7';c.font='20px Segoe UI';c.fillText('CASAS · CADA CASA SOBE UM SEMITOM',350,492);c.fillText('DEDILHE AQUI',792,566);
 c.fillStyle='#e9d4b4';c.font='22px Segoe UI';c.fillText(bass?'BAIXO':electric?'GUITARRA':'VIOLÃO',790,595);
}
