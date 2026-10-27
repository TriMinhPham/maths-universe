"""Build the self-contained public edition for GitHub Pages; no private inputs."""
from pathlib import Path
import sys,json,shutil,hashlib
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R/'laptop'))
import curriculum
from full_math_schema import load_bank
from full_math_store import display_title
bank=load_bank(R/'laptop/full_math_lessons.json',complete=True);D=R/'docs';D.mkdir(exist_ok=True)
domains={}
for tid,t in curriculum.TOPICS.items():
 rows=domains.setdefault(t['domain'],[]);rows.append({'id':tid,'title':display_title(t),'description':t['description'],'level':len(rows)//8+1,'stage':len(rows)%8+1,'parent_check':bool(bank[tid]['parent_activity']),'version':hashlib.sha256(json.dumps(bank[tid],sort_keys=True).encode()).hexdigest()})
(D/'catalog.json').write_text(json.dumps({'topic_count':len(bank),'domains':[{'name':name,'topics':rows} for name,rows in domains.items()],'source_commit':curriculum.COMMIT},ensure_ascii=False))
shutil.copy2(R/'laptop/full_math_lessons.json',D/'lessons.json')
for name in ['adventure.css','full_math.css','full_math_visual.js']:shutil.copy2(R/'laptop'/name,D/name)
shutil.copy2(R/'public_runtime.js',D/'public_runtime.js')
js=(R/'laptop/full_math.js').read_text().replace("async function api(path,body){","async function api(path,body){if(window.MathsPublic)return window.MathsPublic.api(path,body);").replace('quest-pending','maths-universe-public-pending')
js=js.replace('before=h.next_before;',"if(reset&&h.control_audit){$('control-audit').replaceChildren(...h.control_audit.map(a=>el('li',`${a.type}: ${a.delta??JSON.stringify({auto:a.auto,per_correct:a.per_correct})} — ${a.reason} · ${new Date(a.at).toLocaleString()}`)));}before=h.next_before;")
(D/'full_math.js').write_text(js)
html=(R/'laptop/full_math.html').read_text()
for name in ['adventure.css','full_math.css','full_math_visual.js','full_math.js']:html=html.replace('/'+name,'./'+name)
html=html.replace('<script src="./full_math.js"','<script src="./public_runtime.js" defer></script><script src="./full_math.js"')
html=html.replace('href="/curriculum"','href="./"').replace('href="/starter"','href="https://github.com/TriMinhPham/maths-universe"').replace('Starter adventure</a>','Source & local edition</a>').replace('Original starter adventure & full star audit →','Download local edition & starter adventure →').replace('href="/licenses/','href="./licenses/')
html=html.replace('These local controls are not password-protected. Observe practical tasks before confirming them. Browser progress is separate from robot history.','These controls affect only this browser and are not password-protected. No progress is sent to a server. Observe practical tasks before confirming them. This browser does not sync with the Mac app or other devices.')
html=html.replace('<h3>Curriculum attempts</h3>','<h3>Device control audit</h3><ol id="control-audit"></ol><h3>Curriculum attempts</h3>')
(D/'index.html').write_text(html);(D/'.nojekyll').write_text('')
(D/'licenses').mkdir(exist_ok=True)
for name in ['LICENSE','LICENSE-CONTENT','NOTICE.md','PROVENANCE.md']:shutil.copy2(R/'laptop/vendor/os-taxonomy'/name,D/'licenses'/name)
print(json.dumps({'built_topics':len(bank),'questions':sum(len(l['questions']) for l in bank.values()),'output':str(D)}))
