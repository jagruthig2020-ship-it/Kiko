"""Pure, testable logic for grounded Windows UI guidance (no cloud API)."""
from __future__ import annotations
import json
import re
import math
from lessons import TASKS, topic_for

KEYWORDS = {
    'bluetooth': ('bluetooth', 'add device', 'pair'),
    'wifi': ('wi-fi', 'wifi', 'wireless', 'network'),
    'text': ('text size', 'size of text', 'text slider'),
    'display': ('brightness', 'scale', 'display'),
    'sound': ('volume', 'output', 'sound'),
    'mouse': ('pointer speed', 'mouse', 'cursor'),
    'notifications': ('notifications',),
}
INTERACTIVE = ('button','checkbox','toggle','switch','slider','hyperlink','listitem','combobox','radio','menuitem')
DANGER = ('password','credit card','payment','otp','one-time code','banking','transfer money','delete account')


def safe_task(text):
    lower=text.casefold()
    return not any(w in lower for w in DANGER)


def control_candidates(controls, topic):
    """Only return controls grounded in a real UIA bounding rectangle."""
    if topic not in KEYWORDS:
        return []
    scored=[]
    for control in controls:
        name=str(control.get('name','')).strip()
        ctype=str(control.get('type','')).casefold()
        norm=name.casefold()
        hits=[w for w in KEYWORDS[topic] if w in norm]
        if not hits: continue
        x,y,w,h=control.get('rect',(0,0,0,0))
        if not all(isinstance(n,(int,float)) and math.isfinite(n) for n in (x,y,w,h)) or w<=5 or h<=5:
            continue
        score=max(len(z) for z in hits) / 4
        if any(k in ctype for k in INTERACTIVE):score+=8
        if any(k in norm for k in ('toggle','on','off','switch')):score+=3
        if ('window' in ctype or 'pane' in ctype): score-=8
        scored.append((score,control))
    return [c for s,c in sorted(scored,key=lambda q:q[0],reverse=True) if s>=3]


def parse_model(content, width, height, controls, capture_rect):
    """Validate model JSON and prevent pointer targets outside captured content."""
    try:
        data=json.loads(content)
    except (ValueError,TypeError):
        match=re.search(r'\{.*?\}',str(content),re.S)
        if not match:raise ValueError('The local AI did not return a usable step. Press Ctrl+Alt+K to try again.')
        data=json.loads(match.group())
    instruction=data.get('instruction','')
    if not isinstance(instruction,str) or not instruction.strip():
        raise ValueError('The local AI did not find a clear next step. Try again.')
    found=data.get('found') is True
    point=None
    rect=None
    control_id=data.get('control_id')
    if found and isinstance(control_id,int):
        match=next((c for c in controls if c.get('id')==control_id),None)
        if match:
            x,y,w,h=match['rect']
            rect=(x,y,w,h)
            point=(round(x+w/2),round(y+h/2))
    if found and point is None:
        x,y=data.get('x'),data.get('y')
        if (type(x) in (int,float) and type(y) in (int,float) and
            math.isfinite(x) and math.isfinite(y) and 0<=x<=1000 and 0<=y<=1000):
            left,top,_,_=capture_rect
            point=(round(left+x*width/1000),round(top+y*height/1000))
    if point:
        left,top,w,h=capture_rect
        if not (left<=point[0]<=left+w and top<=point[1]<=top+h):
            point=None;rect=None
    return {'instruction':instruction.strip()[:520],'point':point,'rect':rect,'source':'local Ollama vision', 'found':bool(point)}


def next_instruction(topic,lang,completed=0,stuck=False):
    if topic not in TASKS:return ''
    l=lang if lang in ('en','te','hi') else 'en'
    steps=TASKS[topic][l]
    if stuck:return steps[2]
    return steps[1] if completed else steps[0]
