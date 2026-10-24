import {MusicStudio} from './music-studio.js';
import {LibrasPanel} from './libras.js';
import {Sketchbook} from './sketchbook.js';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { GestureController } from './gestures.js';
const $=id=>document.getElementById(id), clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
const mix=(a,b,s,dt)=>THREE.MathUtils.lerp(a,b,1-Math.exp(-s*dt));
let bridge=null, nativeVisible=true, nativeFocused=true, ready=false, faceVisible=true, disposed=false;
let status={state:'LISTENING',speaking:false,muted:false,mode:'normal'};
let signal={ai:0,user:0,bands:[],at:0,userAt:0}, energy=0, voicePulse=0, speed=.06;
let lastTime=0, elapsed=0, nextBlink=3.2, blinkStart=-10, blink=1, interactionsUntil=0;
let nextScan=5.5, scanUntil=0, scanYaw=0;
let sleepingFrameDrawn=false;
let drawCount=0, frameMs=0, lastFrame=0, voiceRotation=null, maskLights=true, eyePanelMode='auto', handPoseTarget=null, armPoseTarget=null;
const armBones={}, armRest={}, palmAnchors=[];
const palette={normal:0x62dfff,evil:0xff2020,good:0xffffff,bom:0xffffff,cute:0xffffff,sentinel:0x49edbf};
let mode='normal', drawColor=new THREE.Color(palette.normal), toastTimer;
const isGoodMode=()=>mode==='good'||mode==='bom'||mode==='cute';
function toast(text){$('toast').textContent=text;$('toast').classList.add('visible');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').classList.remove('visible'),4200);}
function fail(message){$('loading').style.display='flex';$('loading').textContent=message;if(bridge)bridge.reportError(message);}
function updateBrief(){
 const s=status.state,ai=performance.now()-signal.at<220?signal.ai:0,user=performance.now()-signal.userAt<160?signal.user:0,level=Math.round(clamp(Math.max(ai,user))*100);
 const label=status.speaking?'RESPOSTA EM CURSO':({SLEEPING:'SISTEMA SUSPENSO',THINKING:'ANÁLISE ATIVA',PROCESSING:'ANÁLISE ATIVA',LISTENING:'ESCUTA ATIVA',INITIALISING:'INICIALIZANDO',IDLE:'EM ESPERA',ERROR:'ATENÇÃO NECESSÁRIA'}[s]||'EM ESPERA');
 $('brief-state').textContent=label;$('brief-detail').textContent=status.muted&&!status.speaking?'MICROFONE PAUSADO':status.speaking?'SÍNTESE E ÁUDIO AO VIVO':s==='THINKING'||s==='PROCESSING'?'ORGANIZANDO CONTEXTO LOCAL':'AGUARDANDO COMANDO';
 $('brief-core').textContent=s==='ERROR'?'NÚCLEO EM ALERTA':s==='SLEEPING'?'NÚCLEO EM REPOUSO':'NÚCLEO ESTÁVEL';$('brief-signal').textContent=String(level).padStart(2,'0')+'%';
 document.body.dataset.briefState=(status.speaking?'speaking':s).toLowerCase();
}
window.addEventListener('error',e=>{if(!ready)fail('Não foi possível iniciar o visual 3D.');});
const graphicsMode=new URLSearchParams(location.search).get('graphics')||'hardware';
const compatibleGraphics=graphicsMode==='compat';
let renderer;
try{renderer=new THREE.WebGLRenderer({antialias:true,alpha:true,powerPreference:'high-performance'});}catch(e){fail('O driver de vídeo não disponibilizou WebGL.');throw e;}
const graphicsContext=renderer.getContext(),graphicsInfo=graphicsContext.getExtension('WEBGL_debug_renderer_info');
const graphicsRenderer=graphicsInfo?graphicsContext.getParameter(graphicsInfo.UNMASKED_RENDERER_WEBGL):'';
const softwareRenderer=compatibleGraphics||/SwiftShader|Software|Microsoft Basic Render Driver|llvmpipe/i.test(graphicsRenderer);
const maxFps=softwareRenderer?30:45,idleFps=softwareRenderer?24:30,maxPixels=900000;
renderer.setPixelRatio(Math.min(devicePixelRatio,1));renderer.setClearColor(0x000000,0);
renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.0;
$('viewport').appendChild(renderer.domElement);
renderer.domElement.addEventListener('webglcontextlost',e=>{e.preventDefault();fail('O driver interrompeu o visual 3D.');});
const scene=new THREE.Scene(), camera=new THREE.PerspectiveCamera(35,1,.05,50);
camera.position.set(0,.90,3.15);
const controls=new OrbitControls(camera,renderer.domElement);controls.target.set(0,.90,0);controls.enableDamping=true;controls.dampingFactor=.09;controls.minDistance=1.15;controls.maxDistance=13;controls.enablePan=true;
const cursor={x:0,y:0,inside:false,dragging:false};
function clearCursor(){cursor.inside=false;cursor.x=0;cursor.y=0;}
function trackCursor(event){
 if(event.pointerType!=='mouse'||event.buttons)return;
 const rect=renderer.domElement.getBoundingClientRect();
 if(!rect.width||!rect.height)return;
 cursor.x=clamp((event.clientX-rect.left)/rect.width*2-1,-1,1);
 cursor.y=clamp((event.clientY-rect.top)/rect.height*2-1,-1,1);
 cursor.inside=true;cursor.lastMove=performance.now();
}
renderer.domElement.addEventListener('pointermove',trackCursor);
renderer.domElement.addEventListener('pointerleave',clearCursor);
renderer.domElement.addEventListener('pointercancel',clearCursor);
window.addEventListener('blur',()=>{nativeFocused=false;clearCursor();});
window.addEventListener('focus',()=>{nativeFocused=true;sleepingFrameDrawn=false;});
controls.addEventListener('start',()=>{voiceRotation=null;handPoseTarget=null;gestures.suspend(900);cursor.dragging=true;interactionsUntil=Infinity;});
controls.addEventListener('end',()=>{gestures.suspend(300);cursor.dragging=false;interactionsUntil=performance.now()+300;});
const pmrem=new THREE.PMREMGenerator(renderer), env=new RoomEnvironment();
const environment=pmrem.fromScene(env,.035);scene.environment=environment.texture;env.dispose();pmrem.dispose();
scene.add(new THREE.HemisphereLight(0xbfefff,0x1c0f07,1.2));
for(const [color,power,pos] of [[0xe3f8ff,2.8,[-3,4,5]],[0x39b9ff,1.5,[3,-1,3]],[0xff9654,2,[2,2,-2]]]){let l=new THREE.DirectionalLight(color,power);l.position.set(...pos);scene.add(l);}
const root=new THREE.Group();scene.add(root);
const rig=new THREE.Group();root.add(rig);
const armor=new THREE.Group(), head=new THREE.Group(), reactor=new THREE.Group(), outerRotor=new THREE.Group(), innerRotor=new THREE.Group();
rig.add(armor,head,reactor);head.position.y=.76;reactor.position.set(0,-.704,.82);reactor.scale.setScalar(.215);reactor.add(outerRotor,innerRotor);
const cyanMaterials=[], redMaterials=[], energyMaterials=[], eyes=[], maskLightMeshes=[], palmGlows=[];
const holoUniform={value:0},holoColor={value:new THREE.Color().setRGB(.018,.12,.18)};
const armorEyeColor={value:new THREE.Color(0x169cff)},armorEyeMix={value:1},armorEyePower={value:.32};
function setHologram(on){holoUniform.value=on?1:0;$('material-button').setAttribute('aria-pressed',String(!!on));$('material-button').textContent=on?'Holo':'Metal';}
const glowCanvas=document.createElement('canvas');glowCanvas.width=128;glowCanvas.height=128;let gc=glowCanvas.getContext('2d'),gg=gc.createRadialGradient(64,64,2,64,64,64);gg.addColorStop(0,'rgba(80,216,255,.7)');gg.addColorStop(.2,'rgba(32,166,247,.24)');gg.addColorStop(1,'rgba(0,70,150,0)');gc.fillStyle=gg;gc.fillRect(0,0,128,128);let glowTexture=new THREE.CanvasTexture(glowCanvas);
const neutralCanvas=document.createElement('canvas');neutralCanvas.width=neutralCanvas.height=128;const nc=neutralCanvas.getContext('2d'),ng=nc.createRadialGradient(64,64,2,64,64,64);ng.addColorStop(0,'rgba(255,255,255,.7)');ng.addColorStop(.2,'rgba(255,255,255,.24)');ng.addColorStop(1,'rgba(255,255,255,0)');nc.fillStyle=ng;nc.fillRect(0,0,128,128);const neutralGlowTexture=new THREE.CanvasTexture(neutralCanvas);
function glow(parent,x,y,z,sx,sy,opacity){let mat=new THREE.SpriteMaterial({map:glowTexture,color:0xffffff,transparent:true,opacity,depthWrite:false,blending:THREE.AdditiveBlending});let o=new THREE.Sprite(mat);o.position.set(x,y,z);o.scale.set(sx,sy,1);parent.add(o);return o;}
let jaw=new THREE.Group();
const coreGlow=glow(rig,0,-.704,.99,1.0,1.0,.45);
const technical=new THREE.Group();rig.add(technical);
for(const [radius,count] of [[.307,64],[.326,80]]){
 let coords=[];for(let i=0;i<count;i++){let a=i/count*Math.PI*2,r2=radius+(i%5===0?.018:.007);coords.push(Math.cos(a)*radius,Math.sin(a)*radius-.704,.79,Math.cos(a)*r2,Math.sin(a)*r2-.704,.79);}
 let geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(coords,3));let mat=new THREE.LineBasicMaterial({color:0x57c8ef,transparent:true,opacity:.45});cyanMaterials.push(mat);technical.add(new THREE.LineSegments(geo,mat));
}
let armorReady=false,reactorReady=false,fullArmorLoaded=false;
function modelReady(){if(armorReady&&reactorReady){applyTheme();ready=true;$('loading').style.display='none';if(bridge)bridge.ready();}}
new GLTFLoader().load('./armor-full-v5.glb',gltf=>{
 // The renderable surfaces and articulations are Blender meshes, never an image billboard.
 for(const parent of [head,armor]){for(const o of [...parent.children])parent.remove(o);}
 eyes.length=0;maskLightMeshes.length=0;redMaterials.length=0;
 const helmet=gltf.scene.getObjectByName('Helmet'),body=gltf.scene.getObjectByName('Armor');
 if(!body){fail('A nova armadura 3D não contém o corpo.');return;}
 fullArmorLoaded=!helmet;
 const armorSurface=fullArmorLoaded?(body.getObjectByProperty('isSkinnedMesh',true)||body.getObjectByProperty('isMesh',true)):body;
 if(fullArmorLoaded&&!armorSurface?.isMesh){fail('A nova armadura 3D não contém a superfície renderizável.');return;}
 if(helmet){head.add(helmet);helmet.position.set(0,0,0);}
 armor.add(body);
 // The full asset is centered in the existing camera rig; no added geometry or shadows.
 if(fullArmorLoaded){
  body.position.y=-.94;head.visible=false;technical.visible=false;coreGlow.visible=false;
  for(const name of ['LeftUpperArm','LeftForearm','LeftHand','RightUpperArm','RightForearm','RightHand']){
   const bone=body.getObjectByName(name);if(bone){armBones[name]=bone;armRest[name]=bone.quaternion.clone();}
  }
  for(const [boneName,sign] of [['LeftHand',-1],['RightHand',1]]){
   const bone=armBones[boneName];if(!bone)continue;
   // Local coordinates sampled from the blue palm lens in the rig. This is only
   // a soft visual halo; there is no added reactor mesh or floating geometry.
   const palmGlow=glow(bone,sign*.185,.0904,-.125,.115,.115,.30);
   palmGlow.material.color.setHex(0x3dbdff);palmGlows.push(palmGlow);
  }
  body.updateMatrixWorld(true);
 }
 const meshes=[];gltf.scene.updateMatrixWorld(true);for(const root of helmet?[helmet,body]:[body])root.traverse(o=>{if(o.isMesh)meshes.push(o);});
 for(const o of meshes){
  o.material=o.material.clone();
  // Use the armor's existing normal/UV maps to define plate junctions. These are
  // scalar material tweaks only: no extra textures, geometry, lights, or draw calls.
  o.material.metalness=Math.max(.48,o.material.metalness||0);
  o.material.roughness=Math.min(.38,Math.max(.30,o.material.roughness||.34));
  o.material.envMapIntensity=.44;
  if(o.material.normalMap)o.material.normalScale.set(.82,.82);
  if(o.material.aoMap)o.material.aoMapIntensity=Math.max(.72,o.material.aoMapIntensity||0);
  if(o.name.startsWith('Eye_')||o.name.startsWith('Eye ')){
   const center=new THREE.Box3().setFromBufferAttribute(o.geometry.attributes.position).getCenter(new THREE.Vector3());
   o.geometry=o.geometry.clone();o.geometry.translate(-center.x,-center.y,-center.z);o.position.add(center);
   const parent=o.parent,eyeGroup=new THREE.Group();const backing=new THREE.Mesh(o.geometry,new THREE.MeshBasicMaterial({color:0x01090e}));backing.position.copy(o.position);backing.position.z-=.004;parent.add(backing);eyeGroup.position.copy(o.position);parent.add(eyeGroup);eyeGroup.attach(o);o.position.set(0,0,0);
   const [glowWidth,glowHeight]=fullArmorLoaded?[.14,.055]:[.38,.17];const sprite=glow(eyeGroup,0,0,.015,glowWidth,glowHeight,.70);eyes.push({group:eyeGroup,mesh:o,glow:sprite});o.material.emissive.setHex(0x168bff);o.material.emissiveIntensity=1.5;sprite.material.color.setHex(0x329aff);
  }else if(o.name.startsWith('Mask_Light_')){
   o.material.emissive.setHex(0x169aff);o.material.emissiveIntensity=1.1;maskLightMeshes.push(o);
  }else if(o.name==='Chest_Reactor'||o.name.startsWith('Palm_Reactor_')){
   o.material.emissive.setHex(0x21aee8);o.material.emissiveIntensity=1.8;energyMaterials.push(o.material);
  }else{
   o.material.onBeforeCompile=shader=>{
    shader.uniforms.uJarvisHolo=holoUniform;shader.uniforms.uJarvisHoloColor=holoColor;shader.uniforms.uJarvisEyeColor=armorEyeColor;shader.uniforms.uJarvisEyeMix=armorEyeMix;shader.uniforms.uJarvisEyePower=armorEyePower;
    shader.vertexShader='varying vec3 vJarvisLocalPosition;\n'+shader.vertexShader;
    shader.vertexShader=shader.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\nvJarvisLocalPosition=position;');
    shader.fragmentShader='uniform vec3 uJarvisHoloColor;uniform float uJarvisHolo;uniform vec3 uJarvisEyeColor;uniform float uJarvisEyeMix;uniform float uJarvisEyePower;varying vec3 vJarvisLocalPosition;\n'+shader.fragmentShader;
    shader.fragmentShader=shader.fragmentShader.replace('#include <map_fragment>','#include <map_fragment>\nfloat jarvisLuma=dot(diffuseColor.rgb,vec3(.22,.70,.08));diffuseColor.rgb=mix(diffuseColor.rgb,uJarvisHoloColor*(.55+jarvisLuma*2.0),uJarvisHolo);\nfloat jarvisEyeX=abs(vJarvisLocalPosition.x);float jarvisEyeRegion=step(.020,jarvisEyeX)*step(jarvisEyeX,.080)*step(1.740,vJarvisLocalPosition.y)*step(vJarvisLocalPosition.y,1.775)*step(.075,vJarvisLocalPosition.z)*step(vJarvisLocalPosition.z,.145);');
    shader.fragmentShader=shader.fragmentShader.replace('#include <emissivemap_fragment>','#include <emissivemap_fragment>\nfloat jarvisEyeSource=max(totalEmissiveRadiance.r,max(totalEmissiveRadiance.g,totalEmissiveRadiance.b));float jarvisEyeMask=jarvisEyeRegion*step(.055,jarvisEyeSource);diffuseColor.rgb=mix(diffuseColor.rgb,uJarvisEyeColor,jarvisEyeMask*uJarvisEyeMix);totalEmissiveRadiance=mix(totalEmissiveRadiance,uJarvisEyeColor*(uJarvisEyePower*4.0),jarvisEyeMask);');
   };o.material.customProgramCacheKey=()=> 'jarvis-hologram-eye-material-v1';
  }
 }
 jaw=helmet?.getObjectByName('Jaw')||jaw;
 if(fullArmorLoaded&&model){for(const node of reactorNodes){if(/solenoid|NurbsPath|Energy_outer/i.test(node.name))outerRotor.attach(node);else if(/HOleWheel|Holer|Torus001|Torus_001/i.test(node.name))innerRotor.attach(node);else model.attach(node);}model.traverse(o=>{if(o.isMesh)o.visible=true;});model.visible=true;reactor.visible=true;reactor.position.set(0,.500,.185);reactor.scale.setScalar(.055);}
 armorReady=true;modelReady();
},undefined,()=>fail('Não foi possível carregar a armadura 3D.'));
let model,reactorNodes=[];
new GLTFLoader().load('./reactor.glb',gltf=>{
 model=gltf.scene;reactor.add(model);model.updateMatrixWorld(true);
 const nodes=[];model.traverse(o=>{if(o.isMesh){nodes.push(o);o.frustumCulled=true;const mats=Array.isArray(o.material)?o.material:[o.material];for(const m of mats){if(m.emissive&&m.emissive.getHex()!==0&&m.emissiveIntensity>0){energyMaterials.push(m);m.emissive.setHex(0x21aee8);m.emissiveIntensity=1.8;}}}});
 reactorNodes=nodes;
 for(const o of nodes){if(/solenoid|NurbsPath|Energy_outer/i.test(o.name))outerRotor.attach(o);else if(/HOleWheel|Holer|Torus001|Torus_001/i.test(o.name))innerRotor.attach(o);}
 if(fullArmorLoaded){model.visible=true;reactor.visible=true;reactor.position.set(0,.500,.185);reactor.scale.setScalar(.055);}
 reactorReady=true;modelReady();
},undefined,e=>{console.error('Reactor asset failed',e);fail('Não foi possível carregar o modelo do reator.');});
function reset(){voiceRotation=null;handPoseTarget=null;armPoseTarget=null;clearCursor();rig.rotation.set(0,0,0);root.position.set(0,0,0);root.rotation.set(0,0,0);root.scale.setScalar(1);controls.target.set(0,.90,0);camera.position.set(0,.90,3.15);controls.update();gestures.reset();}
function setEye(value='auto'){const next=typeof value==='boolean'?(value?'blue':'white'):String(value).toLowerCase();if(!['auto','blue','white','off'].includes(next))return {ok:false,message:'Estado do olho inválido.'};eyePanelMode=next;sleepingFrameDrawn=false;return {ok:true,status:'completed',eye:eyePanelMode};}
const setEyePanel=setEye;
function control3D(command){
 if(status.state==='SLEEPING')return {ok:false,message:'Jarvis suspenso. Diga Jarvis, acorda.'};
 if(command.action==='eye'||command.action==='eye_panel')return setEye(command.mode);
 if(command.action==='mask_lights'){if(typeof command.enabled!=='boolean')return {ok:false,message:'Estado da iluminação inválido.'};maskLights=command.enabled;return {ok:true,status:'completed',maskLights,message:maskLights?'Iluminação da máscara acesa.':'Iluminação da máscara apagada.'};}
 if(command.action==='reset'){reset();return {ok:true,status:'completed',message:'Modelo 3D centralizado.'};}
 const axis=command.axis||'y',degrees=Number(command.degrees);
 if(command.action!=='rotate'||!['x','y','z'].includes(axis)||!Number.isFinite(degrees)||Math.abs(degrees)>3600)return {ok:false,message:'Rotação inválida.'};
 const from={x:root.rotation.x,y:root.rotation.y,z:root.rotation.z};
 const to=voiceRotation?{...voiceRotation.to}:{...from};to[axis]+=THREE.MathUtils.degToRad(degrees);
 const duration=clamp(Math.abs(degrees)*8,550,2400);
 handPoseTarget=null;gestures.suspend(duration+250);voiceRotation={from,to,started:performance.now(),duration};clearCursor();interactionsUntil=performance.now()+duration+250;
 toast(`Girando ${degrees}°`);
 return {ok:true,status:'rotating',axis,degrees,duration_ms:duration};
}
function updateVoiceRotation(now){
 if(!voiceRotation)return;
 const p=clamp((now-voiceRotation.started)/voiceRotation.duration),e=p*p*(3-2*p);
 for(const axis of ['x','y','z'])root.rotation[axis]=THREE.MathUtils.lerp(voiceRotation.from[axis],voiceRotation.to[axis],e);
 if(p>=1)voiceRotation=null;
}
function applyTheme(){
 const special=mode==='evil'||isGoodMode(),color=special?(palette[mode]||0xffffff):0x168bff;
 holoColor.value.setRGB(...(mode==='evil'?[.18,.005,.008]:mode==='cute'?[.16,.16,.16]:[.018,.12,.18]));
 cyanMaterials.forEach(m=>{m.userData.normalColor??=m.color.clone();mode==='normal'?m.color.copy(m.userData.normalColor):m.color.copy(drawColor);});
 energyMaterials.forEach(m=>m.emissive.copy(drawColor));
 for(const eye of eyes){eye.mesh.material.emissive.setHex(color);eye.glow.material.color.setHex(special?color:0x329aff);eye.glow.material.map=special?neutralGlowTexture:glowTexture;eye.glow.material.needsUpdate=true;}
 maskLightMeshes.forEach(o=>o.material.emissive.setHex(special?color:0x169aff));
 coreGlow.material.map=special?neutralGlowTexture:glowTexture;coreGlow.material.needsUpdate=true;
}
function setStatus(payload){if(payload.protocol)$('protocol-label').textContent=payload.protocol;status={...status,...payload};const s=status.state;if(s==='SLEEPING'){stopCamera();if(sketch.opened)sketch.toggle(false);if(libras.opened)libras.toggle(false);if(music.opened)music.toggle(false);voiceRotation=null;handPoseTarget=null;armPoseTarget=null;clearCursor();signal.ai=signal.user=0;}controls.enabled=s!=='SLEEPING'&&!sketch.opened&&!libras.opened&&!music.opened;let label=status.speaking?'Falando':({SLEEPING:'Suspenso · diga Jarvis, acorda',THINKING:'Processando',PROCESSING:'Processando',LISTENING:'Ouvindo',INITIALISING:'Inicializando',IDLE:'Em espera',ERROR:'Conexão interrompida'}[s]||'Em espera');if(status.muted&&!status.speaking)label='Microfone pausado';$('status').textContent=label;updateBrief();if(palette[status.mode]&&mode!==status.mode){mode=status.mode;drawColor.setHex(palette[mode]);applyTheme();}}
function setMetrics(p){const level=clamp(Number(p.level)||0);if(p.source==='ai'){signal.ai=level;signal.at=performance.now();signal.bands=(p.bands||[]).slice(0,14).map(x=>clamp(Number(x)||0));}else{signal.user=level;signal.userAt=performance.now();}updateBrief();}
function setFace(on){faceVisible=!!on;armor.visible=faceVisible;head.visible=faceVisible&&!fullArmorLoaded;technical.visible=faceVisible&&!fullArmorLoaded;reactor.visible=true;coreGlow.visible=!fullArmorLoaded||!faceVisible;if(fullArmorLoaded){reactor.position.set(0,faceVisible?.500:0,faceVisible?.185:0);reactor.scale.setScalar(faceVisible?.055:.86);}else{reactor.position.set(0,faceVisible?-.704:0,faceVisible?.82:0);reactor.scale.setScalar(faceVisible?.215:.86);}coreGlow.position.set(0,faceVisible?-.704:0,faceVisible?.99:.46);coreGlow.scale.setScalar(faceVisible?1.25:4);$('face-button').setAttribute('aria-pressed',String(faceVisible));$('face-button').textContent=faceVisible?'Armadura':'Reator';reset();}
const sketch=new Sketchbook({
 send:(id,action,payload)=>{if(!bridge)return false;bridge.sketchRequest(id,action,payload);return true;},
 requestCamera:()=>{if(!cameraActive)startCamera();else toast('Mão aberta reposiciona. Indicador apontado desenha.');},
 onToggle:on=>{if(on&&libras.opened)libras.toggle(false);if(on&&music.opened)music.toggle(false);handPoseTarget=null;voiceRotation=null;gestures.reset();controls.enabled=!on;clearCursor();},notify:toast
});
const libras=new LibrasPanel({
 send:(id,action,payload)=>{if(!bridge)return false;bridge.librasRequest(id,action,payload);return true;},
 submit:text=>{if(!bridge||status.state==='SLEEPING')return false;bridge.librasSubmit(text);return true;},
 requestCamera:startCamera,stopCamera,notify:toast,
 onToggle:on=>{gestures.inferencePaused=on;if(on){$('gesture-label').textContent='LIBRAS · enquadre mãos, rosto e tronco';const c=$('landmarks');c.getContext('2d').clearRect(0,0,c.width,c.height);}if(on&&sketch.opened)sketch.toggle(false);if(on&&music.opened)music.toggle(false);handPoseTarget=null;voiceRotation=null;gestures.reset();controls.enabled=!on&&!sketch.opened&&status.state!=='SLEEPING';clearCursor();}
});
const music=new MusicStudio({requestCamera:startCamera,notify:toast,onToggle:on=>{
 if(on){if(sketch.opened)sketch.toggle(false);if(libras.opened)libras.toggle(false);gestures.inferencePaused=false;}
 handPoseTarget=null;voiceRotation=null;gestures.reset();controls.enabled=!on&&!sketch.opened&&!libras.opened&&status.state!=='SLEEPING';clearCursor();
}});
const gestures=new GestureController({
 video:$('camera-video'),canvas:$('landmarks'),label:$('gesture-label'),
 onHands:(hands,labels)=>music.consumeHands(hands,labels)||libras.consumeHands(hands)||sketch.consumeHands(hands,labels)||consumeArmHands(hands),
 getPose:()=>({x:root.position.x,y:root.position.y,rx:root.rotation.x,ry:root.rotation.y,rz:root.rotation.z,scale:root.scale.x}),
 onGesture:change=>{voiceRotation=null;handPoseTarget={...change};interactionsUntil=performance.now()+400;},
 onRelease:()=>{handPoseTarget=null;armPoseTarget=null;},
 onError:msg=>{toast(msg);stopCamera();},onStatus:text=>{$('gesture-label').textContent=text;}
});
function updateHandPose(dt){
 if(!handPoseTarget)return;
 const p=handPoseTarget;
 root.position.x=mix(root.position.x,p.x,13,dt);root.position.y=mix(root.position.y,p.y,13,dt);
 root.rotation.x=mix(root.rotation.x,p.rx,13,dt);root.rotation.y=mix(root.rotation.y,p.ry,13,dt);root.rotation.z=mix(root.rotation.z,p.rz,13,dt);
 root.scale.setScalar(mix(root.scale.x,p.scale,13,dt));
}
function handCenter(hand){return {x:(hand[0].x+hand[9].x)/2,y:(hand[0].y+hand[9].y)/2};}
function openPalm(hand){const wrist=hand[0];return [8,12,16,20].filter(i=>Math.hypot(hand[i].x-wrist.x,hand[i].y-wrist.y)>.115).length>=3;}
function consumeArmHands(hands){
 if(!fullArmorLoaded||!cameraActive||hands.length<2||!hands.slice(0,2).every(openPalm))return false;
 const [screenLeft,screenRight]=hands.slice(0,2).map(handCenter).sort((a,b)=>a.x-b.x);
 const mapHand=(p,sign)=>{const lift=clamp((.76-p.y)*.82,-.08,.42),reach=clamp((p.x-.5)*.36,-.16,.16);return {upper:sign*(lift*.65+reach*.20),fore:sign*(.08+lift*.55),hand:sign*(reach*.30)};};
 armPoseTarget={left:mapHand(screenLeft,-1),right:mapHand(screenRight,1)};
 handPoseTarget=null;voiceRotation=null;$('gesture-label').textContent='2 palmas abertas · controlando braços';return true;
}
const armAxis=new THREE.Vector3(0,1,0),armWorld=new THREE.Matrix4(),armLocal=new THREE.Matrix4();
function updateArmPose(dt){
 if(!fullArmorLoaded||!Object.keys(armBones).length)return;
 const target=armPoseTarget||{left:{upper:0,fore:0,hand:0},right:{upper:0,fore:0,hand:0}};
 for(const [side,key] of [['Left','left'],['Right','right']])for(const [segment,field] of [['UpperArm','upper'],['Forearm','fore'],['Hand','hand']]){
  const name=side+segment,bone=armBones[name],rest=armRest[name];if(!bone||!rest)continue;
  const wanted=rest.clone().multiply(new THREE.Quaternion().setFromAxisAngle(armAxis,target[key][field]));bone.quaternion.slerp(wanted,1-Math.exp(-9*dt));
 }
 if(!palmAnchors.length)return;
 if(!armPoseTarget){for(const anchor of palmAnchors){anchor.emitter.position.copy(anchor.restPosition);anchor.emitter.quaternion.copy(anchor.restQuaternion);anchor.emitter.scale.copy(anchor.restScale);}return;}
 armor.updateMatrixWorld(true);
 for(const anchor of palmAnchors){armWorld.multiplyMatrices(anchor.bone.matrixWorld,anchor.offset);armLocal.copy(anchor.emitter.parent.matrixWorld).invert().multiply(armWorld);armLocal.decompose(anchor.emitter.position,anchor.emitter.quaternion,anchor.emitter.scale);}
}

