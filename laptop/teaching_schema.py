"""Strict declarative teaching schema; local calculations are authoritative.
Only four bounded templates, never arbitrary images or executable content.
"""
from __future__ import annotations
import json

MAX_BYTES = 256
KINDS = ('add', 'subtract', 'count', 'shape')
KEYS = {'cmd', 'v', 'action', 'kind', 'a', 'b', 'choices', 'duration_ms'}

def validate_scene(value):
    if type(value) is not dict or set(value) != KEYS:
        raise ValueError('Exact lesson fields required')
    if value['cmd'] != 'lesson' or type(value['v']) is not int or value['v'] != 1 or value['action'] != 'show':
        raise ValueError('Unsupported lesson protocol')
    if type(value['kind']) is not str or value['kind'] not in KINDS:
        raise ValueError('Unsupported template')
    a, b, ms = value['a'], value['b'], value['duration_ms']
    if any(type(x) is not int for x in (a, b, ms)) or not (0 <= a <= 12 and 0 <= b <= 12 and 5000 <= ms <= 120000):
        raise ValueError('Lesson integers out of bounds')
    kind = value['kind']
    if kind in ('count', 'shape') and b != 0:
        raise ValueError('Unused b must be zero')
    if kind == 'shape' and a not in (0, 3, 4):
        raise ValueError('Only circle, triangle and square')
    result = a + b if kind == 'add' else a - b if kind == 'subtract' else a
    choices = value['choices']
    if type(choices) is not list or not 2 <= len(choices) <= 3 or any(type(x) is not int or not 0 <= x <= 12 for x in choices):
        raise ValueError('Two or three integer answer targets required')
    if not 0 <= result <= 12 or len(set(choices)) != len(choices) or choices.count(result) != 1:
        raise ValueError('Invalid deterministic answers')
    if len(json.dumps(value, separators=(',', ':'), allow_nan=False).encode()) > MAX_BYTES:
        raise ValueError('Payload too large')
    return dict(value, choices=list(choices))

def parse_scene(raw):
    if not isinstance(raw, (str, bytes)) or len(raw.encode() if isinstance(raw, str) else raw) > MAX_BYTES:
        raise ValueError('Payload too large')
    def unique(pairs):
        d = {}
        for k, v in pairs:
            if k in d: raise ValueError('Duplicate field')
            d[k] = v
        return d
    try:
        return validate_scene(json.loads(raw, object_pairs_hook=unique))
    except (TypeError, UnicodeError, RecursionError) as e:
        raise ValueError('Invalid scene') from e

def demo(name):
    templates = {'addition': ('add', 3, 2, [4, 5, 6]),
                 'counting': ('count', 5, 0, [3, 5, 7]),
                 'triangle': ('shape', 3, 0, [2, 3, 4])}
    if name not in templates: raise ValueError('Unknown demo')
    kind, a, b, choices = templates[name]
    return validate_scene(dict(cmd='lesson', v=1, action='show', kind=kind, a=a, b=b, choices=choices, duration_ms=60000))

# For a future registered Hermes tool, or the existing tool-free structured reply.
# Do not enable broad tools: this one function only validates declarative output.
LESSON_TOOL = {'name': 'show_teaching_scene', 'description': 'Propose a small local visual quiz. No spoken answer; child chooses or explicitly reveals.',
 'parameters': {'type': 'object', 'additionalProperties': False, 'required': sorted(KEYS), 'properties': {
 'cmd': {'const': 'lesson'}, 'v': {'const': 1}, 'action': {'const': 'show'},
 'kind': {'enum': list(KINDS)}, 'a': {'type': 'integer', 'minimum': 0, 'maximum': 12},
 'b': {'type': 'integer', 'minimum': 0, 'maximum': 12},
 'choices': {'type': 'array', 'minItems': 2, 'maxItems': 3, 'uniqueItems': True, 'items': {'type': 'integer', 'minimum': 0, 'maximum': 12}},
 'duration_ms': {'type': 'integer', 'minimum': 5000, 'maximum': 120000}}}}

TEACHING_PERSONA = '''For visual teaching, obey the current parent curriculum supplied in context.
When the requested topic matches an available selected skill, add lesson:{"skill_id":"the exact selected ID"}.
The host generates and validates varied bounded exercises locally. Never invent a skill ID or
substitute easy arithmetic for an unsupported request (fractions, multiplication, etc.).
If unavailable or no parent selection, explain the limitation and omit lesson.
Do not claim full curriculum coverage, fluency or mastery from practice.
Never give the answer or claim display success. Lesson speech is replaced by a fixed invitation.
Legacy declarative scenes are accepted only when independently validated against the selected skill.'''

def normalize_reply(value, base_validator):
    if type(value) is not dict: return base_validator(value)
    if 'lesson' not in value: return base_validator(value)
    if set(value) != {'text', 'face', 'lesson'}: raise ValueError('Invalid teaching reply fields')
    base = base_validator({'text': value['text'], 'face': value['face']})
    lesson=value['lesson']
    if type(lesson) is dict and set(lesson)=={'skill_id'} and type(lesson['skill_id']) is str and 1<=len(lesson['skill_id'])<=80:
        base['lesson']=dict(lesson)
    else:
        base['lesson'] = validate_scene(lesson)
    base['text'] = 'Let us try this together. Tap an answer, or tap Help.'
    return base
