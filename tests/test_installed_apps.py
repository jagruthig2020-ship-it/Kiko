"""Regression tests for the generic installed-app flow (Windows calls mocked)."""
import apps
import server

CATALOG=[
    {'name':'Chess Titans','id':'chess-app','kind':'start'},
    {'name':'Paint','id':'paint-app','kind':'start'},
    {'name':'Paint 3D','id':'paint3d','kind':'start'},
    {'name':'Microsoft Solitaire Collection','id':'solitaire','kind':'start'},
    {'name':'Calculator','id':'calc','kind':'start'},
]


def test_open_any_installed_game_without_hardcoded_command(monkeypatch):
    launched=[];scheduled=[]
    monkeypatch.setattr(server.native,'IS_WINDOWS',True)
    monkeypatch.setattr(server.apps,'installed_apps',lambda:CATALOG)
    monkeypatch.setattr(server.apps,'launch',lambda app:launched.append(app['name']))
    monkeypatch.setattr(server,'_start_automatic_guide',lambda *a,**kw:scheduled.append(kw))
    response=server.stage_task('Please open the chess game on my laptop','en')
    assert response['opened_app']=='Chess Titans'
    assert launched==['Chess Titans']
    assert scheduled[0]['app_name']=='Chess Titans'


def test_telugu_app_opening(monkeypatch):
    launched=[]
    monkeypatch.setattr(server.native,'IS_WINDOWS',True)
    monkeypatch.setattr(server.apps,'installed_apps',lambda:CATALOG)
    monkeypatch.setattr(server.apps,'launch',lambda app:launched.append(app['name']))
    monkeypatch.setattr(server,'_start_automatic_guide',lambda *a,**kw:None)
    response=server.stage_task('Calculator తెరువు','te')
    assert response['opened_app']=='Calculator'
    assert 'Calculator' in response['message']
    assert launched==['Calculator']


def test_hindi_app_opening(monkeypatch):
    launched=[]
    monkeypatch.setattr(server.native,'IS_WINDOWS',True)
    monkeypatch.setattr(server.apps,'installed_apps',lambda:CATALOG)
    monkeypatch.setattr(server.apps,'launch',lambda app:launched.append(app['name']))
    monkeypatch.setattr(server,'_start_automatic_guide',lambda *a,**kw:None)
    response=server.stage_task('Paint खोलो','hi')
    assert response['opened_app']=='Paint'
    assert launched==['Paint']


def test_ambiguous_app_choice_does_not_auto_launch(monkeypatch):
    launched=[]
    monkeypatch.setattr(server.native,'IS_WINDOWS',True)
    monkeypatch.setattr(server.apps,'installed_apps',lambda:CATALOG)
    monkeypatch.setattr(server.apps,'launch',lambda app:launched.append(app['name']))
    monkeypatch.setattr(server,'_start_automatic_guide',lambda *a,**kw:None)
    response=server.stage_task('Please open a game','en')
    assert response['needs_choice']
    assert server.STATE['phase']=='choosing'
    assert not launched
    chosen=server.choose_app(0)
    assert chosen['opened_app'] in ('Chess Titans','Microsoft Solitaire Collection')
    assert len(launched)==1


def test_unknown_app_no_shell_code(monkeypatch):
    launched=[]
    monkeypatch.setattr(server.native,'IS_WINDOWS',True)
    monkeypatch.setattr(server.apps,'installed_apps',lambda:CATALOG)
    monkeypatch.setattr(server.apps,'launch',lambda app:launched.append(app))
    monkeypatch.setattr(server,'model_ready',lambda:False)
    result=server.stage_task('open not-a-real-app-9271','en')
    assert result['ok'] is True
    assert 'could not find' in result['message'].lower()
    assert not launched


def test_safe_launch_requires_catalog_membership(monkeypatch):
    monkeypatch.setattr(apps.sys,'platform','win32')
    monkeypatch.setattr(apps,'installed_apps',lambda:CATALOG)
    try:
        apps.launch({'name':'Danger', 'id':'C:\\arbitrary.exe', 'kind':'start'})
    except ValueError as exc:
        assert 'not in' in str(exc)
    else:raise AssertionError('Untrusted app must not launch')


def test_query_parsing():
    assert apps.extract_query('open the Microsoft Paint app')=='microsoft paint'
    assert apps.extract_query('open a new browser tab') is None
    assert apps.extract_query('turn on Bluetooth') is None
    assert apps.extract_query('Calculator తెరువు')=='calculator'
    assert apps.extract_query('Paint खोलो')=='paint'


def test_full_app_to_pointer_guidance(monkeypatch):
    """Model result is grounded in selected app, then sent to pointer/highlighter."""
    shown=[];moved=[]
    monkeypatch.setattr(server.native,'IS_WINDOWS',True)
    monkeypatch.setattr(server.apps,'installed_apps',lambda:CATALOG)
    monkeypatch.setattr(server.apps,'launch',lambda app:None)
    monkeypatch.setattr(server,'_start_automatic_guide',lambda *a,**kw:None)
    server.stage_task('open chess game','en')
    monkeypatch.setattr(server.native,'window_info',lambda hwnd:(hwnd,'Chess Titans',(50,80,850,560)))
    monkeypatch.setattr(server.native,'raise_for_guidance',lambda hwnd:None)
    monkeypatch.setattr(server.native,'accessible_controls',lambda hwnd,bounds:[])
    monkeypatch.setattr(server.native,'snapshot',lambda bounds,hwnd=None:b'fake-jpeg')
    monkeypatch.setattr(server,'ollama_vision',lambda *a,**kw:{'instruction':'Click New game',
                    'point':(455,340),'rect':None,'source':'local Ollama vision','found':True})
    monkeypatch.setattr(server.native,'move_pointer',lambda x,y:moved.append((x,y)))
    monkeypatch.setattr(server.OVERLAY,'show',lambda x,y,rect:shown.append((x,y)))
    server.inspect_screen(preferred_hwnd=123)
    assert server.STATE['guide']['instruction']=='Click New game'
    assert server.STATE['phase']=='guided'
    assert moved==[(455,340)] and shown==[(455,340)]


def test_start_and_choose_via_http(monkeypatch):
    import json, threading, urllib.request
    from http.server import ThreadingHTTPServer
    monkeypatch.setattr(server.native,'IS_WINDOWS',True)
    monkeypatch.setattr(server.apps,'installed_apps',lambda:CATALOG)
    launched=[]
    monkeypatch.setattr(server.apps,'launch',lambda app:launched.append(app['name']))
    monkeypatch.setattr(server,'_start_automatic_guide',lambda *a,**kw:None)
    httpd=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
    t=threading.Thread(target=httpd.serve_forever,daemon=True);t.start()
    try:
        url=f'http://127.0.0.1:{httpd.server_address[1]}'
        def post(route,body):
            raw=json.dumps(body).encode('utf-8')
            req=urllib.request.Request(url+'/api/'+route,data=raw,
                     headers={'Content-Type':'application/json','X-KIKO-TOKEN':server.TOKEN})
            with urllib.request.urlopen(req,timeout=5) as response:return json.load(response)
        response=post('start',{'task':'Please open a game','lang':'en'})
        assert response['needs_choice'] is True
        assert not launched
        choice=post('choose_app',{'index':0})
        assert choice['opened_app'] in ('Chess Titans','Microsoft Solitaire Collection')
        assert launched==[choice['opened_app']]
    finally:
        httpd.shutdown();httpd.server_close();t.join(timeout=2)
