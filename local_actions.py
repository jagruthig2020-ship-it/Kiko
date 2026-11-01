"""Explicit, predictable Windows tasks; never execute arbitrary AI-generated commands.

These actions are deliberately separate from UIA/Ollama screen guidance.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys
import webbrowser


def classify(text: str) -> str | None:
    s = ' '.join(text.casefold().split())
    # A tab request is different from vague requests to operate a browser page.
    if any(x in s for x in (
        'new tab', 'browser tab', 'open a tab', 'open the tab',
        'కొత్త ట్యాబ్', 'బ్రౌజర్ ట్యాబ్', 'న్యూ ట్యాబ్',
        'नया टैब', 'नया टॅब', 'ब्राउज़र टैब', 'नयी टैब')):
        return 'browser_tab'
    if s in ('open browser', 'open the browser', 'బ్రౌజర్ తెరువు', 'ब्राउज़र खोलो'):
        return 'browser_tab'
    download = any(x in s for x in ('download', 'డౌన్‌లోడ్', 'డౌన్లోడ్', 'डाउनलोड'))
    wants_folder = any(x in s for x in (
        'find', 'locate', 'where', 'show', 'folder', 'file', 'open downloads',
        'recent download', 'downloaded', 'files', 'ఫైల్', 'ఫోల్డర్', 'చూపించ', 'ఎక్కడ',
        'వెతుకు', 'खोज', 'फ़ाइल', 'फाइल', 'फोल्डर', 'दिखा', 'कहाँ', 'खोल'))
    if download and (wants_folder or s.strip() in ('downloads', 'my downloads', 'డౌన్‌లోడ్స్', 'डाउनलोड्स')):
        return 'downloads'
    return None


def downloads_folder() -> Path:
    if sys.platform == 'win32':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                    r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders') as key:
                value, _ = winreg.QueryValueEx(key, '{374DE290-123F-4565-9164-39C4925E467B}')
            candidate = Path(os.path.expandvars(value)).expanduser()
            if candidate.is_dir():
                return candidate
        except (OSError, ValueError):
            pass
    return Path.home() / 'Downloads'


def newest_download(folder: Path) -> Path | None:
    try:
        files = (p for p in folder.iterdir() if p.is_file() and
                 p.suffix.casefold() not in {'.crdownload', '.partial', '.part', '.tmp', '.download'})
        return max(files, key=lambda p: p.stat().st_mtime, default=None)
    except OSError:
        return None


def run(action: str) -> dict:
    if sys.platform != 'win32':
        raise RuntimeError('These direct computer actions require Windows.')
    if action == 'browser_tab':
        # Default Windows browser opens a new tab when supported by the browser.
        # A normal https URL is used instead of about:blank, which Windows may not
        # recognize as a URL protocol through its default-app association.
        if not webbrowser.open_new_tab('https://www.google.com/'):
            raise RuntimeError('Could not open the default browser. Try Ctrl+T in Chrome or Edge.')
        return {'action': action, 'file': None}
    if action == 'downloads':
        folder = downloads_folder()
        if not folder.is_dir():
            raise RuntimeError('Windows Downloads folder was not found.')
        newest = newest_download(folder)
        if newest:
            # Passing argv avoids shell interpolation of user file names.
            subprocess.Popen(['explorer.exe', '/select,', str(newest)])
        else:
            os.startfile(str(folder))
        return {'action': action, 'file': newest.name if newest else None}
    raise ValueError('Unsupported direct action')


MESSAGES = {
    'browser_tab': {
        'en': ('I opened a new tab in your default browser. Click the address bar and type a website. If it did not appear, use Ctrl+T in your browser.', 'If you cannot see the new tab, open Chrome or Edge and press Ctrl+T. The address bar is at the top.'),
        'te': ('మీ బ్రౌజర్‌లో కొత్త ట్యాబ్ తెరిచాను. పై ఉన్న అడ్రస్ బార్‌లో వెబ్‌సైట్ పేరు టైప్ చేయండి. ట్యాబ్ కనిపించకపోతే Ctrl+T నొక్కండి.', 'కొత్త ట్యాబ్ కనిపించలేదా? Chrome లేదా Edge తెరిచి Ctrl+T నొక్కండి. అడ్రస్ బార్ పైన ఉంటుంది.'),
        'hi': ('ब्राउज़र में नया टैब खोल दिया है। ऊपर एड्रेस बार में वेबसाइट लिखें। टैब न दिखे तो ब्राउज़र में Ctrl+T दबाएँ।', 'नया टैब नहीं दिख रहा? Chrome या Edge खोलें और Ctrl+T दबाएँ। एड्रेस बार ऊपर है.'),
    },
    'downloads': {
        'en': ('I opened your Downloads folder and selected the most recently downloaded file: {file}. Check its name before opening it.', 'In File Explorer, look for the Downloads folder on the left. The selected file is the newest one; check its name before you open it.'),
        'te': ('Downloads ఫోల్డర్ తెరిచి తాజాగా డౌన్‌లోడ్ అయిన ఫైల్‌ను ఎంచుకున్నాను: {file}. తెరవడానికి ముందు పేరు చూసుకోండి.', 'File Explorer లో ఎడమవైపు Downloads చూడండి. ఎంచుకున్న ఫైల్ పేరు చూసిన తర్వాతే దాన్ని తెరవండి.'),
        'hi': ('Downloads फ़ोल्डर खोलकर सबसे हाल में डाउनलोड हुई फ़ाइल चुनी है: {file}। खोलने से पहले नाम जाँचें।', 'File Explorer में बाईं ओर Downloads चुनें। फ़ाइल खोलने से पहले उसका नाम जाँच लें.'),
    },
}


def message(action: str, lang: str, file: str | None = None, stuck: bool = False) -> str:
    language = lang if lang in ('en', 'te', 'hi') else 'en'
    template = MESSAGES[action][language][1 if stuck else 0]
    if action == 'downloads' and not file and not stuck:
        return {
            'en': 'I opened Downloads, but there are no completed files to select yet.',
            'te': 'Downloads ఫోల్డర్ తెరిచాను. ప్రస్తుతం ఎంచుకోవడానికి డౌన్‌లోడ్ అయిన ఫైల్స్ లేవు.',
            'hi': 'Downloads फ़ोल्डर खोल दिया है, लेकिन चुनने के लिए अभी कोई पूरी डाउनलोड हुई फ़ाइल नहीं है.',
        }[language]
    return template.format(file=file or '—')
