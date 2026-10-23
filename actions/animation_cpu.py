"""CPU-only FFmpeg animation engine and chat adapter for MARK-XL.

Standalone: python -m actions.animation_cpu
Integration: video_generation(provider="ffmpeg", action="cpu_start", ...)
No model download, shell execution, or GPU required.
"""
from __future__ import annotations
import argparse
import json
import math
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import textwrap
import unicodedata
import uuid
from pathlib import Path

if sys.platform=='win32':
    for _stream in (sys.stdout,sys.stderr):
        try:_stream.reconfigure(encoding='utf-8',errors='replace')
        except Exception:pass

BASE = Path(__file__).resolve().parent.parent
OUTPUT = BASE / "generated_videos" / "cpu"
STILLS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
VIDEOS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
STYLES = {
    "cinematic": (0.12, 0.4, "eq=contrast=1.06:saturation=0.92"),
    "suave": (0.06, 0.5, "null"),
    "dinamico": (0.18, 0.15, "eq=contrast=1.08:saturation=1.1"),
    "documental": (0.08, 0.25, "null"),
    "vintage": (0.10, 0.4, "eq=saturation=0.65:contrast=1.06:brightness=0.015"),
}
MOTIONS = {"zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down", "static"}
LOCK = threading.RLock()
DRAFT = {}
JOBS = {}
EXAMPLE = {"scenes": [{"media": 1, "duration": 5, "motion": "zoom_in"}, {"media": 1, "duration": 4, "motion": "pan_right", "fade": 0.3}], "size": 720, "fps": 24, "ratio": "16:9"}


def norm(value):
    return " ".join("".join(c for c in unicodedata.normalize("NFD", str(value).lower()) if unicodedata.category(c) != "Mn").split())


def ffmpeg_path():
    path = os.environ.get("FFMPEG_BINARY") or shutil.which("ffmpeg")
    if path and Path(path).is_file():
        return str(Path(path).resolve())
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError):
        raise ValueError("FFmpeg não encontrado. Execute tools\\video\\INSTALAR_ANIMACAO_CPU.bat ou instale imageio-ffmpeg no Python utilizado pelo Jarvis.") from None


def number(value, low, high, label):
    if isinstance(value, bool): raise ValueError(f"{label}: número esperado.")
    try: result = float(value)
    except (ValueError, TypeError): raise ValueError(f"{label}: número esperado.") from None
    if not math.isfinite(result) or not low <= result <= high:
        raise ValueError(f"{label}: use entre {low} e {high}.")
    return result


