"""End-to-end visual learning acceptance; isolated browser, no real learner data."""
import functools, json, threading, unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'test-data'/'visual-acceptance'
class Quiet(SimpleHTTPRequestHandler):
 def log_message(self,format,*args): pass

def run():
 OUT.mkdir(parents=True,exist_ok=True)
 server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT/'docs')))
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 result={};errors=[]
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch();context=browser.new_context(viewport={'width':1280,'height':900},reduced_motion='reduce');page=context.new_page()
   page.on('pageerror',lambda e:errors.append(str(e)))
   page.on('console',lambda msg:errors.append(msg.text) if msg.type=='error' else None)
   page.goto(f'http://127.0.0.1:{server.server_port}/');page.locator('#discoveries button').first.wait_for()
   assert page.locator('#library').is_hidden()
   discoveries=page.evaluate('window.MathsPlay.discoveries')
   assert len(discoveries)>=6 and len({d['id'] for d in discoveries})==len(discoveries)
   bank={l['topic_id']:l for l in json.loads((ROOT/'docs/lessons.json').read_text())['lessons']}
   assert all(d['id'] in bank for d in discoveries)
   page.screenshot(path=str(OUT/'home-desktop.png'),full_page=True)
   def state():return page.evaluate("window.MathsPublic.api('/api/quests/state')")
   def history():return page.evaluate("window.MathsPublic.api('/api/quests/history')")
   def no_overflow():assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'horizontal overflow'
   interaction=[]
   for i,d in enumerate(discoveries):
    page.locator(f'#discoveries [data-topic="{d["id"]}"]').click()
    host=page.locator('#lesson-playground');expect(host.locator('.mp-root')).to_be_visible()
    assert page.locator('#explanation').is_hidden()
    assert page.locator('#example-answer').is_hidden()
    before=state();oldhistory=history()
    initial=host.inner_text()
    actions=host.locator('button:not(:disabled)').filter(has_not=page.locator('.never'))
    action=host.locator('button:not(:disabled):not([data-mp-key="reset"]):not([data-mp-key="undo"]):not([data-mp-key="back"])').first
    action.focus();page.keyboard.press('Enter')
    assert host.inner_text()!=initial, d['id']+' interaction produced no text change'
    assert state()==before and history()==oldhistory, 'ungraded play mutated progress/history'
    host.get_by_role('button',name='Reset',exact=True).click()
    # Reset may use a different encouragement message but must restore controls.
    for width in (320,390,1280):
     page.set_viewport_size({'width':width,'height':844});no_overflow()
    page.screenshot(path=str(OUT/f'lesson-{i+1}.png'),full_page=True)
    if i==0:
     page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(OUT/'lesson-mobile.png'),full_page=True)
    page.locator('#start').click();page.locator('#choices button:enabled').first.wait_for()
    # First wrong answer is harmless; same exact question resumes after reload.
    if i==0:
     s=state();q=s['active']['problem'];correct=q['choices'].index(bank[d['id']]['questions'][0]['choices'][bank[d['id']]['questions'][0]['correct']]);page.locator('#choices button').nth((correct+1)%4).click();expect(page.locator('#feedback')).to_contain_text('Not quite')
     assert state()['stars']==before['stars'];old=q['id'];page.reload();page.locator('#resume-button').click();assert state()['active']['problem']['id']==old
    for slot in range(3):
     s=state();q=s['active']['problem'];answer=bank[d['id']]['questions'][slot];correct=q['choices'].index(answer['choices'][answer['correct']])
     page.locator('#choices button:enabled').nth(correct).click();page.locator('#next').click()
     if slot<2:page.locator('#choices button:enabled').first.wait_for()
    s=state();assert s['progress'][d['id']]['practice_complete']
    if bank[d['id']]['parent_activity']:
     assert not s['progress'][d['id']]['complete'],'parent check silently passed'
     assert page.locator('#verify-section').is_visible()
    else:assert s['progress'][d['id']]['complete']
    interaction.append({'id':d['id'],'lesson_interaction':True,'ungraded_state_unchanged':True,'three_question_ui_completed':True})
    page.locator('#complete-map').click()
   page.set_viewport_size({'width':390,'height':844});page.locator('#browse-library').click()
   expect(page.locator('#library')).to_be_visible();assert page.locator('#browse-library').get_attribute('aria-expanded')=='true'
   ids=[]
   while True:
    ids+=page.locator('#topics [data-topic]').evaluate_all('(xs)=>xs.map(x=>x.dataset.topic)')
    if page.locator('#more').is_disabled():break
    page.locator('#more').click()
   assert len(ids)==len(set(ids))==576
   fallback=next(tid for tid in ids if tid not in {d['id'] for d in discoveries})
   title=page.evaluate('''async tid=>{const c=await MathsPublic.api('/api/quests/catalog');return c.domains.flatMap(d=>d.topics).find(t=>t.id===tid).title;}''',fallback)
   page.locator('#search').fill(title);page.locator(f'#topics [data-topic="{fallback}"] button').click()
   host=page.locator('#lesson-playground');expect(host.locator('.mp-step')).to_be_visible();initial=host.inner_text()
   host.get_by_role('button',name='Next',exact=False).click();assert host.inner_text()!=initial
   assert page.locator('#example-answer').is_hidden()
   page.locator('#lesson-back').click()
   result.update(discoveries=interaction,library_unique_topics=len(ids),fallback_stepwise=True,page_errors=errors,stars=state()['stars'])
   assert not errors,errors
   context.close();browser.close()
 finally:server.shutdown();server.server_close();thread.join(timeout=5)
 (OUT/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':run()
