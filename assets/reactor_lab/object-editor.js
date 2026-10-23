const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
const copy=value=>JSON.parse(JSON.stringify(value));
const distance=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y);
function segmentDistance(p,a,b){const dx=b.x-a.x,dy=b.y-a.y,t=clamp(((p.x-a.x)*dx+(p.y-a.y)*dy)/(dx*dx+dy*dy||1),0,1);return distance(p,{x:a.x+t*dx,y:a.y+t*dy});}
function insidePolygon(p,points){let inside=false;for(let i=0,j=points.length-1;i<points.length;j=i++){const a=points[i],b=points[j];if((a.y>p.y)!==(b.y>p.y)&&p.x<(b.x-a.x)*(p.y-a.y)/(b.y-a.y)+a.x)inside=!inside;}return inside;}
export function bounds(shapes){
 let left=Infinity,top=Infinity,right=-Infinity,bottom=-Infinity;
 for(const s of shapes)for(const p of s.points){left=Math.min(left,p.x);top=Math.min(top,p.y);right=Math.max(right,p.x);bottom=Math.max(bottom,p.y);}
 return Number.isFinite(left)?{left,top,right,bottom}:null;
}
export function shapeContains(s,p,tolerance=12){
 const ps=s.points;if(!ps?.length)return false;const radius=Math.max(tolerance,s.width/2),a=ps[0],b=ps[1];
 if(s.type==='rectangle'&&b)return p.x>=Math.min(a.x,b.x)-radius&&p.x<=Math.max(a.x,b.x)+radius&&p.y>=Math.min(a.y,b.y)-radius&&p.y<=Math.max(a.y,b.y)+radius;
 if(s.type==='ellipse'&&b){const rx=Math.abs(b.x-a.x)/2,ry=Math.abs(b.y-a.y)/2;return Math.hypot((p.x-(a.x+b.x)/2)/(rx+radius),(p.y-(a.y+b.y)/2)/(ry+radius))<=1;}
 if(ps.length===1)return distance(p,a)<=radius;
 if(s.type!=='erase'&&(s.type==='polygon'||ps.length>4&&distance(a,ps.at(-1))<Math.max(12,s.width*2))&&insidePolygon(p,ps))return true;
 for(let i=1;i<ps.length;i++)if(segmentDistance(p,ps[i-1],ps[i])<=radius)return true;
 return s.type==='polygon'&&segmentDistance(p,ps.at(-1),a)<=radius;
}
export function hitObject(shapes,p,tolerance=12){
 for(let i=shapes.length-1;i>=0;i--){const s=shapes[i];if(shapeContains(s,p,s.type==='erase'?0:tolerance))return s.type==='erase'?null:s.group;}
 return null;
}