def make_plan(style, media_paths, script):
    style = norm(style)
    style = {"cinematografico": "cinematic", "cinematico": "cinematic", "documentario": "documental"}.get(style, style)
    if style not in STYLES: raise ValueError("Estilos disponíveis: " + ", ".join(STYLES))
    if not isinstance(media_paths, list) or not 1 <= len(media_paths) <= 20:
        raise ValueError("Informe de 1 a 20 arquivos de mídia.")
    media = [Path(str(p).strip().strip('"')).expanduser().resolve() for p in media_paths]
    for path in media:
        if not path.is_file() or path.suffix.lower() not in STILLS | VIDEOS:
            raise ValueError(f"Mídia inválida: {path.name}. Use PNG/JPG/WEBP/BMP ou MP4/MOV/MKV/WEBM/AVI.")
    try: raw = json.loads(script) if isinstance(script, str) else script
    except json.JSONDecodeError as exc: raise ValueError(f"Roteiro JSON inválido: linha {exc.lineno}, coluna {exc.colno}.") from None
    if not isinstance(raw, dict) or set(raw) - {"scenes", "size", "fps", "ratio", "audio_path"}:
        raise ValueError("O roteiro deve conter scenes e, opcionalmente, size, fps e ratio.")
    size, fps, ratio = raw.get("size",720), raw.get("fps",24), raw.get("ratio","16:9")
    if size not in (480,720,1080) or fps not in (15,24,30) or ratio not in ("16:9","9:16","1:1"):
        raise ValueError("size: 480/720/1080; fps: 15/24/30; ratio: 16:9/9:16/1:1.")
    scenes = raw.get("scenes")
    if not isinstance(scenes,list) or not 1 <= len(scenes) <= 20:
        raise ValueError("Use de 1 a 20 cenas.")
    result=[]
    for i, scene in enumerate(scenes,1):
        if not isinstance(scene,dict) or set(scene)-{"media","duration","motion","fade","start","caption","caption_position","caption_size"}:
            raise ValueError(f"Cena {i}: campos aceitos são media, duration, motion, fade, start.")
        index=scene.get("media",1)
        if type(index) is not int or not 1 <= index <= len(media): raise ValueError(f"Cena {i}: índice de mídia inválido.")
        duration=number(scene.get("duration",5),0.5,60,"Duração")
        frames=max(1,round(duration*fps))
        duration=frames/fps
        motion=scene.get("motion","zoom_in")
        if motion not in MOTIONS: raise ValueError(f"Cena {i}: movimento inválido. Use {', '.join(sorted(MOTIONS))}.")
        fade=number(scene.get("fade",min(STYLES[style][1],duration/2)),0,duration/2,"Fade")
        start=number(scene.get("start",0),0,86400,"Início do trecho")
        if start and media[index-1].suffix.lower() in STILLS: raise ValueError("start só se aplica a vídeos.")
        caption=str(scene.get('caption','')).strip()
        if len(caption)>500: raise ValueError('Texto da cena: máximo de 500 caracteres.')
        position=scene.get('caption_position','bottom')
        if position not in {'top','center','bottom'}: raise ValueError('Posição do texto: top, center ou bottom.')
        caption_size=int(number(scene.get('caption_size',40),16,100,'Tamanho do texto'))
        result.append(dict(media=index,duration=duration,frames=frames,motion=motion,fade=fade,start=start,caption=caption,caption_position=position,caption_size=caption_size))
    if sum(x['duration'] for x in result)>180: raise ValueError("Limite: 180 segundos por projeto nesta configuração de CPU.")
    audio=str(raw.get('audio_path') or '').strip()
    if audio:
        audio_path=Path(audio).expanduser().resolve()
        if not audio_path.is_file() or audio_path.suffix.lower() not in {'.mp3','.wav','.m4a','.aac','.ogg','.flac'}:
            raise ValueError('Trilha inválida. Use MP3/WAV/M4A/AAC/OGG/FLAC.')
        audio=str(audio_path)
    return dict(style=style,media=[str(p) for p in media],scenes=result,size=size,fps=fps,ratio=ratio,audio_path=audio)


