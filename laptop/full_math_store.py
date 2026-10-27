"""Full curriculum quests, additive tables on the browser ledger only."""
import copy,json,random,re
from uuid import uuid4
import curriculum
from teaching_ledger import Ledger,utc
from adventure_store import Conflict,packed,request_key
from full_math_schema import load_bank

def display_title(topic):
 return re.sub(r'\s*\(ages?\b[^)]*\)', '', topic['name'],flags=re.I).strip()

class CurriculumQuests:
 def __init__(self,store,bank_path=None,require_complete=True):
  self.store=store;self.db=store.db;self.bank=load_bank(bank_path,complete=require_complete) if bank_path else load_bank()
  self.bank_encoded={tid:packed(lesson) for tid,lesson in self.bank.items()}
  with store._transaction():
   for sql in (
    'CREATE TABLE IF NOT EXISTS quest_runs(id TEXT PRIMARY KEY,topic TEXT NOT NULL,snapshot TEXT NOT NULL,cursor INTEGER NOT NULL DEFAULT 0,status TEXT NOT NULL,created TEXT NOT NULL)',
    'CREATE TABLE IF NOT EXISTS quest_problems(id TEXT PRIMARY KEY,run TEXT NOT NULL REFERENCES quest_runs(id),slot INTEGER NOT NULL,item TEXT NOT NULL,status TEXT NOT NULL,star INTEGER UNIQUE REFERENCES stars(id),created TEXT NOT NULL)',
    'CREATE TABLE IF NOT EXISTS quest_attempts(id INTEGER PRIMARY KEY,problem TEXT NOT NULL REFERENCES quest_problems(id),action TEXT NOT NULL,choice INTEGER,correct INTEGER,created TEXT NOT NULL)',
    'CREATE TABLE IF NOT EXISTS quest_current(id INTEGER PRIMARY KEY CHECK(id=1),run TEXT REFERENCES quest_runs(id),problem TEXT REFERENCES quest_problems(id))',
    'CREATE TABLE IF NOT EXISTS quest_requests(id TEXT PRIMARY KEY,payload TEXT NOT NULL,result TEXT NOT NULL)',
    'CREATE TABLE IF NOT EXISTS quest_completions(topic TEXT PRIMARY KEY,run TEXT NOT NULL,practice_at TEXT NOT NULL,activity_at TEXT,activity_reason TEXT)',
    'CREATE TABLE IF NOT EXISTS quest_activity_audit(id INTEGER PRIMARY KEY,topic TEXT NOT NULL,run TEXT NOT NULL UNIQUE REFERENCES quest_runs(id),snapshot TEXT NOT NULL,reason TEXT NOT NULL,created TEXT NOT NULL)',
   ):self.db.execute(sql)
   self.db.execute('INSERT OR IGNORE INTO quest_activity_audit(topic,run,snapshot,reason,created) SELECT c.topic,c.run,r.snapshot,c.activity_reason,c.activity_at FROM quest_completions c JOIN quest_runs r ON r.id=c.run WHERE c.activity_at IS NOT NULL')
 def _topic(self,tid):
  if type(tid) is not str or tid not in self.bank:raise ValueError('Unknown curriculum topic')
  return self.bank[tid]
 def _request(self,rid,payload,fn):
  request_key(rid);body=packed(payload)
  with self.store._transaction():
   old=self.db.execute('SELECT * FROM quest_requests WHERE id=?',(rid,)).fetchone()
   if old:
    if old['payload']!=body:raise Conflict('Request ID reused with different action')
    return json.loads(old['result'])
   fn();result=self._state();self.db.execute('INSERT INTO quest_requests VALUES(?,?,?)',(rid,body,packed(result)));return result
 def _current(self):
  pointer=self.db.execute('SELECT * FROM quest_current WHERE id=1').fetchone()
  if not pointer:return None,None
  return self.db.execute('SELECT * FROM quest_runs WHERE id=?',(pointer['run'],)).fetchone(),self.db.execute('SELECT * FROM quest_problems WHERE id=?',(pointer['problem'],)).fetchone() if pointer['problem'] else None
 def _new_problem(self,run,index,item):
  q=copy.deepcopy(item);indices=list(range(4));random.SystemRandom().shuffle(indices)
  q['choices']=[item['choices'][i] for i in indices];q['correct']=indices.index(item['correct'])
  pid=uuid4().hex
  self.db.execute('INSERT INTO quest_problems VALUES(?,?,?,?,?,?,?)',(pid,run,index,packed(q),'open',None,utc()))
  self.db.execute('INSERT INTO quest_current VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET run=excluded.run,problem=excluded.problem',(run,pid))
  self.db.execute('UPDATE quest_runs SET cursor=?,status=? WHERE id=?',(index,'playing',run))
 def _state(self):
  completions={r['topic']:dict(r) for r in self.db.execute('SELECT c.*,r.snapshot FROM quest_completions c JOIN quest_runs r ON r.id=c.run')}
  active=None;run,p=self._current()
  if run:
   lesson=json.loads(run['snapshot']);tid=run['topic'];topic=curriculum.TOPICS[tid]
   active={'id':run['id'],'topic_id':tid,'title':display_title(topic),'domain':topic['domain'],'index':run['cursor'],'total':3,'status':run['status'],'problem':None,'parent_activity':lesson.get('parent_activity')}
   if p:
    item=json.loads(p['item']);terminal=p['status']!='open'
    attempts=self.db.execute('SELECT correct FROM quest_attempts WHERE problem=? AND action=? ORDER BY id DESC LIMIT 1',(p['id'],'answer')).fetchone()
    active['problem']={'id':p['id'],'prompt':item['prompt'],'choices':item['choices'],'visual':item.get('visual'),'status':p['status'],'feedback':'incorrect' if not terminal and attempts and not attempts['correct'] else p['status'] if terminal else None,'correct':item['correct'] if p['status'] in ('correct','revealed') else None,'rationale':item['rationale'] if p['status'] in ('correct','revealed') else None}
  settings=self.db.execute('SELECT auto,per_correct FROM settings WHERE id=1').fetchone()
  progress={}
  for tid,row in completions.items():
   current=row['snapshot']==self.bank_encoded[tid]
   progress[tid]={'practice_complete':current,'complete':current and (not self.bank[tid].get('parent_activity') or bool(row['activity_at'])),'activity_verified':current and bool(row['activity_at']),'earlier_completion':not current}
  return {'active':active,'progress':progress,'stars':self.db.execute('SELECT COALESCE(SUM(delta),0) FROM stars').fetchone()[0],'settings':{'auto':bool(settings['auto']),'per_correct':settings['per_correct']},'topic_count':len(self.bank),'notice':'All progress stays on this Mac. Browser and robot histories are separate. Introductory practice is not a mastery assessment.'}
 def state(self):
  with self.store._transaction(False):return self._state()
 def catalog(self):
  domains={}
  for topic in curriculum.TOPICS.values():
   tid=topic['id']
   if tid not in self.bank:continue
   domain=topic['domain'];rows=domains.setdefault(domain,[])
   rows.append({'id':tid,'title':display_title(topic),'description':topic['description'],'level':len(rows)//8+1,'stage':len(rows)%8+1,'parent_check':bool(self.bank[tid].get('parent_activity'))})
  return {'domains':[{'name':d,'topics':rows} for d,rows in domains.items()],'topic_count':len(self.bank),'source_commit':curriculum.COMMIT,'limits':'Each topic has an introductory lesson, two practice checks and a boss check. Practical skills include a parent-observed task; quizzes alone do not certify the full skill.'}
 def lesson(self,topic_id):
  item=self._topic(topic_id);topic=curriculum.TOPICS[topic_id]
  return {'topic_id':topic_id,'title':display_title(topic),'domain':topic['domain'],'description':topic['description'],'explanation':item['explanation'],'worked_example':item['worked_example'],'coverage_note':item['coverage_note'],'parent_activity':item.get('parent_activity')}
 def start(self,topic_id,request_id,replay=False):
  lesson=self._topic(topic_id)
  if type(replay) is not bool:raise ValueError('Invalid replay flag')
  def op():
   old=self.db.execute('SELECT * FROM quest_runs WHERE topic=? ORDER BY rowid DESC LIMIT 1',(topic_id,)).fetchone()
   if old and old['snapshot']!=self.bank_encoded[topic_id]:old=None
   if old and old['status']!='complete':
    p=self.db.execute('SELECT id FROM quest_problems WHERE run=? ORDER BY rowid DESC LIMIT 1',(old['id'],)).fetchone()
    self.db.execute('INSERT INTO quest_current VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET run=excluded.run,problem=excluded.problem',(old['id'],p['id']));return
   if old and not replay:
    self.db.execute('INSERT INTO quest_current VALUES(1,?,NULL) ON CONFLICT(id) DO UPDATE SET run=excluded.run,problem=NULL',(old['id'],));return
   rid=uuid4().hex;self.db.execute('INSERT INTO quest_runs VALUES(?,?,?,?,?,?)',(rid,topic_id,packed(lesson),0,'playing',utc()));self._new_problem(rid,0,lesson['questions'][0])
  return self._request(request_id,{'action':'start','topic':topic_id,'replay':replay},op)
 def event(self,problem_id,action,choice,request_id):
  if type(problem_id) is not str or action not in ('answer','reveal','skip'):raise ValueError('Invalid problem action')
  if action=='answer' and (type(choice) is not int or not 0<=choice<4):raise ValueError('Choose a displayed option')
  if action!='answer' and choice is not None:raise ValueError('Help/skip cannot include a choice')
  def op():
   run,p=self._current()
   if not p or p['id']!=problem_id or p['status']!='open':raise Conflict('This problem is no longer open')
   item=json.loads(p['item']);correct=int(choice==item['correct']) if action=='answer' else None
   self.db.execute('INSERT INTO quest_attempts(problem,action,choice,correct,created) VALUES(?,?,?,?,?)',(problem_id,action,choice,correct,utc()))
   if action=='answer' and not correct:return
   status='correct' if action=='answer' else 'revealed' if action=='reveal' else 'skipped';star=None
   if status=='correct':
    settings=self.db.execute('SELECT auto,per_correct FROM settings WHERE id=1').fetchone()
    if settings['auto']:
     star=self.db.execute('INSERT INTO stars(delta,reason,created) VALUES(?,?,?)',(settings['per_correct'],'Curriculum correct: '+run['topic']+' / '+problem_id,utc())).lastrowid
   self.db.execute('UPDATE quest_problems SET status=?,star=? WHERE id=?',(status,star,problem_id));self.db.execute('UPDATE quest_runs SET status=? WHERE id=?',('feedback',run['id']))
  return self._request(request_id,{'action':action,'problem':problem_id,'choice':choice},op)
 def next(self,problem_id,request_id):
  def op():
   run,p=self._current()
   if not p or p['id']!=problem_id or p['status']=='open':raise Conflict('Finish the displayed problem first')
   lesson=json.loads(run['snapshot']);index=run['cursor']+(p['status']=='correct')
   if index<3:self._new_problem(run['id'],index,lesson['questions'][index])
   else:
    self.db.execute('UPDATE quest_runs SET status=? WHERE id=?',('complete',run['id']));self.db.execute('UPDATE quest_current SET problem=NULL WHERE id=1')
    old=self.db.execute('SELECT r.snapshot FROM quest_completions c JOIN quest_runs r ON r.id=c.run WHERE c.topic=?',(run['topic'],)).fetchone()
    if old and old['snapshot']!=run['snapshot']:
     self.db.execute('UPDATE quest_completions SET run=?,practice_at=?,activity_at=NULL,activity_reason=NULL WHERE topic=?',(run['id'],utc(),run['topic']))
    else:self.db.execute('INSERT OR IGNORE INTO quest_completions(topic,run,practice_at) VALUES(?,?,?)',(run['topic'],run['id'],utc()))
  return self._request(request_id,{'action':'next','problem':problem_id},op)
 def verify_activity(self,topic_id,checks,reason,request_id):
  lesson=self._topic(topic_id);activity=lesson.get('parent_activity');Ledger._reason(reason)
  if not activity or type(checks) is not list or len(checks)!=len(activity['checklist']) or any(v is not True for v in checks):raise ValueError('A parent must observe every checklist item')
  def op():
   row=self.db.execute('SELECT c.*,r.snapshot FROM quest_completions c JOIN quest_runs r ON r.id=c.run WHERE c.topic=?',(topic_id,)).fetchone()
   if not row:raise Conflict('Finish the digital practice before verifying the activity')
   if row['snapshot']!=self.bank_encoded[topic_id]:raise Conflict('This lesson changed. Complete the updated practice before observing its activity')
   if row['activity_at']:return
   stamp=utc()
   self.db.execute('INSERT INTO quest_activity_audit(topic,run,snapshot,reason,created) VALUES(?,?,?,?,?)',(topic_id,row['run'],row['snapshot'],reason,stamp))
   self.db.execute('UPDATE quest_completions SET activity_at=?,activity_reason=? WHERE topic=?',(stamp,reason,topic_id))
  return self._request(request_id,{'action':'verify','topic':topic_id,'checks':checks,'reason':reason},op)
 def history(self,before=None):
  if before is not None and (type(before) is not int or before<1):raise ValueError('Invalid history cursor')
  with self.store._transaction(False):
   rows=self.db.execute("SELECT a.*,r.topic,p.slot,p.status AS current_problem_status,CASE WHEN a.action='answer' THEN CASE WHEN a.correct=1 THEN 'correct' ELSE 'incorrect' END ELSE a.action END AS outcome FROM quest_attempts a JOIN quest_problems p ON p.id=a.problem JOIN quest_runs r ON r.id=p.run WHERE a.id<? ORDER BY a.id DESC LIMIT 26",(before or 9223372036854775807,)).fetchall()
   audit=[{'topic':r['topic'],'run':r['run'],'activity_at':r['created'],'activity_reason':r['reason'],'activity':json.loads(r['snapshot']).get('parent_activity')} for r in self.db.execute('SELECT * FROM quest_activity_audit ORDER BY id DESC LIMIT 100')]
   return {'history':[dict(r) for r in rows[:25]],'next_before':rows[24]['id'] if len(rows)>25 else None,'activity_audit':audit}
