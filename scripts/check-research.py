#!/usr/bin/env python3
"""Validate JSONL structure and dependency freshness, never evidence truth."""
import argparse
import copy
import datetime as dt
import json
import re
from collections import deque
from pathlib import Path
from urllib.parse import urlsplit

from research_trace import trace
from research_v2 import EXTRA_KINDS, refs as v2_refs, validate_record
BASE_KINDS=('sources','papers','claims','opportunities')
KINDS=BASE_KINDS+EXTRA_KINDS
ID=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$')
ARXIV=re.compile(r'^(?:\d{4}\.\d{4,5}|[a-z][a-z.-]*/\d{7})$')
GATES=('data','compute','time','baseline','ethics')
def timestamp(value):
 if not isinstance(value,str): return False
 try: return dt.datetime.fromisoformat(value.replace('Z','+00:00')).tzinfo is not None
 except ValueError: return False

def doi(value):
 if value is None: return None
 if not isinstance(value,str): return ''
 return re.sub(r'^(?:https?://(?:dx\.)?doi.org/|doi:\s*)','',value.strip(),flags=re.I).lower()

def dependencies(kind,row,provenance_only=False):
 out=[]
 if kind=='papers':
  out.append(('sources',row.get('source_id'),row.get('source_rev')))
  comparison=row.get('reviewed_against')
  if isinstance(comparison,dict): out.append(('papers',comparison.get('id'),comparison.get('rev')))
 if kind=='claims':
  out.append(('papers',row.get('paper_id'),row.get('paper_rev')))
  if not provenance_only and row.get('schema_version')==2:
   for ref in row.get('conflicts',[]) if isinstance(row.get('conflicts'),list) else []:
    if isinstance(ref,dict):out.append(('claims',ref.get('id'),ref.get('rev')))
 if kind=='opportunities':
  for key in ('supports','refutes'):
   for r in row.get(key,[]) if isinstance(row.get(key,[]),list) else []:
    if isinstance(r,dict): out.append(('claims',r.get('id'),r.get('rev')))
 for r in row.get('depends_on',[]) if isinstance(row.get('depends_on',[]),list) else []:
  if isinstance(r,dict): out.append((r.get('kind'),r.get('id'),r.get('rev')))
 if row.get('schema_version')==2:out.extend(v2_refs(kind,row))
 return out

def read_journals(root,error):
 history={};latest={}
 for kind in KINDS:
  p=root/f'{kind}.jsonl'
  if kind in EXTRA_KINDS and not p.exists() and not p.is_symlink():continue
  if p.is_symlink(): error(kind,'symlink journal refused');continue
  try:
   with p.open() as f:
    for n,line in enumerate(f,1):
     label=f'{kind}:{n}'
     if not line.strip(): continue
     if len(line.encode('utf-8'))>1024*1024: error(label,'record exceeds 1 MiB');continue
     try: row=json.loads(line)
     except json.JSONDecodeError: error(label,'invalid JSON');continue
     if not isinstance(row,dict): error(label,'record must be object');continue
     rid=row.get('id'); rev=row.get('rev')
     if not isinstance(rid,str) or not ID.fullmatch(rid) or type(rev)!=int or rev<1:
      error(label,'invalid stable id/rev');continue
     key=(kind,rid); previous=latest.get(key)
     if previous and previous.get('schema_version',1)==2 and row.get('schema_version',1)!=2:error(label,'schema downgrade from V2 is forbidden')
     if rev!=(previous['rev']+1 if previous else 1): error(label,'rev must start at 1 and append sequentially');continue
     if not timestamp(row.get('updated_at')): error(label,'updated_at requires timezone timestamp')
     if previous and timestamp(row.get('updated_at')) and timestamp(previous.get('updated_at')):
      if dt.datetime.fromisoformat(row['updated_at'].replace('Z','+00:00'))<dt.datetime.fromisoformat(previous['updated_at'].replace('Z','+00:00')):
       error(label,'updated_at moved backwards')
     history[(kind,rid,rev)]=row;latest[key]=row
  except OSError as e: error(kind,f'cannot read journal: {e.strerror}')
 return history,latest

