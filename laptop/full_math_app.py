"""Install full-curriculum browser routes on the existing secured app."""
import json
from pathlib import Path
from fastapi import Request
from fastapi.responses import FileResponse,JSONResponse
from starlette.concurrency import run_in_threadpool
from full_math_store import CurriculumQuests
ROOT=Path(__file__).parent

def install(app,store,bank_path=None,require_complete=True):
 service=CurriculumQuests(store,bank_path,require_complete);app.state.quests=service
 @app.get('/curriculum')
 def page():return FileResponse(ROOT/'full_math.html',media_type='text/html')
 @app.get('/full_math.js')
 def js():return FileResponse(ROOT/'full_math.js',media_type='text/javascript')
 @app.get('/full_math_visual.js')
 def charts():return FileResponse(ROOT/'full_math_visual.js',media_type='text/javascript')
 @app.get('/full_math.css')
 def css():return FileResponse(ROOT/'full_math.css',media_type='text/css')
 @app.get('/api/quests/catalog')
 def catalog():return service.catalog()
 @app.get('/api/quests/state')
 def state():return service.state()
 @app.get('/api/quests/lesson/{topic_id}')
 def lesson(topic_id:str):return service.lesson(topic_id)
 @app.get('/api/quests/history')
 def history(request:Request):
  v=request.query_params.get('before')
  if v is not None and (not v.isascii() or not v.isdecimal() or len(v)>18):raise ValueError('Invalid cursor')
  return service.history(int(v) if v else None)
 operations={'start':(service.start,{'topic_id','request_id'},{'replay'}),'event':(service.event,{'problem_id','action','choice','request_id'},set()),'next':(service.next,{'problem_id','request_id'},set()),'verify':(service.verify_activity,{'topic_id','checks','reason','request_id'},set())}
 @app.post('/api/quests/{operation}')
 async def mutate(operation:str,request:Request):
  if operation not in operations:return JSONResponse({'detail':'Unknown quest action'},status_code=404)
  from adventure_app import _object
  raw=bytearray()
  async for part in request.stream():
   raw.extend(part)
   if len(raw)>16384:raise ValueError('Request too large')
  def reject_constant(value):raise ValueError('Non-finite JSON number')
  try:data=json.loads(raw,object_pairs_hook=_object,parse_constant=reject_constant)
  except (ValueError,UnicodeError,RecursionError):raise ValueError('Invalid JSON')
  fn,required,optional=operations[operation]
  if type(data) is not dict or not required<=data.keys() or not data.keys()<=required|optional:raise ValueError('Exact supported fields required')
  return await run_in_threadpool(fn,**data)
 return service
