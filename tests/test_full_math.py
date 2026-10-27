import json,tempfile,unittest,uuid,threading,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'laptop'))
from adventure_store import AdventureStore,Conflict
from full_math_store import CurriculumQuests
from full_math_schema import load_bank,evaluate
BANK=R/'laptop/full_math_lessons.json'
TESTDIR=R/'test-data'
TESTDIR.mkdir(exist_ok=True)
def uid():return uuid.uuid4().hex
class QuestsTest(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=TESTDIR);self.path=Path(self.temp.name)/'test.sqlite3';self.store=AdventureStore(self.path);self.q=CurriculumQuests(self.store,BANK,False)
 def tearDown(self):self.store.close();self.temp.cleanup()
 def answer(self):
  s=self.q.state();p=s['active']['problem'];row=self.store.db.execute('SELECT item FROM quest_problems WHERE id=?',(p['id'],)).fetchone();key=json.loads(row[0])['correct'];return self.q.event(p['id'],'answer',key,uid())
 def finish(self,tid):
  self.q.start(tid,uid())
  for _ in range(3):
   s=self.answer();s=self.q.next(s['active']['problem']['id'],uid())
  return s
 def test_every_staged_topic(self):
  for tid in self.q.bank:
   s=self.finish(tid);self.assertEqual(s['active']['status'],'complete');self.assertTrue(s['progress'][tid]['practice_complete'])
   if not self.q.bank[tid]['parent_activity']:self.assertTrue(s['progress'][tid]['complete'])
  self.assertEqual(s['stars'],3*len(self.q.bank))
 def test_wrong_reveal_replay_replacement_restart(self):
  tid=next(iter(self.q.bank));s=self.q.start(tid,uid());p=s['active']['problem'];row=json.loads(self.store.db.execute('SELECT item FROM quest_problems WHERE id=?',(p['id'],)).fetchone()[0]);wrong=(row['correct']+1)%4
  rid=uid();a=self.q.event(p['id'],'answer',wrong,rid);self.assertEqual(a,self.q.event(p['id'],'answer',wrong,rid));self.assertEqual(a['stars'],0)
  with self.assertRaises(Conflict):self.q.event(p['id'],'answer',row['correct'],rid)
  self.q.event(p['id'],'reveal',None,uid())
  with self.assertRaises(Conflict):self.q.event(p['id'],'answer',row['correct'],uid())
  s=self.q.next(p['id'],uid());self.assertNotEqual(s['active']['problem']['id'],p['id']);self.assertEqual(s['active']['index'],0)
  self.store.close();self.store=AdventureStore(self.path);self.q=CurriculumQuests(self.store,BANK,False);self.assertEqual(s,self.q.state())
 def test_pause_switch_and_stale_events(self):
  ts=list(self.q.bank);a=self.q.start(ts[0],uid());b=self.q.start(ts[1],uid())
  with self.assertRaises(Conflict):self.q.event(a['active']['problem']['id'],'skip',None,uid())
  c=self.q.start(ts[0],uid());self.assertEqual(c['active'],a['active'])
 def test_parent_observation_required(self):
  ids=[tid for tid,row in self.q.bank.items() if row['parent_activity']]
  self.assertTrue(ids)
  tid=ids[0];activity=self.q.bank[tid]['parent_activity'];s=self.finish(tid);self.assertFalse(s['progress'][tid]['complete']);stars=s['stars']
  with self.assertRaises(ValueError):self.q.verify_activity(tid,[False]*len(activity['checklist']),'test',uid())
  s=self.q.verify_activity(tid,[True]*len(activity['checklist']),'Observed using isolated test fixture',uid());self.assertTrue(s['progress'][tid]['complete']);self.assertEqual(s['stars'],stars)
 def test_untrusted_inputs_and_no_public_keys(self):
  s=self.q.start(next(iter(self.q.bank)),uid());p=s['active']['problem'];self.assertIsNone(p['correct']);self.assertIsNone(p['rationale'])
  for value in (True,1.0,'1',4,-1):
   with self.assertRaises(ValueError):self.q.event(p['id'],'answer',value,uid())
  with self.assertRaises(ValueError):self.q.start('unknown',uid())
  self.assertNotIn('questions',self.q.lesson(s['active']['topic_id']))
 def test_earning_and_starter_preserved(self):
  self.store.adjust(delta=5,reason='isolated existing balance');self.store.earning(False,1,'isolated earning policy');tid=next(iter(self.q.bank));s=self.finish(tid);self.assertEqual(s['stars'],5)
  self.assertIsNone(self.store.state()['active']);self.assertEqual(self.store.state()['stars'],5)
 def test_versioned_observation_and_immutable_audit(self):
  tid=next(t for t,x in self.q.bank.items() if x['parent_activity']);self.finish(tid);count=len(self.q.bank[tid]['parent_activity']['checklist']);self.q.verify_activity(tid,[True]*count,'first observed version',uid())
  data=json.loads(BANK.read_text());row=next(x for x in data['lessons'] if x['topic_id']==tid);row['parent_activity']['checklist'].append('Test fixture: newly required observed criterion');changed=Path(self.temp.name)/'changed.json';changed.write_text(json.dumps(data))
  self.q=CurriculumQuests(self.store,changed,False);p=self.q.state()['progress'][tid];self.assertFalse(p['complete']);self.assertTrue(p['earlier_completion'])
  with self.assertRaises(Conflict):self.q.verify_activity(tid,[True]*(count+1),'must not certify new version',uid())
  self.finish(tid);self.q.verify_activity(tid,[True]*(count+1),'second observed version',uid());self.assertTrue(self.q.state()['progress'][tid]['complete']);audit=self.q.history()['activity_audit'];self.assertEqual(len(audit),2);self.assertNotEqual(audit[0]['activity'],audit[1]['activity']);self.assertEqual(self.q.state()['stars'],6)
 def test_concurrent_reward_and_atomic_rollback(self):
  import concurrent.futures,sqlite3
  tid=next(iter(self.q.bank));s=self.q.start(tid,uid());p=s['active']['problem'];key=json.loads(self.store.db.execute('SELECT item FROM quest_problems WHERE id=?',(p['id'],)).fetchone()[0])['correct']
  self.store.db.execute("CREATE TRIGGER rejectquest BEFORE UPDATE OF status ON quest_problems WHEN NEW.status='correct' BEGIN SELECT RAISE(ABORT,'test rollback'); END")
  with self.assertRaises(sqlite3.IntegrityError):self.q.event(p['id'],'answer',key,uid())
  self.assertEqual(self.q.state()['stars'],0);self.assertEqual(len(self.q.history()['history']),0);self.store.db.execute('DROP TRIGGER rejectquest');barrier=threading.Barrier(2)
  def attempt(_):
   barrier.wait()
   try:self.q.event(p['id'],'answer',key,uid());return 'saved'
   except Conflict:return 'conflict'
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,range(2)))
  self.assertCountEqual(results,['saved','conflict']);self.assertEqual(self.q.state()['stars'],1)
 def test_history_outcomes_and_pagination(self):
  tid=next(iter(self.q.bank));s=self.q.start(tid,uid());p=s['active']['problem'];key=json.loads(self.store.db.execute('SELECT item FROM quest_problems WHERE id=?',(p['id'],)).fetchone()[0])['correct']
  for _ in range(30):self.q.event(p['id'],'answer',(key+1)%4,uid())
  self.answer();first=self.q.history();second=self.q.history(first['next_before']);rows=first['history']+second['history'];self.assertEqual(len(rows),31);self.assertEqual(len({r['id'] for r in rows}),31);self.assertEqual(rows[-1]['outcome'],'incorrect');self.assertEqual(rows[-1]['current_problem_status'],'correct')
 def test_numeric_equivalence_and_strict_large_answers(self):
  from full_math_schema import numeric_choice,same_number,validate_lesson
  self.assertEqual(numeric_choice('45 minutes'),45);self.assertEqual(numeric_choice('1/2'),evaluate('0.5'));self.assertFalse(same_number(evaluate('1000000000000'),evaluate('999999999999')))
  item=json.loads(json.dumps(next(iter(self.q.bank.values()))));item['questions'][0]['choices']=['same']*4
  with self.assertRaises(ValueError):validate_lesson(item)
 def test_chart_bounds_and_rational_resource_limit(self):
  from full_math_schema import validate_chart
  chart={'type':'plot','title':'Test only','alt':'Test line','x_label':'x','y_label':'y','x_min':0,'x_max':2,'y_min':0,'y_max':2,'x_step':1,'y_step':1,'series':[{'label':'Line','connect':True,'points':[[0,0],[2,2]]}]}
  validate_chart(chart)
  for field,value in (('x_step',0),('y_step',0.001),('x_max',float('nan'))):
   bad=json.loads(json.dumps(chart));bad[field]=value
   with self.assertRaises(ValueError):validate_chart(bad)
  bad=json.loads(json.dumps(chart));bad['series'][0]['points'][1]=[3,3]
  with self.assertRaises(ValueError):validate_chart(bad)
  expr='1/10'
  for _ in range(4):expr='('+expr+')**12'
  with self.assertRaises(ValueError):evaluate(expr)
 def test_arithmetic_no_eval(self):
  self.assertEqual(evaluate('1/3+2/3'),1)
  for x in ('__import__("os")','2**999','a+1','[1]'):
   with self.assertRaises((ValueError,SyntaxError)):evaluate(x)
if __name__=='__main__':unittest.main()
