import json,subprocess,time,urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
R=Path(__file__).resolve().parents[1];O=R/'test-data';O.mkdir(exist_ok=True)
log=(O/'public-server.log').open('w');proc=subprocess.Popen(['python3','-m','http.server','8778','--bind','127.0.0.1','--directory',str(R/'docs')],stdout=log,stderr=subprocess.STDOUT);base='http://127.0.0.1:8778/'
try:
 for _ in range(100):
  try:urllib.request.urlopen(base);break
  except OSError:time.sleep(.1)
 with sync_playwright() as pw:
  b=pw.chromium.launch();c=b.new_context();p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)));p.goto(base);p.get_by_text('576 topics · 12 worlds',exact=True).wait_for()
  result=p.evaluate('''async()=>{
   const api=window.MathsPublic.api,body=x=>({...x,request_id:crypto.randomUUID()}),rows=(await (await fetch('./lessons.json')).json()).lessons;
   let count=0,observations=0;
   for(const l of rows){let s=await api('/api/quests/start',body({topic_id:l.topic_id}));
    for(let i=0;i<3;i++){const p=s.active.problem,a=body({problem_id:p.id,action:'answer',choice:p.choices.indexOf(l.questions[i].choices[l.questions[i].correct])});s=await api('/api/quests/event',a);let replay=await api('/api/quests/event',a);if(replay.stars!==s.stars)throw Error('Duplicate reward');s=await api('/api/quests/next',body({problem_id:p.id}));}
    if(!s.progress[l.topic_id].practice_complete)throw Error('Practice incomplete');
    if(l.parent_activity){s=await api('/api/quests/verify',body({topic_id:l.topic_id,checks:l.parent_activity.checklist.map(()=>true),reason:'Synthetic isolated test, not a real observation'}));observations++;}
    if(!s.progress[l.topic_id].complete)throw Error('Stage incomplete');count++;
   }
   const s=await api('/api/quests/state');if(s.stars!==rows.length*3)throw Error('Incorrect reward total');return {topics:count,questions:count*3,parent_checks:observations,stars:s.stars};
  }''');p.reload();p.get_by_text('576 stages completed',exact=True).wait_for();assert result['topics']==576
  c.close();c=b.new_context(viewport={'width':375,'height':812});p=c.new_page();p.on('pageerror',lambda e:errors.append(str(e)));p.goto(base);p.get_by_text('576 topics · 12 worlds',exact=True).wait_for();assert p.locator('#stars').inner_text()=='0'
  tid='mt_iEXqN48w3x';bank=json.loads((R/'docs/lessons.json').read_text());lesson=next(l for l in bank['lessons'] if l['topic_id']==tid);p.locator('#search').fill('Percentages');p.locator(f'[data-topic="{tid}"] button').click();p.locator('#start').click();p.locator('#choices button:enabled').first.wait_for()
  def state():return p.evaluate("window.MathsPublic.api('/api/quests/state')")
  s=state();correct=s['active']['problem']['choices'].index(lesson['questions'][0]['choices'][lesson['questions'][0]['correct']]);p.locator('#choices button').nth((correct+1)%4).click();expect(p.locator('#feedback')).to_contain_text('Not quite');assert state()['stars']==0
  old=state()['active']['problem']['id'];p.reload();p.locator('#resume-button').click();assert state()['active']['problem']['id']==old
  p.on('dialog',lambda d:d.accept());p.locator('#help').click();p.locator('#next').click();p.locator('#choices button:enabled').first.wait_for();assert state()['active']['problem']['id']!=old and state()['stars']==0
  for i in range(3):
   s=state();correct=s['active']['problem']['choices'].index(lesson['questions'][i]['choices'][lesson['questions'][i]['correct']]);p.locator('#choices button:enabled').nth(correct).click();p.locator('#next').click();
   if i<2:p.locator('#choices button:enabled').first.wait_for()
  expect(p.locator('#complete-title')).to_have_text('Stage complete!');assert state()['stars']==3;p.screenshot(path=str(O/'public-mobile-complete.png'),full_page=True);assert p.evaluate('document.body.scrollWidth<=innerWidth');p.reload();p.locator('#resume-button').click();expect(p.locator('#complete-title')).to_have_text('Stage complete!')
  p.locator('#parent').click();p.locator('#delta').fill('2');p.locator('#adjust-reason').fill('Isolated audit test');p.locator('#adjust-form button').click();expect(p.locator('#stars')).to_have_text('5');p.locator('#history-refresh').click();expect(p.locator('#control-audit')).to_contain_text('Isolated audit test');assert not errors,errors
  preserved=p.evaluate("""async()=>{const api=window.MathsPublic.api;const s=await api('/api/quests/start',{topic_id:'mt_iEXqN48w3x',replay:true,request_id:crypto.randomUUID()});return s.progress['mt_iEXqN48w3x'].complete;}""");assert preserved
  result.update(replay_preserves_badge=preserved,browser_errors=errors,reload_persistence=True,isolated_visitors=True,wrong_retry=True,reveal_no_reward=True,mobile_no_overflow=True,parent_audit=True);(O/'public-results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));b.close()
finally:proc.terminate();proc.wait(timeout=10);log.close()
