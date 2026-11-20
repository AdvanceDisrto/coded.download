"""Strict inert CODED™ civilization v1 blueprint, shared with web/irp.mjs.

No model-generated scripts, file paths, URLs, shader source or instructions.
Malformed input never reaches the renderer. This is not model-origin proof.
"""
from __future__ import annotations
import hashlib
import json
import math
import re
from typing import Any
from core.simulation import canonical_bytes

SCHEMA = 'innovulis.irp.blueprint.v1'
SECTORS = frozenset(('habitat','energy','health','agriculture','transport','civic'))
THEMES = frozenset(('ocean','forest','desert','night'))
ID = re.compile(r'^[a-z][a-z0-9-]{0,23}$')
MAX_BLUEPRINT_BYTES = 16384

class WorldBlueprintError(ValueError): pass

def reject(reason): raise WorldBlueprintError('CODED_WORLD_INVALID_'+reason)

def exactly(o: Any, fields: set[str], which: str) -> None:
    if type(o) is not dict or set(o) != fields: reject(which+'_KEYS')

def text(v: Any, lo: int, hi: int, reason: str) -> str:
    if type(v) is not str or not lo <= len(v) <= hi or v.strip()!=v or any(ord(c)<32 or ord(c)==127 for c in v):
        reject(reason+'_TEXT')
    return v

def number(v: Any, lo: float, hi: float, reason: str) -> float|int:
    if type(v) not in (int,float) or not math.isfinite(v) or not lo <= v <= hi:
        reject(reason+'_RANGE')
    return v

def validate_blueprint(value: Any) -> dict:
    exactly(value, {'schema','title','summary','theme','districts','plan'}, 'ROOT')
    if value['schema']!=SCHEMA: reject('SCHEMA')
    title=text(value['title'],3,80,'TITLE')
    summary=text(value['summary'],3,240,'SUMMARY')
    if type(value['theme']) is not str or value['theme'] not in THEMES: reject('THEME')
    raw=value['districts']
    if type(raw) is not list or not 3<=len(raw)<=12: reject('DISTRICTS')
    districts=[];identifiers=set()
    for d in raw:
        exactly(d, {'id','name','sector','x','y','height'}, 'DISTRICT')
        ident=d['id']
        if type(ident) is not str or not ID.fullmatch(ident): reject('DISTRICT_ID')
        if ident in identifiers: reject('DISTRICT_DUPLICATE_ID')
        identifiers.add(ident)
        name=text(d['name'],2,48,'DISTRICT_NAME')
        if type(d['sector']) is not str or d['sector'] not in SECTORS: reject('DISTRICT_SECTOR')
        x=number(d['x'],8,92,'X'); y=number(d['y'],8,92,'Y')
        if type(d['height']) is not int or not 1<=d['height']<=5: reject('HEIGHT')
        districts.append({'id':ident,'name':name,'sector':d['sector'],'x':x,'y':y,'height':d['height']})
    plan=value['plan'];exactly(plan, {'aid_units','diplomacy','communications_disrupted'},'PLAN')
    if type(plan['aid_units']) is not int or not 0<=plan['aid_units']<=100:reject('AID')
    diplomacy=number(plan['diplomacy'],0,1,'DIPLOMACY')
    if type(plan['communications_disrupted']) is not bool:reject('DISRUPTED')
    clean={'schema':SCHEMA,'title':title,'summary':summary,'theme':value['theme'],
        'districts':districts,'plan':{'aid_units':plan['aid_units'],
        'diplomacy':diplomacy,'communications_disrupted':plan['communications_disrupted']}}
    if len(canonical_bytes(clean))>MAX_BLUEPRINT_BYTES:reject('TOO_LARGE')
    return clean

def strict_json_bytes(blob: bytes)->dict:
    if type(blob) is not bytes or not 1 <= len(blob) <= MAX_BLUEPRINT_BYTES:reject('INPUT_SIZE')
    def unique(pairs):
        o={}
        for k,v in pairs:
            if k in o:reject('DUPLICATE_JSON_KEY')
            o[k]=v
        return o
    def nonfinite(value):reject('NONFINITE_JSON_'+value)
    try:
        v=json.loads(blob.decode('utf-8'),object_pairs_hook=unique,parse_constant=nonfinite)
    except (UnicodeError,ValueError) as exc:
        if isinstance(exc,WorldBlueprintError):raise
        reject('JSON_PARSE')
    return validate_blueprint(v)

def blueprint_hash(blueprint: dict)->str:
    return hashlib.sha256(canonical_bytes(validate_blueprint(blueprint))).hexdigest()

SAMPLE={
  'schema':SCHEMA,'title':'Aurelia · The Ocean Citadel',
  'summary':'Fictional ocean civilization, with gardens, healthcare and energy districts.',
  'theme':'ocean','districts':[
    {'id':'central-spire','name':'Civic Nexus','sector':'civic','x':51,'y':25,'height':5},
    {'id':'arc-harbor','name':'Arc Harbor','sector':'transport','x':23,'y':73,'height':3},
    {'id':'helios-grid','name':'Helios Grid','sector':'energy','x':80,'y':61,'height':4},
    {'id':'medica','name':'Medica','sector':'health','x':72,'y':31,'height':3},
    {'id':'garden-dome','name':'Garden Dome','sector':'agriculture','x':33,'y':47,'height':2},
    {'id':'sky-habitat','name':'Sky Habitat','sector':'habitat','x':56,'y':76,'height':4}
  ],'plan':{'aid_units':8,'diplomacy':0.65,'communications_disrupted':False}
}