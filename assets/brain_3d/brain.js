(function () {
'use strict';
const $=id=>document.getElementById(id),fmt=n=>Number(n).toLocaleString('pt-BR');
const fail=message=>{$('loading').hidden=false;$('loading').querySelector('h2').textContent='Não foi possível abrir o cérebro';$('loadingText').textContent=message;$('retry').hidden=false;};
try {
if(!window.JarvisBrainThree||!window.JarvisBrainOrbitControls||!window.JarvisBrainModel)throw Error('Biblioteca 3D local indisponível. Verifique a pasta assets/brain_3d.');
const THREE=window.JarvisBrainThree,Model=window.JarvisBrainModel;
const model=Model.build(window.JARVIS_VAULT_INDEX,window.JARVIS_VAULT_GROUPS||{}),N=model.notes.length;
const groupNames=[...model.groups.keys()],container=$('scene');
const renderer=new THREE.WebGLRenderer({antialias:true,alpha:true,powerPreference:'low-power'});
renderer.setClearColor(0x050c13,0);renderer.outputColorSpace=THREE.SRGBColorSpace;
container.appendChild(renderer.domElement);
const gl=renderer.getContext(),debug=gl.getExtension('WEBGL_debug_renderer_info');
const rendererName=debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):'';
const software=/SwiftShader|Software|Microsoft Basic Render|llvmpipe/i.test(rendererName);
const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(38,1,.1,500);
const controls=new window.JarvisBrainOrbitControls(camera,renderer.domElement);
controls.enableDamping=true;controls.dampingFactor=.12;controls.enablePan=false;controls.autoRotate=false;controls.autoRotateSpeed=.4;
controls.minDistance=12;controls.maxDistance=170;
// Distinct, saturated classes on a dark background. Do not cycle eight similar hues.
const palette=['#25d9ff','#ff943d','#a982ff','#83ea48','#ff5faf','#ffe35b','#598dff','#ff5b59',
  '#28d8a1','#e7a9ff','#b9d537','#ffb398','#00a4c4','#f15fe6','#b89865','#71d58c',
  '#aec8ff','#cf692f','#70f2dc','#d768a4','#bedc8c','#9670d2','#ebca98','#46afff','#dbedf7',
  '#ffa4db','#f7f39b','#75af7e','#e2a857','#84a9c7','#bb7c78','#d998ff'];
const colors=new Map(),usedColors=new Set();
groupNames.forEach((name,i)=>{
  let color=new THREE.Color(palette[i]||`hsl(${(i*137.508)%360},88%,62%)`),probe=0;
  while(usedColors.has(color.getHexString()))color=new THREE.Color(`hsl(${(i*137.508+(++probe)*23)%360},88%,${54+probe%22}%)`);
  usedColors.add(color.getHexString());colors.set(name,color);
});
const baseColors=new Float32Array(N*3),visibility=new Float32Array(N).fill(1),pointIds=new Float32Array(N);
model.notes.forEach((note,i)=>{const c=colors.get(note.group);baseColors.set([c.r,c.g,c.b],i*3);pointIds[i]=i;});
const geometry=new THREE.BufferGeometry();
geometry.setAttribute('position',new THREE.BufferAttribute(model.positions,3));geometry.setAttribute('aNormal',new THREE.BufferAttribute(model.normals,3));
geometry.setAttribute('color',new THREE.BufferAttribute(baseColors,3));geometry.setAttribute('aVisible',new THREE.BufferAttribute(visibility,1));
geometry.setAttribute('aLight',new THREE.BufferAttribute(model.lights,1));geometry.setAttribute('aId',new THREE.BufferAttribute(pointIds,1));
const uniforms={uTime:{value:0},uRead:{value:0},uPulse:{value:reduced?0:1},uGlobalPulse:{value:-2},uRatio:{value:1},uSelected:{value:-1},uScale:{value:1}};
const material=new THREE.ShaderMaterial({transparent:true,depthWrite:false,vertexColors:true,blending:THREE.NormalBlending,uniforms,
vertexShader:`
  attribute vec3 aNormal;attribute float aVisible;attribute float aLight;attribute float aId;
  uniform float uTime;uniform float uRead;uniform float uPulse;uniform float uGlobalPulse;uniform float uRatio;uniform float uSelected;uniform float uScale;
  varying vec3 vColor;varying float vAlpha;varying float vSelected;
  void main(){
    vec4 p=modelViewMatrix*vec4(position,1.0);gl_Position=projectionMatrix*p;
    vec3 n=normalize(normalMatrix*aNormal),viewDir=normalize(-p.xyz);
    float facing=max(0.0,dot(n,viewDir));float front=smoothstep(-.24,.28,dot(n,viewDir));
    float pulse=1.0+uPulse*.015*sin(uTime*.55+position.y*.06+position.z*.04);
    float sweep=exp(-pow(((position.y+14.)/28.)-uGlobalPulse,2.)*82.);
    vSelected=abs(aId-uSelected)<.1?1.0:0.0;
    vColor=mix(color,vec3(1.),vSelected*.38);
    vColor=mix(vColor,vec3(.72,1.,.9),uRead*.24+sweep*.78);
    vAlpha=aVisible*(.02+front*(.48+.50*pow(facing,.6)))*aLight*pulse*(1.+sweep*3.4);
    vAlpha=min(1.,vAlpha*(1.+uRead*1.8)+aVisible*uRead*.09);
    gl_PointSize=clamp((2.5+vSelected*4.5)*(1.+uRead*.18+sweep*.55)*uScale*uRatio*70.0/max(16.0,-p.z),1.0,8.0*uRatio);
  }`,
fragmentShader:`
  varying vec3 vColor;varying float vAlpha;varying float vSelected;
  void main(){
    vec2 p=abs(gl_PointCoord-.5)*2.0;
    float square=1.0-smoothstep(.65,1.0,max(p.x,p.y));
    gl_FragColor=vec4(vColor*(1.30+vSelected*.7),vAlpha*square);
    #include <colorspace_fragment>
  }`});
const cloud=new THREE.Points(geometry,material);scene.add(cloud);

const lineColors=new Float32Array(model.edges.length*6),linePositions=new Float32Array(model.edges.length*6);
const lineBase=new Float32Array(lineColors.length),lineNormals=new Float32Array(lineColors.length),lineSignals=new Float32Array(model.edges.length*2);
model.edges.forEach((e,i)=>{
  const a=e.a*3,b=e.b*3;lineNormals.set(model.normals.subarray(a,a+3),i*6);lineNormals.set(model.normals.subarray(b,b+3),i*6+3);linePositions.set(model.positions.subarray(a,a+3),i*6);linePositions.set(model.positions.subarray(b,b+3),i*6+3);
  const ca=colors.get(model.notes[e.a].group),cb=colors.get(model.notes[e.b].group);
  // Common organisational paths stay in the background; regional synapses have a dedicated cyan channel.
  const dist=Math.hypot(model.positions[a]-model.positions[b],model.positions[a+1]-model.positions[b+1],model.positions[a+2]-model.positions[b+2]);
  const isSynapse=e.type==='sinapse';
  const brightness=isSynapse?2.55:e.type==='cortical'?.34:dist>10?.10:dist>5?.17:.25;
  if(isSynapse)lineBase.set([.20,1.82,1.72,.20,1.82,1.72],i*6);
  else lineBase.set([ca.r*brightness,ca.g*brightness,ca.b*brightness,cb.r*brightness,cb.g*brightness,cb.b*brightness],i*6);
  lineSignals[i*2]=lineSignals[i*2+1]=isSynapse?1:0;
});
lineColors.set(lineBase);
const lineGeometry=new THREE.BufferGeometry();lineGeometry.setAttribute('position',new THREE.BufferAttribute(linePositions,3));lineGeometry.setAttribute('color',new THREE.BufferAttribute(lineColors,3));
lineGeometry.setAttribute('aNormal',new THREE.BufferAttribute(lineNormals,3));lineGeometry.setAttribute('aSynapse',new THREE.BufferAttribute(lineSignals,1));
const lineMaterial=new THREE.ShaderMaterial({vertexColors:true,transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,uniforms:{uOpacity:{value:.20},uRead:uniforms.uRead,uGlobalPulse:uniforms.uGlobalPulse},
vertexShader:`attribute vec3 aNormal;attribute float aSynapse;varying vec3 vColor;varying float vAlpha;varying float vSynapse;uniform float uOpacity;uniform float uRead;uniform float uGlobalPulse;void main(){vec4 p=modelViewMatrix*vec4(position,1.);float front=dot(normalize(normalMatrix*aNormal),normalize(-p.xyz));float sweep=exp(-pow(((position.y+14.)/28.)-uGlobalPulse,2.)*82.);vColor=mix(color,vec3(.42,1.,.96),sweep*.65);vSynapse=aSynapse;vAlpha=uOpacity*(.06+.94*smoothstep(-.22,.40,front))*(1.+uRead*2.1)*(1.+aSynapse*2.8)*(1.+sweep*2.8);gl_Position=projectionMatrix*p;}`,
fragmentShader:`varying vec3 vColor;varying float vAlpha;varying float vSynapse;void main(){gl_FragColor=vec4(vColor*(.78+vAlpha*.34+vSynapse*.72),vAlpha);
#include <colorspace_fragment>
}`});
Object.defineProperty(lineMaterial,'opacity',{get(){return this.uniforms.uOpacity.value;},set(value){this.uniforms.uOpacity.value=value;}});
const lines=new THREE.LineSegments(lineGeometry,lineMaterial);scene.add(lines);
const lineOpacity=()=>Number($('density').value)/100*.22+.025;

// Reusable buffers: selections and route animations do not allocate a new GPU scene.
const selectedGeometry=new THREE.BufferGeometry(),selectedMaterial=new THREE.LineBasicMaterial({color:0x91fff1,transparent:true,opacity:.9,depthWrite:false,blending:THREE.AdditiveBlending});
const selectedLines=new THREE.LineSegments(selectedGeometry,selectedMaterial);scene.add(selectedLines);
const routeGeometry=new THREE.BufferGeometry(),routeMaterial=new THREE.LineBasicMaterial({color:0xffce87,transparent:true,opacity:.95,depthWrite:false,blending:THREE.AdditiveBlending});
const routeLine=new THREE.Line(routeGeometry,routeMaterial);scene.add(routeLine);
const signalGeometry=new THREE.BufferGeometry();signalGeometry.setAttribute('position',new THREE.Float32BufferAttribute([0,0,0],3));
const signalMaterial=new THREE.PointsMaterial({color:0xffe4b7,size:.65,transparent:true,depthWrite:false,blending:THREE.AdditiveBlending});
const signal=new THREE.Points(signalGeometry,signalMaterial);signal.visible=false;scene.add(signal);

// Continuous traffic on existing note edges. Eighteen heads and two short trail
// samples each share one reusable GPU buffer. A pale core and colored halo
// keep each signal legible against dense notes, without bloom or extra passes.
const flowLimit=software?6:28,flowSamples=3,flowCapacity=flowLimit*flowSamples;
const flowPositions=new Float32Array(flowCapacity*3),flowColors=new Float32Array(flowCapacity*3);
const flowNormals=new Float32Array(flowCapacity*3),flowTails=new Float32Array(flowCapacity);
for(let i=0;i<flowCapacity;i++)flowTails[i]=i%flowSamples;
const flowGeometry=new THREE.BufferGeometry();
for(const [name,array,size]of [['position',flowPositions,3],['color',flowColors,3],['aNormal',flowNormals,3],['aTail',flowTails,1]]){
  flowGeometry.setAttribute(name,new THREE.BufferAttribute(array,size).setUsage(THREE.DynamicDrawUsage));
}
flowGeometry.setDrawRange(0,0);
const flowUniforms={uFade:{value:0},uStrength:{value:1},uRatio:uniforms.uRatio};
const flowMaterial=new THREE.ShaderMaterial({transparent:true,vertexColors:true,depthWrite:false,blending:THREE.AdditiveBlending,uniforms:flowUniforms,
vertexShader:`
  attribute vec3 aNormal;attribute float aTail;uniform float uFade;uniform float uStrength;uniform float uRatio;
  varying vec3 vColor;varying float vAlpha;
  void main(){
    vec4 p=modelViewMatrix*vec4(position,1.);gl_Position=projectionMatrix*p;
    float front=.16+.84*smoothstep(-.35,.35,dot(normalize(normalMatrix*aNormal),normalize(-p.xyz)));
    vAlpha=.95*uFade*uStrength*front*pow(.58,aTail);
    vColor=mix(color,vec3(1.),.12);
    gl_PointSize=clamp((18.-aTail*4.)*uRatio*80./max(18.,-p.z),4.*uRatio,24.*uRatio);
  }`,
fragmentShader:`
  varying vec3 vColor;varying float vAlpha;
  void main(){
    float r=length(gl_PointCoord-.5)*2.;if(r>1.||vAlpha<.001)discard;
    float halo=exp(-r*r*4.)*(1.-smoothstep(.72,1.,r));
    float core=1.-smoothstep(.10,.40,r);
    vec3 light=mix(vColor,vec3(.94,1.,1.),core*.96);
    gl_FragColor=vec4(light,min(1.,halo*.60+core*.70)*vAlpha);
    #include <colorspace_fragment>
  }`});
const flowLights=new THREE.Points(flowGeometry,flowMaterial);
flowLights.frustumCulled=false;flowLights.visible=false;scene.add(flowLights);
const flowWalkers=[],flowFacing=new THREE.Vector3();
let flowAge=0,flowHops=0,flowEpoch=0,flowEnabled=false,flowSeed=Model.hash('quiet-flow:'+N);
function flowRandom(){flowSeed=(Math.imul(flowSeed,1664525)+1013904223)>>>0;return flowSeed/4294967296;}
function flowDistance(a,b){return Math.hypot(model.positions[a*3]-model.positions[b*3],model.positions[a*3+1]-model.positions[b*3+1],model.positions[a*3+2]-model.positions[b*3+2]);}
function flowNeighbors(id){return model.adjacency[id].map(edgeId=>{const e=model.edges[edgeId];return e.a===id?e.b:e.a;}).filter(other=>visibility[other]===1);}
function flowNext(id,previous){
  let choices=flowNeighbors(id),forward=choices.filter(other=>other!==previous);if(forward.length)choices=forward;
  let best=-1,score=Infinity;
  for(const next of choices){const value=Math.abs(flowDistance(id,next)-3.5)+flowRandom()*4;if(value<score){score=value;best=next;}}
  return best;
}
function flowDuration(a,b){return Math.max(2.4,Math.min(12,flowDistance(a,b)/(1.6+flowRandom()*.7)));}
function refreshFlow(){
  // Rebuild seeds only when filters change, never across all notes in the frame loop.
  flowEpoch++;flowWalkers.length=0;
  const groups=new Map();
  for(const note of model.notes){
    if(visibility[note.id]!==1||!model.adjacency[note.id].some(edgeId=>{const e=model.edges[edgeId];return visibility[e.a===note.id?e.b:e.a]===1;}))continue;
    if(!groups.has(note.group))groups.set(note.group,[]);groups.get(note.group).push(note.id);
  }
  const available=[...groups.values()],eligible=available.reduce((n,ids)=>n+ids.length,0);
  const count=eligible?Math.min(flowLimit,Math.max(1,Math.ceil(eligible/150))):0;
  flowFacing.copy(camera.position).sub(controls.target).normalize();
  for(let i=0;i<count;i++){
    const ids=available[(Math.floor(i*available.length/count)+flowEpoch-1)%available.length];
    const front=ids.filter(id=>model.normals[id*3]*flowFacing.x+model.normals[id*3+1]*flowFacing.y+model.normals[id*3+2]*flowFacing.z>.2);
    const pool=front.length?front:ids,from=pool[Math.floor(flowRandom()*pool.length)],to=flowNext(from,-1);
    if(to<0)continue;
    flowWalkers.push({from,to,progress:(i+.5)/count,duration:flowDuration(from,to)});
  }
  flowGeometry.setDrawRange(0,flowWalkers.length*flowSamples);writeFlowPositions();syncFlow();
}
function writeFlowPositions(){
  for(let i=0;i<flowWalkers.length;i++){
    const w=flowWalkers[i],a=w.from*3,b=w.to*3;
    const ca=colors.get(model.notes[w.from].group),cb=colors.get(model.notes[w.to].group);
    for(let tail=0;tail<flowSamples;tail++){
      const t=Math.max(0,w.progress-tail*.085),k=t*t*(3-2*t),out=(i*flowSamples+tail)*3;
      for(let axis=0;axis<3;axis++){
        flowPositions[out+axis]=model.positions[a+axis]+(model.positions[b+axis]-model.positions[a+axis])*k;
        flowNormals[out+axis]=model.normals[a+axis]+(model.normals[b+axis]-model.normals[a+axis])*k;
      }
      flowColors[out]=ca.r+(cb.r-ca.r)*k;flowColors[out+1]=ca.g+(cb.g-ca.g)*k;flowColors[out+2]=ca.b+(cb.b-ca.b)*k;
    }
  }
  for(const name of ['position','color','aNormal'])flowGeometry.attributes[name].needsUpdate=true;
}
function syncFlow(){
  flowEnabled=animating&&!reduced&&flowWalkers.length>0;
  flowLights.visible=flowEnabled&&$('connections').checked;
  flowUniforms.uStrength.value=(selected>=0||routeState?.running)? .58:1;
}
function advanceFlow(dt){
  if(!flowEnabled||!flowLights.visible)return;
  flowAge+=dt;const fade=Math.min(1,flowAge/2.8);flowUniforms.uFade.value=fade*fade*(3-2*fade);
  for(const w of flowWalkers){
    w.progress+=dt/w.duration;
    if(w.progress>=1){
      const remaining=(w.progress-1)*w.duration,previous=w.from;w.from=w.to;w.to=flowNext(w.from,previous);
      if(w.to<0)w.to=previous;
      w.duration=flowDuration(w.from,w.to);w.progress=Math.min(.99,remaining/w.duration);flowHops++;
    }
  }
  writeFlowPositions();
}
// Kept for UI callers; repeated requests never add particles or restart a flash.
function activate(){const wasEnabled=flowEnabled;syncFlow();if(flowEnabled)invalidate();return flowEnabled&&!wasEnabled;}

// Counts are real tool operations. This pulse is only their visual indicator.
let reading=null,lastReadingRevision=0n;
function readActivity(payload){
  if(!payload||payload.operation!=='count_notes'||!/^\d{1,22}$/.test(String(payload.revision)))return false;
  const revision=BigInt(payload.revision),age=Date.now()-Number(payload.updated_at);
  if(revision<=lastReadingRevision||!Number.isFinite(age)||age < -5000||age>120000)return false;
  lastReadingRevision=revision;
  if(!payload.active&&age>15000)return false;
  const now=performance.now(),same=reading&&reading.operationAt===payload.started_at;
  const start=same?reading.start:now;
  reading={start,operationAt:payload.started_at,active:!!payload.active,
    until:payload.active?now+Math.max(0,120000-age):Math.max(start+3200,now+1100)};
  const badge=$('brainActivity');badge.hidden=false;
  badge.textContent=payload.active?'Contando notas do Obsidian…':payload.phase==='error'?'Falha na contagem das notas':'Contagem concluída';
  advanceReading(now);invalidate();return true;
}
function advanceReading(now){
  if(!reading){uniforms.uRead.value=0;return;}
  if(now>=reading.until){reading=null;uniforms.uRead.value=0;$('brainActivity').hidden=true;return;}
  const envelope=Math.max(0,Math.min(1,(now-reading.start)/450,(reading.until-now)/900));
  const pulse=.30+.70*(.5+.5*Math.sin((now-reading.start)/1650*Math.PI*2-Math.PI/2));
  uniforms.uRead.value=reduced||!animating?0:envelope*pulse;
}

let selected=-1,activeGroup=null,query='',visibleCount=N,visibleEdges=model.edges.length,routeState=null,cameraTween=null,brainPulse=null;
let auto=false,animating=!reduced,activeUntil=0,dirty=true,raf=0,timer=0,paused=false,disposed=false;
let lastTime=0,frameCount=0,fpsFrames=0,fpsAt=performance.now(),fps=0,searchTimer=0,hoverTimer=0;
let canvasWidth=1,canvasHeight=1,homeDistance=80;
const selectedMask=new Set(),up=new THREE.Vector3(0,1,0);
const setText=(id,value)=>{$(id).textContent=value;};
const point=id=>new THREE.Vector3().fromArray(model.positions,id*3);
const vector=new THREE.Vector3();
function invalidate(interaction=false){dirty=true;if(interaction)activeUntil=performance.now()+850;schedule();}
function schedule(){
  if(disposed||paused||document.hidden||timer||raf)return;
  const now=performance.now(),moving=auto||routeState?.running||cameraTween||brainPulse||now<activeUntil;
  if(!dirty&&!animating&&!moving&&!reading)return;
  const hz=software?(moving?12:4):(moving?24:12);
  timer=setTimeout(()=>{timer=0;raf=requestAnimationFrame(draw);},Math.max(0,1000/hz-(now-lastTime)));
}
function draw(now){
  raf=0;if(disposed||paused||document.hidden)return;
  const elapsed=lastTime?Math.max(0,(now-lastTime)/1000):0;
  const dt=Math.min(.12,elapsed),flowDt=Math.min(1,elapsed);lastTime=now;
  if(cameraTween){
    const t=Math.max(0,Math.min(1,(now-cameraTween.start)/650)),k=t*t*(3-2*t);
    camera.position.lerpVectors(cameraTween.from,cameraTween.to,k);controls.target.lerpVectors(cameraTween.targetFrom,cameraTween.targetTo,k);
    if(t===1)cameraTween=null;
  }
  controls.autoRotate=auto;controls.update(dt);
  if(animating)uniforms.uTime.value=now/1000;
  if(brainPulse){
    const progress=Math.max(0,Math.min(1,(now-brainPulse.start)/brainPulse.duration));
    uniforms.uGlobalPulse.value=progress;
    if(progress===1){brainPulse=null;uniforms.uGlobalPulse.value=-2;if(!routeState?.running)setText('caption','Pulso neural concluído · rede inteira sincronizada');}
  }
  syncFlow();advanceFlow(flowDt);advanceReading(now);
  if(routeState?.running){
    // A queued RAF timestamp may precede a route created in the current frame.
    const progress=Math.max(0,Math.min(1,(now-routeState.start)/routeState.duration)),segments=routeState.ids.length-1,at=progress*segments,idx=Math.min(segments-1,Math.floor(at));
    routeGeometry.setDrawRange(0,Math.min(routeState.ids.length,Math.ceil(at)+1));
    vector.lerpVectors(point(routeState.ids[idx]),point(routeState.ids[idx+1]),at-idx);
    signalGeometry.attributes.position.setXYZ(0,vector.x,vector.y,vector.z);signalGeometry.attributes.position.needsUpdate=true;
    if(progress===1){routeState.running=false;signal.visible=false;setText('caption',routeState.search?'Sinapse de busca ativa · conexão instantânea':'Caminho completo · '+fmt(segments)+' relações percorridas');}
  }
  dirty=false;renderer.render(scene,camera);frameCount++;fpsFrames++;
  if(now-fpsAt>1500){fps=Math.round(fpsFrames*1000/(now-fpsAt));fpsFrames=0;fpsAt=now;setText('performance',(software?'LEVE':'LOCAL')+' / '+fps+' FPS');}
  schedule();
}
function resize(){
  const rect=container.getBoundingClientRect();canvasWidth=Math.max(1,rect.width);canvasHeight=Math.max(1,rect.height);
  const ratio=Math.min(devicePixelRatio||1,1.25,Math.sqrt((software?450000:900000)/(canvasWidth*canvasHeight)));
  renderer.setPixelRatio(ratio);renderer.setSize(canvasWidth,canvasHeight,false);uniforms.uRatio.value=ratio;
  camera.aspect=canvasWidth/canvasHeight;camera.updateProjectionMatrix();
  // Keep the cortex prominent on first open while still fitting narrow windows.
  homeDistance=25.5/(Math.tan(THREE.MathUtils.degToRad(camera.fov/2))*Math.min(1,camera.aspect)) * .98;
  controls.maxDistance=Math.max(170,homeDistance*1.6);invalidate(true);
}
function moveCamera(position,target=new THREE.Vector3(),instant=false){
  if(instant||reduced){camera.position.copy(position);controls.target.copy(target);controls.update();cameraTween=null;}
  else cameraTween={from:camera.position.clone(),to:position,targetFrom:controls.target.clone(),targetTo:target,start:performance.now()};
  invalidate(true);
}
function home(top=false,instant=false){const direction=top?new THREE.Vector3(.001,1,.01):new THREE.Vector3(.18,1.4,.95).normalize();moveCamera(direction.multiplyScalar(homeDistance),new THREE.Vector3(0,0,0),instant);}
function focus(id){const p=point(id),direction=camera.position.clone().sub(controls.target).normalize();moveCamera(p.clone().addScaledVector(direction,38),p);}
const resizeObserver=new ResizeObserver(resize);resizeObserver.observe(container);resize();home(false,true);
controls.addEventListener('start',()=>{cameraTween=null;setAuto(false);$('tooltip').hidden=true;invalidate(true);});
controls.addEventListener('change',()=>{dirty=true;schedule();});
controls.addEventListener('end',()=>invalidate(true));

function renderList(){
  $('groupList').replaceChildren();
  if(query){
    const matches=model.notes.filter(n=>n.search.includes(query)&&(!activeGroup||n.group===activeGroup));
    setText('listTitle','NOTAS ENCONTRADAS');setText('groupCount',fmt(matches.length));
    for(const note of matches.slice(0,60)){
      const button=document.createElement('button');button.className='result-row';button.dataset.noteId=note.id;
      const title=document.createElement('strong'),detail=document.createElement('small');title.textContent=note.title;detail.textContent=note.folder;button.append(title,detail);
      button.onclick=()=>{selectNote(note.id);focus(note.id);};$('groupList').append(button);
    }
    if(!matches.length||matches.length>60){const p=document.createElement('p');p.className='no-results';p.textContent=matches.length?'Mostrando as primeiras 60 notas. Refine a busca para encontrar uma nota específica.':'Nenhuma nota encontrada. Tente outra palavra ou limpe o filtro.';$('groupList').append(p);}
    return;
  }
  setText('listTitle','GRUPOS DE MEMÓRIA');setText('groupCount',fmt(groupNames.length));
  const row=(name,count,color,all=false)=>{
    const button=document.createElement('button');button.className='group-row'+((all?!activeGroup:activeGroup===name)?' active':'');
    button.setAttribute('aria-pressed',String(all?!activeGroup:activeGroup===name));
    button.style.setProperty('--group-color',color);
    if(!all&&activeGroup===name){button.style.borderColor=color;button.style.background=color+'1b';}
    const dot=document.createElement('span'),label=document.createElement('span'),small=document.createElement('small');dot.className='group-dot';dot.style.setProperty('--group-color',color);label.className='group-name';label.textContent=name;small.textContent=fmt(count);button.append(dot,label,small);
    button.onclick=()=>{activeGroup=all||activeGroup===name?null:name;clearRoute();clearSelection();applyFilter();renderList();};$('groupList').append(button);
  };
  row('Todas as memórias',N,'#bdeae5',true);for(const [name,g]of model.groups)row(name,g.ids.length,'#'+colors.get(name).getHexString());
}
function applyFilter(){
  visibleCount=0;
  model.notes.forEach((note,i)=>{const matches=(!activeGroup||note.group===activeGroup)&&(!query||note.search.includes(query));visibility[i]=matches?1:.035;if(matches)visibleCount++;});
  geometry.attributes.aVisible.needsUpdate=true;
  visibleEdges=0;
  model.edges.forEach((edge,i)=>{const show=visibility[edge.a]===1&&visibility[edge.b]===1;if(show)visibleEdges++;for(let j=0;j<6;j++)lineColors[i*6+j]=show?lineBase[i*6+j]:0;});
  lineGeometry.attributes.color.needsUpdate=true;
  setText('viewTitle',query?'Memórias encontradas':activeGroup||'Toda a memória');
  setText('viewSubtitle',query?fmt(visibleCount)+' notas correspondem à busca.':activeGroup?fmt(visibleCount)+' notas conectadas neste grupo.':'Dois hemisférios. Um sistema conectado.');
  setText('visibleNotes',fmt(visibleCount)+' notas');setText('edgeCount',fmt(visibleEdges));setText('caption',fmt(visibleCount)+' notas visíveis · '+fmt(visibleEdges)+' caminhos');
  if(selected>=0&&visibility[selected]!==1)clearSelection();refreshFlow();invalidate();
}
function clearSelection(){selected=-1;uniforms.uSelected.value=-1;selectedMask.clear();selectedLines.visible=false;$('selection').hidden=true;$('emptySelection').hidden=false;lineMaterial.opacity=lineOpacity();invalidate();}
function safeFileURL(path){
  if(!/^[A-Z]:[\\/]/i.test(path))return null;
  return 'file:///'+path.replaceAll('\\','/').split('/').map((part,i)=>i===0?part:encodeURIComponent(part)).join('/');
}
function selectNote(id){
  const note=model.notes[id];if(!note)return false;
  if(visibility[id]!==1){activeGroup=null;query='';$('filter').value='';applyFilter();renderList();}
  clearRoute();selected=id;uniforms.uSelected.value=id;selectedMask.clear();selectedMask.add(id);
  $('emptySelection').hidden=true;$('selection').hidden=false;
  setText('noteGroup',note.group);$('noteGroup').style.color='#'+colors.get(note.group).getHexString();
  selectedMaterial.color.copy(colors.get(note.group)).lerp(new THREE.Color(0xffffff),.25);setText('noteTitle',note.title);setText('noteFolder',note.folder);
  const date=new Date(note.modified);setText('noteDate',Number.isNaN(date.getTime())?'Data não informada':date.toLocaleDateString('pt-BR'));
  $('noteTags').replaceChildren();for(const tag of note.tags.slice(0,12)){const span=document.createElement('span');span.textContent=tag.startsWith('#')?tag:'#'+tag;$('noteTags').append(span);}
  const url=safeFileURL(note.path);if(url)$('openNote').href=url;else $('openNote').removeAttribute('href');
  $('openNote').title=note.relativePath||note.path;
  setText('copyPath','Copiar caminho');
  const related=model.adjacency[id].map(edgeId=>model.edges[edgeId]);
  const coords=[];$('relatedList').replaceChildren();
  for(const edge of related){const other=edge.a===id?edge.b:edge.a;selectedMask.add(other);coords.push(...model.positions.subarray(id*3,id*3+3),...model.positions.subarray(other*3,other*3+3));}
  selectedGeometry.dispose();selectedGeometry.setAttribute('position',new THREE.Float32BufferAttribute(coords,3));selectedGeometry.computeBoundingSphere();
  selectedLines.visible=$('connections').checked;lineMaterial.opacity=.06;
  setText('relatedCount',fmt(related.length));
  for(const edge of related.slice(0,7)){
    const other=edge.a===id?edge.b:edge.a,button=document.createElement('button'),small=document.createElement('small');
    button.textContent=model.notes[other].title;small.textContent=edge.type==='sinapse'?'Sinapse regional':edge.type==='cortical'?'Sinapse cortical':edge.type==='tag'?'Tag compartilhada':edge.type==='grupo'?'Mesmo grupo':'Mesma pasta';button.append(small);button.onclick=()=>{selectNote(other);focus(other);};$('relatedList').append(button);
  }
  if(!related.length){const p=document.createElement('p');p.className='no-results';p.textContent='Nenhuma relação disponível neste índice.';$('relatedList').append(p);}
  setText('caption',note.title+' · '+fmt(related.length)+' caminhos diretos');invalidate(true);return true;
}
function clearRoute(){routeState=null;routeLine.visible=false;signal.visible=false;routeMaterial.color.set(0xffce87);signalMaterial.color.set(0xffe4b7);setText('routeStatus','');invalidate();}
function resolveGroup(text){const q=Model.normalize(text).trim();if(!q)return null;return groupNames.find(g=>Model.normalize(g)===q)||groupNames.find(g=>Model.normalize(g).includes(q))||model.notes.find(n=>Model.normalize(n.folder).includes(q))?.group||null;}
function playRouteConsult(fromText,toText){
  clearRoute();const from=resolveGroup(fromText),to=resolveGroup(toText);
  if(!from||!to){setText('routeStatus','Escolha dois grupos existentes.');return false;}
  const ids=Model.route(model,from,to);
  if(!ids||ids.length<2){setText('routeStatus','Não há um caminho registrado entre esses grupos neste índice.');return false;}
  activeGroup=null;query='';$('filter').value='';clearSelection();applyFilter();renderList();setAuto(false);home();
  $('routeFrom').value=from;$('routeTo').value=to;
  const pos=[];for(const id of ids)pos.push(...model.positions.subarray(id*3,id*3+3));
  routeGeometry.dispose();routeGeometry.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));routeGeometry.computeBoundingSphere();
  routeState={ids,start:performance.now(),duration:Math.max(1800,Math.min(6000,ids.length*190)),running:!reduced};
  routeGeometry.setDrawRange(0,reduced?ids.length:0);routeLine.visible=$('connections').checked;signal.visible=!reduced&&$('connections').checked;
  setText('routeStatus',fmt(ids.length)+' notas · '+fmt(ids.length-1)+' relações. O caminho dourado percorre a organização do índice.');
  setText('caption',from+' → '+to);invalidate(true);return true;
}
function setAuto(value){auto=value;controls.autoRotate=value;$('rotate').setAttribute('aria-pressed',String(value));invalidate(true);}
function playSynapse(ids,label,duration=820){
  if(!ids||ids.length!==2)return false;
  const pos=[];
  for(const id of ids)pos.push(...model.positions.subarray(id*3,id*3+3));
  routeGeometry.dispose();routeGeometry.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));routeGeometry.computeBoundingSphere();
  routeMaterial.color.set(0x75fff4);signalMaterial.color.set(0xd5fffd);
  routeState={ids,start:performance.now(),duration,running:!reduced,search:true};
  routeGeometry.setDrawRange(0,reduced?ids.length:0);routeLine.visible=$('connections').checked;signal.visible=!reduced&&$('connections').checked;
  setText('caption',label);invalidate(true);return true;
}
function playSearchSynapse(matches){
  if(query.length<2||matches.length<2)return false;
  const first=matches[0];
  const opposite=matches.find(note=>note.id!==first.id&&(note.id%2)!==(first.id%2)&&note.group===first.group)
    ||matches.find(note=>note.id!==first.id&&(note.id%2)!==(first.id%2));
  return opposite&&playSynapse([first.id,opposite.id],'Busca: '+first.title+' ↔ '+opposite.title);
}
function routeBetweenIds(from,to){
  const previous=new Int32Array(N).fill(-2),queue=new Int32Array(N);let head=0,tail=0;
  previous[from]=-1;queue[tail++]=from;
  while(head<tail){
    const id=queue[head++];if(id===to)break;
    for(const edgeId of model.adjacency[id]){const edge=model.edges[edgeId],next=edge.a===id?edge.b:edge.a;if(visibility[next]!==1||previous[next]!==-2)continue;previous[next]=id;queue[tail++]=next;}
  }
  if(previous[to]===-2)return null;
  const path=[];for(let id=to;id>=0;id=previous[id])path.push(id);return path.reverse();
}
function demoSynapsePath(){
  const candidates=[...model.groups.values()].map(group=>({group,left:group.ids.filter(id=>visibility[id]===1&&!(id%2)),right:group.ids.filter(id=>visibility[id]===1&&id%2)}))
    .filter(entry=>entry.left.length>3&&entry.right.length>3).sort((a,b)=>Math.min(b.left.length,b.right.length)-Math.min(a.left.length,a.right.length));
  for(const entry of candidates.slice(0,16)){
    for(const fraction of [.16,.29,.43]){
      const from=entry.left[Math.floor(entry.left.length*fraction)],to=entry.right[Math.floor(entry.right.length*(1-fraction))],path=routeBetweenIds(from,to);
      if(path?.length>=7)return path;
    }
  }
  const visible=model.notes.filter(note=>visibility[note.id]===1),from=visible.find(note=>!(note.id%2)),to=visible.find(note=>note.id!==from?.id&&(note.id%2)!==(from?.id%2));
  return from&&to?routeBetweenIds(from.id,to.id)||[from.id,to.id]:null;
}
function testSynapse(){
  clearRoute();
  const path=demoSynapsePath();
  if(!path||path.length<2){setText('caption','Não há dois pontos visíveis para testar a sinapse.');return false;}
  return playSynapse(path,'Sinapse demonstrativa · '+fmt(path.length)+' neurônios em sequência',Math.max(2200,Math.min(5200,path.length*190)));
}
function triggerBrainPulse(){
  if(reduced){setText('caption','Pulso neural disponível quando as animações estiverem ativas.');return false;}
  brainPulse={start:performance.now(),duration:1900};uniforms.uGlobalPulse.value=-.12;
  setText('caption','Pulso neural propagando por todo o cérebro…');invalidate(true);return true;
}
function search(){
  clearTimeout(searchTimer);query=Model.normalize($('filter').value.trim());clearRoute();clearSelection();applyFilter();renderList();
  const matches=query?model.notes.filter(note=>(!activeGroup||note.group===activeGroup)&&note.search.includes(query)):[];
  playSearchSynapse(matches);
}
$('filter').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(search,130);});
$('clearFilter').onclick=()=>{clearTimeout(searchTimer);activeGroup=null;query='';$('filter').value='';clearRoute();clearSelection();applyFilter();renderList();};
$('home').onclick=()=>{setAuto(false);home();};$('topView').onclick=()=>{setAuto(false);home(true);};$('rotate').onclick=()=>setAuto(!auto);
$('focusNote').onclick=()=>{if(selected>=0)focus(selected);};
$('copyPath').onclick=async()=>{
  if(selected<0)return;const text=model.notes[selected].path||model.notes[selected].relativePath;
  try {await navigator.clipboard.writeText(text);setText('copyPath','Caminho copiado');}
  catch{const input=document.createElement('textarea');input.value=text;input.style.position='fixed';input.style.opacity='0';document.body.append(input);input.select();const ok=document.execCommand('copy');input.remove();setText('copyPath',ok?'Caminho copiado':'Não foi possível copiar');}
};
$('connections').onchange=()=>{const enabled=$('connections').checked;lines.visible=enabled;selectedLines.visible=enabled&&selected>=0;routeLine.visible=enabled&&!!routeState;signal.visible=enabled&&!!routeState?.running;syncFlow();invalidate();};
$('density').oninput=()=>{lineMaterial.opacity=lineOpacity();invalidate();};
$('animate').checked=animating;$('animate').onchange=()=>{animating=$('animate').checked;uniforms.uPulse.value=animating?1:0;syncFlow();invalidate();};
$('brainPulse').onclick=triggerBrainPulse;
$('testSynapse').onclick=testSynapse;
$('libraryToggle').onclick=()=>{const open=$('libraryToggle').getAttribute('aria-expanded')!=='true';$('libraryToggle').setAttribute('aria-expanded',String(open));document.querySelector('.library').classList.toggle('open',open);};
for(const name of groupNames)for(const id of ['routeFrom','routeTo']){const option=document.createElement('option');option.value=name;option.textContent=name;$(id).append(option);}
$('routeTo').selectedIndex=Math.min(1,groupNames.length-1);$('routeBtn').disabled=!N;
$('routeBtn').onclick=()=>playRouteConsult($('routeFrom').value,$('routeTo').value);
window.playRouteConsult=playRouteConsult;

