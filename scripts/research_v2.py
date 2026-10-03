"""V2 deterministic contracts. No scientific truth/entailment/originality certification."""
import datetime as dt
import hashlib
import math
import re
from pathlib import Path, PurePosixPath

EXTRA_KINDS=('searches','tensions','experiments','failures','handoffs','assertions')
ASSERTION_STATES={'untested','supported','refuted','inconclusive','withdrawn'}
LAYERS={'review','foundational','strong_baseline','recent','negative_results','countersearch'}
INTENTS={'known_item','exploratory','snowball'}
HASH=re.compile(r'^[0-9a-f]{64}$')
COMMIT=re.compile(r'^[0-9a-f]{7,64}$')
TEXT_LIMIT=16*1024*1024
FILE_LIMIT=128*1024*1024

def when(x):return dt.datetime.fromisoformat(x.replace('Z','+00:00'))
def approval_ok(value):
 # Declared human approval; the script cannot verify who approved or that they did.
 return isinstance(value,dict) and set(value)=={'by','at','scope'} and text(value.get('by')) and stamp(value.get('at')) and text(value.get('scope'))

def text(x): return isinstance(x,str) and bool(x.strip())
def strings(x,nonempty=True): return isinstance(x,list) and (bool(x) or not nonempty) and all(text(v) for v in x)
def number(x): return type(x) in (int,float) and math.isfinite(x) and x>=0
def stamp(x):
 try: return isinstance(x,str) and dt.datetime.fromisoformat(x.replace('Z','+00:00')).tzinfo is not None
 except ValueError: return False

def safe_path(project,value):
 if not text(value) or '\\' in value or '\x00' in value: raise ValueError('unsafe local path')
 rel=PurePosixPath(value)
 if rel.is_absolute() or '..' in rel.parts or not rel.parts: raise ValueError('unsafe local path')
 target=project
 for part in rel.parts:
  target=target/part
  if target.is_symlink(): raise ValueError('symlink local path refused')
 if not target.resolve().is_relative_to(project.resolve()): raise ValueError('local path escapes project')
 return target

def file_state(project,binding,excerpt=False):
 """Computed state only: byte hash + exact UTF-8 substring, never a page/meaning check."""
 path=safe_path(project,binding.get('path'))
 if not path.exists(): return 'unavailable'
 if not path.is_file(): return 'extraction_failed'
 limit=TEXT_LIMIT if excerpt else FILE_LIMIT
 try:
  if path.stat().st_size>limit: return 'extraction_failed'
  h=hashlib.sha256();chunks=[];size=0
  with path.open('rb') as f:
   for chunk in iter(lambda:f.read(65536),b''):
    size+=len(chunk)
    if size>limit: return 'extraction_failed'
    h.update(chunk)
    if excerpt: chunks.append(chunk)
  if h.hexdigest()!=binding.get('sha256'): return 'mismatch'
  if excerpt:
   try: content=b''.join(chunks).decode('utf-8-sig')
   except UnicodeDecodeError:return 'extraction_failed'
   if binding.get('excerpt') not in content: return 'mismatch'
  return 'matched'
 except OSError:return 'unavailable'

def refs(kind,row):
 result=[]
 def simple(field,target):
  value=row.get(field)
  if isinstance(value,dict):result.append((target,value.get('id'),value.get('rev')))
 def many(field,target=None):
  for value in row.get(field,[]) if isinstance(row.get(field),list) else []:
   if isinstance(value,dict):result.append((target or value.get('kind'),value.get('id'),value.get('rev')))
 if kind=='opportunities':many('search_refs','searches');many('tension_refs','tensions')
 if kind=='tensions':many('evidence')
 if kind=='experiments':simple('opportunity','opportunities');simple('plan_ref','experiments')
 if kind=='failures':many('evidence')
 if kind=='assertions':simple('opportunity','opportunities');many('evidence')
 return result

