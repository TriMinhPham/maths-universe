"""Schema and numerical validation for authored curriculum lessons. No eval."""
import ast,json,math,operator,re
from fractions import Fraction
from pathlib import Path
import curriculum
BANK=Path(__file__).with_name('full_math_lessons.json')
def evaluate(expr):
 if type(expr) is not str or not 1<=len(expr)<=180 or not re.fullmatch(r'[0-9.()+*/\s-]+',expr):raise ValueError('Invalid bounded arithmetic expression')
 tree=ast.parse(expr,mode='eval');nodes=list(ast.walk(tree))
 if len(nodes)>60:raise ValueError('Expression too complex')
 def walk(n):
  if isinstance(n,ast.Constant) and type(n.value) in (int,float):
   if abs(n.value)>10**12:raise ValueError('Number too large')
   return Fraction(str(n.value))
  if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):return walk(n.operand)*(1 if isinstance(n.op,ast.UAdd) else -1)
  if isinstance(n,ast.BinOp):
   a,b=walk(n.left),walk(n.right)
   if isinstance(n.op,ast.Pow):
    if abs(b)>12 or abs(a)>10**8:raise ValueError('Power out of bounds')
    if b.denominator==1:r=a**int(b)
    elif b==Fraction(1,2) and a>=0:r=math.sqrt(a)
    else:raise ValueError('Only integer powers and square roots supported')
   elif isinstance(n.op,(ast.Add,ast.Sub,ast.Mult,ast.Div)):
    r={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv}[type(n.op)](a,b)
   else:raise ValueError('Unsupported operation')
   if isinstance(r,Fraction) and max(r.numerator.bit_length(),r.denominator.bit_length())>8192:raise ValueError('Rational representation too large')
   if abs(r)>10**18:raise ValueError('Result too large')
   return r
  raise ValueError('Unsupported arithmetic syntax')
 return walk(tree.body)
def text(x,maximum=4000):
 if type(x) is not str or not x.strip() or len(x)>maximum:raise ValueError('Invalid lesson text')
 return x

def numeric_choice(value):
 """Read arithmetic-only choices or a number with a conventional unit.
 Units remain semantic-review responsibilities; this verifies magnitude only.
 """
 value=value.replace('−','-')
 if re.fullmatch(r'[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?',value):return evaluate(value.replace(',',''))
 try:return evaluate(value)
 except (ValueError,SyntaxError):pass
 match=re.fullmatch(r'\s*[$£€¥]?\s*([+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:/\d+)?)\s*(?:%|°|degrees?|minutes?|hours?|seconds?|cm[²³]?|mm[²³]?|km[²³]?|m[²³]?|kg|g|ml|mL|L|litres?|liters?|pence|cents?|dollars?|pounds?)?\s*',value)
 if not match:raise ValueError('Choice is not a checked numeric magnitude')
 return evaluate(match.group(1))

def same_number(a,b):
 if isinstance(a,Fraction) and isinstance(b,Fraction):return a==b
 return math.isclose(float(a),float(b),rel_tol=0,abs_tol=1e-9)

def require(condition,message):
 if not condition:raise ValueError(message)

