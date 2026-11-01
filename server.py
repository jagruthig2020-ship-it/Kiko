"""KIKO · local multilingual Windows screen coach. No keys or cloud model.

Start: python server.py  |  Windows hotkey: Ctrl+Alt+K (inspect visible app).
"""
from __future__ import annotations
import base64
import copy
import json
import os
from pathlib import Path
import secrets
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import engine
import native
import local_actions
import apps
from lessons import TASKS, topic_for

APP=Path(__file__).resolve().parent
DATA=Path(os.getenv('LOCALAPPDATA',str(Path.home()))) / 'KIKO'
PROGRESS=DATA/'learner_progress.json'
TOKEN=secrets.token_urlsafe(25)
OLLAMA='http://127.0.0.1:11434'
MODEL='gemma3:4b'
LOCK=threading.RLock()
OVERLAY=native.Highlight()
STATE={'task':'','lang':'en','topic':None,'phase':'idle','message':'','guide':None,'busy':False,'hints':0,'inspect_count':0,'hotkey':False,'revision':0,'window':'','target_hwnd':None,'window_bounds':None,'app_choices':[],'target_app':''}
SERVER=None
_model_checked=0.0
_model_ok=False
_model_lock=threading.Lock()


def _update(**kwargs):
    with LOCK:
        STATE.update(kwargs)
        STATE['revision']+=1


def _state():
    with LOCK:return copy.deepcopy(STATE)


def progress_data():
    try:return json.loads(PROGRESS.read_text('utf-8'))
    except (ValueError,OSError):return {}