def check_schema(root,kind,rid,row,label,history,latest,strict_v2,error,notes,extra_stale):
 schema=row.get('schema_version',1)
 if type(schema)!=int or schema not in (1,2):error(label,'unsupported schema_version')
 elif schema==1:
  if kind in EXTRA_KINDS:error(label,'new journal requires schema_version=2')
  elif latest[(kind,rid)] is row and row.get('active') is not False:
   notes.append(f'{label}: legacy schema v1 compatibility; V2 contracts NOT checked')
   if strict_v2:error(label,'strict-v2 requires explicit migrated active snapshot')
 else:
  v2_errors,v2_notes,local_stale=validate_record(root.parent,kind,row,history,latest[(kind,rid)] is row,strict_v2)
  for message in v2_errors:error(label,message)
  notes.extend(f'{label}: {message}' for message in v2_notes)
  if local_stale:extra_stale.add((kind,rid))
 return schema

def check_common(kind,row,label,history,error):
 if 'active' in row and type(row['active'])!=bool: error(label,'active must be boolean')
 if row.get('active') is False:
  if not isinstance(row.get('review_note'),str) or not row['review_note'].strip(): error(label,'retirement requires review_note')
  if kind=='opportunities' and row.get('status')!='rejected': error(label,'retired opportunity must be rejected')
 if 'depends_on' in row and (not isinstance(row['depends_on'],list) or any(not isinstance(x,dict) or x.get('kind') not in KINDS or not isinstance(x.get('id'),str) or type(x.get('rev'))!=int for x in row['depends_on'])): error(label,'invalid depends_on references')
 for dep in dependencies(kind,row):
  if any(type(x) not in (str,int) for x in dep) or dep not in history: error(label,f'missing foreign key {dep}')

def check_source(row,label,error):
 u=row.get('url'); parsed=urlsplit(u) if isinstance(u,str) else None
 if not parsed or parsed.scheme not in ('https','http') or not parsed.netloc or parsed.username or parsed.password: error(label,'url must be HTTP(S), without credentials')
 if not timestamp(row.get('retrieved_at')): error(label,'retrieved_at required')
 if row.get('status') not in ('active','updated','retracted','unavailable'): error(label,'invalid source status')

def check_paper(row,label,error):
 for field in ('work_id','title','version'):
  if not isinstance(row.get(field),str) or not row[field].strip(): error(label,f'{field} required')
 if 'reviewed_against' in row:
  comparison=row['reviewed_against']
  if not isinstance(comparison,dict) or not isinstance(comparison.get('id'),str) or type(comparison.get('rev'))!=int or not isinstance(row.get('review_note'),str) or not row['review_note'].strip(): error(label,'reviewed_against requires pinned paper and review_note')
 a=row.get('arxiv_id')
 if a is not None and (not isinstance(a,str) or not ARXIV.fullmatch(a) or not re.fullmatch(r'v[1-9]\d*',str(row.get('version')))): error(label,'arxiv_id must be unversioned; version must be explicit vN')
 if row.get('doi') is not None and not re.fullmatch(r'10\.\d{4,9}/\S+',doi(row['doi'])): error(label,'invalid DOI')
 if row.get('publication_status') not in ('preprint','accepted','published','corrected','retracted','unknown'): error(label,'invalid publication_status')
 if row.get('reading_depth') not in ('metadata','abstract','skim','targeted_body','full_text'): error(label,'invalid reading_depth')
 if row.get('reading_depth')=='targeted_body' and (not isinstance(row.get('reading_scope'),str) or not row['reading_scope'].strip()):error(label,'targeted_body requires reading_scope declaring sections read and not read; not a full-read certification')
 if row.get('review_status') not in ('current','needs_review'): error(label,'invalid review_status')