// Only the touched objects enter history; no full-canvas copies per camera frame.
export class ObjectEditor{
 constructor(book){this.book=book;this.reset();}
 reset(){this.history=[];this.future=[];this.drags=new Map();this.hovered=new Map();this.selected=null;}
 get busy(){return this.drags.size>0;}
 rows(group){return this.book.shapes.map((shape,index)=>({shape,index})).filter(r=>r.shape.group===group);}
 blocked(group,id){return !group||[...this.book.active.values()].some(b=>b.group===group)||[...this.drags].some(([owner,d])=>owner!==id&&d.group===group);}
 target(p,id){const group=hitObject(this.book.shapes,p,Math.min(25,Math.max(10,7*1024/(this.book.canvas.clientWidth||1024))));return this.blocked(group,id)?null:group;}
 hover(id,p){const group=p?this.target(p,id):null;if(this.hovered.get(id)!==group){this.hovered.set(id,group);this.book.renderSelection();}return group;}
 remember(action){
  action.weight=action.rows?.reduce((n,r)=>n+r.shape.points.length,0)||action.before?.reduce((n,r)=>n+r.points.length*2,0)||1;
  this.history.push(action);this.future=[];
  let weight=this.history.reduce((n,a)=>n+a.weight,0);
  while(this.history.length>80||weight>200000&&this.history.length>1)weight-=this.history.shift().weight;
 }
 recordAdd(group){const rows=this.rows(group);if(rows.length)this.remember({type:'add',rows:copy(rows)});}
 begin(id,p){
  if(this.drags.has(id))return true;const group=this.hover(id,p);
  if(!group){if(id==='mouse')this.selected=null;this.book.renderSelection();return false;}
  const rows=this.rows(group),box=bounds(rows.map(r=>r.shape));if(!box)return false;
  this.selected=group;this.drags.set(id,{group,anchor:{...p},box,offset:{x:0,y:0},before:rows.map(r=>({index:r.index,points:copy(r.shape.points)}))});
  clearTimeout(this.book.analysisTimer);this.book.renderSelection();return true;
 }
 move(id,p){
  const d=this.drags.get(id);if(!d)return;
  const dx=clamp(p.x-d.anchor.x,-d.box.left,1024-d.box.right),dy=clamp(p.y-d.anchor.y,-d.box.top,768-d.box.bottom);
  if(Math.hypot(dx-d.offset.x,dy-d.offset.y)<.5)return;
  // Other hands may append ink, but cannot change this locked object.
  const rows=this.rows(d.group);if(rows.length!==d.before.length){this.end(id,true);return;}
  rows.forEach((r,i)=>r.shape.points=d.before[i].points.map(q=>({x:clamp(q.x+dx,0,1024),y:clamp(q.y+dy,0,768)})));
  d.offset={x:dx,y:dy};this.book.revision++;this.book.render();
 }
 end(id,cancel=false){
  const d=this.drags.get(id);if(!d)return;this.drags.delete(id);this.hovered.delete(id);
  const rows=this.rows(d.group),moved=Math.hypot(d.offset.x,d.offset.y)>.5;
  if(cancel){rows.forEach((r,i)=>{if(d.before[i])r.shape.points=copy(d.before[i].points);});}
  else if(moved)this.remember({type:'move',group:d.group,before:copy(d.before),after:rows.map(r=>({index:r.index,points:copy(r.shape.points)}))});
  if(moved)this.book.changed();else this.book.renderSelection();
 }
 endAll(cancel=false){for(const id of [...this.drags.keys()])this.end(id,cancel);this.hovered.clear();}
 apply(action,forward){
  if(action.type==='move'){const rows=this.rows(action.group),points=forward?action.after:action.before;rows.forEach((r,i)=>{if(points[i])r.shape.points=copy(points[i].points);});this.selected=action.group;}
  else{
   const insert=action.type==='add'?forward:!forward;
   if(insert)for(const r of action.rows)this.book.shapes.splice(Math.min(r.index,this.book.shapes.length),0,copy(r.shape));
   else{const groups=new Set(action.rows.map(r=>r.shape.group));this.book.shapes=this.book.shapes.filter(s=>!groups.has(s.group));if(groups.has(this.selected))this.selected=null;}
  }
 }
 undo(){const a=this.history.pop();if(!a)return;this.apply(a,false);this.future.push(a);this.book.changed();}
 redo(){const a=this.future.pop();if(!a)return;this.apply(a,true);this.history.push(a);this.book.changed();}
 remove(){
  if(!this.selected)return;const rows=this.rows(this.selected);if(!rows.length)return;
  this.remember({type:'remove',rows:copy(rows)});this.book.shapes=this.book.shapes.filter(s=>s.group!==this.selected);this.selected=null;this.book.changed();
 }
 duplicate(){
  const rows=this.rows(this.selected);if(!rows.length)return;
  if(this.book.shapes.length+rows.length>4500||this.book.shapes.reduce((n,s)=>n+s.points.length,0)+rows.reduce((n,r)=>n+r.shape.points.length,0)>50000){this.book.notify('O desenho atingiu o limite. Salve antes de adicionar mais objetos.');return;}
  const box=bounds(rows.map(r=>r.shape)),dx=clamp(24,-box.left,1024-box.right),dy=clamp(24,-box.top,768-box.bottom),group='g'+(++this.book.groupSerial);
  for(const r of rows){const s=copy(r.shape);s.group=group;s.points=s.points.map(p=>({x:p.x+dx,y:p.y+dy}));this.book.shapes.push(s);}
  this.recordAdd(group);this.selected=group;this.book.changed();
 }
 selections(){
  const groups=new Set([this.selected,...this.hovered.values(),...[...this.drags.values()].map(d=>d.group)]);groups.delete(null);groups.delete(undefined);
  return [...groups].map(group=>({group,box:bounds(this.rows(group).map(r=>r.shape)),moving:[...this.drags.values()].some(d=>d.group===group),selected:group===this.selected})).filter(r=>r.box);
 }
}
