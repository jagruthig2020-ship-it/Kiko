import sys
import json
import pathlib
import threading
import urllib.request
import time
import pytest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import engine
import server


def test_telugu_detection():
    assert engine.topic_for('నాకు Bluetooth ఆన్ చేయాలి')=='bluetooth'


def test_hindi_detection():
    assert engine.topic_for('ब्लूटूथ चालू करना है')=='bluetooth'


def test_other_task_unmapped():
    assert engine.topic_for('How do I add page numbers in a document?') is None


def test_sensitive_tasks_filtered():
    assert not engine.safe_task('Type my password for me')
    assert not engine.safe_task('enter OTP')
    assert engine.safe_task('Turn on Bluetooth')


def test_find_real_toggle():
    ctrls=[
      {'id':1,'name':'Bluetooth','type':'TextControl','rect':(30,30,120,20)},
      {'id':2,'name':'Bluetooth toggle, Off','type':'CheckBoxControl','rect':(170,60,40,40)},
      {'id':3,'name':'Windows','type':'WindowControl','rect':(0,0,700,500)}]
    assert engine.control_candidates(ctrls,'bluetooth')[0]['id']==2


def test_no_ungrounded_target():
    assert engine.control_candidates([{'id':1,'name':'Not a button','type':'Button','rect':(1,1,50,30)}],'bluetooth')==[]


def test_model_control_id_maps_to_real_screen():
    ctrls=[{'id':4,'name':'Bluetooth switch','type':'ButtonControl','rect':(430,260,100,32)}]
    parsed=engine.parse_model(json.dumps({'instruction':'Click Bluetooth','found':True,'control_id':4,'x':None,'y':None}),900,600,ctrls,(100,150,900,600))
    assert parsed['point']==(480,276)
    assert parsed['found']


def test_model_coords_scaled_and_clipped():
    out=engine.parse_model(json.dumps({'instruction':'Click','found':True,'control_id':None,'x':500,'y':250}),800,400,[],(100,200,800,400))
    assert out['point']==(500,300)
    out=engine.parse_model(json.dumps({'instruction':'Click','found':True,'x':1800,'y':250}),800,400,[],(100,200,800,400))
    assert out['point'] is None


def test_model_invalid_returns_error():
    with pytest.raises(ValueError):engine.parse_model('no json',800,400,[],(0,0,800,400))


def test_task_can_start_without_selected_window(monkeypatch):
    monkeypatch.setattr(server.native,'IS_WINDOWS',False)
    data=server.stage_task('Turn on Bluetooth','en')
    assert data['topic']=='bluetooth'
    assert server._state()['phase']=='ready'


def test_arbitrary_task_stages_without_api_key(monkeypatch):
    monkeypatch.setattr(server.native,'IS_WINDOWS',False)
    data=server.stage_task('How do I export a PDF from Word?','te')
    assert data['topic'] is None
    assert server._state()['lang']=='te'


def test_hinted_localization():
    assert 'Bluetooth' in engine.next_instruction('bluetooth','te',stuck=True)
    assert 'Bluetooth' in engine.next_instruction('bluetooth','hi',stuck=True)


def test_real_pointer_flow_simulated(monkeypatch):
    server.stage_task('Turn on Bluetooth','te')
    monkeypatch.setattr(server.native,'foreground_info',lambda:(101,'Bluetooth & devices',(0,0,800,600)))
    monkeypatch.setattr(server.native,'snapshot',lambda bounds, **kw:b'fake jpeg')
    monkeypatch.setattr(server.native,'accessible_controls',lambda handle,bounds:[{'id':1,'name':'Bluetooth toggle, Off','type':'CheckBoxControl','rect':(250,160,60,30)}])
    moves=[]
    monkeypatch.setattr(server.native,'move_pointer',lambda x,y:moves.append((x,y)))
    monkeypatch.setattr(server.OVERLAY,'show',lambda x,y,rect=None:None)
    server.inspect_screen()
    state=server._state()
    assert state['phase']=='guided'
    assert state['guide']['source']=='Windows accessibility'
    assert state['guide']['point']==(280,175)
    assert moves==[(280,175)]


def test_vision_fallback_and_dont_invent(monkeypatch):
    server.stage_task('Find the page margins in Word','en')
    monkeypatch.setattr(server.native,'foreground_info',lambda:(7,'Word',(0,0,800,600)))
    monkeypatch.setattr(server.native,'snapshot',lambda bounds, **kw:b'fake')
    monkeypatch.setattr(server.native,'accessible_controls',lambda hwnd,bounds:[])
    monkeypatch.setattr(server,'ollama_vision',lambda *args:{'instruction':'Choose Layout','point':(400,300),'rect':None,'found':True,'source':'local Ollama vision'})
    moves=[]
    monkeypatch.setattr(server.native,'move_pointer',lambda x,y:moves.append((x,y)))
    monkeypatch.setattr(server.OVERLAY,'show',lambda *args:None)
    server.inspect_screen()
    assert server._state()['guide']['point']==(400,300)
    assert moves==[(400,300)]


def test_no_model_error_ends_busy(monkeypatch):
    server.stage_task('How do I make a new spreadsheet','en')
    monkeypatch.setattr(server.native,'foreground_info',lambda:(7,'Excel',(0,0,800,600)))
    monkeypatch.setattr(server.native,'snapshot',lambda bounds, **kw:b'fake')
    monkeypatch.setattr(server.native,'accessible_controls',lambda hwnd,bounds:[])
    monkeypatch.setattr(server,'ollama_vision',lambda *args: (_ for _ in ()).throw(RuntimeError('Model missing')))
    server.inspect_screen()
    assert not server._state()['busy']
    assert server._state()['phase']=='error'
    assert 'Model missing' in server._state()['message']


def test_status_http_server():
    # True HTTP contract and CORS/CSRF protections on localhost.
    from http.server import ThreadingHTTPServer
    http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
    thread=threading.Thread(target=http.serve_forever,daemon=True)
    thread.start()
    base=f'http://127.0.0.1:{http.server_address[1]}'
    try:
        response=json.load(urllib.request.urlopen(base+'/api/status',timeout=5))
        assert 'phase' in response
        html=urllib.request.urlopen(base+'/',timeout=5).read().decode()
        assert server.TOKEN in html
        assert 'Ctrl + Alt + K' in html
        payload=json.dumps({'task':'Find mouse settings','lang':'en'}).encode()
        req=urllib.request.Request(base+'/api/start',data=payload,headers={'X-KIKO-TOKEN':server.TOKEN,'Content-Type':'application/json'})
        assert json.load(urllib.request.urlopen(req,timeout=5))['ok']
        with pytest.raises(urllib.error.HTTPError) as ex:
            req=urllib.request.Request(base+'/api/start',data=payload)
            urllib.request.urlopen(req,timeout=5)
        assert ex.value.code==403
    finally:http.shutdown();http.server_close()