let cameraActive=false,cameraPending=false;
async function startCamera(){if(status.state==='SLEEPING'||cameraActive||cameraPending)return;cameraPending=true;$('camera-button').disabled=true;try{if(bridge)await new Promise(resolve=>bridge.armCamera(resolve));cameraActive=await gestures.start();if(status.state==='SLEEPING'){stopCamera();return;}$('camera-panel').hidden=!cameraActive;$('camera-button').setAttribute('aria-pressed',String(cameraActive));$('help').textContent=cameraActive?'2 palmas abertas: controlar braços · 2 punhos: girar\nPinça: mover · Retire as mãos para soltar':'Mova o mouse para olhar · Arraste para girar · Role para zoom';}finally{cameraPending=false;$('camera-button').disabled=false;}}
function stopCamera(){music.cameraStopped();libras.cameraStopped();sketch.releaseHands();gestures.stop();cameraActive=false;$('camera-panel').hidden=true;$('camera-button').setAttribute('aria-pressed','false');$('help').textContent='Mova o mouse para olhar · Arraste para girar · Role para zoom';if(bridge)bridge.disarmCamera();}
$('music-button').onclick=()=>{if(status.state!=='SLEEPING')music.toggle();};$('libras-button').onclick=()=>{if(status.state!=='SLEEPING')libras.toggle();};$('sketch-button').onclick=()=>{if(status.state!=='SLEEPING')sketch.toggle();};$('material-button').onclick=()=>setHologram(!holoUniform.value);$('camera-button').onclick=()=>cameraActive?stopCamera():startCamera();$('reset-button').onclick=()=>{reset();gestures.reset();};$('face-button').onclick=()=>setFace(!faceVisible);$('briefing-button').onclick=()=>{if(status.state==='SLEEPING')return;bridge?.requestBriefing('daily');toast('Solicitando relatório local…');};$('expand-button').onclick=()=>{if(bridge)bridge.toggleExpanded();else document.documentElement.requestFullscreen?.();};
function resize(){sleepingFrameDrawn=false;let w=innerWidth,h=innerHeight;renderer.setPixelRatio(Math.min(devicePixelRatio,1,Math.sqrt(maxPixels/Math.max(1,w*h))));renderer.setSize(w,h);camera.aspect=w/h;camera.fov=w/h<.85?43:35;camera.updateProjectionMatrix();}
addEventListener('resize',resize);resize();
function animate(now){if(disposed)return;requestAnimationFrame(animate);if(document.hidden||!nativeVisible){lastTime=now;return;}if(status.state==='SLEEPING'){
  if(sleepingFrameDrawn)return;lastFrame=now;lastTime=now;energy=voicePulse=speed=0;blink=0;
  energyMaterials.forEach(m=>{m.emissive.setHex(0x000000);m.emissiveIntensity=0;});coreGlow.material.color.setHex(0x000000);coreGlow.material.opacity=0;
  palmGlows.forEach(g=>g.material.opacity=0);
  armorEyeColor.value.setHex(0x000000);armorEyeMix.value=1;armorEyePower.value=0;
  eyes.forEach(e=>{e.mesh.material.emissiveIntensity=0;e.mesh.material.color.setHex(0x01080f);e.glow.material.opacity=0;});
  maskLightMeshes.forEach(o=>{o.material.emissiveIntensity=0;o.material.color.setHex(0x01080f);});
  cyanMaterials.forEach(m=>m.opacity=0);$('energy-bar').style.width='0%';$('activity-label').textContent='SUSPENSO';$('signal-label').textContent='AGUARDANDO JARVIS, ACORDA';
  renderer.render(scene,camera);drawCount++;sleepingFrameDrawn=true;return;
 }
 sleepingFrameDrawn=false;
 // The panel covers the armor; keep its last image and leave time for hands/audio.
 if(sketch.opened||libras.opened||music.opened){lastTime=now;return;}
 const active=status.speaking||['THINKING','PROCESSING'].includes(status.state)||voiceRotation||handPoseTarget||cursor.dragging||now-(cursor.lastMove||-Infinity)<1200||(now-signal.at<220&&signal.ai>.012);
 const targetFps=nativeFocused?(active?maxFps:idleFps):2;
 if(now-lastFrame<1000/targetFps)return;let dt=clamp((now-(lastTime||now))/1000,.001,.08);lastTime=now;lastFrame=now;elapsed+=dt;updateVoiceRotation(now);updateHandPose(dt);updateArmPose(dt);
 let ai=now-signal.at<220?signal.ai:0,user=now-signal.userAt<160?signal.user:0;
 let speaking=status.speaking||ai>.012,thinking=['THINKING','PROCESSING'].includes(status.state),muted=!!status.muted,sleeping=muted&&!speaking,error=status.state==='ERROR';
 energy=mix(energy,Math.max(ai,user*.22),ai>energy?22:7,dt);voicePulse=mix(voicePulse,ai,ai>voicePulse?32:13,dt);
 const speechGlow=speaking?(.55+.45*(.5+.5*Math.sin(elapsed*13.5))):0;
 let breath=(Math.sin(elapsed*1.35)+1)*.5;
 speed=mix(speed,speaking?.30+energy*2.3:thinking?.9:sleeping?.025:.075,3.5,dt);
 outerRotor.rotation.z+=dt*speed;innerRotor.rotation.z-=dt*speed*.73;
 reactor.rotation.x=Math.sin(elapsed*.55)*.015;reactor.rotation.y=Math.sin(elapsed*.37)*.022;
 let power=(sleeping?.32:.68)+breath*.12+energy*1.65;
 const coreColor=muted?0xe42b20:drawColor;
 energyMaterials.forEach(m=>{m.emissive.setHex(coreColor);m.emissiveIntensity=power*2;});
 coreGlow.material.opacity=.22+power*.38;coreGlow.material.color.setHex(coreColor);coreGlow.scale.setScalar((faceVisible?1.25:4)*(1+energy*.12));
 // Keep the hands blue and make the existing palm lenses readable without
 // introducing a physical reator. The sprites stay parented to each hand bone.
 palmGlows.forEach(g=>{g.material.color.setHex(0x3dbdff);g.material.opacity=.18+energy*.18+speechGlow*.10;});
 if(now/1000>nextBlink){blinkStart=now/1000;nextBlink=now/1000+3.0+Math.random()*3.4;}
 const bt=now/1000-blinkStart;let blinkTarget=bt<.08?1-bt/.08:bt<.145?0:bt<.275?(bt-.145)/.13:1;blink=maskLights?clamp(blinkTarget,0,1):0;
 // The armor's lenses are rigid: blinking dims their light, never deforms the mesh.
 const eyeColor=eyePanelMode==='blue'?0x169cff:error?0xff2020:muted?0x169cff:(status.speaking||thinking)?0xffc329:isGoodMode()?0xffffff:mode==='evil'?0xff2020:0x169cff;
 const eyeAppearance=eyePanelMode==='auto'?(maskLights?'active':'white'):eyePanelMode;
 if(eyeAppearance==='off'){armorEyeColor.value.setHex(0x000000);armorEyeMix.value=1;armorEyePower.value=0;}
 else if(eyeAppearance==='white'){armorEyeColor.value.setHex(0xf4f7fa);armorEyeMix.value=1;armorEyePower.value=.025;}
 else{armorEyeColor.value.setHex(eyeColor).multiplyScalar(.12+.88*blink);armorEyeMix.value=1;armorEyePower.value=(.28+energy*.16+speechGlow*.14)*blink;}
 for(const eye of eyes){eye.group.scale.set(1,1,1);eye.glow.material.color.setHex(eyeColor);eye.glow.material.opacity=(.55+energy*.3+speechGlow*.20)*blink;eye.mesh.material.emissive.setHex(eyeColor);eye.mesh.material.emissiveIntensity=(1.5+energy*.9+speechGlow*.8)*blink;eye.mesh.material.color.setHex(eyeColor).multiplyScalar(.03+.74*blink);}
 // The mask is rigid, so speech is expressed through a synchronized light pulse.
 const accentColor=isGoodMode()?0xffffff:mode==='evil'?0xff2020:0x0b6aa8;
 jaw.position.y=0;maskLightMeshes.forEach(o=>{o.material.emissiveIntensity=maskLights ? .82+energy*1.45+speechGlow*2.35 : 0;o.material.emissive.setHex(accentColor);o.material.color.setHex(maskLights?accentColor:0x01080f);});
 // Cursor motion is additive on the visual rig; manual orbit and hand gestures keep priority.
 const following=!sketch.opened&&!libras.opened&&cursor.inside&&!cursor.dragging&&!cameraActive&&now>=interactionsUntil;
 // A low-cost idle rig: transforms only, so no geometry, materials, or textures are allocated.
 if(!following&&now/1000>nextScan){scanUntil=now/1000+.8+Math.random()*.55;scanYaw=(Math.random()>.5?1:-1)*(.055+Math.random()*.035);nextScan=now/1000+5.5+Math.random()*6.5;}
 const scanning=!following&&now/1000<scanUntil;
 const idleYaw=Math.sin(elapsed*.51)*.035*(sleeping?.3:1)+(scanning?scanYaw:0);
 const idlePitch=Math.sin(elapsed*.74)*.012+voicePulse*.018;
 technical.rotation.z=thinking?elapsed*.11:Math.sin(elapsed*.28)*.012;
 const lookX=following?cursor.x:0,lookY=following?cursor.y:0;
 rig.rotation.y=mix(rig.rotation.y,lookX*.42,5.5,dt);
 rig.rotation.x=mix(rig.rotation.x,lookY*.20,5.5,dt);
 head.rotation.y=mix(head.rotation.y,lookX*.14+idleYaw,7.5,dt);
 head.rotation.x=mix(head.rotation.x,lookY*.065+idlePitch,7.5,dt);
 head.rotation.z=mix(head.rotation.z,scanning?scanYaw*.12:Math.sin(elapsed*.39)*.006,7.5,dt);
 rig.position.y=Math.sin(elapsed*1.35)*.006;
 if(thinking){cyanMaterials.forEach((m,i)=>m.opacity=.30+.40*(.5+.5*Math.sin(elapsed*3.3-i*.06)));}else{cyanMaterials.forEach(m=>{m.opacity=mix(m.opacity,(sleeping?.12:holoUniform.value?.40:.14)+energy*.15,4,dt);});}
 if(drawCount%4===0){$('energy-bar').style.width=`${6+energy*94}%`;$('activity-label').textContent=speaking?'VOZ ATIVA':thinking?'PROCESSANDO':'NÚCLEO ESTÁVEL';$('signal-label').textContent=ai>.012?'ÁUDIO SINCRONIZADO':sleeping?'PAUSADO':'EM ESPERA';}
 controls.update();const begin=performance.now();renderer.render(scene,camera);frameMs=mix(frameMs,performance.now()-begin,2,dt);drawCount++;
}
requestAnimationFrame(animate);
function setVisible(on){nativeVisible=!!on;if(!on){clearCursor();stopCamera();}}
function dispose(){if(disposed)return;disposed=true;music.dispose();libras.dispose();sketch.dispose();clearCursor();window.removeEventListener('blur',clearCursor);stopCamera();controls.dispose();scene.traverse(o=>{o.geometry?.dispose();let mats=Array.isArray(o.material)?o.material:[o.material];for(const m of mats)if(m)m.dispose();});environment.dispose();glowTexture.dispose();neutralGlowTexture.dispose();renderer.dispose();}
window.JarvisReactor={control3D,setStatus,setMetrics,setVisible,reset,setFace,setHologram,setEye,setEyePanel,stopCamera,dispose,setPose:(x,y)=>{root.rotation.set(x,y,0)},diagnostics:()=>({graphicsMode,graphicsRenderer,softwareRenderer,maxFps,idleFps,pixelRatio:renderer.getPixelRatio(),ready,armorReady,reactorReady,fullArmorLoaded,palmGlowCount:palmGlows.length,drawCount,frameMs,geometries:renderer.info.memory.geometries,calls:renderer.info.render.calls,triangles:renderer.info.render.triangles,energy,voicePulse,reactorColor:energyMaterials[0]?.emissive.getHex(),reactorEmission:energyMaterials[0]?.emissiveIntensity,poseDegrees:{x:THREE.MathUtils.radToDeg(root.rotation.x),y:THREE.MathUtils.radToDeg(root.rotation.y),z:THREE.MathUtils.radToDeg(root.rotation.z)},voiceRotating:!!voiceRotation,maskLights,eyePanelMode,jawY:jaw.position.y,sideLights:maskLightMeshes.map(o=>o.material.emissiveIntensity),sideColors:maskLightMeshes.map(o=>o.material.emissive.getHex()),detailColors:cyanMaterials.map(m=>m.color.getHex()),blink,eyeLights:eyes.map(e=>({scaleY:e.group.scale.y,emission:e.mesh.material.emissiveIntensity,color:e.mesh.material.emissive.getHex()})),speed,outerAngle:outerRotor.rotation.z,faceVisible,cameraActive,workerActive:gestures.running,handControl:{active:!!handPoseTarget,scale:root.scale.x,x:root.position.x,y:root.position.y,roll:root.rotation.z},cursorFollow:{inside:cursor.inside,dragging:cursor.dragging,x:cursor.x,y:cursor.y,yaw:rig.rotation.y,pitch:rig.rotation.x},status})};
window.addEventListener('pagehide',dispose);document.addEventListener('visibilitychange',()=>{if(document.hidden)stopCamera();});
if(window.qt&&window.QWebChannel){new QWebChannel(qt.webChannelTransport,channel=>{bridge=channel.objects.reactorBridge;bridge.librasResult.connect(raw=>libras.receive(JSON.parse(raw)));bridge.sketchResult.connect(raw=>sketch.receive(JSON.parse(raw)));bridge.statusChanged.connect(raw=>setStatus(JSON.parse(raw)));bridge.metricsChanged.connect(raw=>setMetrics(JSON.parse(raw)));bridge.visibilityChanged.connect(setVisible);bridge.command.connect(cmd=>{if(cmd==='reset')reset();else if(cmd==='stopCamera')stopCamera();else if(cmd==='openSketch'&&status.state!=='SLEEPING')sketch.toggle(true);else if(cmd==='closeSketch')sketch.toggle(false);else if(cmd==='openLibras'&&status.state!=='SLEEPING')libras.toggle(true);else if(cmd==='closeLibras')libras.toggle(false);else if(cmd==='openMusic'&&status.state!=='SLEEPING')music.toggle(true);else if(cmd==='closeMusic')music.toggle(false);});if(ready)bridge.ready();});}