def check_claim(row,label,schema,history,error):
 if not isinstance(row.get('statement'),str) or not row['statement'].strip(): error(label,'statement required')
 if row.get('basis') not in ('abstract','full_text'): error(label,'invalid basis')
 if row.get('review_status') not in ('current','needs_review'): error(label,'invalid review_status')
 paper=history.get(('papers',row.get('paper_id'),row.get('paper_rev'))) if isinstance(row.get('paper_id'),str) and type(row.get('paper_rev'))==int else None
 loc=row.get('locator');loc=loc if isinstance(loc,dict) else {}
 if not paper or loc.get('version')!=paper.get('version'): error(label,'locator version must match pinned paper')
 if row.get('basis')=='full_text':
  if paper and paper.get('reading_depth') not in ('full_text','targeted_body'): error(label,'full_text claim exceeds paper reading depth')
  if schema==1 and not (type(loc.get('page'))==int and loc['page']>0 or any(isinstance(loc.get(k),str) and loc[k].strip() for k in ('figure','table'))): error(label,'full_text locator needs positive page or figure/table')
 elif loc.get('section')!='abstract': error(label,'abstract locator must specify section=abstract')

def check_opportunity(row,label,history,error):
 if not isinstance(row.get('title'),str) or not row['title'].strip(): error(label,'title required')
 if row.get('status') not in ('candidate','blocked','rejected','ready','needs_review'): error(label,'invalid opportunity status')
 for field in ('supports','refutes'):
  if not isinstance(row.get(field),list) or any(not isinstance(x,dict) or not isinstance(x.get('id'),str) or type(x.get('rev'))!=int for x in row.get(field,[]) if isinstance(row.get(field),list)): error(label,f'invalid {field} references')
 gates=row.get('gates'); gates=gates if isinstance(gates,dict) else {}
 if any(gates.get(g) not in ('pass','fail','unknown') for g in GATES): error(label,'all data/compute/time/baseline/ethics gates require pass/fail/unknown')
 if row.get('status')!='ready': return
 closest=row.get('closest_work');closest=closest if isinstance(closest,dict) else {}
 experiment=row.get('minimal_experiment');experiment=experiment if isinstance(experiment,dict) else {}
 for g in GATES:
  if gates.get(g)!='pass': error(label,f'ready blocked by {g}={gates.get(g)}')
 if not row.get('supports'): error(label,'ready requires supporting evidence')
 if closest.get('decision') not in ('distinct','revised') or not isinstance(closest.get('queries'),list) or not closest['queries'] or not timestamp(closest.get('searched_at')) or not closest.get('rationale'): error(label,'ready requires closest-work countersearch and distinct/revised rationale')
 if any(not isinstance(experiment.get(k),str) or not experiment[k].strip() for k in ('hypothesis','baseline','metric','budget','falsifier')): error(label,'ready requires falsifiable minimal experiment')
 if not isinstance(row.get('stop_conditions'),list) or not row['stop_conditions'] or not all(isinstance(x,str) and x.strip() for x in row['stop_conditions']): error(label,'ready requires stop conditions')
 for dep in dependencies('opportunities',row):
  c=history.get(dep) if all(type(x) in (str,int) for x in dep) else None
  if dep[0]=='claims' and c and c.get('basis')!='full_text': error(label,'ready requires full_text evidence; abstracts remain provisional')

def check_identities(history,error):
 # Identity invariants across versions and across revisions (identity cannot drift).
 identities={};works={};seen_versions={}
 for (kind,rid,rev),row in history.items():
  if kind!='papers': continue
  signature=(row.get('work_id'),row.get('arxiv_id'),doi(row.get('doi')),row.get('version'))
  if rid in identities and identities[rid]!=signature: error(rid,'paper identity/version immutable; create a linked version record')
  identities[rid]=signature
  for namespace,value in [('arxiv',row.get('arxiv_id')),('doi',doi(row.get('doi')))]:
   if not isinstance(value,str) or not value: continue
   if (namespace,value) in works and works[(namespace,value)]!=row.get('work_id'): error(rid,'same DOI/arxiv identity requires same work_id')
   works[(namespace,value)]=row.get('work_id')
   vkey=(namespace,value,row.get('version'))
   if vkey in seen_versions and seen_versions[vkey]!=rid: error(rid,'duplicate paper version identity')
   seen_versions[vkey]=rid