const raycaster=new THREE.Raycaster(),pointer=new THREE.Vector2();let down=null,dragging=false;
function pick(event){
  const rect=renderer.domElement.getBoundingClientRect();pointer.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1);
  raycaster.setFromCamera(pointer,camera);raycaster.params.Points.threshold=camera.position.distanceTo(controls.target)*.0065;
  const hits=raycaster.intersectObject(cloud);let best=null,bestScore=Infinity;
  for(const hit of hits){
    if(visibility[hit.index]!==1)continue;
    vector.fromArray(model.positions,hit.index*3).project(camera);
    const dx=(vector.x-pointer.x)*rect.width*.5,dy=(vector.y-pointer.y)*rect.height*.5,px=Math.hypot(dx,dy);
    if(px>9)continue;
    const score=px+hit.distance*.04;if(score<bestScore){bestScore=score;best=hit.index;}
  }
  return best;
}
renderer.domElement.addEventListener('pointerdown',e=>{down={x:e.clientX,y:e.clientY};dragging=false;});
renderer.domElement.addEventListener('pointermove',e=>{
  if(down&&Math.hypot(e.clientX-down.x,e.clientY-down.y)>5)dragging=true;
  clearTimeout(hoverTimer);$('tooltip').hidden=true;if(e.buttons||dragging)return;
  hoverTimer=setTimeout(()=>{
    const id=pick(e);if(id===null)return;
    $('tooltip').textContent=model.notes[id].title;const rect=container.getBoundingClientRect();
    $('tooltip').style.left=Math.min(canvasWidth-235,Math.max(5,e.clientX-rect.left+14))+'px';$('tooltip').style.top=Math.min(canvasHeight-40,e.clientY-rect.top+14)+'px';$('tooltip').hidden=false;
  },150);
});
renderer.domElement.addEventListener('pointerup',e=>{if(down&&!dragging&&Math.hypot(e.clientX-down.x,e.clientY-down.y)<=5){const id=pick(e);if(id!==null)selectNote(id);else clearSelection();}down=null;dragging=false;});
renderer.domElement.addEventListener('pointercancel',()=>{down=null;dragging=false;});
renderer.domElement.addEventListener('pointerleave',()=>{clearTimeout(hoverTimer);$('tooltip').hidden=true;});
addEventListener('keydown',event=>{
  if(/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName))return;
  if(event.key==='/'){event.preventDefault();$('filter').focus();}
  else if(event.key==='0')home();else if(event.key==='Escape'){$('clearFilter').click();home();}
  else if(event.key.toLowerCase()==='r')playRouteConsult($('routeFrom').value,$('routeTo').value);
});
document.addEventListener('visibilitychange',()=>{if(document.hidden){clearTimeout(timer);timer=0;cancelAnimationFrame(raf);raf=0;}else{lastTime=performance.now();invalidate();}});
renderer.domElement.addEventListener('webglcontextlost',event=>{event.preventDefault();paused=true;clearTimeout(timer);timer=0;cancelAnimationFrame(raf);raf=0;fail('O navegador interrompeu a renderização 3D. Recarregue para retomar. Suas notas permanecem no índice.');});

