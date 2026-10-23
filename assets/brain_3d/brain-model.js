/* Builds relationships from local metadata. Never reads note contents. */
(function(root){
'use strict';
const hash=value=>{let h=2166136261;for(const c of String(value))h=Math.imul(h^c.charCodeAt(0),16777619);return h>>>0;};
const unit=value=>hash(value)/4294967296;
const normalize=value=>String(value??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
const morton=(x,y,z)=>{const expand=v=>{let out=0;for(let b=0;b<8;b++)out|=((v>>b)&1)<<(3*b);return out;};const clamp=v=>Math.max(0,Math.min(255,Math.round(v)));return expand(clamp((x+20)*6))|expand(clamp((y+18)*7))<<1|expand(clamp((z+22)*5.5))<<2;};
function surface(count,side){
  const points=[],golden=Math.PI*(3-Math.sqrt(5));
  for(let i=0;i<count;i++){
    const ny=1-2*(i+.5)/count,phi=Math.acos(ny),theta=(i*golden)%Math.PI-Math.PI/2,radial=Math.sqrt(Math.max(0,1-ny*ny));
    const nx=Math.cos(theta)*radial,nz=Math.sin(theta)*radial;
    // Winding cortical grooves, with an open midline between hemispheres.
    const wave=Math.sin(9*phi+2.4*Math.sin(3*theta)+.6*Math.cos(7*theta));
    const cross=Math.sin(7*theta+2.1*Math.sin(5*phi));
    const crease=.12*Math.exp(-((wave/.30)**2))+.04*Math.exp(-((cross/.22)**2));
    const depth=i%17===0?.76+.15*unit(i+':depth'):1,r=(1-crease)*depth;
    const taper=1-.12*Math.max(0,-ny)-.06*Math.max(0,nz);
    const medial=1-.15*Math.exp(-nx*nx/.04);
    const x=side*(.65+nx*16*r*taper),y=ny*13.5*r*medial+1.2*nz,z=nz*22*r*(1-.05*ny)-.6;
    points.push({x,y,z,nx:side*nx,ny,nz,light:1-crease*4.6,key:morton(x*side,y,z)});
  }
  return points.sort((a,b)=>a.key-b.key);
}
function build(index,classifications={}){
  if(!index||!index.categories||typeof index.categories!=='object')throw Error('Índice de memória indisponível. Reconstrua o mapa de memória no Jarvis e abra esta página novamente.');
  const groups=new Map(),notes=[],folderGroup=new Map();
  for(const [name,data]of Object.entries(classifications.groups||{}))for(const folder of data.categories||[])folderGroup.set(folder,name);
  for(const [folder,category]of Object.entries(index.categories)){
    const group=String(classifications.categories?.[folder]?.group||folderGroup.get(folder)||'Outras memórias');
    for(const file of category.sample_files||[]){
      if(!file||typeof file!=='object')continue;
      const tags=Array.isArray(file.tags)?[...new Set(file.tags.filter(t=>typeof t==='string').map(t=>t.trim()).filter(Boolean))]:[];
      const note={title:String(file.title||file.name||'Sem título'),folder,group,tags,path:String(file.path||''),relativePath:String(file.relative_path||file.name||''),modified:String(file.modified||''),type:String(file.type||'')};
      note.key=[group,folder,note.path||note.relativePath,note.title].join('\u0000');note.search=normalize([note.title,folder,group,...tags].join(' '));notes.push(note);
    }
  }
  notes.sort((a,b)=>a.key.localeCompare(b.key,'pt-BR'));
  const left=surface(Math.ceil(notes.length/2),-1),right=surface(Math.floor(notes.length/2),1);
  const positions=new Float32Array(notes.length*3),normals=new Float32Array(notes.length*3),lights=new Float32Array(notes.length),folders=new Map(),tags=new Map();
  const bucket=(map,key,id)=>{if(!map.has(key))map.set(key,[]);map.get(key).push(id);};
  notes.forEach((note,id)=>{
    note.id=id;const p=(id%2?right:left)[id>>1];positions.set([p.x,p.y,p.z],id*3);normals.set([p.nx,p.ny,p.nz],id*3);lights[id]=p.light;
    if(!groups.has(note.group))groups.set(note.group,{name:note.group,ids:[],center:[0,0,0],folders:new Set()});
    const group=groups.get(note.group);group.ids.push(id);group.folders.add(note.folder);group.center[0]+=p.x;group.center[1]+=p.y;group.center[2]+=p.z;
    bucket(folders,note.folder,id);for(const tag of note.tags)bucket(tags,normalize(tag).replace(/^#/,''),id);
  });
  for(const group of groups.values())group.center=group.center.map(v=>v/group.ids.length);
  const edges=[],adjacency=Array.from({length:notes.length},()=>[]),seen=new Set();
  const edge=(a,b,type)=>{if(a===b)return;const key=Math.min(a,b)*Math.max(1,notes.length)+Math.max(a,b);if(seen.has(key))return;seen.add(key);const id=edges.length;edges.push({a,b,type});adjacency[a].push(id);adjacency[b].push(id);};
  const distance=(a,b)=>(positions[a*3]-positions[b*3])**2+(positions[a*3+1]-positions[b*3+1])**2+(positions[a*3+2]-positions[b*3+2])**2;
  // Deterministic local chains avoid all-pairs work and include every note.
  for(const ids of folders.values()){
    const halves=[ids.filter(id=>!(id%2)),ids.filter(id=>id%2)];
    for(const half of halves)for(let k=1;k<half.length;k++){
      edge(half[k-1],half[k],'pasta');let best=-1,d=Infinity;
      for(let j=Math.max(0,k-7);j<k-1;j++){const next=distance(half[k],half[j]);if(next<d){d=next;best=half[j];}}
      if(best>=0&&d<90)edge(half[k],best,'pasta');
      // Dense, short cortical synapses make the surface read as neural tissue
      // without the cost of an all-to-all mesh.
      if(k>2&&k%2===0)edge(half[k],half[k-2],'cortical');
      if(k>3)edge(half[k],half[k-3],'cortical');
      if(k>7&&k%2===0)edge(half[k],half[k-6],'cortical');
      if(k>5&&k%2===1)edge(half[k],half[k-5],'cortical');
      if(k>10&&k%3===0)edge(half[k],half[k-9],'cortical');
    }
    if(halves[0].length&&halves[1].length)edge(halves[0][halves[0].length>>1],halves[1][halves[1].length>>1],'pasta');
  }
  for(const group of groups.values()){
    const reps=[...group.folders].map(folder=>folders.get(folder)[Math.floor(folders.get(folder).length/2)]);
    for(let k=1;k<reps.length;k++)edge(reps[k-1],reps[k],'grupo');
  }
  // Tag bridges use only shared tags already present in the index.
  for(const ids of tags.values()){
    const representatives=new Map();for(const id of ids)if(!representatives.has(notes[id].group))representatives.set(notes[id].group,id);
    const reps=[...representatives.values()];for(let k=1;k<Math.min(reps.length,32);k++)edge(reps[k-1],reps[k],'tag');
  }
  // Region hubs carry explicit connect-* tags. Give each new neural area several
  // visible synapses into its real source domains, rather than leaving it as an
  // isolated label in the atlas.
  for(const hub of notes){
    if(hub.type!=='jarvis-knowledge-region')continue;
    for(const tag of hub.tags){
      if(!tag.startsWith('connect-'))continue;
      const ids=folders.get(tag.slice('connect-'.length));
      if(!ids?.length)continue;
      const taps=Math.min(6,Math.max(3,Math.ceil(ids.length/30)));
      for(let tap=1;tap<=taps;tap++)edge(hub.id,ids[Math.floor(tap*ids.length/(taps+1))],'sinapse');
    }
  }
  return {notes,groups,folders,positions,normals,lights,edges,adjacency,indexedTotal:Number(index.total_files)||notes.length,updated:index.updated||''};
}
function route(model,startGroup,endGroup){
  const start=model.groups.get(startGroup),end=model.groups.get(endGroup);if(!start||!end)return null;
  const previous=new Int32Array(model.notes.length).fill(-2),queue=new Int32Array(model.notes.length);let head=0,tail=0;
  if(startGroup===endGroup){if(start.ids.length<2)return null;const from=start.ids[0];previous[from]=-1;queue[tail++]=from;}
  else for(const id of start.ids){previous[id]=-1;queue[tail++]=id;}
  const target=startGroup===endGroup?start.ids[start.ids.length-1]:-1;
  while(head<tail){
    const id=queue[head++];if((target>=0&&id===target)||(target<0&&model.notes[id].group===endGroup)){
      const result=[];for(let at=id;at>=0;at=previous[at])result.push(at);return result.reverse();
    }
    for(const edgeId of model.adjacency[id]){const e=model.edges[edgeId],next=e.a===id?e.b:e.a;if(previous[next]!==-2)continue;previous[next]=id;queue[tail++]=next;}
  }
  return null;
}
root.JarvisBrainModel={build,route,hash,normalize};if(typeof module!=='undefined'&&module.exports)module.exports=root.JarvisBrainModel;
})(typeof window==='undefined'?globalThis:window);