def check_acyclic(history,error):
 # Reject circular provenance, including additional explicit dependencies (Kahn's algorithm).
 graph={key:{d for d in dependencies(key[0],row,True) if all(type(x) in (str,int) for x in d) and d in history} for key,row in history.items()}
 incoming={key:len(deps) for key,deps in graph.items()};reverse={key:[] for key in graph}
 for key,deps in graph.items():
  for dep in deps: reverse[dep].append(key)
 queue=deque(key for key,n in incoming.items() if n==0);processed=0
 while queue:
  key=queue.popleft();processed+=1
  for dependent in reverse[key]:
   incoming[dependent]-=1
   if incoming[dependent]==0: queue.append(dependent)
 if processed!=len(graph): error('dependencies','cycle in pinned provenance graph')

def propagating(key,row):
 """Pinned dependencies that carry staleness from target to dependent."""
 # A plan's built-in opportunity pin records which direction it was designed for; revising the
 # direction (a downstream decision) must not invalidate the evidence it was decided from.
 # Explicit depends_on keeps normal freshness.
 link=row.get('opportunity') if key[0]=='experiments' and row.get('phase')=='planned' else None
 plan_link=('opportunities',link.get('id'),link.get('rev')) if isinstance(link,dict) else None
 explicit={(d.get('kind'),d.get('id'),d.get('rev')) for d in row.get('depends_on',[]) if isinstance(d,dict)} if isinstance(row.get('depends_on'),list) else set()
 return [dep for dep in dependencies(key[0],row) if all(type(x) in (str,int) for x in dep) and (dep!=plan_link or dep in explicit)]

def acknowledged(opportunity):
 """Assertion revisions an opportunity decided on; malformed entries are reported by the V2 validator."""
 value=opportunity.get('assertion_review')
 return {(a['id'],a['rev']) for a in value if isinstance(a,dict) and isinstance(a.get('id'),str) and type(a.get('rev'))==int} if isinstance(value,list) else set()

def own_opportunity_pins(history,latest):
 """Assertions whose pinned chain (exact revisions) reaches their own opportunity: with the reverse link that is a stale cycle."""
 bad=[]
 for (kind,rid),row in latest.items():
  oid=row.get('opportunity_id')
  if kind!='assertions' or row.get('active') is False or not isinstance(oid,str):continue
  seen=set();todo=[(kind,rid,row['rev'])]
  while todo:
   current=todo.pop()
   if current in seen or current not in history:continue
   seen.add(current)
   for dep in propagating(current[:2],history[current]):
    if dep[:2]==('opportunities',oid):bad.append((kind,rid));todo=[];break
    todo.append(dep)
 return bad

