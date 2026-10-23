"""Lightweight advertisement editor for MARK-XL, backed by FFmpeg on CPU."""
from __future__ import annotations
import json
import os
import re
import sys
import threading
import uuid
from pathlib import Path
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QPixmap, QDesktopServices, QFontDatabase, QFont
from PyQt6.QtWidgets import (QApplication,QMainWindow,QWidget,QHBoxLayout,QVBoxLayout,QLabel,QPushButton,QListWidget,QListWidgetItem,QFileDialog,QComboBox,QDoubleSpinBox,QSpinBox,QLineEdit,QPlainTextEdit,QTableWidget,QTableWidgetItem,QHeaderView,QSplitter,QTabWidget,QMessageBox,QProgressBar)
from actions.animation_cpu import BASE,OUTPUT,STILLS,VIDEOS,MOTIONS,STYLES,make_plan,render,Cancelled

MOTION_LABELS={'zoom_in':'Aproximação','zoom_out':'Afastamento','pan_left':'Para esquerda','pan_right':'Para direita','pan_up':'Para cima','pan_down':'Para baixo','static':'Sem movimento'}
CSS='''QMainWindow,QWidget{background:#10141c;color:#e9eef7;font-family:Segoe UI;font-size:12px;} QLabel#brand{font-size:23px;font-weight:700;color:white;} QLabel#subtitle{color:#8e9cb2;} QPushButton{background:#222d3f;border:1px solid #36465c;border-radius:7px;padding:9px 13px;} QPushButton:hover{background:#304159;} QPushButton:disabled{color:#637086;background:#1a2130;} QPushButton#primary{background:#3768ef;color:white;border:0;font-weight:bold;} QLineEdit,QPlainTextEdit,QListWidget,QTableWidget,QComboBox,QSpinBox,QDoubleSpinBox{background:#171e2a;border:1px solid #303b50;border-radius:5px;padding:5px;} QHeaderView::section{background:#253044;color:#cbd6e8;padding:8px;border:0;} QTableWidget::item:selected,QListWidget::item:selected{background:#29467a;} QTabBar::tab{padding:9px 14px;background:#1b2332;} QTabBar::tab:selected{background:#29467a;} QProgressBar{border:0;background:#222d3f;border-radius:4px;text-align:center;} QProgressBar::chunk{background:#3768ef;} QSplitter::handle{background:#273248;}'''

class Worker(QThread):
    progress=pyqtSignal(str)
    done=pyqtSignal(str)
    failed=pyqtSignal(str)
    def __init__(self,plan,path):
        super().__init__(); self.plan=plan; self.path=path; self.cancel=threading.Event()
    def run(self):
        try: self.done.emit(str(render(self.plan,self.path,self.cancel,self.progress.emit)))
        except Exception as exc: self.failed.emit(str(exc))