def validate_record(project,kind,row,history,current,strict=False):
 errors=[];notes=[];stale=False
 def fail(message):errors.append(message)
 if 'review_status' in row and row['review_status'] not in ('current','needs_review'):fail('invalid review_status')
 def require_string(field):
  if not text(row.get(field)):fail(f'{field} required')
 def enum(field,values):
  if row.get(field) not in values:fail(f'invalid {field}')
 def obj(field):
  value=row.get(field)
  if not isinstance(value,dict):fail(f'{field} must be object');return {}
  return value
 def ref_list(field,target=None):
  value=row.get(field)
  if not isinstance(value,list):fail(f'{field} must be reference list');return []
  for ref in value:
   if not isinstance(ref,dict) or not text(ref.get('id')) or type(ref.get('rev'))!=int or (target or ref.get('kind')) not in ('sources','papers','claims','opportunities',*EXTRA_KINDS):fail(f'invalid {field} reference');continue
   key=(target or ref.get('kind'),ref['id'],ref['rev'])
   if key not in history:fail(f'{field} missing foreign key {key}')
  return value
 def budget(value,label='budget'):
  if not isinstance(value,dict) or not number(value.get('limit')) or not number(value.get('spent',0)) or not text(value.get('unit')):fail(f'invalid {label}');return
  if value.get('spent',0)>value['limit'] and value.get('state')!='exhausted':fail(f'{label} exceeded without exhausted state')
 def binding(value,excerpt=False):
  nonlocal stale
  if not isinstance(value,dict):fail('binding must be object');return
  allowed={'path','sha256','excerpt'} if excerpt else {'path','sha256'}
  if set(value)-allowed:fail('caller status/verified cannot certify binding')
  if not isinstance(value.get('sha256'),str) or not HASH.fullmatch(value['sha256']):fail('binding requires SHA-256')
  if excerpt and not text(value.get('excerpt')):fail('binding excerpt required')
  try:safe_path(project,value.get('path'))
  except ValueError as e:fail(str(e));return
  if current:
   state=file_state(project,value,excerpt)
   notes.append(f'local binding {state}: {value.get("path")} (byte/substring provenance only)')
   if state!='matched':stale=True
 def provenance(value):
  # Declared code identity plus byte bindings; never proof that the command actually produced the outputs.
  if not isinstance(value,dict) or set(value)-{'code','command','environment','outputs'}:fail('invalid provenance; caller status/verified cannot certify a run');return
  code=value.get('code');code=code if isinstance(code,dict) else {}
  if not text(code.get('repo')) or not isinstance(code.get('commit'),str) or not COMMIT.fullmatch(code['commit']):fail('provenance code requires repo and hex commit (declared, not verified)')
  if not text(value.get('command')):fail('provenance command required')
  outputs=value.get('outputs')
  if not isinstance(outputs,list) or not outputs:fail('provenance outputs require at least one binding');outputs=[]
  start=len(errors)
  for item in [value.get('environment'),*outputs]:binding(item)
  errors[start:]=[f'provenance {message}' for message in errors[start:]]
 if kind=='sources':
  if 'material_binding' in row:binding(row['material_binding'])
  if 'acquisition_manifest_binding' in row:binding(row['acquisition_manifest_binding'])
  if 'material_kind' in row:enum('material_kind',{'pdf','xml','html'})
  if 'acquisition_state' in row:enum('acquisition_state',{'fulltext_saved'})
  if 'identity_verified' in row and type(row['identity_verified'])!=bool:fail('identity_verified must be boolean declaration; never certified by script')
 elif kind=='searches':
  require_string('query');enum('layer',LAYERS)
  if 'subq' in row and not text(row['subq']):fail('subq must be nonempty string naming a brief sub-question')
  if 'intent' in row:enum('intent',INTENTS)
  if not stamp(row.get('searched_at')):fail('searched_at requires timezone')
  bounds=obj('time_range')
  try:
   start=dt.date.fromisoformat(bounds.get('start',''));end=dt.date.fromisoformat(bounds.get('end',''))
   if start>end:fail('time_range start after end')
  except (ValueError,TypeError):fail('time_range requires ISO dates')
  cap=obj('capability')
  if not text(cap.get('name')) or cap.get('access') not in ('available','access_failed','unavailable') or not strings(cap.get('supports'),False) or not strings(cap.get('limitations'),False):fail('invalid source capability')
  if 'total_hits' not in row:fail('total_hits must be explicit integer or null (unknown)')
  returned=row.get('returned_count');total=row.get('total_hits')
  if type(returned)!=int or returned<0:fail('returned_count requires nonnegative integer')
  if total is not None and (type(total)!=int or total<0 or type(returned)==int and total<returned):fail('total_hits invalid or smaller than returned_count')
  page=obj('pagination')
  if page.get('state') not in ('complete','truncated','incomplete','unavailable','not_started') or type(page.get('fetched_pages'))!=int or page.get('fetched_pages',-1)<0:fail('invalid pagination state')
  enum('status',{'complete','zero_hits','access_failed','unavailable','incomplete'});enum('coverage_claim',{'bounded','exhaustive','unknown'});budget(row.get('budget'))
  if row.get('status')=='zero_hits' and (returned!=0 or total not in (None,0)):fail('zero_hits must have returned_count=0 and total_hits=0 or unknown')
  if row.get('status')=='complete' and (not isinstance(returned,int) or returned<1 or page.get('state')!='complete' or cap.get('access')!='available'):fail('complete search requires access, hits and completed pagination')
  if row.get('coverage_claim')=='exhaustive' and (total is None or total!=returned or page.get('state')!='complete' or row.get('status') not in ('complete','zero_hits') or cap.get('access')!='available' or 'total_hits' not in cap.get('supports',[]) or 'pagination' not in cap.get('supports',[])):fail('exhaustive claim requires known total and completed capable source')
  if row.get('status') in ('access_failed','unavailable','incomplete') and row.get('coverage_claim')!='unknown':fail('failed/incomplete search coverage must be unknown')
 elif kind=='claims':
  enum('locator_reliability',{'page','structure','source_only'});enum('evidence_kind',{'paper_statement','inference','hypothesis'});enum('material_access',{'available','unavailable','extraction_failed','unchecked'})
  require_string('supports_statement')
  if not strings(row.get('does_not_support')):fail('does_not_support must state stronger conclusions excluded')
  scope=obj('scope')
  if any(not text(scope.get(key)) for key in ('data','scale','evaluation','method_version')):fail('scope requires data/scale/evaluation/method_version')
  ref_list('conflicts','claims');loc=row.get('locator',{});loc=loc if isinstance(loc,dict) else {}
  if row.get('locator_reliability')=='page' and not(type(loc.get('page'))==int and loc['page']>0):fail('page reliability requires positive page declaration (not certified)')
  if row.get('locator_reliability')=='structure' and not any(text(loc.get(k)) for k in ('section','table','figure')):fail('structure reliability requires section/table/figure')
  if 'verified' in row:fail('caller verified cannot certify claim')
  if 'text_binding' in row:binding(row['text_binding'],True)
 elif kind=='tensions':
  enum('tension_type',{'conflict','anomaly','repeated_failure','access_bottleneck','observation_bottleneck','measurement_bottleneck'})
  require_string('observation');require_string('importance');ref_list('evidence')
  if not row.get('evidence') or not strings(row.get('alternative_explanations')):fail('tension requires evidence and alternative explanations')
  why_now(row,fail);attackability(row,fail)
 elif kind=='opportunities':
  searches=ref_list('search_refs','searches');ref_list('tension_refs','tensions')
  enum('novelty',{'provisional','unknown','covered'});enum('decision',{'continue','revise','park','abandon'})
  if not strings(row.get('critical_unknown')):fail('critical_unknown list required')
  require_string('change_decision_if');require_string('importance');why_now(row,fail);attackability(row,fail)
  nxt=obj('next_search');budget(nxt.get('budget'),'next_search budget')
  if not text(nxt.get('query')) or nxt.get('state') not in ('planned','complete','exhausted','unresolved'):fail('invalid next_search decision action')
  if nxt.get('priority') not in ('strongest_falsifier','coverage_gap'):fail('next_search priority must test strongest falsifier or retain coverage gap')
  nb=nxt.get('budget');nb=nb if isinstance(nb,dict) else {}
  if (nb.get('state')=='exhausted' or number(nb.get('spent')) and number(nb.get('limit')) and nb['spent']>nb['limit']) and (nxt.get('state') not in ('exhausted','unresolved') or nxt.get('unresolved') is not True):fail('next_search budget exhausted must remain explicitly unresolved')
  if nxt.get('state')=='planned' and number(nb.get('spent')) and number(nb.get('limit')) and nb['spent']>=nb['limit']:fail('planned next_search has no remaining budget')
  if nxt.get('state')=='exhausted' and nxt.get('unresolved') is not True:fail('exhausted search budget must mark unresolved')
  if 'experiment_plan' in row:discrimination(row['experiment_plan'],fail)
  if row.get('status')=='ready':
   found=[history.get(('searches',r.get('id'),r.get('rev')),{}) for r in searches if isinstance(r,dict) and isinstance(r.get('id'),str) and type(r.get('rev'))==int]
   good=[r for r in found if r.get('status')=='complete' and r.get('returned_count',0)>0 and r.get('schema_version')==2]
   if {r.get('layer') for r in good}!=LAYERS:fail('ready search coverage needs review/classic/baseline/recent/negative/countersearch; zero/failure is unresolved')
   if row.get('novelty')!='provisional' or row.get('decision') not in ('continue','revise') or row.get('attackability',{}).get('status')!='actionable':fail('ready requires provisional novelty and actionable decision')
   if nxt.get('state') in ('exhausted','unresolved'):fail('ready search decision unresolved')
   if 'experiment_plan' not in row:fail('ready requires competing-explanation experiment_plan')
   for ref in row.get('supports',[]) if isinstance(row.get('supports'),list) else []:
    if not isinstance(ref,dict) or not isinstance(ref.get('id'),str) or type(ref.get('rev'))!=int:continue
    c=history.get(('claims',ref['id'],ref['rev']),{})
    if c.get('schema_version')!=2 or c.get('evidence_kind')=='hypothesis' or c.get('locator_reliability') not in ('page','structure') or c.get('material_access')!='available':fail('ready evidence needs v2 non-hypothesis, usable material and declared reliable locator')
   for ref in row.get('tension_refs',[]) if isinstance(row.get('tension_refs'),list) else []:
    if isinstance(ref,dict) and isinstance(ref.get('id'),str) and type(ref.get('rev'))==int:
     t=history.get(('tensions',ref['id'],ref['rev']),{})
     if t.get('attackability',{}).get('status')!='actionable':fail('ready cannot depend on a parked tension without an attack path')
 elif kind=='experiments':
  enum('phase',{'planned','executed'})
  if row.get('phase')=='planned':discrimination(row,fail)
  else:
   ref=row.get('plan_ref');p={}
   if not isinstance(ref,dict) or not isinstance(ref.get('id'),str) or type(ref.get('rev'))!=int:fail('executed record needs pinned plan_ref')
   else:p=history.get(('experiments',ref['id'],ref['rev']),{})
   if p.get('phase')!='planned':fail('plan_ref must refer to planned experiment')
   actual=obj('actual')
   if not stamp(actual.get('executed_at')) or not isinstance(actual.get('measured_values'),list) or not actual['measured_values'] or not all(type(x) in (int,float) and math.isfinite(x) for x in actual['measured_values']):fail('execution requires actual timestamp and measured values')
   if actual.get('result') not in ('supporting','refuting','inconclusive') or type(actual.get('discriminating'))!=bool or not text(actual.get('reason')) or not number(actual.get('budget_spent')):fail('invalid executed outcome')
   if actual.get('discriminating') is False and actual.get('result')!='inconclusive':fail('non-discriminating result must be inconclusive, not refuting/supporting')
   if actual.get('execution_state') not in ('completed','technical_failure'):fail('actual execution_state required')
   if actual.get('execution_state')=='technical_failure' and actual.get('result')!='inconclusive':fail('technical failure cannot refute hypothesis')
   approval_gate(row,p,actual,current,strict,fail,notes)
   if 'provenance' in actual:provenance(actual['provenance'])
   elif actual.get('execution_state')=='completed' and current and row.get('active') is not False:
    if strict:fail('strict-v2 completed run requires actual.provenance (code/command/environment/outputs)')
    else:notes.append('completed run not traceable: add actual.provenance with code commit, command, environment and output bindings')
 elif kind=='failures':
  enum('failure_type',{'technical','non_discriminating','hypothesis_refuted','resource_infeasible'})
  require_string('cause');require_string('generalization_scope')
  conditions=obj('conditions')
  if any(not text(conditions.get(k)) for k in ('data','scale','evaluation','method_version')):fail('failure conditions require data/scale/evaluation/method_version')
  evidence=ref_list('evidence')
  if not evidence or not strings(row.get('reopen_conditions')):fail('failure needs evidence and reopen_conditions')
  linked=[(r.get('kind'),history.get((r.get('kind'),r.get('id'),r.get('rev')),{})) for r in evidence if isinstance(r,dict) and isinstance(r.get('kind'),str) and isinstance(r.get('id'),str) and type(r.get('rev'))==int]
  runs=[value for target_kind,value in linked if target_kind=='experiments']
  if row.get('failure_type')=='hypothesis_refuted' and not any(r.get('phase')=='executed' and r.get('actual',{}).get('result')=='refuting' and r.get('actual',{}).get('discriminating') is True for r in runs):fail('hypothesis_refuted needs discriminating refuting executed experiments evidence')
  if row.get('failure_type')=='technical' and not (any(r.get('phase')=='executed' and r.get('actual',{}).get('execution_state')=='technical_failure' for r in runs) or any(target_kind=='sources' and r.get('status')=='unavailable' for target_kind,r in linked)):fail('technical failure requires execution or acquisition failure evidence of correct kind')
  if row.get('failure_type')=='non_discriminating' and not any(r.get('phase')=='executed' and r.get('actual',{}).get('discriminating') is False for r in runs):fail('non_discriminating requires executed low-discrimination experiments evidence')
 elif kind=='handoffs':
  enum('step_state',{'planned','in_progress','completed','needs_review'});require_string('step')
  if not strings(row.get('pending_questions'),False) or not strings(row.get('invalidation_reasons'),False):fail('handoff pending_questions/invalidation_reasons must be lists')
  for field in ('inputs','outputs'):
   values=row.get(field)
   if not isinstance(values,list):fail(f'handoff {field} requires bindings');continue
   if row.get('step_state')=='completed' and not values:fail(f'completed handoff requires {field}')
   for value in values:binding(value)
  prior=[(rev,value) for (target_kind,rid,rev),value in history.items() if target_kind=='handoffs' and rid==row.get('id') and rev<row.get('rev',0)]
  unresolved=False
  for _,value in sorted(prior,key=lambda item:item[0],reverse=True):
   if value.get('step_state')=='completed' and value.get('review_status','current')=='current' and text(value.get('recovery_note')) and strings(value.get('invalidation_reasons')):break
   if value.get('step_state')=='needs_review' or value.get('review_status')=='needs_review':unresolved=True;break
  if row.get('step_state')=='completed' and row.get('review_status','current')=='current' and unresolved:
   if not text(row.get('recovery_note')) or not strings(row.get('invalidation_reasons')):fail('handoff recovery requires recovery_note and retained invalidation reasons across intermediate revisions')
  if row.get('step_state')=='completed' and row.get('summary_only') is True:fail('summary alone cannot complete handoff')
 elif kind=='assertions':
  # Our own research claims; state is a declaration checked only against the typed evidence it cites.
  require_string('statement');enum('assertion_state',ASSERTION_STATES)
  if not strings(row.get('does_not_support')):fail('does_not_support must state stronger conclusions excluded')
  linked=[]
  for ref in ref_list('evidence'):
   if not isinstance(ref,dict):continue
   role=ref.get('role')
   if role not in ('supports','refutes','context'):fail('evidence role must be supports/refutes/context');continue
   target=history.get((ref.get('kind'),ref.get('id'),ref.get('rev')),{})
   actual=target.get('actual') if ref.get('kind')=='experiments' and target.get('phase')=='executed' and isinstance(target.get('actual'),dict) else {}
   if role=='supports' and actual.get('result') in ('refuting','inconclusive') or role=='refutes' and actual.get('result') in ('supporting','inconclusive'):fail(f'evidence role {role} contradicts run result {actual.get("result")}')
   linked.append((role,ref.get('kind'),target,actual))
  def decisive(role,result):return any(r==role and a.get('result')==result and a.get('discriminating') is True and a.get('execution_state')=='completed' for r,_,_,a in linked)
  state=row.get('assertion_state')
  if state=='supported' and not (decisive('supports','supporting') or any(r=='supports' and k=='claims' and t.get('schema_version')==2 and t.get('basis')=='full_text' and t.get('evidence_kind')=='paper_statement' for r,k,t,_ in linked)):fail('supported needs a discriminating supporting run or a full-text paper statement')
  if state=='refuted' and not decisive('refutes','refuting'):fail('refuted needs a discriminating refuting run')
  if state=='inconclusive' and not any(a for *_,a in linked):fail('inconclusive needs an executed run')
  if state=='withdrawn' and not text(row.get('review_note')):fail('withdrawn requires review_note')
 return errors,notes,stale

