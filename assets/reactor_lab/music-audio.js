export class MusicAudio{
 constructor(){this.context=null;this.synth=null;this.loading=null;this.enabled=false;this.volume=.55;this.program=24;this.timers=new Map();this.count=0;this.generation=0;}
 async start(){
  this.enabled=true;
  if(this.loading)return this.loading;
  if(this.synth){await this.context.resume();return;}
  const generation=++this.generation;
  this.loading=(async()=>{
   const context=this.context=new AudioContext({latencyHint:'interactive',sampleRate:44100});await context.resume();
   const [{WorkletSynthesizer},response]=await Promise.all([import('./music-bank/index.js'),fetch(new URL('./music-bank/GeneralUser-GS.sf2',import.meta.url))]);
   if(!response.ok)throw Error('Banco de instrumentos indisponível.');const buffer=await response.arrayBuffer();
   await context.audioWorklet.addModule(new URL('./music-bank/spessasynth_processor.min.js',import.meta.url));
   const synth=this.synth=new WorkletSynthesizer(context);this.gain=context.createGain();this.gain.gain.value=this.volume;
   this.analyser=context.createAnalyser();this.analyser.fftSize=256;const limiter=context.createDynamicsCompressor();limiter.threshold.value=-8;limiter.ratio.value=12;
   synth.connect(this.gain);this.gain.connect(limiter);limiter.connect(this.analyser);this.analyser.connect(context.destination);
   await synth.isReady;await synth.soundBankManager.addSoundBank(buffer,'generaluser');synth.programChange(0,this.program);
   if(!this.enabled||generation!==this.generation)await context.suspend();
  })().catch(async e=>{this.enabled=false;this.synth?.destroy();this.synth=null;await this.context?.close();this.context=null;throw e;}).finally(()=>{this.loading=null;});
  return this.loading;
 }
 setVolume(value){this.volume=Math.max(0,Math.min(1,value));if(this.gain)this.gain.gain.setTargetAtTime(this.volume,this.context.currentTime,.02);}
 select(program){this.stopNotes();this.program=program;this.synth?.programChange(0,program);}
 play(note,velocity=92,drum=false,duration=600){
  if(!this.enabled||!this.synth||this.context.state!=='running')return false;
  const channel=drum?9:0,key=channel+':'+note;clearTimeout(this.timers.get(key));
  if(this.timers.size>=24){const first=this.timers.keys().next().value;clearTimeout(this.timers.get(first));this.timers.delete(first);const [ch,n]=first.split(':').map(Number);this.synth.noteOff(ch,n);}
  this.synth.noteOn(channel,note,Math.max(35,Math.min(115,Math.round(velocity))));this.count++;
  this.timers.set(key,setTimeout(()=>{this.synth?.noteOff(channel,note);this.timers.delete(key);},duration));return true;
 }
 stopNote(note,drum=false){const channel=drum?9:0,key=channel+':'+note;clearTimeout(this.timers.get(key));this.timers.delete(key);this.synth?.noteOff(channel,note);}
 stopNotes(){for(const t of this.timers.values())clearTimeout(t);this.timers.clear();this.synth?.stopAll(true);}
 async pause(){this.enabled=false;this.generation++;this.stopNotes();if(this.context?.state==='running')await this.context.suspend();}
 async dispose(){await this.pause();if(this.loading)try{await this.loading;}catch{}this.synth?.destroy();this.synth=null;await this.context?.close();this.context=null;}
}
