"""Local authenticated LRM transport; never launches Chrome/Edge as fallback."""
import json
import os
import subprocess
import time
import urllib.request
import webbrowser
from pathlib import Path

CONNECTION = Path(r'D:\LRM-Engine\perfil\jarvis-navigation.json')

def _request(parameters):
    settings = json.loads(CONNECTION.read_text(encoding='utf-8'))
    port = int(settings['port'])
    if not 1024 <= port <= 65535:
        raise ValueError('Invalid local port')
    request = urllib.request.Request(f'http://127.0.0.1:{port}/command', data=json.dumps(parameters).encode(), headers={'Content-Type':'application/json','Authorization':'Bearer '+settings['token']}, method='POST')
    # No proxy or redirect may receive the local credential.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs): return None
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    with opener.open(request,timeout=120) as response:
        return json.loads(response.read(100000))

def navigate(parameters):
    try:
        _request({'action':'status'})
    except Exception:
        env=os.environ.copy()
        env.pop('ELECTRON_RUN_AS_NODE',None)
        env.pop('LRM_TEST_PROFILE',None)
        subprocess.Popen(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-WindowStyle','Hidden','-File',r'D:\LRM-Engine\Iniciar-LRM.ps1','-Background'],env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        for _ in range(60):
            time.sleep(2)
            try:
                _request({'action':'status'})
                break
            except Exception: pass
        else:
            return 'LRM não respondeu. Abra o atalho LRM Engine e tente novamente.'
    try:
        return str(_request(parameters).get('message','Sem resposta do LRM.'))
    except Exception:
        return 'Falha na comunicação local com o LRM. Nenhum outro navegador foi aberto.'

def install_web_routing():
    if getattr(webbrowser,'_lrm_installed',False): return
    original=webbrowser.open
    def routed(url,new=0,autoraise=True):
        if str(url).lower().startswith(('https://','http://')):
            result=navigate({'action':'go_to','url':str(url)})
            return result.startswith('Navegação encaminhada')
        return original(url,new,autoraise)
    webbrowser.open=routed
    webbrowser.open_new=lambda url:routed(url,1)
    webbrowser.open_new_tab=lambda url:routed(url,2)
    webbrowser._lrm_installed=True