class Editor(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle('JARVIS Studio | Propagandas • CPU'); self.resize(1320,900); self.setMinimumSize(980,720)
        # Explicit font loading also supports offscreen previews on Windows.
        fontdir=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Fonts'
        for filename in ('segoeui.ttf','segoeuib.ttf'):
            if (fontdir/filename).is_file():QFontDatabase.addApplicationFont(str(fontdir/filename))
        QApplication.instance().setFont(QFont('Segoe UI',10))
        self.media=[]; self.worker=None; self.last_output=None; self.project_file=None; self.player=None
        self.setAcceptDrops(True)
        root=QWidget(); self.setCentralWidget(root); layout=QVBoxLayout(root); layout.setContentsMargins(22,18,22,18); layout.setSpacing(13)
        top=QHBoxLayout(); brand=QLabel('JARVIS STUDIO'); brand.setObjectName('brand'); top.addWidget(brand)
        sub=QLabel('IMAGENS → PROPAGANDAS  /  CPU'); sub.setObjectName('subtitle'); top.addWidget(sub); top.addStretch()
        self.button(top,'Abrir projeto',self.open_project); self.button(top,'Salvar projeto',self.save_project)
        self.export=self.button(top,'Exportar MP4',lambda:self.export_video(False),'primary'); layout.addLayout(top)
        settings=QHBoxLayout()
        self.style=QComboBox(); self.style.addItems(list(STYLES)); self.ratio=QComboBox(); self.ratio.addItems(['9:16','16:9','1:1']); self.size=QComboBox(); self.size.addItems(['720','480','1080']); self.fps=QComboBox(); self.fps.addItems(['24','15','30'])
        for label,widget in [('Estilo',self.style),('Formato',self.ratio),('Resolução',self.size),('FPS',self.fps)]: settings.addWidget(QLabel(label)); settings.addWidget(widget)
        settings.addStretch(); self.draft=self.button(settings,'Gerar prévia 480p',lambda:self.export_video(True)); layout.addLayout(settings)
        split=QSplitter(Qt.Orientation.Horizontal); layout.addWidget(split,1)
        library=QWidget(); ll=QVBoxLayout(library); ll.setContentsMargins(0,0,12,0); ll.addWidget(QLabel('01  MÍDIAS DO PROJETO'))
        self.library=QListWidget(); self.library.currentRowChanged.connect(self.preview_media); ll.addWidget(self.library)
        self.button(ll,'+ Adicionar imagens / vídeos',self.pick_media)
        self.button(ll,'Imagens geradas pelo Jarvis',self.pick_generated)
        self.button(ll,'Usar última imagem gerada',self.latest_image)
        self.button(ll,'Adicionar mídia à sequência',self.add_selected_scene)
        split.addWidget(library)
        center=QWidget(); cl=QVBoxLayout(center); cl.setContentsMargins(8,0,8,0); cl.addWidget(QLabel('02  PRÉVIA'))
        self.tabs=QTabWidget(); self.image=QLabel('Adicione uma imagem ou arraste arquivos para esta janela.'); self.image.setAlignment(Qt.AlignmentFlag.AlignCenter); self.image.setMinimumSize(300,220); self.tabs.addTab(self.image,'Imagem original')
        try:
            from PyQt6.QtMultimedia import QMediaPlayer,QAudioOutput
            from PyQt6.QtMultimediaWidgets import QVideoWidget
            self.video=QVideoWidget(); self.player=QMediaPlayer(self); self.audio=QAudioOutput(self); self.player.setAudioOutput(self.audio); self.player.setVideoOutput(self.video); self.tabs.addTab(self.video,'Vídeo renderizado')
            self.player.errorOccurred.connect(lambda *args:self.status.setText('Prévia: '+self.player.errorString()+' — use Abrir MP4 para o player do sistema.'))
        except ImportError: pass
        cl.addWidget(self.tabs,1)
        playrow=QHBoxLayout(); self.button(playrow,'▶ Reproduzir',self.play); self.button(playrow,'Pausar',lambda:self.player.pause() if self.player else None); self.button(playrow,'Abrir MP4',self.open_output); cl.addLayout(playrow)
        cl.addWidget(QLabel('A prévia de imagem não simula os efeitos. Gere a prévia para ver o resultado.'))
        split.addWidget(center)
        right=QWidget(); rl=QVBoxLayout(right); rl.setContentsMargins(12,0,0,0); rl.addWidget(QLabel('03  ROTEIRO DA PROPAGANDA'))
        rl.addWidget(QLabel('Uma cena por linha: duração | movimento | texto\nEx.: 5s | zoom_in | Sua oferta começa aqui'))
        self.brief=QPlainTextEdit(); self.brief.setPlaceholderText('5s | zoom_in | Conheça o produto\n4s | pan_right | Feito para você\n3s | zoom_out | Peça agora'); rl.addWidget(self.brief)
        self.button(rl,'Aplicar roteiro às mídias',self.apply_brief)
        rl.addWidget(QLabel('TRILHA SONORA (opcional)')); self.audio_path=QLineEdit(); self.audio_path.setReadOnly(True); rl.addWidget(self.audio_path)
        self.button(rl,'Escolher áudio',self.pick_audio); self.button(rl,'Remover áudio',lambda:self.audio_path.clear())
        hint=QLabel('A trilha repete até o fim do vídeo.\nO áudio original dos clipes não é usado.\n\nNo chat do Jarvis, você pode descrever o roteiro em linguagem natural.'); hint.setWordWrap(True); hint.setObjectName('subtitle'); rl.addWidget(hint)
        split.addWidget(right); split.setSizes([260,620,330])
        layout.addWidget(QLabel('04  SEQUÊNCIA DE CENAS  •  ajuste os textos, tempos e movimentos'))
        self.table=QTableWidget(0,7); self.table.setHorizontalHeaderLabels(['Mídia','Segundos','Movimento','Fade (s)','Texto da oferta','Posição','Fonte'])
        self.table.horizontalHeader().setSectionResizeMode(4,QHeaderView.ResizeMode.Stretch); self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.table.setMinimumHeight(175); self.table.setMaximumHeight(260); layout.addWidget(self.table)
        row=QHBoxLayout(); self.button(row,'↑ Subir',lambda:self.move_scene(-1)); self.button(row,'↓ Descer',lambda:self.move_scene(1)); self.button(row,'Duplicar',self.duplicate); self.button(row,'Remover cena',self.remove_scene); row.addStretch(); self.total=QLabel('0 cenas'); row.addWidget(self.total); layout.addLayout(row)
        foot=QHBoxLayout(); self.status=QLabel('Pronto. Importe suas imagens para começar.'); self.status.setWordWrap(True); foot.addWidget(self.status,1); self.progress=QProgressBar(); self.progress.setRange(0,1); self.progress.setValue(0); self.progress.setMaximumWidth(160); foot.addWidget(self.progress); self.cancel_button=self.button(foot,'Cancelar render',self.cancel); self.cancel_button.setEnabled(False); layout.addLayout(foot)
        self.setStyleSheet(CSS)

    def button(self,layout,text,callback,name=None):
        b=QPushButton(text); b.clicked.connect(callback)
        if name:b.setObjectName(name)
        layout.addWidget(b); return b
    def error(self,exc): QMessageBox.warning(self,'JARVIS Studio',str(exc))
    def add_media(self,paths):
        for raw in paths:
            p=Path(raw).resolve()
            if p.is_file() and p.suffix.lower() in STILLS|VIDEOS and str(p) not in self.media:
                if len(self.media)>=20: self.error('Máximo de 20 mídias.'); break
                self.media.append(str(p)); self.library.addItem(f'{len(self.media):02d}  {p.name}'); self.add_scene({'media':len(self.media)})
        if self.media:self.library.setCurrentRow(len(self.media)-1)
    def pick_media(self):
        paths,_=QFileDialog.getOpenFileNames(self,'Adicionar mídias',str(BASE/'generated_images'),'Mídias (*.png *.jpg *.jpeg *.webp *.bmp *.mp4 *.mov *.mkv *.webm *.avi)'); self.add_media(paths)
    def pick_generated(self): self.pick_media()
    def latest_image(self):
        folder=BASE/'generated_images'; files=[p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in STILLS] if folder.exists() else []
        if not files:self.error('Nenhuma imagem gerada encontrada em generated_images.'); return
        self.add_media([max(files,key=lambda p:p.stat().st_mtime)])
    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls():event.acceptProposedAction()
    def dropEvent(self,event): self.add_media([u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()])
    def preview_media(self,index):
        if not 0<=index<len(self.media):return
        pix=QPixmap(self.media[index])
        if pix.isNull():self.image.setText('Clipe de vídeo selecionado. Gere uma prévia para reproduzir.'); return
        self.image.setPixmap(pix.scaled(self.image.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)); self.tabs.setCurrentIndex(0)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'library'):self.preview_media(self.library.currentRow())
    def add_selected_scene(self):
        i=self.library.currentRow()
        if i>=0:self.add_scene({'media':i+1})
    def add_scene(self,scene):
        if self.table.rowCount()>=20:self.error('Máximo de 20 cenas.');return
        i=self.table.rowCount(); self.table.insertRow(i)
        media=QSpinBox(); media.setRange(1,20); media.setValue(scene.get('media',1)); self.table.setCellWidget(i,0,media)
        duration=QDoubleSpinBox(); duration.setRange(.5,60);duration.setSingleStep(.5);duration.setValue(scene.get('duration',5)); self.table.setCellWidget(i,1,duration)
        motion=QComboBox()
        for key,label in MOTION_LABELS.items():motion.addItem(label,key)
        motion.setCurrentIndex(max(0,motion.findData(scene.get('motion','zoom_in')))); self.table.setCellWidget(i,2,motion)
        fade=QDoubleSpinBox();fade.setRange(0,5);fade.setSingleStep(.1);fade.setValue(scene.get('fade',.3)); self.table.setCellWidget(i,3,fade)
        self.table.setItem(i,4,QTableWidgetItem(scene.get('caption','')))
        position=QComboBox(); position.addItem('Embaixo','bottom'); position.addItem('Centro','center');position.addItem('Em cima','top');position.setCurrentIndex(max(0,position.findData(scene.get('caption_position','bottom'))));self.table.setCellWidget(i,5,position)
        font=QSpinBox();font.setRange(16,100);font.setValue(scene.get('caption_size',40));self.table.setCellWidget(i,6,font)
        duration.valueChanged.connect(self.update_total); self.update_total()
    def scenes(self):
        return [dict(media=self.table.cellWidget(i,0).value(),duration=self.table.cellWidget(i,1).value(),motion=self.table.cellWidget(i,2).currentData(),fade=self.table.cellWidget(i,3).value(),caption=self.table.item(i,4).text(),caption_position=self.table.cellWidget(i,5).currentData(),caption_size=self.table.cellWidget(i,6).value()) for i in range(self.table.rowCount())]
    def update_total(self):
        if hasattr(self,'total'):self.total.setText(f'{self.table.rowCount()} cenas • {sum(s["duration"] for s in self.scenes()):g} s')
    def replace_scenes(self,scenes):
        self.table.setRowCount(0)
        for s in scenes:self.add_scene(s)
        self.update_total()
    def remove_scene(self):
        i=self.table.currentRow()
        if i>=0:self.table.removeRow(i);self.update_total()
    def duplicate(self):
        i=self.table.currentRow()
        if i>=0:self.add_scene(self.scenes()[i])
    def move_scene(self,delta):
        i=self.table.currentRow();j=i+delta;rows=self.scenes()
        if i>=0 and 0<=j<len(rows):rows[i],rows[j]=rows[j],rows[i];self.replace_scenes(rows);self.table.selectRow(j)
    def apply_brief(self):
        try:
            if not self.media:raise ValueError('Adicione as imagens primeiro.')
            scenes=[]
            for line in self.brief.toPlainText().splitlines():
                if not line.strip():continue
                parts=line.split('|',2)
                if len(parts)<2:raise ValueError('Use duração | movimento | texto em cada linha.')
                duration=float(parts[0].strip().lower().removesuffix('s').replace(',','.')); motion=parts[1].strip()
                if motion not in MOTIONS:raise ValueError('Movimentos: '+', '.join(sorted(MOTIONS)))
                scenes.append(dict(media=min(len(scenes)+1,len(self.media)),duration=duration,motion=motion,caption=parts[2].strip() if len(parts)>2 else '',fade=min(.3,duration/2)))
            make_plan(self.style.currentText(),self.media,{'scenes':scenes})
            self.replace_scenes(scenes);self.status.setText('Roteiro aplicado. Revise a sequência e gere uma prévia.')
        except (ValueError,TypeError) as exc:self.error(exc)
    def pick_audio(self):
        path,_=QFileDialog.getOpenFileName(self,'Trilha sonora','','Áudio (*.mp3 *.wav *.m4a *.aac *.ogg *.flac)')
        if path:self.audio_path.setText(path)
    def project(self):
        return {'style':self.style.currentText(),'media_paths':self.media,'animation_script':{'scenes':self.scenes(),'size':int(self.size.currentText()),'fps':int(self.fps.currentText()),'ratio':self.ratio.currentText(),'audio_path':self.audio_path.text()},'brief':self.brief.toPlainText()}
    def save_project(self):
        path,_=QFileDialog.getSaveFileName(self,'Salvar projeto',str(self.project_file or BASE/'propaganda.json'),'Projeto (*.json)')
        if path:
            try:Path(path).write_text(json.dumps(self.project(),ensure_ascii=False,indent=2),encoding='utf-8');self.project_file=path;self.status.setText('Projeto salvo.')
            except OSError as exc:self.error(exc)
    def load_project(self,path):
        data=json.loads(Path(path).read_text(encoding='utf-8-sig'));raw=data['animation_script'];plan=make_plan(data['style'],data['media_paths'],raw)
        # Validate before replacing the editor contents.
        if any(s.get('start',0) for s in plan['scenes']):raise ValueError('Projetos com start devem ser renderizados pelo chat/CLI; este editor trabalha desde o início do clipe.')
        self.media=[];self.library.clear();self.table.setRowCount(0);self.add_media(plan['media']);self.replace_scenes(plan['scenes']);self.style.setCurrentText(plan['style']);self.ratio.setCurrentText(plan['ratio']);self.size.setCurrentText(str(plan['size']));self.fps.setCurrentText(str(plan['fps']));self.audio_path.setText(plan['audio_path']);self.brief.setPlainText(data.get('brief',''));self.project_file=path
    def open_project(self):
        path,_=QFileDialog.getOpenFileName(self,'Abrir projeto',str(BASE),'Projeto (*.json)')
        if path:
            try:self.load_project(path)
            except (OSError,ValueError,KeyError,TypeError) as exc:self.error(exc)
    def export_video(self,preview=False):
        if self.worker and self.worker.isRunning():return
        try:
            data=self.project()
            if preview:data['animation_script']['size']=480
            plan=make_plan(data['style'],data['media_paths'],data['animation_script'])
            OUTPUT.mkdir(parents=True,exist_ok=True); path=OUTPUT/f'{"previa" if preview else "propaganda"}_{uuid.uuid4().hex[:10]}.mp4'
            (path.with_suffix('.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
            self.worker=Worker(plan,path);self.worker.progress.connect(self.update_render_progress);self.worker.done.connect(self.render_done);self.worker.failed.connect(self.render_failed);self.worker.finished.connect(self.render_finished);self.export.setEnabled(False);self.draft.setEnabled(False);self.cancel_button.setEnabled(True);self.progress.setRange(0,100);self.progress.setValue(0);self.status.setText('Renderizando pela CPU…');self.worker.start()
        except (OSError,ValueError) as exc:self.error(exc)
    def update_render_progress(self,message):
        self.status.setText(message)
        match=re.match(r'\s*([0-9]+(?:\.[0-9]+)?)%',message)
        if match:self.progress.setValue(max(0,min(100,int(float(match.group(1))))))
    def render_done(self,path):
        self.last_output=path;self.status.setText('MP4 pronto: '+path)
        if self.player:self.player.setSource(QUrl.fromLocalFile(path));self.tabs.setCurrentIndex(1)
    def render_failed(self,message):self.status.setText(message);self.error(message)
    def render_finished(self):self.export.setEnabled(True);self.draft.setEnabled(True);self.cancel_button.setEnabled(False);self.progress.setRange(0,1);self.progress.setValue(1)
    def cancel(self):
        if self.worker:self.worker.cancel.set();self.status.setText('Cancelando…')
    def play(self):
        if self.player and self.last_output:self.player.play()
        elif self.last_output:self.open_output()
    def open_output(self):
        if self.last_output:QDesktopServices.openUrl(QUrl.fromLocalFile(self.last_output))
    def closeEvent(self,event):
        if self.worker and self.worker.isRunning():self.error('Cancele ou aguarde a renderização antes de fechar.');event.ignore();return
        if self.player:self.player.stop()
        event.accept()

def main():
    app=QApplication(sys.argv);window=Editor()
    if '--project' in sys.argv:
        try:window.load_project(sys.argv[sys.argv.index('--project')+1])
        except Exception as exc:window.error(exc)
    window.show();sys.exit(app.exec())
if __name__=='__main__':main()
