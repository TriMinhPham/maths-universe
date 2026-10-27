"""Pinned data only; local capability mapping, not a mastery assessment.
Mapping/selection projection: ODbL 1.0; Marble labels: CC BY-SA 4.0.
"""
import hashlib
import json
import random
from pathlib import Path
from teaching_schema import validate_scene

ROOT = Path(__file__).parent / 'vendor/os-taxonomy'
COMMIT = '7bd8b6794cb78d9ca18216adb935f3cfd59cf5ac'
MANIFEST = json.loads((ROOT/'data/manifest.json').read_text())
raw = (ROOT/'data/topics.json').read_bytes()
if hashlib.sha256(raw).hexdigest() != MANIFEST['files']['topics.json']['sha256']:
    raise RuntimeError('Taxonomy checksum mismatch')
DATA = json.loads(raw)
TOPICS = {t['id']: t for t in DATA['topics'] if t['subject'] == 'Mathematics'}
# Explicit narrow alignments; none imply the complete upstream evidence is assessed.
SUPPORT = {
    'mt_ghF3Vv6taM': (('add','subtract'), 5, 'Facts within 5; practice only, fluency not measured.'),
    'mt__we2TDqnJx': (('add','subtract'), 10, 'Facts within 10; practice only, fluency not measured.'),
    'mt_mr_Vk7FGzK': (('add','subtract'), 12, 'Partial: integers through 12 only, NOT the full through-20 skill.'),
    'mt_yqAL6O5i_v': (('count',), 12, 'Partial: count 1–12 displayed dots only, NOT sets through 20 or counting out objects.'),
    'mt_yGv8doDAmp': (('shape',), 4, 'Partial: straight sides of circle/triangle/square only; no 3-D, corners or comparisons.'),
    'mt_sBcRdUfAzV': (('shape',), 4, 'Partial: straight sides of circle/triangle/square only; no symmetry or other shapes.'),
}
assert SUPPORT.keys() <= TOPICS.keys()
DEFAULT = {'age': None, 'level_age': None, 'difficulty': 'auto', 'skill_id': None}

def settings(value):
    if type(value) is not dict or set(value) != set(DEFAULT):
        raise ValueError('Exact curriculum settings required; no name or date of birth')
    for key in ('age','level_age'):
        if value[key] is not None and (type(value[key]) is not int or not 4 <= value[key] <= 15):
            raise ValueError('Age/level guidance must be 4–15 or unset')
    if value['difficulty'] not in ('auto','within5','within10','within12'):
        raise ValueError('Unknown practice difficulty')
    if value['skill_id'] is not None and (type(value['skill_id']) is not str or value['skill_id'] not in TOPICS):
        raise ValueError('Unknown mathematics skill ID')
    return dict(value)

def level(config):
    return config['level_age'] if config['level_age'] is not None else config['age']

def recommended(topic, age):
    return age is not None and topic['ageRangeStart'] is not None and topic['ageRangeEnd'] is not None and topic['ageRangeStart'] <= age <= topic['ageRangeEnd']

def catalog(config):
    config = settings(config)
    topics=[]
    for t in TOPICS.values():
        s=SUPPORT.get(t['id'])
        topics.append({k:t[k] for k in ('id','name','domain','description','ageRangeStart','ageRangeEnd')} | {
            'recommended': recommended(t,level(config)), 'available':bool(s),
            'coverage':s[2] if s else 'Not yet supported by Firstbot; browsing only.',
            'templates':list(s[0]) if s else []})
    return {'settings':config,'commit':COMMIT,'version':DATA['version'],'math_topic_count':len(TOPICS),
            'available_skill_count':len(SUPPORT),'topics':topics,
            'age_guidance':'Upstream approximate ageRangeStart/ageRangeEnd, inclusive. Age is guidance, not diagnosis or mastery. Override recommendation age freely.',
            'limits':'Only six narrow practice alignments. Older learners: most recommended topics are NOT implemented. No automatic fallback to easy lessons. All device integers remain 0–12.',
            'attribution':'Marble Skill Taxonomy (v1) · © Generative Spark, Inc. (Marble) · https://withmarble.com · ODbL 1.0 (database), CC BY-SA 4.0 (content). Firstbot capability mapping is an adaptation, not Marble endorsement.'}

def bounds(config):
    settings(config)
    if config['age'] is None: raise ValueError('Choose an age for guidance first; no identity is required')
    sid=config['skill_id']
    if sid not in SUPPORT: raise ValueError('Selected skill is not yet supported. Choose an explicitly available practice skill; no substitution was made.')
    kinds,cap,_=SUPPORT[sid]
    age=level(config)
    difficulty=config['difficulty']
    selected=(5 if age<=5 else 10 if age<=7 else 12) if difficulty=='auto' else int(difficulty[6:])
    return kinds,min(cap,selected)

def metadata(config, scene, source):
    kinds,cap=bounds(config)
    s=validate_scene(scene)
    answer=s['a']+s['b'] if s['kind']=='add' else s['a']-s['b'] if s['kind']=='subtract' else s['a']
    if s['kind'] not in kinds or max(s['a'],s['b'],answer,*s['choices'])>cap:
        raise ValueError('Lesson does not match the selected skill/difficulty; no unrelated substitution made')
    t=TOPICS[config['skill_id']]
    return {'taxonomy':'Marble Skill Taxonomy','version':DATA['version'],'commit':COMMIT,
            'skill_id':t['id'],'skill_name':t['name'],'domain':t['domain'],
            'selection':dict(config),'effective_level_age':level(config),'max_value':cap,
            'coverage':SUPPORT[t['id']][2],'source':source,'generator_version':1}

def generate(config, rng=None, previous=None):
    rng=rng or random.SystemRandom()
    kinds,cap=bounds(config)
    candidates=[]
    for kind in kinds:
        if kind=='shape': candidates.extend((kind,a,0) for a in (0,3,4))
        elif kind=='count': candidates.extend((kind,a,0) for a in range(1,cap+1))
        else:
            candidates.extend((kind,a,b) for a in range(cap+1) for b in range(cap+1)
                              if 0 <= (a+b if kind=='add' else a-b) <= cap)
    if previous:
        candidates=[x for x in candidates if x!=(previous['kind'],previous['a'],previous['b'])] or candidates
    kind,a,b=rng.choice(candidates)
    answer=a+b if kind=='add' else a-b if kind=='subtract' else a
    choices=[answer]+rng.sample([n for n in range(cap+1) if n!=answer],2)
    rng.shuffle(choices)
    scene=validate_scene(dict(cmd='lesson',v=1,action='show',kind=kind,a=a,b=b,choices=choices,duration_ms=60000))
    metadata(config,scene,'local')
    return scene

def prompt(config):
    # No age, DOB, history or stars transmitted. Only the selected public skill/capability.
    try:
        kinds,cap=bounds(config)
        t=TOPICS[config['skill_id']]
        return ('Current parent curriculum: '+t['id']+' — '+t['name']+'. '+SUPPORT[t['id']][2]+
                ' Allowed templates: '+','.join(kinds)+f'; integers/answers/choices 0..{cap}. '+
                'For a matching visual lesson return lesson:{"skill_id":"'+t['id']+'"}; host generates varied exercises. '+
                'Never substitute this skill for an unsupported requested topic. Say that requested topic is not yet supported instead. Do not claim full curriculum or mastery.')
    except ValueError:
        return 'Visual lessons unavailable: ask parent to select an available curriculum skill at /teaching. Do not include a lesson.'