def scene_filter(plan, scene):
    size=plan['size']; wide=round(size*16/9/2)*2
    w,h={'16:9':(wide,size),'9:16':(size,wide),'1:1':(size,size)}[plan['ratio']]
    n=max(1,scene['frames']-1)
    amount,_,tone=STYLES[plan['style']]
    z='1'; x='(iw-iw/zoom)/2'; y='(ih-ih/zoom)/2'
    motion=scene['motion']
    if motion=='zoom_in': z=f'1+{amount}*min(on/{n},1)'
    elif motion=='zoom_out': z=f'1+{amount}*(1-min(on/{n},1))'
    elif motion.startswith('pan_'):
        z=str(1+amount)
        axis='x' if motion in {'pan_left','pan_right'} else 'y'
        extent='iw-iw/zoom' if axis=='x' else 'ih-ih/zoom'
        position=f'({extent})*'+(f'(1-min(on/{n},1))' if motion in {'pan_left','pan_up'} else f'min(on/{n},1)')
        if axis=='x': x=position
        else: y=position
    # Reduce input dimensions first; never create full-resolution frame arrays in Python.
    filters=[f'fps={plan["fps"]}', 'setpts=PTS-STARTPTS',
             f'scale={w}:{h}:force_original_aspect_ratio=decrease:flags=bilinear',
             f'pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black', 'setsar=1',
             f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={w}x{h}:fps={plan['fps']}",tone]
    if scene['fade']:
        f=scene['fade']; d=scene['duration']
        filters += [f'fade=t=in:st=0:d={f}',f'fade=t=out:st={d-f}:d={f}']
    return ','.join(filters+['format=yuv420p'])


class Cancelled(Exception): pass


def _clock(seconds):
    if seconds is None or not math.isfinite(float(seconds)) or seconds < 0:
        return '--:--'
    seconds=int(round(seconds))
    hours,remainder=divmod(seconds,3600)
    minutes,secs=divmod(remainder,60)
    return f'{hours:02d}:{minutes:02d}:{secs:02d}' if hours else f'{minutes:02d}:{secs:02d}'


def _ffmpeg_seconds(value):
    try:
        hours,minutes,seconds=str(value).strip().split(':',2)
        return int(hours)*3600+int(minutes)*60+float(seconds)
    except (ValueError,TypeError):
        return 0.0


class TerminalVideoProgress:
    """One stable CMD line shared by every FFmpeg phase of a render."""
    def __init__(self):
        self.started=time.monotonic();self.last_length=0;self.last_percent=-1.0;self.last_label=''

    def update(self,percent,label,force=False):
        percent=max(0.0,min(100.0,float(percent)))
        elapsed=max(0.0,time.monotonic()-self.started)
        eta=(elapsed/percent)*(100.0-percent) if percent>=0.5 else None
        width=30;filled=min(width,int(round(width*percent/100.0)))
        bar='#'*filled+'-'*(width-filled)
        label=str(label or 'Renderizando').strip()
        line=f'[JARVIS VIDEO] [{bar}] {percent:5.1f}% | {label[:34]:<34} | decorrido {_clock(elapsed)} | resta {_clock(eta)}'
        should_write=force or label!=self.last_label or percent-self.last_percent>=0.2 or percent>=100
        if should_write:
            padding=' '*max(0,self.last_length-len(line))
            print('\r'+line+padding,end='\n' if percent>=100 else '',flush=True)
            self.last_length=len(line);self.last_percent=percent;self.last_label=label
        return f'{percent:05.1f}% | {label} | decorrido {_clock(elapsed)} | restante {_clock(eta)}'


def run_ffmpeg(args,log,cancel,timeout=1800,cwd=None,duration=None,on_progress=None):
    flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
    with open(log,'ab') as out:
        command=list(args[:-1])+['-stats_period','0.25','-progress','pipe:1','-nostats',args[-1]]
        proc=subprocess.Popen(
            command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=out,
            cwd=cwd,creationflags=flags,text=True,encoding='utf-8',errors='replace',bufsize=1,
        )
        lines=queue.Queue()
        def read_progress():
            try:
                for line in proc.stdout or ():
                    lines.put(line.rstrip('\r\n'))
            finally:
                lines.put(None)
        reader=threading.Thread(target=read_progress,daemon=True,name='FFmpegProgress')
        reader.start()
        start=time.monotonic()
        current_seconds=0.0
        def drain_progress():
            nonlocal current_seconds
            while True:
                try:line=lines.get_nowait()
                except queue.Empty:break
                if line is None:continue
                key,separator,value=line.partition('=')
                if not separator:continue
                if key=='out_time':current_seconds=_ffmpeg_seconds(value)
                elif key=='out_time_us':
                    try:current_seconds=max(current_seconds,float(value)/1_000_000.0)
                    except ValueError:pass
                elif key=='progress' and on_progress:
                    fraction=min(1.0,current_seconds/max(0.001,float(duration or 0.001))) if duration else 0.0
                    on_progress(1.0 if value=='end' else fraction)
        try:
            while proc.poll() is None:
                drain_progress()
                if cancel.wait(0.10): raise Cancelled('Renderização cancelada.')
                if time.monotonic()-start>timeout: raise RuntimeError('Tempo limite de renderização excedido.')
        finally:
            if proc.poll() is None:
                proc.terminate()
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired: proc.kill(); proc.wait()
        reader.join(timeout=1.0)
        drain_progress()
        if proc.returncode:
            with open(log,'rb') as inp:
                inp.seek(max(0,inp.seek(0,2)-1800))
                detail=inp.read().decode('utf-8',errors='replace')
            raise RuntimeError('FFmpeg falhou. '+detail)
        if on_progress: on_progress(1.0)


def render(plan, output, cancel=None, progress=None):
    cancel=cancel or threading.Event(); progress=progress or (lambda text:None)
    binary=ffmpeg_path(); output=Path(output).resolve()
    if output.exists(): raise ValueError('A saída já existe; escolha outro nome.')
    output.parent.mkdir(parents=True,exist_ok=True)
    threads=max(1,min(4,(os.cpu_count() or 2)//2))
    common=[binary,'-hide_banner','-loglevel','error','-nostdin','-y','-hwaccel','none','-threads',str(threads),'-filter_threads','1']
    terminal=TerminalVideoProgress()
    total_duration=sum(scene['duration'] for scene in plan['scenes'])
    scene_budget=92.0 if plan.get('audio_path') else 95.0
    completed_duration=0.0
    def emit(percent,label,force=False):
        progress(terminal.update(percent,label,force))
    emit(0,'Preparando renderização',True)
    with tempfile.TemporaryDirectory(prefix='animacao_',dir=output.parent) as tmp:
        temp=Path(tmp); log=temp/'ffmpeg.log'
        for i,scene in enumerate(plan['scenes']):
            if cancel.is_set(): raise Cancelled('Renderização cancelada.')
            path=Path(plan['media'][scene['media']-1])
            label=f"Cena {i+1}/{len(plan['scenes'])}"
            emit(scene_budget*completed_duration/max(total_duration,0.001),label,True)
            inp=['-loop','1','-framerate',str(plan['fps'])] if path.suffix.lower() in STILLS else ['-stream_loop','-1','-ss',str(scene['start'])]
            vf=scene_filter(plan,scene)
            if scene.get('caption'):
                font=Path(os.environ.get('ANIMATION_FONT',str(Path(os.environ.get('WINDIR',r'C:\Windows'))/'Fonts'/'segoeui.ttf')))
                if not font.is_file(): raise ValueError('Defina ANIMATION_FONT com um arquivo TTF para renderizar textos.')
                if not (temp/'font.ttf').exists(): shutil.copyfile(font,temp/'font.ttf')
                fontsize=scene['caption_size']*plan['size']/720
                width=plan['size'] if plan['ratio']!='16:9' else round(plan['size']*16/9)
                lines='\n'.join(textwrap.fill(line,width=max(10,int(width*0.86/(fontsize*0.57))),break_long_words=True) for line in scene['caption'].splitlines())
                captionfile=f'caption_{i:03d}.txt'
                (temp/captionfile).write_text(lines,encoding='utf-8')
                y={'top':'h*0.08','center':'(h-text_h)/2','bottom':'h*0.90-text_h'}[scene['caption_position']]
                vf+=f",drawtext=fontfile=font.ttf:textfile={captionfile}:expansion=none:fontcolor=white:fontsize={fontsize}:x=(w-text_w)/2:y={y}:box=1:boxcolor=black@0.55:boxborderw=14"
            args=common+inp+['-i',str(path),'-map','0:v:0','-an','-vf',vf,'-frames:v',str(scene['frames']),'-c:v','libx264','-preset','veryfast','-crf','23','-threads',str(threads),'-pix_fmt','yuv420p','-video_track_timescale','24000',str(temp/f'scene_{i:03d}.mp4')]
            run_ffmpeg(
                args,log,cancel,cwd=temp,duration=scene['duration'],
                on_progress=lambda fraction,done=completed_duration,duration=scene['duration'],label=label: emit(
                    scene_budget*(done+duration*fraction)/max(total_duration,0.001),label
                ),
            )
            completed_duration+=scene['duration']
        playlist=temp/'concat.txt'
        playlist.write_text(''.join(f"file 'scene_{i:03d}.mp4'\n" for i in range(len(plan['scenes']))),encoding='utf-8')
        concat_end=96.0 if plan.get('audio_path') else 99.0
        emit(scene_budget,'Montando MP4 final',True)
        run_ffmpeg(
            [binary,'-hide_banner','-loglevel','error','-nostdin','-y','-f','concat','-safe','1','-i','concat.txt','-c','copy','-movflags','+faststart','final.mp4'],
            log,cancel,cwd=temp,duration=total_duration,
            on_progress=lambda fraction: emit(scene_budget+(concat_end-scene_budget)*fraction,'Montando MP4 final'),
        )
        if plan.get('audio_path'):
            emit(concat_end,'Adicionando trilha sonora',True)
            total=total_duration
            run_ffmpeg(
                [binary,'-hide_banner','-loglevel','error','-nostdin','-y','-i','final.mp4','-stream_loop','-1','-i',plan['audio_path'],'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','128k','-af',f'afade=t=out:st={max(0,total-0.5)}:d=0.5','-t',str(total),'-movflags','+faststart','with_audio.mp4'],
                log,cancel,cwd=temp,duration=total,
                on_progress=lambda fraction: emit(concat_end+(99.0-concat_end)*fraction,'Adicionando trilha sonora'),
            )
            (temp/'with_audio.mp4').replace(temp/'final.mp4')
        if cancel.is_set(): raise Cancelled('Renderização cancelada.')
        if not (temp/'final.mp4').is_file() or (temp/'final.mp4').stat().st_size<100: raise RuntimeError('Saída inválida.')
        # Exclusive creation avoids silently overwriting an existing artifact.
        emit(99,'Salvando arquivo final',True)
        with output.open('xb') as dst, (temp/'final.mp4').open('rb') as src: shutil.copyfileobj(src,dst)
    emit(100,'Vídeo concluído',True)
    return output


def launch_job(plan):
    with LOCK:
        if any(j['state']=='rendering' for j in JOBS.values()): raise ValueError('Já existe uma renderização. Consulte cpu_status ou cancele com cpu_cancel.')
        job_id=uuid.uuid4().hex[:12]; OUTPUT.mkdir(parents=True,exist_ok=True)
        job={'id':job_id,'state':'rendering','progress':'Preparando','percent':0.0,'output':str(OUTPUT/f'{job_id}.mp4'),'cancel':threading.Event()}
        JOBS[job_id]=job
    def save():
        with LOCK:
            info={k:v for k,v in job.items() if k!='cancel'}
            (OUTPUT/f'{job_id}.json').write_text(json.dumps({'job':info,'plan':plan},ensure_ascii=False,indent=2),encoding='utf-8')
    def worker():
        try:
            save()
            def update_progress(text):
                try: percent=float(str(text).split('%',1)[0])
                except (ValueError,IndexError): percent=job.get('percent',0.0)
                job.update(progress=text,percent=percent)
            render(plan,job['output'],job['cancel'],update_progress)
            job.update(state='complete',progress='100.0% | Concluído',percent=100.0)
        except Cancelled: job.update(state='cancelled',progress='Cancelado')
        except Exception as exc: job.update(state='failed',progress=str(exc)[-1800:])
        finally: save()
    threading.Thread(target=worker,daemon=True,name='AnimationCPU').start()
    return f"Renderização CPU iniciada: {job_id}. Use cpu_status para acompanhar. Saída: {job['output']}"


def animation_cpu(parameters=None):
    params=parameters or {}; action=str(params.get('action') or 'cpu_start').lower()
    try:
        if action in {'cpu_status','cpu_cancel'}:
            with LOCK:
                job=JOBS.get(params.get('job_id')) if params.get('job_id') else next(reversed(JOBS.values()),None)
                if not job: return 'Nenhum trabalho ativo nesta sessão. Resultados anteriores: '+str(OUTPUT)
                if action=='cpu_cancel':
                    if job['state']!='rendering': return 'Esse trabalho já terminou.'
                    job['cancel'].set(); return 'Cancelamento solicitado.'
                return json.dumps({k:v for k,v in job.items() if k!='cancel'},ensure_ascii=False)
        if action=='cpu_check': return 'FFmpeg disponível: '+ffmpeg_path()
        if action not in {'cpu_start','cpu_media','cpu_plan','cpu_render'}: return 'Ações: cpu_start, cpu_media, cpu_plan, cpu_render, cpu_status, cpu_cancel, cpu_check.'
        with LOCK:
            if action=='cpu_start': DRAFT.clear()
            if params.get('style'): DRAFT['style']=params['style']
            if params.get('media_paths'): DRAFT['media_paths']=params['media_paths']
            elif params.get('image_path'): DRAFT['media_paths']=[params['image_path']]
            if params.get('animation_script'): DRAFT['script']=params['animation_script']
            if not DRAFT.get('style'): return 'Qual estilo de animação você quer? Cinematic, suave, dinâmico, documental ou vintage.'
            if not DRAFT.get('media_paths'): return 'Envie pelo chat a imagem/vídeo ou seu caminho local. Pode enviar vários arquivos, na ordem das cenas.'
            if not DRAFT.get('script'): return 'Descreva o roteiro detalhado: duração de cada cena, qual mídia usar, zoom ou deslocamento e fades. Exemplo: primeira imagem por 5 segundos com aproximação; depois a mesma imagem por 4 segundos deslocando para a direita.'
            plan=make_plan(DRAFT['style'],DRAFT['media_paths'],DRAFT['script'])
        if action=='cpu_render': return launch_job(plan)
        return 'Plano CPU validado. '+json.dumps(plan,ensure_ascii=False)+'. Para gerar, use cpu_render. A animação aplica movimentos de câmera e cores; não gera movimentos de pessoas/objetos. O áudio original dos vídeos não é usado; audio_path pode fornecer uma trilha.'
    except (ValueError,OSError) as exc: return 'Não foi possível preparar a animação: '+str(exc)


_EDITOR_PROCESS = None

def open_editor(project_path=None):
    global _EDITOR_PROCESS
    import sys
    if _EDITOR_PROCESS is not None and _EDITOR_PROCESS.poll() is None:
        return "O JARVIS Studio já está aberto. Selecione a janela JARVIS Studio na barra de tarefas."
    try:
        import PyQt6
    except ImportError:
        return "Execute tools\\video\\INSTALAR_ANIMACAO_CPU.bat para instalar o editor."
    args=[sys.executable,"-m","actions.animation_editor"]
    if project_path:
        path=Path(project_path).expanduser().resolve()
        if not path.is_file(): return "Projeto não encontrado."
        args += ["--project",str(path)]
    _EDITOR_PROCESS=subprocess.Popen(args,cwd=BASE,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    return "JARVIS Studio aberto. Use 'Usar última imagem gerada' ou 'Adicionar imagens', monte as cenas e clique em Exportar MP4."


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--plan',type=Path,help='JSON com style, media_paths e animation_script')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.check: print(ffmpeg_path()); return
    if args.plan:
        data=json.loads(args.plan.read_text(encoding='utf-8-sig'))
    else:
        print('JARVIS | Animação CPU. Zoom, deslocamento, cor e fades; saída sem áudio.')
        style=input('Estilo (cinematic/suave/dinamico/documental/vintage): ').strip()
        paths=input('Mídias (caminhos separados por ;): ').strip()
        print('Roteiro JSON. Cole e finalize com uma linha FIM. Exemplo:')
        print(json.dumps(EXAMPLE,ensure_ascii=False))
        lines=[]
        while True:
            line=input()
            if line.strip().upper()=='FIM': break
            lines.append(line)
        data=dict(style=style,media_paths=[x.strip() for x in paths.split(';') if x.strip()],animation_script='\n'.join(lines))
    plan=make_plan(data['style'],data['media_paths'],data['animation_script'])
    output=args.output or OUTPUT/f'{uuid.uuid4().hex[:12]}.mp4'
    print(render(plan,output))

if __name__=='__main__':
    try: main()
    except (ValueError,RuntimeError,OSError,KeyError) as exc: raise SystemExit(str(exc))
