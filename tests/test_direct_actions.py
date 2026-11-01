"""A regression test for the two tasks advertised to KIKO users."""
import pathlib
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import local_actions
import server


def test_intents_in_three_languages():
    for request in ('Open a new browser tab', 'open the browser tab', 'కొత్త ట్యాబ్ తెరువు', 'नया टैब खोलो'):
        assert local_actions.classify(request) == 'browser_tab', request
    for request in ('Find a downloaded file', 'find the downloads file', 'డౌన్‌లోడ్ ఫైల్ కనిపెట్టాలి', 'डाउनलोड की फाइल खोजो'):
        assert local_actions.classify(request) == 'downloads', request
    assert local_actions.classify('download a game from the internet') is None
    assert local_actions.classify('Click save as in Photoshop') is None


def test_browser_action_needs_no_screen_or_model(monkeypatch):
    called=[]
    monkeypatch.setattr(local_actions.sys,'platform','win32')
    monkeypatch.setattr(local_actions.webbrowser,'open_new_tab',lambda url: called.append(url) or True)
    monkeypatch.setattr(server.native,'IS_WINDOWS',True)
    monkeypatch.setattr(server,'_start_automatic_guide',lambda *args: (_ for _ in ()).throw(AssertionError('No screenshot or AI')))
    response=server.stage_task('open the browser tab','en')
    assert response['ok'] and response['topic']=='browser_tab'
    assert called == ['https://www.google.com/']
    assert server._state()['phase']=='guided'
    assert server._state()['guide']['point'] is None


def test_downloads_opens_and_selects_most_recent(monkeypatch,tmp_path):
    monkeypatch.setattr(local_actions.sys,'platform','win32')
    old=tmp_path/'older.pdf';old.write_text('a')
    new=tmp_path/'newer.docx';new.write_text('b')
    partial=tmp_path/'newest.crdownload';partial.write_text('c')
    import os,time
    os.utime(old,(1,1));os.utime(new,(2,2));os.utime(partial,(3,3))
    monkeypatch.setattr(local_actions,'downloads_folder',lambda:tmp_path)
    calls=[]
    monkeypatch.setattr(local_actions.subprocess,'Popen',lambda argv:calls.append(argv))
    monkeypatch.setattr(server.native,'IS_WINDOWS',True)
    monkeypatch.setattr(server,'_start_automatic_guide',lambda *args: (_ for _ in ()).throw(AssertionError('No screenshot or AI')))
    response=server.stage_task('Find a downloaded file','te')
    assert response['ok'] and response['topic']=='downloads'
    assert calls==[['explorer.exe', '/select,', str(new)]]
    assert 'newer.docx' in server._state()['guide']['instruction']
    assert 'డౌన్' in server._state()['guide']['instruction']


def test_downloads_empty_opens_folder_not_file(monkeypatch,tmp_path):
    monkeypatch.setattr(local_actions.sys,'platform','win32')
    monkeypatch.setattr(local_actions,'downloads_folder',lambda:tmp_path)
    calls=[]
    monkeypatch.setattr(local_actions.os,'startfile',lambda p:calls.append(p),raising=False)
    result=local_actions.run('downloads')
    assert result == {'action':'downloads','file':None}
    assert calls==[str(tmp_path)]


def test_stuck_is_language_consistent(monkeypatch):
    monkeypatch.setattr(local_actions.sys,'platform','win32')
    monkeypatch.setattr(local_actions.webbrowser,'open_new_tab',lambda url:True)
    monkeypatch.setattr(server.native,'IS_WINDOWS',True)
    server.stage_task('नया टैब खोलो','hi')
    assert 'टैब' in local_actions.message('browser_tab','hi',stuck=True)
    assert 'Ctrl+T' in local_actions.message('browser_tab','hi',stuck=True)
