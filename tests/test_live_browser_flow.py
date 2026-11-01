"""HTTP browser contract with mocked Windows shell (no OS side effects)."""
import json
import pathlib
import sys
import threading
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import server


def test_post_start_reaches_downloads_action(monkeypatch):
    called=[]
    monkeypatch.setattr(server.native,'IS_WINDOWS',True)
    monkeypatch.setattr(server.local_actions,'run',lambda kind: (called.append(kind) or {'action':kind,'file':'report.pdf'}))
    httpd=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
    thread=threading.Thread(target=httpd.serve_forever,daemon=True)
    thread.start()
    try:
        base=f'http://127.0.0.1:{httpd.server_address[1]}'
        def call(message):
            data=json.dumps({'task':message,'lang':'en'}).encode()
            request=urllib.request.Request(base+'/api/start', data=data,
                headers={'Content-Type':'application/json','X-KIKO-TOKEN':server.TOKEN})
            with urllib.request.urlopen(request,timeout=3) as response:
                return json.load(response)
        result=call('Find a downloaded file')
        assert result['ok']
        assert 'report.pdf' in result['message']
        result=call('open the browser tab')
        assert result['ok']
        assert called==['downloads','browser_tab']
    finally:
        httpd.shutdown();httpd.server_close();thread.join(timeout=2)