def mark_complete(task,topic,hints):
    data=progress_data()
    key=(topic or task.casefold().strip()[:80])
    old=data.get(key,{'completions':0,'hints':0})
    old['completions']+=1;old['hints']+=hints
    data[key]=old
    DATA.mkdir(parents=True,exist_ok=True)
    temp=PROGRESS.with_suffix('.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(PROGRESS)
    return old


def model_ready():
    """Fast, cached status to avoid repeatedly blocking the UI on Ollama requests."""
    global _model_checked, _model_ok
    with _model_lock:
        if time.monotonic()-_model_checked<7:
            return _model_ok
        try:
            with urllib.request.urlopen(OLLAMA+'/api/tags',timeout=1.8) as r:
                models=json.load(r).get('models',[])
            _model_ok=any(x.get('name','').lower().startswith('gemma3:4b') for x in models)
        except (OSError,ValueError):
            _model_ok=False
        _model_checked=time.monotonic()
        return _model_ok


def ollama_vision(task,lang,topic,history,help_needed,image_bytes,rect,controls,completed=0):
    if not model_ready():
        raise RuntimeError('Ollama Gemma 3 is missing. Run: ollama pull gemma3:4b')
    supported={'en':'English','te':'natural Telugu (తెలుగు script)','hi':'natural Hindi (देवनागरी script)'}
    short=json.dumps([{'id':c['id'],'name':c['name'],'type':c['type']} for c in controls[:130]],ensure_ascii=False)
    prompt=(
        'You are KIKO, an accessible, patient computer-use TUTOR, never an autonomous operator. '
        'You are looking at a screenshot of the CURRENT real Windows application. '
        f'Goal: {task[:260]!r}. Reply exclusively in {supported[lang]}, except exact English UI labels. '
        'Say EXACTLY ONE actionable step based on the screen, not generic Windows advice. '
        'Choose a visible target from the numbered Windows accessibility controls when one matches; '
        'otherwise locate a visible button using image coordinates. NEVER invent target positions. '
        'Do not offer to click for the user; they must click. Do not ask for credentials, payments or secrets. '
        f'Previous step: {history[:220]!r}. The learner previously reported completing this task {completed} time(s). '
        f'{"The user is stuck. Explain more clearly with smaller instructions." if help_needed else ("Use a minimal hint, since this learner has practiced the task before." if completed else "Keep explanation short and concrete.")} '
        'Return ONLY JSON with exactly fields: '
        '{"instruction":"one small step","found":true,"control_id":1,"x":null,"y":null}. '
        'When choosing a control from list, set control_id to its numeric id. '
        'If there is NO suitable listed control, use found=true and x/y as the CENTER of the control '
        'in the screenshot scaled 0..1000 (top-left 0,0; bottom-right 1000,1000), control_id=null. '
        'When uncertain or no control is visible, return found=false and null target fields. '
        'Do not claim success until a screen actually shows success. '
        f'Accessible controls: {short}'
    )
    request={'model':MODEL,'stream':False,'format':'json','options':{'temperature':0.1,'num_predict':350},
             'messages':[{'role':'user','content':prompt,'images':[base64.b64encode(image_bytes).decode('ascii')]}]}
    req=urllib.request.Request(OLLAMA+'/api/chat',data=json.dumps(request).encode('utf-8'),headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=75) as res:
            result=json.load(res)
    except (TimeoutError,urllib.error.URLError) as exc:
        raise RuntimeError('Local model did not respond. Check that Ollama is running, then use Check Again.') from exc
    content=result.get('message',{}).get('content','')
    return engine.parse_model(content,rect[2],rect[3],controls,rect)


def ollama_controls(task,lang,history,controls,bounds,stuck=False,completed=0):
    """Screen-safe fallback: grounded accessibility data, no screenshot required."""
    if not model_ready():
        raise RuntimeError('Start Ollama and install gemma3:4b for unfamiliar screens.')
    if not controls:raise RuntimeError('This app does not expose readable controls.')
    language={'en':'English','te':'Telugu in Telugu script','hi':'Hindi in Devanagari script'}[lang]
    visible=[{'id':c['id'],'label':c['name'],'type':c['type']} for c in controls[:130]]
    prompt=(f'You are KIKO, a patient Windows navigation teacher. Reply in {language}; preserve Windows UI labels. '
        'The user clicks; you NEVER click. Pick exactly one relevant control from this real accessibility list. '
        'If no control fits, return found false rather than inventing a click. '
        'JSON ONLY: {"instruction":"one short next step", "found":true, "control_id":2}. '
        'When not found: {"instruction":"short honest explanation", "found":false, "control_id":null}. '
        'Never request secret codes, payments, passwords or account deletion. '
        f'Goal: {task[:250]}; previous: {history[:180]}; stuck: {stuck}; practiced: {completed}. '
        'Visible controls: '+json.dumps(visible,ensure_ascii=False))
    request={'model':MODEL,'stream':False,'format':'json',
             'options':{'temperature':0,'num_predict':220},
             'messages':[{'role':'user','content':prompt}]}
    req=urllib.request.Request(OLLAMA+'/api/chat',data=json.dumps(request).encode('utf-8'),
                               headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=50) as reply:
        content=json.load(reply).get('message',{}).get('content','')
    result=engine.parse_model(content,bounds[2],bounds[3],controls,bounds)
    result['source']='Windows accessibility + local Ollama (no screenshot)'
    return result


def _t(lang, en, te, hi):
    return {'en':en,'te':te,'hi':hi}.get(lang,en)


def _candidate_apps(task):
    """Find installed programs without ever waiting for Ollama.

    Opening an app is a Windows catalog operation, not an image-reasoning task.
    Keep matching deterministic even when the user speaks Telugu or Hindi.
    """
    requested = apps.extract_query(task)
    if requested is None:
        return None, []
    installed = apps.installed_apps()
    if not installed:
        return requested, []
    choices = apps.matches(requested, installed)
    # A longer spoken request can contain follow-up instructions (e.g.,
    # "open Spotify and find my playlist"). Recognize the installed name first.
    mentioned = apps.mentioned_apps(task, installed)
    if mentioned:
        choices = mentioned
    if (not requested or requested in ('game','games','a game','any','screen','any screen','something') or
        (('game' in task.casefold() or 'గేమ్' in task or 'गेम' in task) and requested in ('any','screen','something'))):
        game_terms = ('chess','solitaire','minecraft','roblox','game','puzzle','sudoku')
        choices = [{**a,'score':0.55} for a in installed if any(t in a['name'].casefold() for t in game_terms)][:8]
    return requested, choices


def _begin_installed_app(task,lang,app):
    # Intentionally NO model call for "open Spotify" / "Spotify తెరువు".
    # Windows is responsible for launching its registered Start-menu app.
    apps.launch(app)
    launch_only = apps.open_only_request(task, app['name'])
    msg = _t(lang,
        f'Asked Windows to open {app["name"]}. If it appears, you can use it now. Ask another question to learn a feature inside it.',
        f'{app["name"]} తెరవమని Windows‌కు చెప్పాను. యాప్ కనిపిస్తే ఇప్పుడు వాడవచ్చు. దానిలో ఏదైనా నేర్చుకోవాలంటే మళ్లీ అడగండి.',
        f'Windows को {app["name"]} खोलने के लिए कहा है। ऐप दिखे तो इस्तेमाल करें। उसमें कुछ सीखना हो तो फिर पूछें।')
    guide = {'instruction':msg,'point':None,'rect':None,'found':False,
             'source':'Windows installed-app launcher (no AI)'} if launch_only else None
    with LOCK:
        STATE.update(task=task,lang=lang,topic=None,
                     phase='guided' if launch_only else 'opening',message=msg,
                     hints=0,inspect_count=0,guide=guide,window='',busy=False,
                     target_hwnd=None,window_bounds=None,app_choices=[],target_app=app['name'])
        STATE['revision']+=1
    if not launch_only and native.IS_WINDOWS:
        _start_automatic_guide(None,lang,task,app_name=app['name'])
    return {'ok':True,'message':msg,'opened_app':app['name'],'launch_only':launch_only}


def choose_app(index):
    with LOCK:
        options=list(STATE.get('app_choices') or [])
        task=STATE['task'];lang=STATE['lang']
    if not isinstance(index,int) or not 0<=index<len(options):
        raise ValueError('Choose one of the suggested installed apps.')
    return _begin_installed_app(task,lang,options[index])


def _auto_note(lang, key):
    messages = {
        'opening': {
            'en': 'Opening the right Windows page. KIKO will point to the next button automatically.',
            'te': 'సరైన Windows పేజీని తెరుస్తున్నాను. తర్వాతి బటన్‌ను కికో చూపిస్తుంది.',
            'hi': 'ज़रूरी Windows पेज खोल रहा हूँ। KIKO अगला बटन अपने आप दिखाएगा.'},
        'working': {
            'en': 'KIKO is reading the window and finding your next click…',
            'te': 'కికో స్క్రీన్ చూసి తర్వాత ఎక్కడ నొక్కాలో వెతుకుతోంది…',
            'hi': 'KIKO स्क्रीन देखकर अगला बटन ढूँढ रहा है…'},
        'click': {
            'en': 'Click the highlighted control. KIKO will check again after your click.',
            'te': 'చూపించిన బటన్‌ను నొక్కండి. తర్వాత కికో మళ్లీ చూస్తుంది.',
            'hi': 'दिखाए गए बटन को दबाएँ। इसके बाद KIKO फिर जाँच करेगा.'},
        'unknown': {
            'en': 'I cannot open every app automatically. If that app is already open, switch to it once; KIKO will inspect it. Ctrl+Alt+K is optional.',
            'te': 'ప్రతి యాప్‌ను కికో తెరవలేదు. మీ యాప్ ఇప్పటికే తెరిచి ఉంటే ఒక్కసారి దానికి వెళ్లండి. కికో చూస్తుంది. షార్ట్‌కట్ అవసరం లేదు.',
            'hi': 'हर ऐप अपने आप नहीं खुल सकता। ऐप खुला है तो एक बार उस पर जाएँ। KIKO उसकी जाँच करेगा। शॉर्टकट ज़रूरी नहीं.'}
    }
    return messages[key].get(lang, messages[key]['en'])


def _start_automatic_guide(topic, lang, task, app_name=None):
    """Auto guide after an explicit request; never capture the browser by mistake."""
    def work():
        # Give Settings time to appear, without blocking the HTTP response/UI.
        for attempt in range(9):
            time.sleep(0.6)
            with LOCK:
                if STATE['task'] != task or STATE['phase'] in ('done', 'idle'):
                    return
            if topic and native.IS_WINDOWS:
                found = native.find_settings_window(topic)
                if found:
                    try: native.raise_for_guidance(found[0])
                    except (OSError, RuntimeError): pass
                    start_inspection(preferred_hwnd=found[0])
                    return
            elif app_name:
                found=native.find_app_window(app_name)
                if found:
                    start_inspection(preferred_hwnd=found[0])
                    return
            else:
                try:
                    hwnd, title, _ = native.foreground_info()
                    if not native.is_kiko_browser(title):
                        start_inspection(preferred_hwnd=hwnd)
                        return
                except (OSError, RuntimeError): pass
        # A real missing window is surfaced honestly; no imaginary success.
        with LOCK:
            if STATE['task'] == task and STATE['phase'] not in ('guided','inspecting','done'):
                STATE.update(phase='ready', message=(_t(lang, f'{app_name} opened, but I cannot yet see its window. Switch to it and choose CHECK AGAIN.', f'{app_name} తెరుచుకుంది. ఆ యాప్‌కు వెళ్లి CHECK AGAIN నొక్కండి.', f'{app_name} खुल गया। उस ऐप पर जाएँ और CHECK AGAIN दबाएँ.') if app_name else _auto_note(lang, 'unknown')) if topic is None else
                    {'en':'Settings did not open. Try opening Windows Settings once or press SHOW ME again.',
                     'te':'Settings తెరుచుకోలేదు. Windows Settings తెరిచి SHOW ME నొక్కండి.',
                     'hi':'Settings नहीं खुलीं। Windows Settings खोलकर SHOW ME दबाएँ.'}[lang])
                STATE['revision'] += 1
    threading.Thread(target=work,daemon=True,name='KIKO auto open and guide').start()


def stage_task(task,lang):
    task=str(task).strip()[:300]
    if not task:raise ValueError('Tell KIKO what you want to learn.')
    if lang not in ('en','te','hi'):raise ValueError('Unsupported language')
    if not engine.safe_task(task):
        raise ValueError('This task could involve private credentials or payments. KIKO will not inspect it.')
    direct_action=local_actions.classify(task)
    if direct_action:
        # Run only a strictly allowlisted local action. Never let an AI model
        # generate a process launch, file open, or shell command.
        with LOCK:
            if STATE['busy']: raise ValueError('KIKO is currently inspecting the screen.')
        try:
            outcome=local_actions.run(direct_action)
        except (OSError, RuntimeError) as exc:
            _update(task=task, lang=lang, topic=direct_action, phase='error',
                    message=str(exc), guide=None, busy=False)
            return {'ok':False, 'topic':direct_action, 'message':str(exc)}
        instruction=local_actions.message(direct_action, lang, outcome['file'])
        guide={'instruction':instruction,'point':None,'rect':None,
               'source':'Windows direct action (no AI)', 'found':False}
        with LOCK:
            STATE.update(app_choices=[],target_app='',task=task,lang=lang,topic=direct_action,phase='guided',
                         hints=0,inspect_count=0,guide=guide,window='',
                         message=instruction,busy=False,target_hwnd=None,window_bounds=None,
                         direct_file=outcome['file'])
            STATE['revision']+=1
        return {'ok':True,'topic':direct_action,'message':instruction}
    # Settings routes stay direct and free. Other explicitly named apps are
    # discovered from Windows Start, not an ever-growing command dictionary.
    topic=topic_for(task)
    if topic is None and native.IS_WINDOWS:
        app_query, choices=_candidate_apps(task)
        if app_query is not None:
            if choices and apps.confident(choices):
                try: return _begin_installed_app(task,lang,choices[0])
                except (OSError,ValueError,RuntimeError) as exc:
                    _update(phase='error',message=str(exc),busy=False)
                    return {'ok':False,'message':str(exc)}
            if choices:
                msg=_t(lang, 'Which installed app did you mean? Choose one below.',
                       'ఏ యాప్‌ను తెరవాలి? కింద ఎంచుకోండి.',
                       'कौन-सा ऐप खोलना है? नीचे चुनें।')
                with LOCK:
                    STATE.update(task=task,lang=lang,topic=None,phase='choosing',message=msg,
                                 busy=False,guide=None,app_choices=choices[:7],target_app='')
                    STATE['revision']+=1
                return {'ok':True,'message':msg,'needs_choice':True}
            # Explicit app request with no match: explain, don't silently switch to AI.
            msg=_t(lang, f'I could not find an installed app matching “{app_query or "game"}”. Say its Start-menu name.',
                  'ఆ పేరుతో ఇన్‌స్టాల్ చేసిన యాప్ కనిపించలేదు. Start మెనూలో ఉన్న పేరు చెప్పండి.',
                  'उस नाम का इंस्टॉल किया ऐप नहीं मिला। Start मेनू में दिखने वाला नाम बताइए।')
            with LOCK:
                STATE.update(task=task,lang=lang,topic=None,phase='ready',message=msg,
                             busy=False,guide=None,app_choices=[],target_app='')
                STATE['revision']+=1
            return {'ok':True,'message':msg}
    with LOCK:
        if STATE['busy']:raise ValueError('KIKO is currently inspecting the screen.')
        STATE.update(app_choices=[],target_app='',direct_file=None,task=task,lang=lang,topic=topic,phase='opening' if (topic and native.IS_WINDOWS) else 'ready',hints=0,inspect_count=0,guide=None,window='',message='',busy=False,target_hwnd=None,window_bounds=None)
        STATE['revision']+=1
    if topic and native.IS_WINDOWS:
        try:os.startfile(TASKS[topic]['uri'])
        except OSError as exc:
            _update(phase='error',message=f'Windows could not open this Settings page: {exc}')
            return {'ok':False,'topic':topic,'message':str(exc)}
    wording=_auto_note(lang, 'opening' if topic else 'unknown')
    _update(message=wording)
    if native.IS_WINDOWS:
        _start_automatic_guide(topic, lang, task)
    return {'ok':True,'topic':topic,'message':wording}


def _guidance_for_uia(topic,lang,control,first,stuck,completed=0):
    label=control['name']
    if completed and not stuck:
        if lang=='te':detail=f'“{label}” ఎక్కడుందో చూపిస్తున్నాను. తర్వాత మీరే ప్రయత్నించండి.'
        elif lang=='hi':detail=f'“{label}” की जगह दिखा रहा हूँ। अगली बार खुद कोशिश करें।'
        else:detail=f'Find the highlight around “{label}”. Your turn.'
    elif lang=='te':
        detail=f'స్క్రీన్‌లో “{label}” కనిపిస్తోంది. కికో చూపిన చోట చూడండి. మీరు క్లిక్ చేయండి.'
        if stuck:detail=f'“{label}” బటన్ చుట్టూ రంగు వలయం కనిపిస్తుంది. ఆ చోట ఒక్కసారి క్లిక్ చేయండి.'
    elif lang=='hi':
        detail=f'स्क्रीन पर “{label}” दिख रहा है। KIKO जहाँ दिखा रहा है, वहाँ खुद क्लिक करें।'
        if stuck:detail=f'“{label}” बटन के चारों ओर रंगीन घेरा देखें और वहाँ एक बार क्लिक करें।'
    else:
        detail=f'I found “{label}” on your screen. Look for the highlighted ring and click that control.'
        if stuck:detail=f'Find the ring around “{label}”. Move your mouse there and click once.'
    return {'instruction':detail,'point':(round(control['rect'][0]+control['rect'][2]/2),round(control['rect'][1]+control['rect'][3]/2)),
            'rect':control['rect'],'found':True,'source':'Windows accessibility'}


def inspect_screen(preferred_hwnd=None):
    with LOCK:
        if not STATE['task']:
            _update(phase='error',message='Tell KIKO what you want to do first.');return
        if STATE['busy']:return
        STATE.update(busy=True,phase='inspecting',message=_auto_note(STATE['lang'],'working'))
        STATE['revision']+=1
        task=STATE['task'];lang=STATE['lang'];topic=STATE['topic'];hints=STATE['hints']
        history=(STATE['guide'] or {}).get('instruction','')
        first=STATE['inspect_count']==0
    try:
        topic_key=(topic or task.casefold().strip()[:80])
        completed=progress_data().get(topic_key,{}).get('completions',0)
        hwnd_choice=preferred_hwnd or _state().get('target_hwnd')
        if not hwnd_choice and _state().get('target_app') and native.IS_WINDOWS:
            located=native.find_app_window(_state()['target_app'])
            hwnd_choice=located[0] if located else None
        if hwnd_choice and native.IS_WINDOWS:
            hwnd,title,bounds=native.window_info(hwnd_choice)
            try:native.raise_for_guidance(hwnd)
            except (OSError,RuntimeError):pass
        else:
            if topic and native.IS_WINDOWS:
                found=native.find_settings_window(topic)
                if found:
                    hwnd,title,bounds=found
                    try:native.raise_for_guidance(hwnd)
                    except (RuntimeError,OSError):pass
                else:
                    hwnd,title,bounds=native.foreground_info()
            else:
                hwnd,title,bounds=native.foreground_info()
        if native.is_kiko_browser(title):
            raise RuntimeError(_auto_note(lang,'unknown'))
        # IMPORTANT: Prefer Windows accessibility before screenshots. Basic tasks
        # should not fail just because screen capture or Ollama is unavailable.
        controls=native.accessible_controls(hwnd,bounds)
        candidates=engine.control_candidates(controls,topic)
        if candidates and first:
            result=_guidance_for_uia(topic,lang,candidates[0],first,hints>0,completed)
        else:
            try:
                shot=native.snapshot(bounds,hwnd=hwnd)
                result=ollama_vision(task,lang,topic,history,hints>0,shot,bounds,controls,completed)
            except (OSError,RuntimeError,ValueError) as exc:
                if controls and model_ready():
                    try:
                        result=ollama_controls(task,lang,history,controls,bounds,
                                               stuck=hints>0,completed=completed)
                    except (OSError,RuntimeError,ValueError):
                        if candidates:
                            result=_guidance_for_uia(topic,lang,candidates[0],first,hints>0,completed)
                            result['source']='Windows accessibility (AI unavailable)'
                        else:
                            raise RuntimeError(str(exc)) from exc
                elif candidates:
                    result=_guidance_for_uia(topic,lang,candidates[0],first,hints>0,completed)
                    result['source']='Windows accessibility (AI unavailable)'
                elif topic:
                    instruction=engine.next_instruction(topic,lang,completed=completed,stuck=hints>0)
                    result={'instruction':instruction,'point':None,'rect':None,
                            'source':'Local Windows lesson; target not verified','found':False}
                else:
                    raise RuntimeError(str(exc)) from exc
        with LOCK:
            if task!=STATE['task']:
                STATE['busy']=False;return
            STATE.update(guide=result,phase='guided',busy=False,window=title,window_bounds=bounds,target_hwnd=hwnd,
                         message=_auto_note(lang,'click') if result.get('point') else
                            {'en':'The next step is shown, but I cannot safely locate a button.',
                             'te':'తర్వాతి సూచన ఉంది, కానీ ఖచ్చితమైన బటన్ కనిపించలేదు.',
                             'hi':'अगला निर्देश दिख रहा है, लेकिन सही बटन की जगह नहीं मिली.'}[lang],
                         inspect_count=STATE['inspect_count']+1)
            STATE['revision']+=1
        if result.get('point'):
            x,y=result['point']
            try:
                native.move_pointer(x,y)
                OVERLAY.show(x,y,result.get('rect'))
            except Exception as exc:
                _update(message='Instruction ready. Pointer unavailable: '+str(exc)[:120])
    except Exception as exc:
        current = _state()
        if current.get('target_app') and current.get('task') == task:
            # Never turn an app launch into a false launch failure because the
            # optional screen-reading model ran out of time or VRAM.
            details = _t(lang,
                f'{current["target_app"]} was asked to open. Screen guidance is unavailable right now: {str(exc)[:170]}. You can use the app without AI.',
                f'{current["target_app"]} తెరవడానికి ప్రయత్నించాను. ప్రస్తుతం స్క్రీన్ సూచనలు అందుబాటులో లేవు. యాప్‌ను AI లేకుండానే వాడవచ్చు.',
                f'{current["target_app"]} खोलने का प्रयास किया। अभी स्क्रीन सहायता उपलब्ध नहीं है। आप बिना AI के ऐप इस्तेमाल कर सकते हैं।')
            _update(phase='ready',busy=False,message=details)
        else:
            _update(phase='error',busy=False,message=str(exc)[:350])
        print('KIKO inspection error:',repr(exc),flush=True)


def start_inspection(preferred_hwnd=None):
    with LOCK:
        if STATE['busy']:return False
    threading.Thread(target=inspect_screen,args=(preferred_hwnd,),daemon=True,name='KIKO screen inspector').start()
    return True


def auto_click_watcher():
    """During an active lesson, read the next screen after user's own click."""
    if not native.IS_WINDOWS:return
    previous=False
    last_scan=0.0
    while True:
        try:
            current=native.mouse_is_down()
            if previous and not current:
                state=_state()
                rect=state.get('window_bounds')
                pos=native.cursor_position()
                # A click in the guided window is the person's explicit next step.
                if (state['phase']=='guided' and not state['busy'] and rect and pos and
                    rect[0]<=pos[0]<=rect[0]+rect[2] and
                    rect[1]<=pos[1]<=rect[1]+rect[3] and
                    time.monotonic()-last_scan>1.0):
                    try:
                        hwnd,title,_=native.foreground_info()
                        if native.is_kiko_browser(title):
                            previous=current
                            time.sleep(.07)
                            continue
                    except (RuntimeError,OSError):
                        hwnd=state['target_hwnd']
                    last_scan=time.monotonic()
                    def after_click(window=hwnd):
                        time.sleep(.65)  # Allow the page or dialog to change
                        with LOCK:
                            if STATE['phase']!='guided':return
                        start_inspection(preferred_hwnd=window)
                    threading.Thread(target=after_click,daemon=True,name='KIKO next step').start()
            previous=current
            time.sleep(.075)
        except Exception as exc:
            print('Auto click watcher:',str(exc)[:90],flush=True)
            time.sleep(.5)


def delayed_inspection():
    with LOCK:
        if not STATE['task']:raise ValueError('Start a task first.')
        if STATE['busy']:raise ValueError('Already inspecting.')
        STATE.update(phase='countdown',message='Switch to the app now. Capturing in 3 seconds…')
        STATE['revision']+=1
    def run():
        time.sleep(3)
        start_inspection()
    threading.Thread(target=run,daemon=True).start()
    return {'ok':True}


def repeat_pointer():
    with LOCK:
        guide=STATE.get('guide') or {}
        point=guide.get('point')
    if not point:raise ValueError('No reliable target yet. Try Check Again with the app visible.')
    def run():
        time.sleep(2.5)
        native.move_pointer(*point)
        OVERLAY.show(*point,guide.get('rect'))
    threading.Thread(target=run,daemon=True).start()
    return {'ok':True,'message':'Switch back to your app; the highlight appears in 2.5 seconds.'}


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def reply(self,data,status=200):
        raw=json.dumps(data,ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Length',str(len(raw)))
        self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        path=urllib.parse.urlsplit(self.path).path
        if self.headers.get('Host','').split(':')[0] not in ('127.0.0.1','localhost'):
            return self.reply({'error':'Local host only'},403)
        if path=='/':
            data=(APP/'index.html').read_text(encoding='utf-8').replace('KIKO_TOKEN_HERE',TOKEN).encode('utf-8')
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(data)))
            self.end_headers();self.wfile.write(data);return
        if path=='/api/status':
            state=_state()
            state['model_ready']=model_ready()
            topic=state['topic'] or state['task'].casefold().strip()[:80]
            state['progress']=progress_data().get(topic,{'completions':0,'hints':0})
            return self.reply(state)
        self.reply({'error':'Not found'},404)
    def do_POST(self):
        host=self.headers.get('Host','').split(':')[0]
        origin=self.headers.get('Origin','')
        if host not in ('127.0.0.1','localhost') or self.headers.get('X-KIKO-TOKEN')!=TOKEN:
            return self.reply({'error':'Forbidden'},403)
        if origin and urllib.parse.urlsplit(origin).hostname not in ('127.0.0.1','localhost'):
            return self.reply({'error':'Forbidden origin'},403)
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=6000:return self.reply({'error':'Invalid request size'},400)
            data=json.loads(self.rfile.read(length))
            path=urllib.parse.urlsplit(self.path).path
            if path=='/api/start':result=stage_task(data.get('task',''),data.get('lang','en'))
            elif path=='/api/capture':result=delayed_inspection()
            elif path=='/api/choose_app':result=choose_app(data.get('index'))
            elif path=='/api/point':result=repeat_pointer()
            elif path=='/api/stuck':
                with LOCK:
                    if not STATE['task']:raise ValueError('Start a task first.')
                    STATE['hints']+=1
                    STATE['message']=_auto_note(STATE['lang'],'working')
                    STATE['revision']+=1
                direct=STATE.get('topic')
                if direct in local_actions.MESSAGES:
                    with LOCK:
                        instruction=local_actions.message(direct,STATE['lang'],
                            STATE.get('direct_file'),stuck=True)
                        STATE['guide']={'instruction':instruction,'point':None,
                            'rect':None,'source':'Windows direct action','found':False}
                        STATE['phase']='guided'
                        STATE['revision']+=1
                else:
                    start_inspection(preferred_hwnd=STATE.get('target_hwnd'))
                result={'ok':True}
            elif path=='/api/done':
                with LOCK:
                    if not STATE['task']:raise ValueError('Start a task first.')
                    result=mark_complete(STATE['task'],STATE['topic'],STATE['hints'])
                    STATE.update(phase='done',message='Saved locally. Next time, KIKO will use shorter hints.',busy=False)
                    STATE['revision']+=1
                result={'ok':True,'progress':result}
            else:return self.reply({'error':'Unknown action'},404)
            self.reply(result)
        except (ValueError,RuntimeError) as exc:self.reply({'error':str(exc)},400)
        except Exception as exc:
            print('KIKO request error:',repr(exc),flush=True)
            self.reply({'error':str(exc)[:220]},500)


def serve():
    native.enable_dpi()
    if native.IS_WINDOWS:
        OVERLAY.start()
        threading.Thread(target=native.hotkey_loop,args=(start_inspection,lambda ok:_update(hotkey=bool(ok))),daemon=True,name='KIKO hotkey').start()
        threading.Thread(target=auto_click_watcher,daemon=True,name='KIKO auto-step watcher').start()
    try:
        server=ThreadingHTTPServer(('127.0.0.1',8797),Handler)
    except OSError:
        # Older KIKO versions may still be running; use a free local port
        # rather than showing another unnecessary launch error.
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    port=server.server_address[1]
    url=f'http://127.0.0.1:{port}/'
    print('\nKIKO Interactive (Spotify language routing fix) — no API key',flush=True)
    print('Open: '+url,flush=True)
    print('1. Ask a task in your language.',flush=True)
    print('2. KIKO opens supported Windows Settings and points automatically.',flush=True)
    print('3. Click the highlighted control; KIKO checks again after your click.',flush=True)
    threading.Timer(0.7,lambda:webbrowser.open(url)).start()
    try:server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':serve()