def find_stale(history,latest,extra_stale):
 stale=set(extra_stale)
 # A newly recorded arXiv version makes older interpretations require comparison.
 newest={}
 for (kind,rid),row in latest.items():
  a=row.get('arxiv_id');v=row.get('version')
  if kind=='papers' and isinstance(a,str) and isinstance(v,str) and re.fullmatch(r'v[1-9]\d*',v):
   if a not in newest or int(v[1:])>newest[a][0]: newest[a]=(int(v[1:]),rid,row['rev'])
 for key,row in latest.items():
  a=row.get('arxiv_id');v=row.get('version')
  if key[0]=='papers' and isinstance(a,str) and isinstance(v,str) and re.fullmatch(r'v[1-9]\d*',v) and a in newest and int(v[1:])<newest[a][0]:
   comparison=row.get('reviewed_against');comparison=comparison if isinstance(comparison,dict) else {}
   newer=latest.get(('papers',newest[a][1]),{})
   if comparison!={'id':newest[a][1],'rev':newest[a][2]} or newer.get('reading_depth')!='full_text' or not row.get('review_note'): stale.add(key)
 for key,row in latest.items():
  if key[0]=='sources' and row.get('status') in ('retracted','unavailable') or key[0]=='papers' and row.get('publication_status')=='retracted' or row.get('review_status')=='needs_review' or key[0]=='opportunities' and row.get('status')=='needs_review' or row.get('active') is False or key[0]=='handoffs' and row.get('step_state')=='needs_review': stale.add(key)
 # Reverse link: a re-judged or stale assertion re-opens its (unpinned) opportunity decision.
 # Safe inside the closure because no built-in edge propagates from opportunities back down.
 linked={}
 for (kind,rid,_),row in history.items():
  if kind=='assertions' and isinstance(row.get('opportunity_id'),str):linked.setdefault(rid,set()).add(row['opportunity_id'])
 reverse=[]
 for key,row in latest.items():
  if key[0]!='assertions':continue
  oid=row.get('opportunity_id')
  # Retiring is a judgment change (acknowledgement check below), but a retired record stays stale forever,
  # so only active assertions pass inherited staleness back to their current direction.
  if row.get('active') is not False and isinstance(oid,str) and ('opportunities',oid) in latest:
   reverse.append((key,('opportunities',oid)))
   if row.get('review_status')=='needs_review':stale.add(('opportunities',oid))
  # Every direction this assertion was ever linked to must name its latest revision; timestamps can tie,
  # and a moved or detached assertion must still reopen the direction it left.
  for former in linked.get(key[1],()):
   opp=latest.get(('opportunities',former))
   if opp is not None and (key[1],row['rev']) not in acknowledged(opp):stale.add(('opportunities',former))
 # Any acknowledged assertion that has since moved on.
 for key,row in latest.items():
  if key[0]=='opportunities' and any(('assertions',aid) in latest and latest[('assertions',aid)]['rev']!=rev for aid,rev in acknowledged(row)):stale.add(key)
 # Propagate staleness to everything pinned to a moved or stale record.
 changed=True
 while changed:
  changed=False
  for key,row in latest.items():
   for dep in propagating(key,row):
    target=latest.get(dep[:2])
    if target and (target['rev']!=dep[2] or dep[:2] in stale) and key not in stale:
     stale.add(key);changed=True
  for source,opp in reverse:
   if source in stale and opp not in stale:stale.add(opp);changed=True
 return stale

# Discovery-yield heuristics: notes only; a compliant project can still be a low-yield one.
MIN_DISCOVERY_SEARCHES=5
MAX_SHALLOW_SHARE=0.5
def yield_notes(latest):
 rows=lambda kind:[r for (k,_),r in latest.items() if k==kind and r.get('active') is not False]
 notes=[];searches=rows('searches');papers=rows('papers')
 if searches:
  intents=[r.get('intent') for r in searches]
  if all(i is None for i in intents):notes.append('discovery yield: searches lack intent; known-item lookups cannot be told from discovery')
  else:
   found=sum(i in ('exploratory','snowball') for i in intents)
   if found<MIN_DISCOVERY_SEARCHES:notes.append(f'discovery yield: only {found} exploratory/snowball searches; known-item lookups confirm a reading list, not discover one')
   if 'snowball' not in intents:notes.append('discovery yield: no snowball (citation-chasing) search from core papers')
 if papers:
  shallow=sum(r.get('reading_depth') in ('metadata','abstract') for r in papers)
  if shallow/len(papers)>MAX_SHALLOW_SHARE:notes.append(f'discovery yield: {shallow}/{len(papers)} papers read at abstract depth or less')
 return notes

