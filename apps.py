"""Discover and launch ONLY installed Windows Start apps and shortcuts.

No model-generated shell commands, executable paths, or URLs are ever run.
"""
from __future__ import annotations
from difflib import SequenceMatcher
from pathlib import Path
import json
import os
import re
import subprocess
import sys
import threading
import time

_LOCK = threading.RLock()
_CACHED: list[dict] = []
_AT = 0.0

STOP = {'a','an','the','my','on','this','that','laptop','computer','pc','please','for',
        'me','installed','installation','app','application','program','software','game',
        'to','can','you','i','want','would','like','help','let','start','open','launch',
        'run','play','up','the','desktop','find','new','could','would','please','just','kindly','chey','cheyyi','cheyyandi','cheyyali','karo','kar','do'}
# Longest Indian-language command forms first: matching just "తెరవ" left
# the trailing vowel in the app name (e.g. "Spotify తెరవాలి" -> "spotify ాలి").
INTENT = re.compile(
    r'\b(open|launch|run|play|start|find|locate|teruvu|teravali|teravandi|khol|kholo)\b|'
    r'తెరవాలి|తెరవండి|తెరువు|తెరవ|తెరచు|తీయి|ఓపెన్|ఆరంభించ|ప్రారంభించ|స్టార్ట్|ప్లే|చూపించ|ఆడాలి|ఆడటం|'
    r'खोलना|खोलें|खोलो|खोल|चलाओ|खेलना|खेलो|चालू|ओपन|स्टार्ट|दिखाओ', re.I)
NON_APP = {'new tab', 'browser tab', 'download', 'bluetooth', 'wifi', 'wi-fi',
           'brightness', 'text size', 'volume', 'settings'}

# Small spoken-name normalization table. This is NOT a list of supported apps:
# any installed app in the Windows catalog is still discoverable by its name.
APP_NAME_ALIASES = {
    'స్పాటిఫై': 'spotify', 'స్పోటిఫై': 'spotify', 'స్పాటీఫై': 'spotify',
    'स्पॉटिफाई': 'spotify', 'स्पॉटिफ़ाई': 'spotify',
    'स्पोटीफाई': 'spotify', 'स्पॉटिफाइ': 'spotify',
}
LANGUAGE_FILLERS = {
    'నాకు', 'నా', 'నాది', 'గేమ్', 'యాప్', 'అప్లికేషన్', 'దయచేసి', 'లో',
    'ని', 'ను', 'చెయ్యి', 'చేయి', 'చేయండి', 'చేయాలి', 'చేసి', 'కావాలి',
    'తెరిపించు', 'తెరిపించండి', 'మా', 'నేను', 'ఉన్న', 'ఒక్కసారి',
    'मुझे', 'मेरा', 'मेरी', 'गेम', 'ऐप', 'पर', 'है', 'को', 'में',
    'चाहिए', 'कृपया', 'कर', 'करो', 'दो', 'जी', 'मेरा', 'मुझे',
}



def _norm(s: str) -> str:
    return ' '.join(re.findall(r'[\w\u0900-\u097f\u0c00-\u0c7f]+', s.casefold()))


def extract_query(phrase: str) -> str | None:
    """Return requested Start app name, independent of surrounding language."""
    if not INTENT.search(phrase):
        return None
    normalized = _norm(phrase)
    if any(term in normalized for term in NON_APP):
        return None
    for spoken, latin in APP_NAME_ALIASES.items():
        normalized = normalized.replace(spoken, latin)
    # Handle code-switching without whitespace: Spotifyని, Spotifyको, etc.
    normalized = re.sub(r'([a-z0-9]+)(ని|ను|లో|కి|తో|को|में|पर|से)(?=\s|$)', r'\1', normalized)
    normalized = INTENT.sub(' ', normalized)
    tokens = [t for t in normalized.split() if t not in STOP and t not in LANGUAGE_FILLERS]
    return ' '.join(tokens) if tokens else ''


def open_only_request(phrase: str, app_name: str) -> bool:
    """A launch-only request must never wait for a multimodal model to respond."""
    name = _norm(app_name)
    query = extract_query(phrase)
    if query is None or not query:
        return False
    # Explicit additional task words warrant screen guidance after launch.
    return bool(name == query or name.startswith(query + ' '))



def _get_start_apps() -> list[dict]:
    # Get-StartApps is a trusted enumeration of Start-menu registrations.
    script = (
        '[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; '
        '$ErrorActionPreference="SilentlyContinue"; '
        'Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress -Depth 3'
    )
    try:
        r = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],
                           capture_output=True, timeout=14, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        raw = r.stdout.decode('utf-8-sig','replace').strip()
        payload = json.loads(raw) if raw else []
        if isinstance(payload, dict): payload = [payload]
        return [{'name':x['Name'].strip(), 'id':x['AppID'].strip(), 'kind':'start'}
                for x in payload if isinstance(x,dict) and isinstance(x.get('Name'),str)
                and isinstance(x.get('AppID'),str) and x['Name'].strip() and x['AppID'].strip()]
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return []


