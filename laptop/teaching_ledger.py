"""Local-only unnamed learner ledger. Transactions + event/award idempotence.
No raw audio, names or cloud integration. Parent controls trust the laptop user.
"""
import json
import os
from pathlib import Path
import sqlite3
import threading
from datetime import datetime, timezone
from uuid import uuid4
from teaching_schema import validate_scene

def utc(): return datetime.now(timezone.utc).isoformat()

class Ledger:
    def __init__(self, path=None):
        self.path = Path(path or Path(__file__).resolve().parents[1] / '.private/teaching.sqlite3')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        os.chmod(self.path, 0o600)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        PRAGMA foreign_keys=ON;
        PRAGMA journal_mode=DELETE;
        CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), auto INTEGER NOT NULL, per_correct INTEGER NOT NULL);
        INSERT OR IGNORE INTO settings VALUES(1,1,1);
        CREATE TABLE IF NOT EXISTS problems(id INTEGER PRIMARY KEY AUTOINCREMENT, session TEXT NOT NULL, scene TEXT NOT NULL, answer INTEGER NOT NULL, created TEXT NOT NULL, outcome TEXT NOT NULL DEFAULT 'pending', completed TEXT);
        CREATE TABLE IF NOT EXISTS events(boot TEXT NOT NULL, seq INTEGER NOT NULL, problem INTEGER NOT NULL REFERENCES problems(id), type TEXT NOT NULL, choice INTEGER, correct INTEGER, device_ms INTEGER NOT NULL, received TEXT NOT NULL, PRIMARY KEY(boot,seq));
        CREATE TABLE IF NOT EXISTS stars(id INTEGER PRIMARY KEY, problem INTEGER UNIQUE REFERENCES problems(id), delta INTEGER NOT NULL, reason TEXT NOT NULL, created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings_audit(id INTEGER PRIMARY KEY, auto INTEGER, per_correct INTEGER, reason TEXT NOT NULL, created TEXT NOT NULL);
        ''')
        # Additive migration: prior scenes, attempts, IDs and star rows are untouched.
        if 'curriculum' not in {r[1] for r in self.db.execute('PRAGMA table_info(problems)')}:
            self.db.execute('ALTER TABLE problems ADD COLUMN curriculum TEXT')
        self.db.execute('CREATE TABLE IF NOT EXISTS curriculum_settings(id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)')
        self.db.commit()
        self.session = uuid4().hex
    def curriculum_settings(self, value=None):
        from curriculum import DEFAULT, settings
        with self.lock, self.db:
            if value is not None:
                value=settings(value)
                self.db.execute('INSERT INTO curriculum_settings VALUES(1,?) ON CONFLICT(id) DO UPDATE SET value=excluded.value',(json.dumps(value),))
            row=self.db.execute('SELECT value FROM curriculum_settings WHERE id=1').fetchone()
            return settings(json.loads(row[0])) if row else dict(DEFAULT)
    def create(self, scene, curriculum=None):
        s = validate_scene(scene)
        result = s['a']+s['b'] if s['kind']=='add' else s['a']-s['b'] if s['kind']=='subtract' else s['a']
        with self.lock, self.db:
            cur = self.db.execute('INSERT INTO problems(session,scene,answer,created,curriculum) VALUES(?,?,?,?,?)', (self.session,json.dumps(s,sort_keys=True),result,utc(),json.dumps(curriculum,sort_keys=True) if curriculum else None))
            if cur.lastrowid > 2147483647: raise ValueError('Problem ID capacity reached')
            return cur.lastrowid
    def ingest(self, boot, event):
        if not isinstance(boot,str) or not 1<=len(boot)<=64: raise ValueError('Invalid boot ID')
        if type(event) is not dict or set(event)!={'problem','seq','ms','choice','type'}: raise ValueError('Invalid event')
        pid, seq, ms, choice, kind = (event[k] for k in ('problem','seq','ms','choice','type'))
        if any(type(x) is not int for x in (pid,seq,ms,choice)) or pid<=0 or not 1<=seq<=4294967295 or not 0<=ms<=4294967295: raise ValueError('Invalid counters')
        if kind not in ('attempt','correct','incorrect','revealed','skipped'): raise ValueError('Invalid event type')
        with self.lock, self.db:
            old = self.db.execute('SELECT * FROM events WHERE boot=? AND seq=?',(boot,seq)).fetchone()
            if old:
                if (old['problem'],old['type'],old['choice'],old['device_ms']) != (pid,kind,choice,ms): raise ValueError('Conflicting replay')
                return False
            p = self.db.execute('SELECT * FROM problems WHERE id=?',(pid,)).fetchone()
            if not p: raise ValueError('Unknown problem; cannot acknowledge')
            correct = None
            if kind=='attempt':
                if p['outcome']!='pending' or choice not in json.loads(p['scene'])['choices']: raise ValueError('Invalid attempt')
                correct = int(choice==p['answer'])
            else:
                if choice!=-1: raise ValueError('Final event cannot contain answer')
                if p['outcome']!='pending': raise ValueError('Problem already finalized')
                attempts = self.db.execute("SELECT correct FROM events WHERE problem=? AND type='attempt' ORDER BY rowid",(pid,)).fetchall()
                if kind=='correct' and (not attempts or attempts[-1]['correct']!=1): raise ValueError('Unproven correct completion')
                if kind=='incorrect' and (not attempts or any(a['correct'] for a in attempts)): raise ValueError('Unproven incorrect outcome')
                if kind=='skipped' and attempts: raise ValueError('Attempted problem is not skipped')
            self.db.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?,?)',(boot,seq,pid,kind,choice,correct,ms,utc()))
            if kind!='attempt':
                self.db.execute('UPDATE problems SET outcome=?,completed=? WHERE id=?',(kind,utc(),pid))
                config=self.db.execute('SELECT * FROM settings WHERE id=1').fetchone()
                if kind=='correct' and config['auto']:
                    self.db.execute('INSERT OR IGNORE INTO stars(problem,delta,reason,created) VALUES(?,?,?,?)',(pid,config['per_correct'],'Correct completion',utc()))
            return True
    def settings(self, auto, per_correct, reason):
        if type(auto) is not bool or type(per_correct) is not int or not 0<=per_correct<=5: raise ValueError('Invalid earning settings')
        self._reason(reason)
        with self.lock, self.db:
            self.db.execute('UPDATE settings SET auto=?,per_correct=? WHERE id=1',(auto,per_correct))
            self.db.execute('INSERT INTO settings_audit(auto,per_correct,reason,created) VALUES(?,?,?,?)',(auto,per_correct,reason,utc()))
    @staticmethod
    def _reason(reason):
        if type(reason) is not str or not 1<=len(reason.strip())<=160: raise ValueError('A short audit reason is required')
    def adjust(self, *, reason, delta=None, total=None):
        self._reason(reason)
        if (delta is None)==(total is None): raise ValueError('Choose delta or total')
        value=delta if delta is not None else total
        if type(value) is not int or abs(value)>100000: raise ValueError('Invalid star value')
        with self.lock, self.db:
            current=self.db.execute('SELECT COALESCE(SUM(delta),0) FROM stars').fetchone()[0]
            new=current+delta if delta is not None else total
            if not 0<=new<=100000: raise ValueError('Star total must be 0..100000')
            self.db.execute('INSERT INTO stars(delta,reason,created) VALUES(?,?,?)',(new-current,reason,utc()))
    def snapshot(self, limit=100, before=None):
        if type(limit) is not int or not 1<=limit<=100: raise ValueError('Invalid page size')
        if before is not None and (type(before) is not int or before<1): raise ValueError('Invalid cursor')
        with self.lock:
            rows=self.db.execute('SELECT * FROM problems WHERE id<? ORDER BY id DESC LIMIT ?', (before or 2147483648,limit+1)).fetchall()
            history=[]
            for row in rows[:limit]:
                item=dict(row);item['scene']=json.loads(item['scene'])
                item['curriculum']=json.loads(item['curriculum']) if item['curriculum'] else None
                item['attempts']=[dict(x) for x in self.db.execute("SELECT * FROM events WHERE problem=? AND type='attempt' ORDER BY rowid",(row['id'],))]
                history.append(item)
            return {'learner':'Unnamed learner','stars':self.db.execute('SELECT COALESCE(SUM(delta),0) FROM stars').fetchone()[0],
                    'settings':dict(self.db.execute('SELECT * FROM settings WHERE id=1').fetchone()),'history':history,
                    'next_before':history[-1]['id'] if len(rows)>limit else None,
                    'star_audit':[dict(x) for x in self.db.execute('SELECT * FROM stars ORDER BY id DESC LIMIT 100')],
                    'settings_audit':[dict(x) for x in self.db.execute('SELECT * FROM settings_audit ORDER BY id DESC LIMIT 100')],
                    'privacy':'Local laptop only; no child history sent to Hermes. Laptop access is parent-control access, not authentication.'}
    def close(self):
        with self.lock:self.db.close()