def validate(root,strict_v2=False):
 errors=[];notes=[];extra_stale=set()
 def error(label,msg): errors.append(f'{label}: {msg}')
 history,latest=read_journals(root,error)
 # Validate every historical record, not just current snapshots.
 for (kind,rid,rev),row in history.items():
  label=f'{kind}/{rid}@{rev}'
  schema=check_schema(root,kind,rid,row,label,history,latest,strict_v2,error,notes,extra_stale)
  check_common(kind,row,label,history,error)
  if kind=='sources': check_source(row,label,error)
  elif kind=='papers': check_paper(row,label,error)
  elif kind=='claims': check_claim(row,label,schema,history,error)
  elif kind=='opportunities': check_opportunity(row,label,history,error)
 check_identities(history,error)
 check_acyclic(history,error)
 for kind,rid in own_opportunity_pins(history,latest):error(f'{kind}/{rid}','assertion must not depend on its own opportunity (directly or via evidence); with opportunity_id that closes a stale cycle')
 stale=find_stale(history,latest,extra_stale)
 for kind,rid in sorted(stale):
  if kind!='sources' and latest[(kind,rid)].get('active') is not False:
   error(f'{kind}/{rid}','needs_review: evidence changed, unavailable, retracted or dependent on stale evidence')
 notes.extend(yield_notes(latest))
 independent=len({row.get('work_id') for (k,_),row in latest.items() if k=='papers' and isinstance(row.get('work_id'),str)})
 return errors,latest,stale,independent,notes

def mark_review(root,latest,stale):
 # Caller holds advisory lock. Complete snapshots append, original rows remain intact.
 for key in sorted(stale):
  kind,rid=key
  if kind=='sources' or latest[key].get('active') is False: continue
  old=latest[key];field='status' if kind=='opportunities' else 'review_status'
  if old.get(field)=='needs_review': continue
  row=copy.deepcopy(old);row.update(rev=old['rev']+1,updated_at=dt.datetime.now(dt.timezone.utc).isoformat());row[field]='needs_review'
  row['review_reason']='Evidence revision/status, retirement or local input/output binding changed; manually re-check before repinning.'
  if kind=='handoffs':
   row['step_state']='needs_review'
   row['invalidation_reasons']=[*row.get('invalidation_reasons',[]),row['review_reason']]
  path=root/f'{kind}.jsonl'
  prefix=''
  if path.stat().st_size:
   with path.open('rb') as previous:
    previous.seek(-1,2)
    if previous.read(1)!=b'\n': prefix='\n'
  with path.open('a') as f:
   f.write(prefix+json.dumps(row,ensure_ascii=False)+'\n');f.flush()
   import os;os.fsync(f.fileno())

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('project',type=Path);parser.add_argument('--mark-review',action='store_true');parser.add_argument('--strict-v2',action='store_true');args=parser.parse_args();root=args.project/'research'
 if root.is_symlink(): parser.exit(1,'symlink research directory refused\n')
 try:
  if args.mark_review:
   import fcntl
   # Lock is a coordination file, not a source of evidence.
   import os
   fd=os.open(root/'.review.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
   with os.fdopen(fd,'w') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX);errors,latest,stale,independent,notes=validate(root,args.strict_v2)
    # Never mutate structurally invalid journals; freshness diagnostics alone are safe.
    if all('needs_review:' in e for e in errors): mark_review(root,latest,stale)
  else: errors,latest,stale,independent,notes=validate(root,args.strict_v2)
  # Deliverable citations are checked after any marking so report typos never block journal review.
  trace_errors,trace_notes=trace(args.project,latest,stale);errors+=trace_errors;notes+=trace_notes
 except (OSError,ValueError,TypeError) as e: parser.exit(1,f'validation could not complete: {e}\n')
 print(f'structure/freshness only; independent_works={independent}; records={len(latest)}')
 for note in notes: print(note)
 for e in errors: print(e)
 print('FAIL' if errors else 'PASS (not a truth or originality certification)')
 return 1 if errors else 0
if __name__=='__main__': raise SystemExit(main())