def validate_chart(v):
 require(type(v) is dict and v.get('type') in ('plot','bars','comparison'),'Invalid chart type')
 if v['type']=='comparison':
  text(v['title'],60);text(v['alt'],300);require(v['orientation'] in ('horizontal','vertical'),'Invalid comparison direction');require(type(v['items']) is list and 2<=len(v['items'])<=3,'Invalid comparison items')
  for item in v['items']:
   text(item['label'],5);require(type(item['units']) in (int,float) and math.isfinite(item['units']) and 0<item['units']<=12,'Invalid comparison size')
  return
 for key in ('title','alt','x_label','y_label'):text(v[key],300)
 def number(x):require(type(x) in (int,float) and math.isfinite(x) and abs(x)<=1e6,'Invalid chart number')
 ymin=v['y_min'] if v['type']=='plot' else 0
 for x in (ymin,v['y_max'],v['y_step']):number(x)
 require(v['y_max']>ymin and v['y_step']>0 and (v['y_max']-ymin)/v['y_step']<=20,'Invalid y scale')
 require(type(v['series']) is list and 1<=len(v['series'])<=4,'Invalid chart series')
 if v['type']=='plot':
  for key in ('x_min','x_max','x_step'):number(v[key])
  require(v['x_max']>v['x_min'] and v['x_step']>0 and (v['x_max']-v['x_min'])/v['x_step']<=20,'Invalid x scale')
 else:
  require(type(v['categories']) is list and 1<=len(v['categories'])<=12,'Invalid bar categories')
  for c in v['categories']:text(c,30)
 for series in v['series']:
  require(type(series) is dict,'Invalid series');text(series['label'],30)
  if v['type']=='plot':
   require(type(series['connect']) is bool and type(series['points']) is list and 1<=len(series['points'])<=200,'Invalid plot points')
   for point in series['points']:
    require(type(point) is list and len(point)==2,'Invalid point');number(point[0]);number(point[1]);require(v['x_min']<=point[0]<=v['x_max'] and ymin<=point[1]<=v['y_max'],'Point outside chart')
  else:
   require(type(series['values']) is list and len(series['values'])==len(v['categories']),'Invalid bar values')
   for value in series['values']:number(value);require(0<=value<=v['y_max'],'Bar outside chart')

def validate_lesson(item):
 require(type(item) is dict and item.get('topic_id') in curriculum.TOPICS,'Unknown topic')
 text(item['explanation']);text(item['coverage_note'])
 ex=item['worked_example'];require(type(ex) is dict,'Invalid worked example');text(ex['prompt']);text(ex['answer'])
 require(type(ex['steps']) is list and 2<=len(ex['steps'])<=8,'Worked example needs 2–8 steps')
 for s in ex['steps']:text(s)
 qs=item['questions'];require(type(qs) is list and len(qs)==3,'Exactly three questions required')
 for q in qs:
  require(type(q) is dict,'Invalid question');text(q['prompt']);text(q['rationale']);choices=q['choices']
  require(type(choices) is list and len(choices)==4,'Four choices required')
  for c in choices:text(c,1000)
  require(len(set(c.strip().casefold() for c in choices))==4,'Duplicate choices')
  require(type(q['correct']) is int and 0<=q['correct']<4,'Invalid correct index')
  check=q.get('check')
  if check is not None:
   require(type(check) is dict,'Invalid numeric check');expected=evaluate(check.get('expression'));actual=evaluate(check.get('answer'))
   require(same_number(numeric_choice(choices[q['correct']]),actual),'Numeric check does not match the keyed choice')
   require(same_number(expected,actual),f'Incorrect numeric key: {check}')
  visual=q.get('visual')
  if visual is not None and isinstance(visual,dict) and visual.get('type') in ('plot','bars','comparison'):validate_chart(visual)
  elif visual is not None:
   require(type(visual) is dict and visual.get('type')=='table','Invalid visual')
   require(type(visual['headers']) is list and 1<=len(visual['headers'])<=8,'Invalid table headers')
   require(type(visual['rows']) is list and 1<=len(visual['rows'])<=20,'Invalid table rows')
   for h in visual['headers']:text(h,200)
   for row in visual['rows']:
    require(type(row) is list and len(row)==len(visual['headers']),'Invalid table row')
    for cell in row:text(cell,300)
 activity=item.get('parent_activity')
 if activity is not None:
  require(type(activity) is dict,'Invalid parent activity');text(activity['prompt'])
  require(type(activity['checklist']) is list and 2<=len(activity['checklist'])<=8,'Invalid parent checklist')
  for line in activity['checklist']:text(line,1000)
 return item

def load_bank(path=BANK,complete=True):
 data=json.loads(Path(path).read_text());rows=data['lessons']
 ids=[x['topic_id'] for x in rows]
 if len(set(ids))!=len(ids):raise ValueError('Duplicate curriculum IDs')
 if complete and set(ids)!=set(curriculum.TOPICS):raise ValueError('Curriculum bank must cover exact source topic set')
 if data.get('source_commit')!=curriculum.COMMIT:raise ValueError('Wrong source commit')
 for row in rows:validate_lesson(row)
 return {r['topic_id']:r for r in rows}