def why_now(row,fail):
 why=row.get('why_now');why=why if isinstance(why,dict) else {}
 if why.get('kind') not in ('tool','data','conditions') or not text(why.get('reason')):fail('why_now requires tool/data/conditions and reason')

def attackability(row,fail):
 value=row.get('attackability');value=value if isinstance(value,dict) else {}
 if value.get('status') not in ('actionable','parked','unknown'):fail('invalid attackability')
 if value.get('status')=='actionable' and not text(value.get('path')):fail('actionable requires attack path; otherwise park')
 if value.get('status')=='parked' and not text(value.get('reason')):fail('parked requires reason')

def discrimination(row,fail):
 if not isinstance(row,dict):fail('discrimination plan must be object');return
 if row.get('phase')!='planned':fail('experiment plan must be planned, not a reported execution')
 if 'actual' in row or 'result' in row or row.get('executed') is True:fail('planned experiment cannot contain actual/measured result')
 for field in ('observation','explanation','strongest_rival','unit','metric','uncertainty','discrimination_limit'):
  if not text(row.get(field)):fail(f'discrimination {field} required')
 if row.get('explanation')==row.get('strongest_rival'):fail('strongest rival must differ from own explanation')
 base=row.get('baseline_sufficiency');base=base if isinstance(base,dict) else {}
 if type(base.get('possible'))!=bool or not text(base.get('rationale')):fail('baseline sufficiency must be considered')
 predictions=row.get('predictions')
 if not isinstance(predictions,list) or not predictions:fail('predictions under conditions/interventions required')
 else:
  for p in predictions:
   if not isinstance(p,dict) or any(not text(p.get(k)) for k in ('condition','own','rival')) or p.get('own')==p.get('rival'):fail('prediction needs condition and divergent own/rival outcomes')
 controls=row.get('controls');controls=controls if isinstance(controls,dict) else {}
 if controls.get('task_type') not in ('ml','theory','observational','wet_lab','other') or not strings(controls.get('items'),False) or not text(controls.get('rationale')):fail('task-adapted controls require task_type/items/rationale')
 if not strings(row.get('leakage_risks'),False) or not strings(row.get('stop_conditions')):fail('leakage risks and stop conditions required')
 b=row.get('budget');b=b if isinstance(b,dict) else {}
 if not number(b.get('limit')) or not text(b.get('unit')):fail('experiment budget required')
 if 'approval' in row and not approval_ok(row['approval']):fail('approval requires exactly by/at/scope (declared, not verified)')

def approval_gate(row,plan,actual,current,strict,fail,notes):
 """Plan-before-spend: execution needs prior approval; overruns need their own approval."""
 def soft(message):
  if current and row.get('active') is not False:(fail if strict else notes.append)(message)
 approval=plan.get('approval')
 if approval is None:soft('executed run has no recorded approval on its pinned plan')
 elif approval_ok(approval) and stamp(actual.get('executed_at')) and when(approval['at'])>when(actual['executed_at']):fail('approval must be recorded before execution')
 if 'overrun_approval' in actual and not approval_ok(actual['overrun_approval']):fail('overrun_approval requires exactly by/at/scope (declared, not verified)')
 elif 'overrun_approval' in actual and stamp(actual.get('executed_at')) and when(actual['overrun_approval']['at'])>when(actual['executed_at']):fail('overrun_approval must be recorded before execution')
 limit=plan.get('budget',{}).get('limit') if isinstance(plan.get('budget'),dict) else None
 if number(limit) and number(actual.get('budget_spent')) and actual['budget_spent']>limit and 'overrun_approval' not in actual:soft(f'budget overrun ({actual["budget_spent"]}>{limit}) without overrun_approval')