def _shortcuts() -> list[dict]:
    roots = [Path(os.environ.get('APPDATA',''))/'Microsoft/Windows/Start Menu/Programs',
             Path(os.environ.get('PROGRAMDATA',''))/'Microsoft/Windows/Start Menu/Programs']
    found = []
    for root in roots:
        if not root.is_dir(): continue
        try:
            for path in root.rglob('*.lnk'):
                if path.is_file():
                    found.append({'name':path.stem, 'id':str(path), 'kind':'link'})
        except OSError: pass
    return found


def _registered_protocol_apps() -> list[dict]:
    """Registered Spotify URI is a second installed-app signal on Windows.

    Never open arbitrary browser URLs or AI-generated schemes. Only the fixed
    spotify: scheme, if Windows actually registered a URL protocol handler.
    """
    if sys.platform != 'win32': return []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, 'spotify') as key:
            winreg.QueryValueEx(key, 'URL Protocol')
        return [{'name':'Spotify','id':'spotify:','kind':'protocol'}]
    except (OSError, ImportError):
        return []


def installed_apps(force=False) -> list[dict]:
    global _CACHED, _AT
    if sys.platform != 'win32': return []
    with _LOCK:
        if _CACHED and not force and time.monotonic()-_AT < 180:
            return [dict(x) for x in _CACHED]
        items = _get_start_apps() + _shortcuts() + _registered_protocol_apps()
        dedup = {}
        for item in items:
            key = _norm(item['name'])
            if not key or key in ('uninstall','help','readme'): continue
            # Prefer start-app registrations, which support packaged Windows apps.
            if key not in dedup: dedup[key] = item
        _CACHED = sorted(dedup.values(),key=lambda x:x['name'].casefold())
        _AT = time.monotonic()
        return [dict(x) for x in _CACHED]


def score(query: str, name: str) -> float:
    q, n = _norm(query), _norm(name)
    if not q or not n: return 0.0
    if q == n: return 1.0
    if n.startswith(q+' '): return .94
    if q in n and len(q) >= 3: return .86
    qtok = set(q.split()); ntok=set(n.split())
    overlap = len(qtok & ntok)/max(1,len(qtok))
    simil = SequenceMatcher(None,q,n).ratio()
    return round(max(.68*overlap + .32*simil, simil*.78),4)


def matches(query: str, entries: list[dict], limit=7) -> list[dict]:
    if not query or _norm(query) in ('game','app','program','application'):
        # Never select a random game from a generic request.
        return []
    ranked = [{**e, 'score':score(query,e['name'])} for e in entries]
    ranked.sort(key=lambda x:(x['score'],len(x['name'])*-1),reverse=True)
    return [x for x in ranked if x['score']>=.48][:limit]


def mentioned_apps(phrase: str, entries: list[dict]) -> list[dict]:
    """Spot an installed app explicitly mentioned inside a longer sentence.

    Uses registered Windows names, never an LLM-generated executable path.
    """
    spoken = _norm(phrase)
    for alt, standard in APP_NAME_ALIASES.items():
        spoken = spoken.replace(alt, standard)
    spoken = re.sub(r'([a-z0-9]+)(ని|ను|లో|కి|తో|को|में|पर|से)(?=\s|$)', r'\1', spoken)
    padded = ' ' + spoken + ' '
    result=[]
    for app in entries:
        name = _norm(app.get('name',''))
        if len(name) >= 4 and (' ' + name + ' ') in padded:
            result.append({**app,'score':1.0})
    return sorted(result,key=lambda a:len(_norm(a['name'])),reverse=True)[:7]


def confident(results: list[dict]) -> bool:
    if not results:return False
    a=results[0]['score']
    b=results[1]['score'] if len(results)>1 else 0
    return a>=.87 and (a-b>=.07 or a>=.99)


def launch(app: dict) -> None:
    if sys.platform!='win32': raise RuntimeError('Launching installed applications requires Windows.')
    # Validation: lookup again in installed catalog. Never execute a caller-supplied file/path.
    current=installed_apps()
    chosen=next((x for x in current if x['name']==app.get('name') and
                 x['id']==app.get('id') and x['kind']==app.get('kind')),None)
    if chosen is None:raise ValueError('App is not in the installed Start menu list. Refresh apps.')
    if chosen['kind']=='link':
        p=Path(chosen['id'])
        if p.suffix.lower()!='.lnk' or not p.is_file():raise ValueError('Shortcut is unavailable.')
        os.startfile(str(p))
    elif chosen['kind']=='protocol':
        if chosen['id']!='spotify:' or chosen['name']!='Spotify':
            raise ValueError('Untrusted application protocol.')
        if not _registered_protocol_apps():
            raise ValueError('Spotify is not registered with Windows.')
        os.startfile('spotify:')
    else:
        # Windows Shell's AppsFolder executes only a registered app identifier.
        subprocess.Popen(['explorer.exe', 'shell:AppsFolder\\'+chosen['id']],
                         creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
