"""CPU rendering and editor smoke tests. No real user assets or network used."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent.parent
sys.path.insert(0,str(ROOT))
from actions.animation_cpu import make_plan,render,ffmpeg_path,Cancelled,animation_cpu,STYLES,MOTIONS
_TEST_TEMP=tempfile.TemporaryDirectory(prefix='mark_xl_animation_test_')
TEST=Path(_TEST_TEMP.name)
ff=ffmpeg_path(); probe=str(Path(ff).with_name('ffprobe.exe' if os.name=='nt' else 'ffprobe'))
def command(args):
    subprocess.run(args,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=90,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
image=TEST/"mídia 'teste'; imagem.png"
command([ff,'-hide_banner','-loglevel','error','-y','-f','lavfi','-i','testsrc2=s=640x480:r=15','-frames:v','1',str(image)])
video=TEST/'source.mp4'
command([ff,'-hide_banner','-loglevel','error','-y','-f','lavfi','-i','testsrc2=s=640x360:r=15','-t','1','-c:v','libx264','-pix_fmt','yuv420p',str(video)])
audio=TEST/'source.wav'
command([ff,'-hide_banner','-loglevel','error','-y','-f','lavfi','-i','sine=frequency=440:duration=1',str(audio)])
assert 'estilo' in animation_cpu({'action':'cpu_start'}).lower()
assert 'caminho' in animation_cpu({'action':'cpu_start','style':'suave'}).lower()
assert 'roteiro' in animation_cpu({'action':'cpu_media','media_paths':[str(image)]}).lower()
for scene in [{'motion':'exec'}, {'duration':float('nan')}, {'media':True}, {'caption_position':'unknown'}, {'duration':1,'fade':2}]:
    try:make_plan('suave',[str(image)],{'scenes':[scene]})
    except ValueError:pass
    else:raise AssertionError(scene)
plan=make_plan('suave',[str(image)],{'scenes':[{'duration':.5,'motion':m,'fade':.1} for m in sorted(MOTIONS)],'size':480,'fps':15})
output=TEST/'all_motions.mp4'
if output.exists():output.unlink() # Only the exact test-owned output is replaced.
render(plan,output,progress=lambda _:None)
def metadata(path):
    return json.loads(subprocess.check_output([probe,'-v','error','-count_frames','-show_streams','-show_format','-of','json',str(path)]))
meta=metadata(output);stream=meta['streams'][0]
assert stream['codec_name']=='h264' and stream['height']==480 and int(stream['nb_read_frames'])==sum(s['frames'] for s in plan['scenes']),stream
try:render(plan,output)
except ValueError:pass
else:raise AssertionError('overwrite allowed')
cancel=threading.Event();cancel.set()
try:render(plan,TEST/'cancelled.mp4',cancel)
except Cancelled:pass
else:raise AssertionError('cancellation ignored')
assert not (TEST/'cancelled.mp4').exists()
raw={'scenes':[{'media':1,'duration':1,'motion':'zoom_in','caption':"Oferta 50%: ação d'água!",'caption_position':'center'},{'media':2,'duration':1.5,'motion':'pan_right','caption':'Peça agora • Entrega rápida','caption_position':'bottom'}],'ratio':'9:16','size':480,'fps':24,'audio_path':str(audio)}
plan=make_plan('cinematic',[str(image),str(video)],raw)
output2=TEST/'vertical_text_audio.mp4'
if output2.exists():output2.unlink()
render(plan,output2,progress=lambda _:None)
meta=metadata(output2)
assert any(s['codec_type']=='audio' and s['codec_name']=='aac' for s in meta['streams'])
vs=next(s for s in meta['streams'] if s['codec_type']=='video'); assert vs['width']==480 and vs['height']>vs['width']
assert abs(float(meta['format']['duration'])-2.5)<.15
project=TEST/'example_project.json'
project.write_text(json.dumps({'style':'cinematic','media_paths':[str(image),str(video)],'animation_script':raw,'brief':'1s | zoom_in | Oferta especial\n1.5s | pan_right | Peça agora'},ensure_ascii=False),encoding='utf-8')
from PyQt6.QtWidgets import QApplication
from actions.animation_editor import Editor
app=QApplication([]);editor=Editor();editor.load_project(project);editor.show();app.processEvents()
assert len(editor.scenes())==2
editor.table.selectRow(0);editor.duplicate();assert len(editor.scenes())==3
editor.table.selectRow(2);editor.move_scene(-1);assert len(editor.scenes())==3
editor.remove_scene();assert len(editor.scenes())==2
editor.load_project(project);editor.apply_brief();assert len(editor.scenes())==2
editor.library.setCurrentRow(0);app.processEvents()
editor.grab().save(str(TEST/'editor-preview.png'))
editor.close();app.processEvents()
from actions.video_generation import video_generation
assert 'FFmpeg disponível' in video_generation({'action':'cpu_check','provider':'ffmpeg'})
print('PASS: chat intake, validation, 7 motions, real H264 renders, frame count, vertical format, Unicode text, AAC audio, overwrite protection, cancellation, editor construction/project/storyboard, and Jarvis routing.')
