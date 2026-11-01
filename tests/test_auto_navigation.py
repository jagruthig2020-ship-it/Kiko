"""Regression tests for no app picker, auto-open, accessibility-first guidance."""
import pathlib
import sys
import threading
import time
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import server


def test_bluetooth_opens_directly_and_schedules_guidance(monkeypatch):
    opened=[]; scheduled=[]
    monkeypatch.setattr(server.native,'IS_WINDOWS',True)
    monkeypatch.setattr(server.os,'startfile',lambda uri:opened.append(uri),raising=False)
    monkeypatch.setattr(server,'_start_automatic_guide',lambda *a:scheduled.append(a))
    result=server.stage_task('Turn on Bluetooth','en')
    assert result['ok']
    assert opened==['ms-settings:bluetooth']
    assert scheduled==[('bluetooth','en','Turn on Bluetooth')]
    assert server._state()['phase']=='opening'


def test_telugu_bluetooth_auto_opens_and_schedules(monkeypatch):
    opened=[];scheduled=[]
    monkeypatch.setattr(server.native,'IS_WINDOWS',True)
    monkeypatch.setattr(server.os,'startfile',lambda uri:opened.append(uri),raising=False)
    monkeypatch.setattr(server,'_start_automatic_guide',lambda *a:scheduled.append(a))
    result=server.stage_task('బ్లూటూత్ ఆన్ చేయాలి','te')
    assert result['ok'] and 'కికో' in result['message']
    assert opened==['ms-settings:bluetooth']
    assert scheduled and scheduled[0][1]=='te'


def test_auto_selects_settings_without_picker(monkeypatch):
    done=threading.Event();called=[]
    monkeypatch.setattr(server.native,'IS_WINDOWS',True)
    monkeypatch.setattr(server.native,'find_settings_window',lambda topic:(200,'Settings',(0,0,1000,750)))
    monkeypatch.setattr(server.native,'raise_for_guidance',lambda hwnd:called.append(('raise',hwnd)))
    monkeypatch.setattr(server,'start_inspection',lambda preferred_hwnd=None: (called.append(('inspect',preferred_hwnd)),done.set()))
    server._update(task='Bluetooth',phase='opening',busy=False)
    server._start_automatic_guide('bluetooth','en','Bluetooth')
    assert done.wait(2), 'automatic guidance never started'
    assert called==[('raise',200),('inspect',200)]


def test_accessibility_first_does_not_require_screenshot_or_ollama(monkeypatch):
    monkeypatch.setattr(server.native,'IS_WINDOWS',False)
    server.stage_task('Turn on Bluetooth','en')
    monkeypatch.setattr(server.native,'foreground_info',lambda:(202,'Settings',(0,0,1200,800)))
    monkeypatch.setattr(server.native,'accessible_controls',lambda *a:[{'id':1,'name':'Bluetooth toggle, Off','type':'CheckBoxControl','rect':(450,120,80,40)}])
    monkeypatch.setattr(server.native,'snapshot',lambda *a: (_ for _ in ()).throw(AssertionError('Screenshot should not be needed')))
    monkeypatch.setattr(server.native,'move_pointer',lambda *a:None)
    monkeypatch.setattr(server.OVERLAY,'show',lambda *a:None)
    server.inspect_screen()
    guide=server._state()['guide']
    assert guide['found'] and guide['point']==(490,140)


def test_unknown_task_does_not_open_random_programs(monkeypatch):
    opened=[]
    monkeypatch.setattr(server.native,'IS_WINDOWS',True)
    monkeypatch.setattr(server.os,'startfile',lambda uri:opened.append(uri),raising=False)
    monkeypatch.setattr(server,'_start_automatic_guide',lambda *a:None)
    result=server.stage_task('How to use pivot tables in spreadsheets','en')
    assert result['ok'] and result['topic'] is None
    assert opened==[]


def test_complete_request_to_highlight_automatic(monkeypatch):
    """Exercise stage -> Settings URI -> auto-detect -> real control -> pointer."""
    opened=[];highlight=[];pointer=[]
    monkeypatch.setattr(server.native,'IS_WINDOWS',True)
    monkeypatch.setattr(server.os,'startfile',lambda uri:opened.append(uri),raising=False)
    monkeypatch.setattr(server.native,'find_settings_window',lambda t:(101,'Settings',(0,0,900,650)))
    monkeypatch.setattr(server.native,'raise_for_guidance',lambda hwnd:None)
    monkeypatch.setattr(server.native,'window_info',lambda hwnd:(101,'Settings',(0,0,900,650)))
    monkeypatch.setattr(server.native,'accessible_controls',lambda *a:[
        {'id':1,'name':'Bluetooth, Off','type':'CheckBoxControl','rect':(350,150,80,48)}])
    monkeypatch.setattr(server.native,'snapshot',lambda *a: (_ for _ in ()).throw(AssertionError('No screenshot needed')))
    monkeypatch.setattr(server.native,'move_pointer',lambda x,y:pointer.append((x,y)))
    monkeypatch.setattr(server.OVERLAY,'show',lambda *a:highlight.append(a))
    result=server.stage_task('Turn on Bluetooth','en')
    assert result['ok']
    for _ in range(35):
        if server._state()['phase'] == 'guided':
            break
        time.sleep(.05)
    assert server._state()['phase'] == 'guided',server._state()['message']
    assert opened==['ms-settings:bluetooth']
    assert pointer==[(390,174)]
    assert highlight and highlight[0][:2]==(390,174)
