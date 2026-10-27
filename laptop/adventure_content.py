"""Age-free, bounded content for the Firstbot browser adventure."""
from __future__ import annotations
import random
from teaching_schema import validate_scene
import curriculum

VERSION = '1'
COUNT_ID = 'mt_yqAL6O5i_v'
SKILL5 = 'mt_ghF3Vv6taM'
SKILL10 = 'mt__we2TDqnJx'
SKILL12 = 'mt_mr_Vk7FGzK'
SHAPE_ID = 'mt_yGv8doDAmp'

_LEVELS = (
    ('L1','Dot Dock','Count bright dots and build number confidence.','#56d6bd', [('L1-1','Tiny tidepool','Count 1–3 dots.'),('L1-2','Five-point pier','Count 1–5, including 4 and 5.'),('L1-3','Mixed dock','Practice mixed counts from 1–5.')],'L1-boss'),
    ('L2','Number Bridge','Cross the bridge with addition and subtraction within 5.','#f2b35d', [('L2-1','Addition span','Add within 5.'),('L2-2','Subtraction span','Subtract within 5.'),('L2-3','Two-way bridge','Mix addition and subtraction within 5.')],'L2-boss'),
    ('L3','Ten Towers','Count, add, and subtract within 10.','#a78bfa', [('L3-1','Tower counters','Count 6–10.'),('L3-2','Tower builders','Add within 10, including sums 6–10.'),('L3-3','Tower toppers','Subtract within 10, including minuends 6–10.')],'L3-boss'),
    ('L4','Twelve Station','Practice counting and arithmetic through 12.','#65a9f5', [('L4-1','Platform numbers','Count 1–12, including 11 and 12.'),('L4-2','Train additions','Add through 12, including sums 11 and 12.'),('L4-3','Train departures','Subtract through 12, including minuends 11 and 12.')],'L4-boss'),
    ('S','Shape Workshop','Explore straight sides of a circle, triangle, and square.','#f28bad', [('S-1','Shape studio','Circle, triangle, and square straight sides only.')],'S-boss'),
)
_STAGE_LEVEL={sid: lid for lid,_,_,_,stages,_ in _LEVELS for sid,_,_ in stages}
_BOSSES={boss:lid for lid,_,_,_,_,boss in _LEVELS}

def catalog():
    return [{'id':lid,'title':title,'description':desc,'color':color,'stages':[{'id':s,'title':t,'description':d} for s,t,d in stages],'boss_id':boss} for lid,title,desc,color,stages,boss in _LEVELS]

def stage_info(stage_id):
    if type(stage_id) is not str: raise ValueError('Unknown stage')
    if stage_id in _STAGE_LEVEL:
        level=_STAGE_LEVEL[stage_id]
        title=next(s[1] for l in _LEVELS for s in l[4] if s[0]==stage_id)
        return {'id':stage_id,'title':title,'level_id':level,'is_boss':False,'required_challenges':2}
    if stage_id in _BOSSES:
        return {'id':stage_id,'title':next(l[1]+' Boss' for l in _LEVELS if l[5]==stage_id),'level_id':_BOSSES[stage_id],'is_boss':True,'required_challenges':1}
    raise ValueError('Unknown stage')

def _meta(skill, cap):
    topic=curriculum.TOPICS[skill]
    return {'taxonomy':'Marble Skill Taxonomy','version':curriculum.DATA['version'],'commit':curriculum.COMMIT,'skill_id':skill,'skill_name':topic['name'],'domain':topic['domain'],'coverage':curriculum.SUPPORT[skill][2],'max_value':cap,'source':'browser-adventure','generator_version':1}

def _answer(kind,a,b):
    return a+b if kind=='add' else a-b if kind=='subtract' else a

def _scene(kind,a,b,cap,rng):
    answer=_answer(kind,a,b)
    choices=[answer]+rng.sample([n for n in range(cap+1) if n!=answer],2)
    rng.shuffle(choices)
    return validate_scene({'cmd':'lesson','v':1,'action':'show','kind':kind,'a':a,'b':b,'choices':choices,'duration_ms':60000})

def _candidates(stage_id):
    """Finite candidate space; each item encodes its own tuple, cap and skill."""
    if stage_id.startswith('L1'):
        lo,hi=(1,3) if stage_id=='L1-1' else (1,5)
        return [('count',n,0,hi,COUNT_ID) for n in range(lo,hi+1)]
    if stage_id.startswith('L2'):
        ops={'L2-1':('add',),'L2-2':('subtract',),'L2-3':('add','subtract'),'L2-boss':('add','add','subtract','subtract')}[stage_id]
        return [(k,a,b,5,SKILL5) for k in set(ops) for a in range(6) for b in range(6) if (k=='add' and a+b<=5 or k=='subtract' and b<=a)]
    if stage_id=='L3-1': return [('count',n,0,10,COUNT_ID) for n in range(6,11)]
    if stage_id in ('L3-2','L3-3'):
        k='add' if stage_id=='L3-2' else 'subtract'
        return [(k,a,b,10,SKILL10) for a in range(11) for b in range(11) if (a+b<=10 and a+b>=6 if k=='add' else b<=a and a>=6)]
    if stage_id=='L4-1': return [('count',n,0,12,COUNT_ID) for n in range(1,13)]
    if stage_id in ('L4-2','L4-3'):
        k='add' if stage_id=='L4-2' else 'subtract'
        return [(k,a,b,12,SKILL12) for a in range(13) for b in range(13) if (a+b<=12 and a+b>=11 if k=='add' else b<=a and a>=11)]
    if stage_id in ('L3-boss','L4-boss'):
        cap=10 if stage_id=='L3-boss' else 12; skill=SKILL10 if cap==10 else SKILL12
        out=[('count',n,0,cap,COUNT_ID) for n in range(6,cap+1)]
        out += [('add',a,b,cap,skill) for a in range(1,cap) for b in range(1,cap-a+1) if a+b<=cap]
        out += [('subtract',a,b,cap,skill) for a in range(6,cap+1) for b in range(1,a)]
        return out
    if stage_id in ('S-1','S-boss'): return [('shape',s,0,4,SHAPE_ID) for s in (0,3,4)]
    raise ValueError('Unknown stage')

