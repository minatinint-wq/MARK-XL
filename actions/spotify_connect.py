"""Shared Spotify playback routing. Explicit targets never fall back to the PC."""
import re
import unicodedata

ALIASES = {
    'tocar':'play','play/pause':'toggle','pausar':'pause','skip':'next','proxima':'next',
    'back':'previous','voltar':'previous','anterior':'previous','mais':'volume_up','menos':'volume_down',
    'aumentar_volume':'volume_up','diminuir_volume':'volume_down','volume_set':'volume','set_volume':'volume',
    'definir_volume':'volume','buscar':'search','find':'search','now playing':'current',"what's playing":'current',
    'aleatorio':'shuffle','repetir':'repeat','device':'devices','dispositivos':'devices',
    'connect':'devices','connect_device':'devices','transfer':'devices',
}
def norm(text):
    return ' '.join(re.sub(r'[^\w\s]', ' ', ''.join(c for c in unicodedata.normalize('NFKD', str(text or '').casefold()) if not unicodedata.combining(c))).split())

def action_name(action):
    raw=str(action or '').strip().lower()
    key=''.join(c for c in unicodedata.normalize('NFKD',raw) if not unicodedata.combining(c))
    if re.fullmatch(r'(?:volume_)?\d{1,3}%?',key):return 'volume'
    return ALIASES.get(key,key)

def handles(action):
    return action_name(action) in {'play','toggle','pause','next','previous','volume','volume_up','volume_down','search','current','shuffle','repeat','devices'}

def device_request(params):
    return str(params.get('device_id') or params.get('device') or params.get('device_name') or params.get('target') or '').strip()

def format_devices(devices):
    if not devices:return 'Nenhum dispositivo Spotify encontrado. Abra o Spotify no aparelho e tente novamente.'
    lines=['Dispositivos Spotify disponíveis:']
    for d in devices:
        volume=d.get('volume_percent')
        suffix=f" · {volume}%" if volume is not None else ''
        if d.get('is_active'):suffix+=' · ATIVO'
        if d.get('supports_volume') is False:suffix+=' · volume manual'
        if d.get('is_restricted'):suffix+=' · controle restrito'
        lines.append(f"• {d.get('name','?')} ({d.get('type','device')}){suffix}")
    return '\n'.join(lines)

def devices_text(sp):
    return format_devices((sp.devices() or {}).get('devices',[]))

def pick_device(sp, device=''):
    devices=[d for d in (sp.devices() or {}).get('devices',[]) if isinstance(d,dict)]
    if not devices:return None,devices,format_devices(devices)
    matches=[]
    if device:
        raw=str(device).strip().lstrip('• ').split('·',1)[0].strip()
        matches=[d for d in devices if str(d.get('id') or '')==raw]
        if not matches:matches=[d for d in devices if norm(raw) in {norm(d.get('name')),norm(f"{d.get('name')} ({d.get('type')})")}]
        if not matches:
            # Strip only known type suffixes, not arbitrary parts of a real name.
            clean=re.sub(r'\s*\((?:smartphone|computer|speaker|tv|tablet|castaudio|castvideo|gameconsole|automobile|unknown|device)\)\s*$','',raw,flags=re.I)
            needle=norm(clean)
            matches=[d for d in devices if needle and needle in norm(d.get('name'))]
        if not matches:return None,devices,f"Dispositivo '{device}' não encontrado.\n{format_devices(devices)}"
    else:
        matches=[d for d in devices if d.get('is_active')]
        if not matches and len(devices)==1:matches=devices
    if len(matches)!=1:
        return None,devices,'Escolha um dispositivo pelo nome completo ou ID; há mais de uma possibilidade.\n'+format_devices(matches or devices)
    target=matches[0]
    if not target.get('id'):return None,devices,'O Spotify não forneceu o ID deste aparelho. Abra o app nele e tente novamente.'
    if target.get('is_restricted'):return None,devices,f"O dispositivo {target.get('name')} restringe comandos pela API Spotify."
    return target,devices,None

def error_text(exc):
    status=getattr(exc,'http_status',getattr(exc,'status_code',0))
    if status==401:return 'A autorização Spotify expirou. Reconecte a conta nas configurações do Spotify do Jarvis.'
    if status==403:return 'Spotify recusou o controle (403). Confira o plano Premium, as permissões da conta e as restrições do dispositivo.'
    if status==404:return 'O player Spotify não está disponível nesse aparelho. Abra o app nele, toque algo e tente novamente.'
    if status==429:
        headers=getattr(exc,'headers',{}) or {};delay=str(headers.get('Retry-After',headers.get('retry-after','')))
        return f'Spotify limitou as chamadas. Aguarde {delay} segundos antes de repetir.' if delay.isdigit() else 'Spotify limitou as chamadas. Aguarde um pouco antes de repetir.'
    if isinstance(status,int) and status>=500:return 'O serviço Spotify está temporariamente indisponível. Tente novamente em instantes.'
    return 'Não foi possível confirmar o comando no Spotify. Confira a conexão antes de repetir.'

