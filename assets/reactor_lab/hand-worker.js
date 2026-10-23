self.exports={};let detector=null;
self.onmessage=async e=>{const msg=e.data;try{
 if(msg.type==='init'){
  importScripts('./vendor/vision_bundle.cjs');
  const {HandLandmarker,FilesetResolver}=self.exports;
  const files=await FilesetResolver.forVisionTasks('./vendor/wasm');
  detector=await HandLandmarker.createFromOptions(files,{baseOptions:{modelAssetPath:'./vendor/hand_landmarker.task',delegate:'CPU'},runningMode:'VIDEO',numHands:2,minHandDetectionConfidence:.50,minHandPresenceConfidence:.50,minTrackingConfidence:.50});
  self.postMessage({type:'ready'});
 }else if(msg.type==='frame'&&detector){try{let result=detector.detectForVideo(msg.bitmap,msg.time);self.postMessage({type:'landmarks',hands:result.landmarks,handedness:result.handedness});}finally{msg.bitmap.close();}}
}catch(error){msg.bitmap?.close();self.postMessage({type:'error',message:'Não foi possível processar as mãos localmente.'});}};
