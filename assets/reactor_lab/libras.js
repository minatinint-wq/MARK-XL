export const CAPTURE_PROFILES={alfabeto:{duration:1400,frames:7},sinais:{duration:2400,frames:10},frase:{duration:4000,frames:16}};
export class LibrasPanel{
 constructor({send,submit,requestCamera,stopCamera,onToggle,notify}){
  Object.assign(this,{send,submit,requestCamera,stopCamera,onToggle,notify});this.opened=false;this.generation=0;this.serial=0;this.pending=new Map();this.recording=false;this.busy=false;this.lastSent=0;
  this.panel=document.createElement('section');this.panel.id='libras-panel';this.panel.hidden=true;
  this.panel.innerHTML=`<div class="libras-heading"><div><b>LIBRAS</b><small>Modo exclusivo de comunicação</small></div><button id="libras-close">Voltar ao 3D</button></div>
   <div class="libras-camera" id="libras-camera-slot"><p>Enquadre rosto, tronco e as duas mãos. A prévia é espelhada.</p></div>
   <div class="libras-controls"><select id="libras-focus" aria-label="Tipo de sinal"><option value="sinais">Sinais do cotidiano</option><option value="alfabeto">Alfabeto / soletração</option><option value="frase">Frase curta</option></select><button id="libras-capture">Interpretar gesto · 2,4 s</button><label><input type="checkbox" id="libras-auto">Captura contínua</label></div>
   <p id="libras-status" role="status">Clique em Interpretar gesto e sinalize. A IA analisa o movimento, sem controlar a armadura.</p>
   <div class="libras-suggestion"><span id="libras-result">A sugestão aparece aqui.</span><small id="libras-evidence"></small><button id="libras-use" disabled>Usar sugestão</button></div>
   <textarea id="libras-text" rows="2" maxlength="1200" aria-label="Mensagem revisada" placeholder="Revise a interpretação ou escreva sua mensagem…"></textarea>
   <div class="libras-controls"><button id="libras-send">Enviar ao Jarvis</button><button id="libras-reset">Limpar</button></div>
   <p class="libras-note">Interpretação experimental por IA; pode errar. Ao interpretar, os quadros desta câmera vão ao Gemini já configurado. Não gravamos vídeo em disco. Nenhum gesto executa comandos automaticamente.</p>
   <details><summary>Referências de Libras</summary><p>Confira configuração, orientação, movimento e expressão em materiais do INES e no Signbank da UFSC. Uma figura estática não descreve todos esses elementos.</p><button id="libras-ines">Manuário INES</button><button id="libras-ufsc">Signbank UFSC</button></details>`;
  document.body.append(this.panel);this.camera=document.getElementById('camera-panel');this.cameraParent=this.camera.parentNode;this.cameraNext=this.camera.nextSibling;this.video=document.getElementById('camera-video');this.canvas=document.createElement('canvas');this.canvas.width=480;this.canvas.height=360;
  this.$('close').onclick=()=>this.toggle(false);this.$('capture').onclick=()=>this.capture();this.$('auto').onchange=()=>{clearTimeout(this.autoTimer);if(this.$('auto').checked)this.capture();};
  this.$('use').onclick=()=>{if(this.suggestion)this.$('text').value=(this.$('text').value+' '+this.suggestion).trim().slice(0,1200);};
  this.$('send').onclick=()=>{const text=this.$('text').value.trim();if(text&&this.submit(text)){this.$('status').textContent='Mensagem enviada ao Jarvis.';this.$('auto').checked=false;clearTimeout(this.autoTimer);}};
  this.$('focus').onchange=()=>{this.cancel();const profile=this.profile();this.$('capture').textContent='Interpretar gesto · '+(profile.duration/1000).toLocaleString('pt-BR')+' s';this.$('status').textContent='Modo alterado. Prepare o sinal e clique em Interpretar gesto.';};
  this.$('reset').onclick=()=>this.reset();for(const id of ['ines','ufsc'])this.$(id).onclick=()=>this.send('reference-'+id,'reference',JSON.stringify({source:id}));
 }
 $(id){return document.getElementById('libras-'+id);}
 profile(){return CAPTURE_PROFILES[this.$('focus').value]||CAPTURE_PROFILES.sinais;}
 toggle(on=!this.opened){
  if(on===this.opened)return;this.cancel();this.opened=on;this.onToggle(on);this.panel.hidden=!on;document.body.classList.toggle('libras-open',on);
  if(on){this.$('camera-slot').append(this.camera);this.$('status').textContent='Clique em Interpretar gesto. Alfabeto: 1,4 s · sinais: 2,4 s · frase: 4 s.';}
  else{this.cameraParent.insertBefore(this.camera,this.cameraNext);this.stopCamera();}
 }
 consumeHands(hands){if(!this.opened)return false;document.getElementById('gesture-label').textContent=`LIBRAS · ${(hands||[]).length} mão(s) · 3D bloqueado`;return true;}
 cancel(){this.generation++;clearInterval(this.captureTimer);clearTimeout(this.autoTimer);this.frames=[];this.canvas.getContext('2d').clearRect(0,0,this.canvas.width,this.canvas.height);this.recording=false;this.$('auto').checked=false;this.$('capture').disabled=this.busy;}
 reset(){this.cancel();this.suggestion='';this.$('text').value='';this.$('result').textContent='A sugestão aparece aqui.';this.$('evidence').textContent='';this.$('use').disabled=true;this.$('status').textContent='Pronto para um novo gesto.';}
 cameraStopped(){if(this.recording){this.cancel();this.$('status').textContent='Captura interrompida. Ative a câmera para tentar novamente.';}}
 async capture(){
  if(!this.opened||this.busy||this.recording||this.preparing||document.hidden)return;
  const gen=this.generation;this.$('status').textContent='Preparando câmera…';
  this.preparing=true;try{if(!this.video.srcObject)await this.requestCamera();}finally{this.preparing=false;}
  if(gen!==this.generation||!this.opened)return;
  if(!this.video.srcObject||this.video.readyState<2){this.$('status').textContent='Câmera indisponível. Ative o acesso e tente novamente.';return;}
  const waitForSlot=Math.max(0,2000-(performance.now()-this.lastSent)-this.profile().duration);if(waitForSlot&&this.lastSent){this.$('status').textContent='Preparando a próxima captura…';this.autoTimer=setTimeout(()=>this.capture(),waitForSlot);return;}
  this.recording=true;this.frames=[];this.$('capture').disabled=true;this.suggestion='';this.$('use').disabled=true;const start=performance.now(),profile=this.profile(),focus=this.$('focus').value;
  this.captureTimer=setInterval(()=>{
   if(gen!==this.generation||!this.opened||document.hidden||!this.video.srcObject){this.cameraStopped();return;}
   const ms=Math.round(performance.now()-start);this.$('status').textContent=`Sinalize agora · ${Math.max(0,Math.ceil((profile.duration-ms)/1000))} s`;
   this.canvas.getContext('2d').drawImage(this.video,0,0,480,360);this.frames.push({ms,image:this.canvas.toDataURL('image/jpeg',.65)});
   if(ms>=profile.duration||this.frames.length>=profile.frames){clearInterval(this.captureTimer);this.recording=false;this.analyze(gen,this.frames,focus);this.frames=[];}
  },profile.duration/profile.frames);
 }
 async analyze(gen,frames,focus=this.$('focus').value){
  this.busy=true;this.lastSent=performance.now();this.$('status').textContent='Gemini interpretando…';const started=performance.now(),progress=setInterval(()=>{if(gen===this.generation&&this.opened)this.$('status').textContent='Gemini interpretando · '+((performance.now()-started)/1000).toFixed(1)+' s';},250);
  try{
   const result=await this.call({frames,focus});
   if(gen!==this.generation||!this.opened)return;
   this.suggestion=result.recognized?result.text:'';this.$('result').textContent=this.suggestion||'Não reconheci com segurança. Repita o gesto mais devagar e mantenha as mãos visíveis.';
   this.$('evidence').textContent=`Confiança sugerida: ${result.confidence}. ${result.observation||''}`+(result.alternatives?.length?' Possibilidades: '+result.alternatives.join(', '):'');
   this.$('use').disabled=!this.suggestion;this.$('status').textContent='Resposta em '+((performance.now()-started)/1000).toFixed(1)+' s · revise antes de enviar ao Jarvis.';
  }catch(e){if(gen===this.generation&&this.opened){this.$('status').textContent=e.message;this.$('auto').checked=false;}}
  finally{clearInterval(progress);this.busy=false;this.$('capture').disabled=false;if(gen===this.generation&&this.opened&&this.$('auto').checked)this.autoTimer=setTimeout(()=>this.capture(),Math.max(200,8000-(performance.now()-this.lastSent)-this.profile().duration));}
 }
 call(payload){return new Promise((resolve,reject)=>{const id='libras-'+(++this.serial),timer=setTimeout(()=>{this.pending.delete(id);reject(Error('A interpretação demorou. Tente novamente.'));},21000);this.pending.set(id,{resolve,reject,timer});if(!this.send(id,'analyze',JSON.stringify(payload))){clearTimeout(timer);this.pending.delete(id);reject(Error('Conexão com o Jarvis indisponível.'));}});}
 receive(result){const p=this.pending.get(result.requestId);if(!p)return;clearTimeout(p.timer);this.pending.delete(result.requestId);result.ok?p.resolve(result):p.reject(Error(result.message||'Não foi possível interpretar agora.'));}
 dispose(){this.cancel();for(const p of this.pending.values()){clearTimeout(p.timer);p.reject(Error('Modo encerrado.'));}this.pending.clear();}
}