// Adjacent local scripts work on file:// without fetch permissions or a server.
// Only the tiny activity file is reloaded, never the note index.
let activityScript=null,activityTimeout=0;
function pollActivity(){
  if(disposed||paused||document.hidden||activityScript)return;
  const script=document.createElement('script');activityScript=script;
  const release=()=>{clearTimeout(activityTimeout);script.remove();if(activityScript===script)activityScript=null;};
  script.onload=()=>{readActivity(window.JARVIS_BRAIN_ACTIVITY);release();};script.onerror=release;
  script.src='memory/brain_activity.js?t='+Date.now();script.async=true;
  activityTimeout=setTimeout(release,2500);document.head.appendChild(script);
}
const activityPoll=setInterval(pollActivity,2000);

// External Jarvis route triggers are supported on HTTP. File pages never poll fetch().
let lastTrigger='',triggerBusy=false,triggerController=null;
const routePoll=/^https?:$/.test(location.protocol)?setInterval(async()=>{
  if(document.hidden||triggerBusy)return;triggerBusy=true;triggerController=new AbortController();const timeout=setTimeout(()=>triggerController?.abort(),2200);
  try{const response=await fetch('memory/route_anim_trigger.json',{cache:'no-store',signal:triggerController.signal});if(!response.ok)return;const data=await response.json(),key=String(data.timestamp)+data.origin+data.destination;if(data.event==='route_consult'&&key!==lastTrigger){lastTrigger=key;playRouteConsult(data.origin,data.destination);}}catch{}finally{clearTimeout(timeout);triggerBusy=false;triggerController=null;}
},3000):null;
function dispose(){disposed=true;clearInterval(activityPoll);clearTimeout(activityTimeout);activityScript?.remove();activityScript=null;clearTimeout(timer);cancelAnimationFrame(raf);clearTimeout(searchTimer);clearTimeout(hoverTimer);clearInterval(routePoll);triggerController?.abort();resizeObserver.disconnect();controls.dispose();scene.traverse(object=>{object.geometry?.dispose();if(object.material)object.material.dispose();});renderer.dispose();}
addEventListener('pagehide',event=>{if(!event.persisted)dispose();});

