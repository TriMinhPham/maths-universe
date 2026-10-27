"""Durable browser-only adventure using the existing teaching Ledger tables.

Never opens the robot ledger. No nested Ledger mutators: each adventure write,
including its teaching events, reward and replay response, has one transaction.
Browser history is deliberately separate, not migrated or synchronized.
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
import json
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

import adventure_content as content
from teaching_ledger import Ledger, utc
from teaching_schema import validate_scene

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / '.private/math-adventure.sqlite3'
NOTICE = 'Browser adventure progress is separate from robot lesson history.'
SCHEMA_VERSION = '1'


class Conflict(ValueError):
    """Valid request conflicts with durable current state (HTTP 409)."""


def packed(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def request_key(value):
    if type(value) is not str or not 1 <= len(value) <= 128 or not value.strip():
        raise ValueError('request_id must be a nonempty string of at most 128 characters')
    return value


def answer(scene):
    return (scene['a'] + scene['b'] if scene['kind'] == 'add' else
            scene['a'] - scene['b'] if scene['kind'] == 'subtract' else scene['a'])


class AdventureStore:
    def __init__(self, path=DEFAULT_DB):
        path = Path(path).expanduser().resolve()
        if not path.is_relative_to(ROOT) or path.name == 'teaching.sqlite3':
            raise ValueError('Use a separate project-local browser adventure database, never teaching.sqlite3')
        # Refuse existing foreign/malformed databases BEFORE Ledger can initialize
        # or migrate them. This also protects copies/hard links of robot history.
        if path.exists():
            if not path.is_file():
                raise ValueError('Database path is not a file')
            self._preflight(path)
        self.ledger = Ledger(path)
        self.db = self.ledger.db
        self.lock = self.ledger.lock
        self.path = path
        self.db.execute('PRAGMA busy_timeout=5000')
        try:
            with self._transaction():
                for sql in (
                    'CREATE TABLE IF NOT EXISTS adventure_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)',
                    '''CREATE TABLE IF NOT EXISTS adventure_runs(
                        id TEXT PRIMARY KEY,stage_id TEXT NOT NULL,version TEXT NOT NULL,
                        info TEXT NOT NULL,catalog TEXT NOT NULL,status TEXT NOT NULL
                        CHECK(status IN ('playing','feedback','complete')),
                        cursor INTEGER NOT NULL DEFAULT 0,current_problem INTEGER REFERENCES problems(id),
                        feedback TEXT,created TEXT NOT NULL,completed TEXT)''',
                    "CREATE UNIQUE INDEX IF NOT EXISTS adventure_one_open ON adventure_runs((1)) WHERE status!='complete'",
                    '''CREATE TABLE IF NOT EXISTS adventure_slots(
                        run TEXT NOT NULL REFERENCES adventure_runs(id),position INTEGER NOT NULL,
                        challenge INTEGER NOT NULL,slot INTEGER NOT NULL,item TEXT NOT NULL,
                        solved INTEGER NOT NULL DEFAULT 0,problem INTEGER REFERENCES problems(id),
                        PRIMARY KEY(run,position))''',
                    '''CREATE TABLE IF NOT EXISTS adventure_completions(
                        stage_id TEXT PRIMARY KEY,run TEXT NOT NULL REFERENCES adventure_runs(id),created TEXT NOT NULL)''',
                    '''CREATE TABLE IF NOT EXISTS adventure_badges(
                        level_id TEXT PRIMARY KEY,run TEXT NOT NULL REFERENCES adventure_runs(id),created TEXT NOT NULL)''',
                    '''CREATE TABLE IF NOT EXISTS adventure_overrides(
                        id INTEGER PRIMARY KEY,stage_id TEXT NOT NULL,reason TEXT NOT NULL,created TEXT NOT NULL)''',
                    '''CREATE TABLE IF NOT EXISTS adventure_requests(
                        id TEXT PRIMARY KEY,payload TEXT NOT NULL,result TEXT NOT NULL,created TEXT NOT NULL)''',
                ):
                    self.db.execute(sql)
                self.db.execute('INSERT OR IGNORE INTO adventure_meta VALUES(?,?)', ('schema', SCHEMA_VERSION))
                self.db.execute('INSERT OR IGNORE INTO adventure_meta VALUES(?,?)', ('purpose', 'separate-browser-adventure'))
                self._validate_durable()
        except BaseException:
            self.ledger.close()
            raise

    @staticmethod
    def _preflight(path):
        db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
        try:
            meta = dict(db.execute('SELECT key,value FROM adventure_meta'))
            if meta != {'schema': SCHEMA_VERSION, 'purpose': 'separate-browser-adventure'}:
                raise ValueError('Unknown browser database version or purpose; no migration performed')
            expected = {
                'settings': {'id', 'auto', 'per_correct'},
                'problems': {'id', 'session', 'scene', 'answer', 'created', 'outcome', 'completed', 'curriculum'},
                'events': {'boot', 'seq', 'problem', 'type', 'choice', 'correct', 'device_ms', 'received'},
                'stars': {'id', 'problem', 'delta', 'reason', 'created'},
                'settings_audit': {'id', 'auto', 'per_correct', 'reason', 'created'},
                'curriculum_settings': {'id', 'value'},
                'adventure_runs': {'id', 'stage_id', 'version', 'info', 'catalog', 'status', 'cursor', 'current_problem', 'feedback', 'created', 'completed'},
                'adventure_slots': {'run', 'position', 'challenge', 'slot', 'item', 'solved', 'problem'},
                'adventure_completions': {'stage_id', 'run', 'created'},
                'adventure_badges': {'level_id', 'run', 'created'},
                'adventure_overrides': {'id', 'stage_id', 'reason', 'created'},
                'adventure_requests': {'id', 'payload', 'result', 'created'},
            }
            for table, columns in expected.items():
                if {row[1] for row in db.execute('PRAGMA table_info(' + table + ')')} != columns:
                    raise ValueError('Malformed browser database schema; no rewriting performed')
            settings = db.execute('SELECT id,auto,per_correct FROM settings').fetchall()
            if len(settings) != 1 or settings[0][0] != 1 or settings[0][1] not in (0, 1) or type(settings[0][2]) is not int or not 0 <= settings[0][2] <= 5:
                raise ValueError('Malformed earning settings')
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchone():
                raise ValueError('Malformed browser database integrity')
        except sqlite3.DatabaseError as exc:
            raise ValueError('Not an initialized browser adventure database; refusing to change it') from exc
        finally:
            db.close()

    @contextmanager
    def _transaction(self, write=True):
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            try:
                yield
                self.db.commit()
            except BaseException:
                self.db.rollback()
                raise

    def _validate_durable(self):
        for row in self.db.execute('SELECT * FROM adventure_runs'):
            if row['version'] != content.VERSION:
                raise ValueError('Unsupported persisted campaign version; no regeneration performed')
            info = json.loads(row['info'])
            if info['id'] != row['stage_id']:
                raise ValueError('Malformed saved run')
            json.loads(row['catalog'])
            slots = self.db.execute('SELECT * FROM adventure_slots WHERE run=? ORDER BY position', (row['id'],)).fetchall()
            if not slots or [s['position'] for s in slots] != list(range(len(slots))):
                raise ValueError('Malformed saved slots')
            for slot in slots:
                self._item(json.loads(slot['item']))
            if row['status'] != 'complete':
                if not 0 <= row['cursor'] < len(slots) or slots[row['cursor']]['problem'] != row['current_problem']:
                    raise ValueError('Malformed saved current problem')
                p = self.db.execute('SELECT * FROM problems WHERE id=?', (row['current_problem'],)).fetchone()
                if not p or answer(validate_scene(json.loads(p['scene']))) != p['answer']:
                    raise ValueError('Malformed saved problem')
                if (row['status'] == 'playing') != (p['outcome'] == 'pending'):
                    raise ValueError('Malformed saved feedback')

    @staticmethod
    def _item(item):
        if type(item) is not dict or not {'scene', 'metadata'} <= item.keys():
            raise ValueError('Invalid campaign item')
        scene = validate_scene(item['scene'])
        if len(scene['choices']) != 3 or type(item['metadata']) is not dict or not {'skill_id', 'coverage'} <= item['metadata'].keys():
            raise ValueError('Campaign requires three choices and explicit coverage metadata')
        if any('age' == key or key.endswith('_age') for key in item['metadata']):
            raise ValueError('Adventure metadata must be age-free')
        packed(item)
        return item

    def _info(self, stage_id):
        if type(stage_id) is not str or len(stage_id) > 32:
            raise ValueError('Invalid stage ID')
        ids = {s['id'] for level in content.catalog() for s in level['stages']}
        ids.update(level['boss_id'] for level in content.catalog())
        if stage_id not in ids:
            raise ValueError('Unknown stage')
        return content.stage_info(stage_id)

    def _latest(self):
        return self.db.execute('SELECT * FROM adventure_runs ORDER BY rowid DESC LIMIT 1').fetchone()

    def _levels(self):
        done = {r[0] for r in self.db.execute('SELECT stage_id FROM adventure_completions')}
        overrides = {r[0] for r in self.db.execute('SELECT stage_id FROM adventure_overrides')}
        badges = {r[0] for r in self.db.execute('SELECT level_id FROM adventure_badges')}
        levels = copy.deepcopy(content.catalog())
        for level in levels:
            lid = level['id']
            entrance = lid == 'L1' or ('L1' in badges if lid == 'S' else 'L' + str(int(lid[1:]) - 1) in badges)
            previous = None
            for stage in level['stages']:
                sid = stage['id']
                stage.update(unlocked=(sid in overrides or sid in done or (entrance if previous is None else previous in done)),
                             completed=sid in done, overridden=sid in overrides)
                previous = sid
            bid = level['boss_id']
            level['boss'] = {'id': bid, 'title': content.stage_info(bid)['title'],
                             'unlocked': bid in overrides or bid in done or all(s['completed'] for s in level['stages']),
                             'completed': bid in done, 'overridden': bid in overrides}
        return levels

    def _unlocked(self, stage_id):
        return any(s['id'] == stage_id and s['unlocked'] for level in self._levels() for s in [*level['stages'], level['boss']])

    def _state(self):
        run = self._latest()
        active = None
        if run:
            info = json.loads(run['info'])
            slots = self.db.execute('SELECT * FROM adventure_slots WHERE run=? ORDER BY position', (run['id'],)).fetchall()
            slot = slots[min(run['cursor'], len(slots) - 1)]
            problem = None
            if run['status'] != 'complete':
                p = self.db.execute('SELECT * FROM problems WHERE id=?', (run['current_problem'],)).fetchone()
                problem = {'id': p['id'], 'scene': json.loads(p['scene']), 'feedback': run['feedback'],
                           'answer': p['answer'] if run['feedback'] in ('correct', 'revealed') else None}
            active = {'id': run['id'], 'stage_id': run['stage_id'], 'title': info['title'], 'is_boss': info['is_boss'],
                      'challenge_index': slot['challenge'], 'challenge_count': info['required_challenges'],
                      'slot_index': slot['slot'], 'slot_count': sum(s['challenge'] == slot['challenge'] for s in slots),
                      'completed_count': sum(s['solved'] for s in slots), 'total_count': len(slots),
                      'status': run['status'], 'problem': problem}
        settings = self.db.execute('SELECT auto,per_correct FROM settings WHERE id=1').fetchone()
        return {'version': content.VERSION, 'levels': self._levels(),
                'stars': self.db.execute('SELECT COALESCE(SUM(delta),0) FROM stars').fetchone()[0],
                'settings': {'auto': bool(settings['auto']), 'per_correct': settings['per_correct']},
                'active': active, 'badges': [r[0] for r in self.db.execute('SELECT level_id FROM adventure_badges ORDER BY level_id')],
                'notice': NOTICE}

    def state(self):
        with self._transaction(False):
            return self._state()

    def _request(self, request_id, payload, operation):
        request_key(request_id)
        payload = packed(payload)
        with self._transaction():
            old = self.db.execute('SELECT payload,result FROM adventure_requests WHERE id=?', (request_id,)).fetchone()
            if old:
                if old['payload'] != payload:
                    raise Conflict('request_id was already used with a different payload')
                return json.loads(old['result'])
            operation()
            result = self._state()
            self.db.execute('INSERT INTO adventure_requests VALUES(?,?,?,?)', (request_id, payload, packed(result), utc()))
            return result

    def _new_problem(self, run_id, position, item):
        item = self._item(item)
        scene = item['scene']
        cur = self.db.execute('INSERT INTO problems(session,scene,answer,created,curriculum) VALUES(?,?,?,?,?)',
                              ('adventure:' + run_id, packed(scene), answer(scene), utc(), packed(item['metadata'])))
        pid = cur.lastrowid
        if pid > 2147483647:
            raise ValueError('Problem ID capacity reached')
        self.db.execute('UPDATE adventure_slots SET problem=? WHERE run=? AND position=?', (pid, run_id, position))
        self.db.execute("UPDATE adventure_runs SET current_problem=?,status='playing',feedback=NULL WHERE id=?", (pid, run_id))

    def start(self, stage_id, request_id):
        info = self._info(stage_id)
        def operation():
            previous = self._latest()
            if previous and previous['status'] != 'complete':
                if previous['stage_id'] == stage_id:
                    return
                raise Conflict('Finish or resume the active stage before starting another')
            if not self._unlocked(stage_id):
                raise Conflict('Stage is locked; a parent can explicitly override the lock')
            batches = [content.batch(stage_id, challenge=i) for i in range(info['required_challenges'])]
            expected = 3 if not info['is_boss'] or info['level_id'] == 'S' else 4
            if info['required_challenges'] != (1 if info['is_boss'] else 2) or any(len(b) != expected for b in batches):
                raise ValueError('Campaign batch length violates the stage contract')
            run = uuid4().hex
            self.db.execute('INSERT INTO adventure_runs(id,stage_id,version,info,catalog,status,created) VALUES(?,?,?,?,?,?,?)',
                            (run, stage_id, content.VERSION, packed(info), packed(content.catalog()), 'playing', utc()))
            position = 0
            for challenge, items in enumerate(batches):
                for slot, item in enumerate(items):
                    self._item(item)
                    self.db.execute('INSERT INTO adventure_slots(run,position,challenge,slot,item) VALUES(?,?,?,?,?)',
                                    (run, position, challenge, slot, packed(item)))
                    position += 1
            self._new_problem(run, 0, batches[0][0])
        return self._request(request_id, {'method': 'start', 'stage_id': stage_id}, operation)

    def event(self, problem_id, action, choice, request_id):
        if type(problem_id) is not int or not 1 <= problem_id <= 2147483647:
            raise ValueError('Invalid problem ID')
        if type(action) is not str or action not in ('answer', 'reveal', 'skip'):
            raise ValueError('Invalid action; correctness is calculated by the server')
        if action == 'answer' and type(choice) is not int:
            raise ValueError('An integer displayed choice is required')
        if action != 'answer' and choice is not None:
            raise ValueError('Reveal and skip must not contain an answer')
        def operation():
            run = self._latest()
            if not run or run['status'] != 'playing' or run['current_problem'] != problem_id:
                raise Conflict('This is not the current open problem')
            p = self.db.execute('SELECT * FROM problems WHERE id=?', (problem_id,)).fetchone()
            if p['outcome'] != 'pending':
                raise Conflict('Problem is already finalized')
            boot = 'adventure:' + run['id']
            seq = self.db.execute('SELECT COALESCE(MAX(seq),0)+1 FROM events WHERE boot=?', (boot,)).fetchone()[0]
            now = utc()
            outcome = None
            if action == 'answer':
                if choice not in json.loads(p['scene'])['choices']:
                    raise ValueError('Only a displayed answer choice is accepted')
                correct = int(choice == p['answer'])
                self.db.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?,?)', (boot, seq, problem_id, 'attempt', choice, correct, 0, now))
                seq += 1
                feedback = 'correct' if correct else 'incorrect'
                if correct:
                    outcome = 'correct'
            else:
                feedback = 'revealed' if action == 'reveal' else 'skipped'
                outcome = feedback
                # Ledger defines skipped as unattempted. Preserve that convention:
                # skipping after wrong attempts closes it as incorrect in the
                # teaching ledger, while browser feedback records explicit skip.
                if action == 'skip' and self.db.execute("SELECT 1 FROM events WHERE problem=? AND type='attempt'", (problem_id,)).fetchone():
                    outcome = 'incorrect'
            if outcome:
                self.db.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?,?)', (boot, seq, problem_id, outcome, -1, None, 0, now))
                updated = self.db.execute("UPDATE problems SET outcome=?,completed=? WHERE id=? AND outcome='pending'", (outcome, now, problem_id))
                if updated.rowcount != 1:
                    raise Conflict('Problem was already finalized')
                if outcome == 'correct':
                    settings = self.db.execute('SELECT * FROM settings WHERE id=1').fetchone()
                    if settings['auto']:
                        self.db.execute('INSERT INTO stars(problem,delta,reason,created) VALUES(?,?,?,?)',
                                        (problem_id, settings['per_correct'], 'Correct completion', now))
                    self.db.execute('UPDATE adventure_slots SET solved=1 WHERE run=? AND position=?', (run['id'], run['cursor']))
            self.db.execute('UPDATE adventure_runs SET status=?,feedback=? WHERE id=?',
                            ('feedback' if outcome else 'playing', feedback, run['id']))
        return self._request(request_id, {'method': 'event', 'problem_id': problem_id, 'action': action, 'choice': choice}, operation)

    def next(self, request_id):
        def operation():
            run = self._latest()
            if not run or run['status'] != 'feedback':
                raise Conflict('Next requires a finished problem awaiting feedback acknowledgement')
            slot = self.db.execute('SELECT * FROM adventure_slots WHERE run=? AND position=?', (run['id'], run['cursor'])).fetchone()
            if not slot['solved']:
                item = content.replacement(run['stage_id'], slot['challenge'], json.loads(slot['item']))
                self._item(item)
                # Replacements must retain the mathematical tuple, so quota and
                # nontrivial constraints cannot be weakened by Help or Skip.
                original = json.loads(slot['item'])['scene']
                if any(item['scene'][key] != original[key] for key in ('kind', 'a', 'b')):
                    raise ValueError('Replacement must preserve its slot mathematical tuple')
                self._new_problem(run['id'], run['cursor'], item)
                return
            position = run['cursor'] + 1
            upcoming = self.db.execute('SELECT * FROM adventure_slots WHERE run=? AND position=?', (run['id'], position)).fetchone()
            if upcoming:
                self.db.execute('UPDATE adventure_runs SET cursor=? WHERE id=?', (position, run['id']))
                self._new_problem(run['id'], position, json.loads(upcoming['item']))
            else:
                now = utc()
                self.db.execute("UPDATE adventure_runs SET status='complete',current_problem=NULL,feedback=NULL,completed=? WHERE id=?", (now, run['id']))
                self.db.execute('INSERT OR IGNORE INTO adventure_completions VALUES(?,?,?)', (run['stage_id'], run['id'], now))
                info = json.loads(run['info'])
                if info['is_boss']:
                    self.db.execute('INSERT OR IGNORE INTO adventure_badges VALUES(?,?,?)', (info['level_id'], run['id'], now))
        return self._request(request_id, {'method': 'next'}, operation)

    def override(self, stage_id, reason, request_id):
        self._info(stage_id)
        Ledger._reason(reason)
        def operation():
            self.db.execute('INSERT INTO adventure_overrides(stage_id,reason,created) VALUES(?,?,?)', (stage_id, reason, utc()))
        return self._request(request_id, {'method': 'override', 'stage_id': stage_id, 'reason': reason}, operation)

    def adjust(self, delta=None, total=None, reason=None):
        Ledger._reason(reason)
        if (delta is None) == (total is None):
            raise ValueError('Choose delta or total')
        value = delta if delta is not None else total
        if type(value) is not int or abs(value) > 100000:
            raise ValueError('Invalid star value')
        with self._transaction():
            current = self.db.execute('SELECT COALESCE(SUM(delta),0) FROM stars').fetchone()[0]
            new = current + delta if delta is not None else total
            if not 0 <= new <= 100000:
                raise ValueError('Star total must be 0..100000')
            self.db.execute('INSERT INTO stars(delta,reason,created) VALUES(?,?,?)', (new - current, reason, utc()))
            return self._state()

    def earning(self, auto, per_correct, reason):
        Ledger._reason(reason)
        if type(auto) is not bool or type(per_correct) is not int or not 0 <= per_correct <= 5:
            raise ValueError('Invalid earning settings')
        with self._transaction():
            self.db.execute('UPDATE settings SET auto=?,per_correct=? WHERE id=1', (auto, per_correct))
            self.db.execute('INSERT INTO settings_audit(auto,per_correct,reason,created) VALUES(?,?,?,?)', (auto, per_correct, reason, utc()))
            return self._state()

    def history(self, before=None):
        if before is not None and (type(before) is not int or before < 1 or before > 2147483648):
            raise ValueError('Invalid history cursor')
        with self._transaction(False):
            # snapshot is a read-only Ledger method; unlike its mutators it never
            # commits our encompassing transaction. Keep its established audit shape.
            result = self.ledger.snapshot(limit=25, before=before)
            for item in result['history']:
                if item['outcome'] not in ('correct', 'revealed'):
                    item['answer'] = None
                    for attempt in item['attempts']:
                        attempt['correct'] = None
            result['override_audit'] = [dict(r) for r in self.db.execute('SELECT * FROM adventure_overrides ORDER BY id DESC LIMIT 100')]
            result['notice'] = NOTICE
            return result

    def close(self):
        self.ledger.close()