def _valid_candidate(c):
    kind,a,b,cap,_=c
    if kind in ('add','subtract') and (a==0 or b==0 if kind=='add' else b==0 or a==b): return False
    answer=_answer(kind,a,b)
    wrong=[n for n in range(cap+1) if n!=answer]
    return len(wrong)>=2 and answer<=cap

def _plan(stage_id):
    if stage_id in ('L1-boss',): return [(('count',n,0,5,COUNT_ID),) for n in (2,3,4,5)]
    if stage_id in ('S-1','S-boss'): return [(c,) for c in [('shape',0,0,4,SHAPE_ID),('shape',3,0,4,SHAPE_ID),('shape',4,0,4,SHAPE_ID)]]
    if stage_id=='L2-boss': return [('add',),('add',),('subtract',),('subtract',)]
    if stage_id in ('L2-1','L2-2','L2-3'): return [(stage_id=='L2-1' and 'add' or 'subtract',)]*3 if stage_id!='L2-3' else [('add',),('subtract',),('add','subtract')]
    return [None]* (3 if not stage_id.endswith('boss') else 4)

def batch(stage_id, challenge=0, rng=None):
    stage_info(stage_id)
    if type(challenge) is not int or challenge not in (0,1): raise ValueError('Challenge must be integer 0 or 1')
    rng=rng or random.SystemRandom()
    candidates=[c for c in _candidates(stage_id) if _valid_candidate(c)]
    count=3 if not stage_id.endswith('boss') or stage_id=='S-boss' else 4
    if stage_id=='L1-boss':
        selected=[('count',n,0,5,COUNT_ID) for n in (2,3,4,5)]
    elif stage_id in ('S-1','S-boss'):
        selected=[('shape',n,0,4,SHAPE_ID) for n in (0,3,4)]
    else:
        slots=_plan(stage_id)
        selected=[]
        for i in range(count):
            options=[c for c in candidates if c not in selected and (slots[i] is None or (c[0] in slots[i]))]
            if stage_id in ('L1-2','L4-1') and i<2:
                target=(4,5) if stage_id=='L1-2' else (11,12)
                options=[c for c in options if c[1]==target[i]]
            if stage_id=='L3-2' and i<2: options=[c for c in options if _answer(c[0],c[1],c[2])>=6]
            if stage_id=='L4-2' and i<2: options=[c for c in options if _answer(c[0],c[1],c[2])==(11,12)[i]]
            if stage_id=='L3-3' and i<2: options=[c for c in options if c[1]>=6]
            if stage_id=='L4-3' and i<2: options=[c for c in options if c[1]==(11,12)[i]]
            # Boss slots cover counting and both operations; final slot is arithmetic.
            if stage_id in ('L3-boss','L4-boss'):
                options=[c for c in options if c[0]==('count','add','subtract')[i]] if i<3 else [c for c in options if c[0] in ('add','subtract')]
                high=6 if stage_id=='L3-boss' else 11
                if i==0 or i==2: options=[c for c in options if c[1]>=high]
                if i==1: options=[c for c in options if c[1]+c[2]>=high]
            if not options: raise RuntimeError('No valid candidate for required slot')
            selected.append(rng.choice(options))
    # Validate distinctness and constraints from the complete chosen set.
    if len(set(selected))!=count: raise RuntimeError('Candidate plan is not distinct')
    trivial=sum(c[0] in ('add','subtract') and (c[1]==0 if c[0]=='add' else c[2]==0 or c[1]==c[2]) for c in selected)
    if trivial>1: raise RuntimeError('Too many trivial arithmetic facts')
    return [{'scene':_scene(k,a,b,cap,rng),'metadata':_meta(skill,cap)} for k,a,b,cap,skill in selected]

def replacement(stage_id, challenge, original_item, rng=None):
    if type(original_item) is not dict or set(original_item)!={'scene','metadata'} or type(original_item['metadata']) is not dict: raise ValueError('Invalid original item')
    info=stage_info(stage_id)
    if type(challenge) is not int or challenge not in (0,1): raise ValueError('Challenge must be integer 0 or 1')
    scene=validate_scene(original_item['scene']); md=original_item['metadata']
    valid=[c for c in _candidates(stage_id) if _valid_candidate(c)]
    match=[c for c in valid if c[:3]==(scene['kind'],scene['a'],scene['b'])]
    if not match or md.get('skill_id')!=match[0][4]: raise ValueError('Original does not belong to stage')
    cap=match[0][3]
    if max(scene['choices'])>cap or _answer(scene['kind'],scene['a'],scene['b'])>cap: raise ValueError('Original exceeds stage cap')
    fresh=_scene(scene['kind'],scene['a'],scene['b'],cap,rng or random.SystemRandom())
    metadata=_meta(match[0][4],cap); metadata['retry_after_help']=True
    return {'scene':fresh,'metadata':metadata}