const indexedTotal=Math.max(N,Number(model.indexedTotal)||0);
setText('total',fmt(indexedTotal));const date=new Date(model.updated);setText('updated',Number.isNaN(date.getTime())?'Índice carregado':'Índice de '+date.toLocaleDateString('pt-BR'));
renderList();applyFilter();$('loading').hidden=true;
if(!N){setText('caption','O índice está vazio. Reconstrua o mapa de memória no Jarvis.');setText('viewSubtitle','Nenhuma nota disponível neste índice.');}
// Diagnostics contain counts only, never personal note content.
window.JarvisBrain={
  diagnostics:()=>({ready:!disposed,notes:N,points:geometry.attributes.position.count,groups:groupNames.length,edges:model.edges.length,visibleNotes:visibleCount,visibleEdges,selected,routeLength:routeState?.ids.length||0,routeRunning:!!routeState?.running,drawCalls:renderer.info.render.calls,geometryCount:renderer.info.memory.geometries,frameCount,fps,pixelRatio:renderer.getPixelRatio(),width:canvasWidth,height:canvasHeight,softwareRenderer:software,networkPolling:!!routePoll,renderer:rendererName,rotation:auto,paused,animating,uniqueGroupColors:usedColors.size,readingActive:!!reading,readingPulse:uniforms.uRead.value,readingRevision:String(lastReadingRevision),flowRunning:flowEnabled&&flowLights.visible&&!paused&&!document.hidden,flowAge,flowHops,flowHeads:flowWalkers.length,flowParticles:flowWalkers.length*flowSamples,flowCapacity,flowVisible:flowLights.visible,flowPositionSum:Math.round(flowPositions.reduce((sum,value,i)=>sum+value*(i+1),0)*1000)/1000}),
  activate,readActivity,selectNote,clearSelection,reset:()=>{$('clearFilter').click();home();},playRouteConsult,
  setPaused:value=>{paused=!!value;if(paused){clearTimeout(timer);timer=0;cancelAnimationFrame(raf);raf=0;}else{lastTime=performance.now();invalidate();}},
  screenPoint:id=>{if(!model.notes[id])return null;const rect=renderer.domElement.getBoundingClientRect();const p=point(id).project(camera);return {x:rect.left+(p.x+1)*rect.width/2,y:rect.top+(1-p.y)*rect.height/2};}
};
pollActivity();activate();invalidate();
}catch(error){fail(error.message||String(error));console.error('Brain view:',error);}
})();