def _start(sp,target,kwargs):
    # A 404 means the player disappeared after devices() was read. Retrying a
    # transfer/play against that stale id only creates rate-limit noise; the
    # next explicit request will fetch a fresh device list instead.
    sp.start_playback(device_id=target['id'],**kwargs)

def start_on_device(sp,device='',**kwargs):
    target,_,error=pick_device(sp,device)
    if error:return error,None
    try:_start(sp,target,kwargs)
    except Exception as exc:return error_text(exc),None
    return f"Tocando em {target['name']}.",target

def transfer_to_device(sp,device,force_play=True):
    target,_,error=pick_device(sp,device)
    if error:return error
    try:sp.transfer_playback(target['id'],force_play=force_play)
    except Exception as exc:return error_text(exc)
    return f"Spotify transferido para {target['name']}."

def percent(value):
    if isinstance(value,bool) or not re.fullmatch(r'\s*\d{1,3}\s*%?\s*',str(value)):
        raise ValueError('Informe um volume inteiro de 0 a 100, por exemplo 80%.')
    result=int(str(value).strip().rstrip('%').strip())
    if not 0<=result<=100:raise ValueError('O volume deve ficar entre 0 e 100%.')
    return result

def control(sp,action,params):
    raw=action;action=action_name(action);device=device_request(params)
    if not handles(action):return None
    try:
        if action=='devices':return transfer_to_device(sp,device) if device else devices_text(sp)
        if action=='current':
            cur=sp.current_playback() or {};item=cur.get('item') or {}
            if not item:return 'Nada tocando no momento.'
            artists=', '.join(a.get('name','') for a in item.get('artists',[]))
            return f"{item.get('name','?')} — {artists} em {(cur.get('device') or {}).get('name','?')}"
        target,_,error=pick_device(sp,device)
        if error:return error
        did=target['id'];where=target.get('name','Spotify')
        query=str(params.get('query') or params.get('text') or '').strip()
        if action=='search' or action=='play' and query:
            if not query:return 'O que você quer ouvir no Spotify?'
            tracks=((sp.search(q=query,limit=3,type='track') or {}).get('tracks') or {}).get('items',[])
            if not tracks:return f'Nenhuma música encontrada para {query}.'
            _start(sp,target,{'uris':[t['uri'] for t in tracks if t.get('uri')]})
            return f"Tocando {tracks[0]['name']} em {where}."
        if action=='play':_start(sp,target,{})
        elif action=='toggle':
            cur=sp.current_playback() or {}
            if cur.get('is_playing') and (cur.get('device') or {}).get('id')==did:
                sp.pause_playback(device_id=did);return f'Pausado em {where}.'
            _start(sp,target,{})
        elif action=='pause':sp.pause_playback(device_id=did)
        elif action=='next':sp.next_track(device_id=did)
        elif action=='previous':sp.previous_track(device_id=did)
        elif action.startswith('volume'):
            if target.get('supports_volume') is False:
                return f'{where} não permite ajustar volume pela API Spotify. Use os botões de volume desse aparelho.'
            val=next((params[k] for k in ('value','volume','volume_percent','amount') if params.get(k) is not None),None)
            if action=='volume':
                if val is None and re.fullmatch(r'(?:volume_)?\d{1,3}%?',str(raw)):val=str(raw).removeprefix('volume_')
                if val is None:return 'Qual volume deseja? Informe de 0 a 100%.'
                volume=percent(val)
            else:
                current=target.get('volume_percent')
                if current is None:return f'{where} não informou o volume atual. Peça um valor absoluto, por exemplo 50%.'
                step=percent(10 if val is None else val)
                volume=max(0,min(100,int(current)+(step if action=='volume_up' else -step)))
            sp.volume(volume,device_id=did)
            return f'Volume do Spotify em {where} ajustado para {volume}%.'
        elif action in {'shuffle','repeat'}:
            current=sp.current_playback() or {}
            same=(current.get('device') or {}).get('id')==did
            state=params.get('state',params.get('value'))
            if action=='shuffle':
                if state is None:
                    if not same:return 'Para esse aparelho, informe aleatório ativado ou desativado.'
                    state=not current.get('shuffle_state',False)
                elif not isinstance(state,bool):
                    if norm(state) not in {'true','false','on','off','ativado','desativado'}:return 'Use aleatório ativado ou desativado.'
                    state=norm(state) in {'true','on','ativado'}
                sp.shuffle(state,device_id=did)
            else:
                if state is None:
                    if not same:return 'Informe repetir off, context ou track para esse aparelho.'
                    state={'off':'context','context':'track','track':'off'}.get(current.get('repeat_state'),'off')
                if state not in {'off','context','track'}:return 'Use repetir off, context ou track.'
                sp.repeat(state,device_id=did)
            return f'{action} em {where}: {state}.'
        return {'play':f'Tocando em {where}.','toggle':f'Tocando em {where}.','pause':f'Pausado em {where}.','next':f'Próxima música em {where}.','previous':f'Música anterior em {where}.'}[action]
    except ValueError as exc:return str(exc)
    except Exception as exc:return error_text(exc)
