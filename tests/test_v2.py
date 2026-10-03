import copy,hashlib,importlib.util,json,subprocess,tempfile,unittest
from pathlib import Path
from test_research import sample,STAMP
ROOT=Path(__file__).resolve().parents[1]
LAYERS=['review','foundational','strong_baseline','recent','negative_results','countersearch']
def search(i=0):
 return dict(schema_version=2,id=f'q{i}',rev=1,updated_at=STAMP,query='条件异常 强基线',layer=LAYERS[i%6],searched_at=STAMP,time_range={'start':'2000-01-01','end':'2026-10-01'},capability={'name':'local fixture index','access':'available','supports':['pagination','total_hits','full_text'],'limitations':[]},returned_count=2,total_hits=2,pagination={'state':'complete','fetched_pages':1},status='complete',coverage_claim='bounded',budget={'limit':5,'spent':1,'unit':'queries'})
def claim_fields():
 return dict(locator_reliability='page',evidence_kind='paper_statement',supports_statement='Fixture result under measured setting',does_not_support=['universal improvement','originality'],scope={'data':'synthetic sample','scale':'small','evaluation':'fixed accuracy','method_version':'fixture-v1'},conflicts=[],material_access='available')
def plan():
 return dict(schema_version=2,id='e1',rev=1,updated_at=STAMP,phase='planned',review_status='current',opportunity={'id':'o1','rev':1},observation='gain only on small data',explanation='mechanism helps rare cases',strongest_rival='baseline tuning explains gain',baseline_sufficiency={'possible':True,'rationale':'tuned baseline may suffice'},predictions=[{'condition':'increase data with budget fixed','own':'gain persists','rival':'gain disappears'}],controls={'task_type':'ml','items':['tuned baseline','split holdout'],'rationale':'control tuning and leakage'},unit='dataset split',metric='accuracy',uncertainty='bootstrap intervals',discrimination_limit='delta=0.02; interval width<=0.01, else inconclusive',leakage_risks=['same source across split'],budget={'limit':1,'unit':'CPU-hour'},stop_conditions=['no separable prediction'])
def bundle():
 d=sample()
 for rows in d.values():
  for row in rows:row['schema_version']=2
 d['claims'][0].update(claim_fields())
 d['searches']=[search(i) for i in range(6)]
 d['opportunities'][0].update(search_refs=[{'id':f'q{i}','rev':1} for i in range(6)],novelty='provisional',critical_unknown=['whether tuned baseline suffices'],decision='continue',change_decision_if='strong baseline explains the gain',next_search={'query':'negative result tuned baseline rare data','budget':{'limit':2,'spent':0,'unit':'queries'},'state':'planned','priority':'strongest_falsifier'},importance='rare failure matters',attackability={'status':'actionable','path':'small controlled split comparison'},why_now={'kind':'conditions','reason':'new accessible synthetic diagnostic split'},tension_refs=[],experiment_plan=plan(),decisive_neighbors=[{'id':'p1-v1','rev':1}])
 return d
class V2Tests(unittest.TestCase):
 def setUp(self):
  self.assertTrue((ROOT/'scripts/research_v2.py').exists(),'v2 contract implementation missing')
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.project=Path(self.tmp.name);(self.project/'research').mkdir()
 def check(self,data,*args):
  for p in (self.project/'research').glob('*.jsonl'):p.unlink()
  for kind,rows in data.items():(self.project/'research'/f'{kind}.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows),encoding='utf-8')
  return subprocess.run(['python3',str(ROOT/'scripts/check-research.py'),str(self.project),*args],capture_output=True,text=True)
 def test_v2_positive_and_legacy_compatibility_explicit(self):
  r=self.check(bundle(),'--strict-v2');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
  r=self.check(sample());self.assertEqual(r.returncode,0,r.stdout);self.assertIn('legacy',r.stdout)
  r=self.check(sample(),'--strict-v2');self.assertNotEqual(r.returncode,0)
 def test_unknown_total_and_truncation_never_exhaustive(self):
  for total,state in [(None,'complete'),(10,'truncated')]:
   d=bundle();d['searches'][0].update(total_hits=total,coverage_claim='exhaustive');d['searches'][0]['pagination']['state']=state
   r=self.check(d);self.assertNotEqual(r.returncode,0);self.assertIn('exhaustive',r.stdout)
 def test_zero_and_access_failure_not_novelty(self):
  for state in ['zero_hits','access_failed','unavailable','incomplete']:
   d=bundle()
   for row in d['searches']:
    row.update(status=state,returned_count=0,total_hits=None);row['pagination'].update(state='incomplete',fetched_pages=0)
   r=self.check(d);self.assertNotEqual(r.returncode,0);self.assertIn('search',r.stdout)
 def test_optional_subquestion_tag(self):
  d=bundle();d['searches'][0]['subq']='sq2';r=self.check(d,'--strict-v2');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
  for bad in ('',' ',2,['sq1']):
   d=bundle();d['searches'][0]['subq']=bad;r=self.check(d);self.assertNotEqual(r.returncode,0);self.assertIn('subq',r.stdout)
 def test_search_intent_and_discovery_yield_notes_never_fail(self):
  r=self.check(bundle(),'--strict-v2');self.assertEqual(r.returncode,0,r.stdout);self.assertIn('searches lack intent',r.stdout)
  d=bundle()
  for row in d['searches']:row['intent']='known_item'
  r=self.check(d,'--strict-v2');self.assertEqual(r.returncode,0,r.stdout)
  self.assertIn('only 0 exploratory/snowball',r.stdout);self.assertIn('no snowball',r.stdout)
  for i,row in enumerate(d['searches']):row['intent']='snowball' if i==0 else 'exploratory'
  r=self.check(d,'--strict-v2');self.assertEqual(r.returncode,0,r.stdout);self.assertNotIn('discovery yield: only',r.stdout);self.assertNotIn('no snowball',r.stdout)
  d['papers'][0]['reading_depth']='abstract';d['opportunities'][0]['status']='candidate'
  r=self.check(d);self.assertIn('1/1 papers read at abstract depth',r.stdout)
  d=bundle();d['searches'][0]['intent']='lookup';r=self.check(d);self.assertNotEqual(r.returncode,0);self.assertIn('intent',r.stdout)
 def test_actionable_decision_requires_body_read_decisive_neighbors(self):
  def opp(decision='continue',depth='full_text',**changes):
   d=bundle();o=d['opportunities'][0];o.update(status='candidate',decision=decision,**changes);d['papers'][0]['reading_depth']=depth
   if depth=='targeted_body':d['papers'][0]['reading_scope']='method and experiments read; appendix not read'
   if depth=='abstract':d['claims'][0].update(basis='abstract',locator={'version':'v1','section':'abstract'},locator_reliability='source_only')
   return d
  for depth in ('full_text','targeted_body'):
   r=self.check(opp(depth=depth),'--strict-v2');self.assertEqual(r.returncode,0,r.stdout)
  for decision in ('continue','revise'):
   r=self.check(opp(decision,'abstract'));self.assertNotEqual(r.returncode,0);self.assertIn('decisive neighbor p1-v1 read only at abstract',r.stdout)
  r=self.check(opp('park','abstract'),'--strict-v2');self.assertEqual(r.returncode,0,r.stdout)
  d=opp();del d['opportunities'][0]['decisive_neighbors']
  r=self.check(d);self.assertEqual(r.returncode,0,r.stdout);self.assertIn('decisive_neighbors',r.stdout)
  r=self.check(d,'--strict-v2');self.assertNotEqual(r.returncode,0);self.assertIn('decisive_neighbors',r.stdout)
  r=self.check(opp(decisive_neighbors=[]),'--strict-v2');self.assertNotEqual(r.returncode,0);self.assertIn('decisive_neighbors',r.stdout)
  r=self.check(opp(decisive_neighbors=[{'id':'missing','rev':1}]));self.assertNotEqual(r.returncode,0);self.assertIn('missing foreign key',r.stdout)
  # Append-only repair: a later body read plus a new opportunity rev must restore PASS without rewriting history.
  d=opp(depth='abstract');old=d['opportunities'][0]
  read=copy.deepcopy(d['papers'][0]);read.update(rev=2,reading_depth='full_text')
  claim=copy.deepcopy(d['claims'][0]);claim.update(rev=2,paper_rev=2)
  fixed=copy.deepcopy(old);fixed.update(rev=2,decisive_neighbors=[{'id':'p1-v1','rev':2}],supports=[{'id':claim['id'],'rev':2}])
  d['papers'].append(read);d['claims'].append(claim);d['opportunities'].append(fixed)
  r=self.check(d,'--strict-v2');self.assertEqual(r.returncode,0,r.stdout)
 def test_critical_unknown_unread_neighbor_blocks_actionable_decision(self):
  def opp(decision='continue',depth='abstract',unknown=None,**changes):
   d=bundle();other=copy.deepcopy(d['papers'][0])
   other.update(id='p2-v1',work_id='w2',arxiv_id='2301.11306',title='Possible covering work',reading_depth=depth)
   if depth=='targeted_body':other['reading_scope']='evaluation section read; appendix not read'
   d['papers'].append(other)
   o=d['opportunities'][0];o.update(status='candidate',decision=decision,**changes)
   o['critical_unknown']=unknown if unknown is not None else [{'paper':{'id':'p2-v1','rev':1},'gap':'may already score human revisions'}]
   return d
  for decision in ('continue','revise'):
   r=self.check(opp(decision));self.assertNotEqual(r.returncode,0);self.assertIn('critical unknown paper p2-v1 read only at abstract',r.stdout)
  r=self.check(opp('park'),'--strict-v2');self.assertEqual(r.returncode,0,r.stdout)
  r=self.check(opp(depth='targeted_body'),'--strict-v2');self.assertEqual(r.returncode,0,r.stdout)
  for prose in (['the 2025 ingestion paper was not body-read'],['相关专利正文未读'],['ok'],):
   d=opp(unknown=prose)
   if prose==['ok']:d['opportunities'][0]['change_decision_if']='The unread 2025 paper already scores revisions'
   r=self.check(d);self.assertEqual(r.returncode,0,r.stdout);self.assertIn('names an unread work in prose',r.stdout)
   r=self.check(d,'--strict-v2');self.assertNotEqual(r.returncode,0);self.assertIn('names an unread work in prose',r.stdout)
  r=self.check(opp('park',unknown=['the 2025 paper was not read']),'--strict-v2');self.assertEqual(r.returncode,0,r.stdout)
  r=self.check(opp(unknown=['strong baseline reproduction pending']),'--strict-v2');self.assertEqual(r.returncode,0,r.stdout)
  for bad in ([{'paper':{'id':'p2-v1'},'gap':'x'}],[{'paper':{'id':'p2-v1','rev':1}}],[{'gap':'x'}],[3]):
   r=self.check(opp(unknown=bad));self.assertNotEqual(r.returncode,0,bad);self.assertIn('critical_unknown',r.stdout)
  r=self.check(opp(unknown=[{'paper':{'id':'nope','rev':1},'gap':'x'}]));self.assertNotEqual(r.returncode,0);self.assertIn('missing foreign key',r.stdout)
  # Malformed values must surface as schema errors, not crash the whole validation.
  for bad in (None,3,'text'):
   d=opp();d['opportunities'][0]['critical_unknown']=bad
   r=self.check(d);self.assertNotEqual(r.returncode,0,bad);self.assertIn('critical_unknown list required',r.stdout);self.assertNotIn('could not complete',r.stdout+r.stderr)
  d=opp();d['opportunities'][0]['change_decision_if']=None
  r=self.check(d);self.assertNotIn('could not complete',r.stdout+r.stderr);self.assertIn('change_decision_if',r.stdout)
  # A body-read finding that something was not reported is not an unread work.
  r=self.check(opp(depth='full_text',unknown=['该近邻正文未报告训练成本']),'--strict-v2');self.assertEqual(r.returncode,0,r.stdout)
 def test_negative_counts_and_time_bounds(self):
  for field,value in [('returned_count',-1),('total_hits',1),('time_range',{'start':'2026-10-02','end':'2026-10-01'})]:
   d=bundle();d['searches'][0][field]=value;r=self.check(d);self.assertNotEqual(r.returncode,0)
 def test_reading_separate_from_locator_and_hypothesis_not_evidence(self):
  d=bundle();d['opportunities'][0]['status']='candidate';d['claims'][0]['locator_reliability']='source_only';d['claims'][0]['locator']={'version':'v1'}
  r=self.check(d);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
  for field,value in [('locator_reliability','source_only'),('evidence_kind','hypothesis'),('material_access','extraction_failed')]:
   d=bundle();d['claims'][0][field]=value;r=self.check(d);self.assertNotEqual(r.returncode,0)
 def test_excerpt_unicode_hash_recomputed_and_forgery_rejected(self):
  content='观测：在小规模数据中效果改善。\n'.encode();p=self.project/'摘录 文本.txt';p.write_bytes(content)
  d=bundle();d['claims'][0]['text_binding']={'path':p.name,'sha256':hashlib.sha256(content).hexdigest(),'excerpt':'小规模数据'}
  r=self.check(d);self.assertEqual(r.returncode,0,r.stdout);self.assertIn('matched',r.stdout)
  for replacement in [{'verified':True},{'sha256':'0'*64},{'excerpt':'不存在的引用'}]:
   bad=copy.deepcopy(d);bad['claims'][0]['text_binding'].update(replacement);r=self.check(bad);self.assertNotEqual(r.returncode,0)
 def test_excerpt_states_and_paths(self):
  for path in ['../outside','/etc/passwd','a\\b','missing.txt']:
   d=bundle();d['claims'][0]['text_binding']={'path':path,'sha256':'0'*64,'excerpt':'abc'};r=self.check(d);self.assertNotEqual(r.returncode,0);self.assertNotIn('Traceback',r.stderr)
  p=self.project/'bad.txt';p.write_bytes(b'\xff');d=bundle();d['claims'][0]['text_binding']={'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'excerpt':'abc'}
  r=self.check(d);self.assertNotEqual(r.returncode,0);self.assertIn('extraction_failed',r.stdout)
  (self.project/'link.txt').symlink_to(p);d['claims'][0]['text_binding']['path']='link.txt';r=self.check(d);self.assertNotEqual(r.returncode,0)
 def test_coverage_layers_preserved_and_budget_unresolved(self):
  d=bundle();d['opportunities'][0]['search_refs']=[{'id':'q5','rev':1}];r=self.check(d);self.assertNotEqual(r.returncode,0);self.assertIn('coverage',r.stdout)
  d=bundle();d['opportunities'][0]['next_search'].update(state='exhausted',unresolved=True);r=self.check(d);self.assertNotEqual(r.returncode,0)
 def tension(self):
  return dict(schema_version=2,id='t1',rev=1,updated_at=STAMP,review_status='current',tension_type='conflict',observation='gain vanishes at large scale',evidence=[{'kind':'claims','id':'c1','rev':1}],alternative_explanations=['baseline tuning','measurement ceiling'],importance='deployment gap',why_now={'kind':'data','reason':'new diagnostic set'},attackability={'status':'actionable','path':'vary scale with fixed evaluation'})
 def run_record(self):
  return dict(schema_version=2,id='run1',rev=1,updated_at=STAMP,review_status='current',phase='executed',plan_ref={'id':'e1','rev':1},actual={'executed_at':STAMP,'measured_values':[0.51,0.50],'result':'inconclusive','discriminating':False,'reason':'too little separation','budget_spent':0.5,'execution_state':'completed'})
 def failure(self):
  return dict(schema_version=2,id='f1',rev=1,updated_at=STAMP,review_status='current',failure_type='non_discriminating',cause='confidence interval overlaps both predictions',conditions={'data':'synthetic','scale':'small','evaluation':'accuracy','method_version':'fixture-v1'},evidence=[{'kind':'experiments','id':'run1','rev':1}],generalization_scope='only this diagnostic split',reopen_conditions=['more informative split or higher power'])
 def test_parked_tension_and_missing_attack_path(self):
  d=bundle();t=self.tension();t['attackability']={'status':'parked','reason':'no intervention available'};d['tensions']=[t];d['opportunities'][0]['tension_refs']=[{'id':'t1','rev':1}]
  r=self.check(d);self.assertNotEqual(r.returncode,0);self.assertIn('parked',r.stdout)
  d['opportunities'][0].update(status='blocked',decision='park');r=self.check(d);self.assertEqual(r.returncode,0,r.stdout)
  d['tensions'][0]['attackability']={'status':'actionable','path':None};r=self.check(d);self.assertNotEqual(r.returncode,0)
 def test_discrimination_requires_rival_and_divergent_prediction(self):
  for key,value in [('strongest_rival','mechanism helps rare cases'),('predictions',[{'condition':'change scale','own':'same','rival':'same'}]),('baseline_sufficiency',{}),('uncertainty','')]:
   d=bundle();d['opportunities'][0]['experiment_plan'][key]=value;r=self.check(d);self.assertNotEqual(r.returncode,0)
 def test_theory_controls_not_forced_wet_negative_control(self):
  d=bundle();d['opportunities'][0]['experiment_plan']['controls']={'task_type':'theory','items':[],'rationale':'check boundary counterexample and alternative proof assumptions'}
  r=self.check(d);self.assertEqual(r.returncode,0,r.stdout)
 def test_plan_and_actual_strictly_separate(self):
  d=bundle();d['experiments']=[plan()];r=self.check(d);self.assertEqual(r.returncode,0,r.stdout)
  d['experiments'][0]['actual']={'result':'supporting'};r=self.check(d);self.assertNotEqual(r.returncode,0)
  d=bundle();d['experiments']=[plan(),self.run_record()];r=self.check(d);self.assertEqual(r.returncode,0,r.stdout)
  d['experiments'][1]['actual']['measured_values']=[];r=self.check(d);self.assertNotEqual(r.returncode,0)
 def test_low_power_negative_is_inconclusive_and_technical_failure_not_refutation(self):
  for state in ['completed','technical_failure']:
   d=bundle();run=self.run_record();run['actual'].update(result='refuting',execution_state=state);d['experiments']=[plan(),run]
   r=self.check(d);self.assertNotEqual(r.returncode,0)
 def test_conditional_failure_and_reopen_requirements(self):
  d=bundle();d['experiments']=[plan(),self.run_record()];d['failures']=[self.failure()];r=self.check(d);self.assertEqual(r.returncode,0,r.stdout)
  d['failures'][0]['failure_type']='hypothesis_refuted';r=self.check(d);self.assertNotEqual(r.returncode,0)
  d['experiments'][1]['actual'].update(result='refuting',discriminating=True);r=self.check(d);self.assertEqual(r.returncode,0,r.stdout)
  d['failures'][0]['reopen_conditions']=[];r=self.check(d);self.assertNotEqual(r.returncode,0)
 def test_handoff_hash_change_marks_review_and_append_recovery(self):
  p=self.project/'输入.txt';q=self.project/'产物.txt';p.write_text('input');q.write_text('output')
  h=dict(schema_version=2,id='h1',rev=1,updated_at=STAMP,review_status='current',step='map evidence',step_state='completed',inputs=[{'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}],outputs=[{'path':q.name,'sha256':hashlib.sha256(q.read_bytes()).hexdigest()}],pending_questions=['critical uncertainty'],invalidation_reasons=[])
  d=bundle();d['handoffs']=[h];r=self.check(d);self.assertEqual(r.returncode,0,r.stdout)
  p.write_text('changed');r=self.check(d,'--mark-review');self.assertNotEqual(r.returncode,0);self.assertIn('mismatch',r.stdout)
  rows=[json.loads(x) for x in (self.project/'research/handoffs.jsonl').read_text().splitlines()];self.assertEqual(len(rows),2);self.assertEqual(rows[-1]['review_status'],'needs_review')
  fixed=copy.deepcopy(rows[-1]);fixed.update(rev=3,review_status='current',step_state='completed',updated_at=rows[-1]['updated_at'],invalidation_reasons=['input changed; repeated step'],recovery_note='Repeated input and output hash checks after input change');fixed['inputs'][0]['sha256']=hashlib.sha256(p.read_bytes()).hexdigest();d['handoffs']=rows+[fixed]
  r=self.check(d);self.assertEqual(r.returncode,0,r.stdout)
 def test_summary_completion_cannot_bypass_missing_bindings(self):
  d=bundle();d['handoffs']=[dict(schema_version=2,id='h1',rev=1,updated_at=STAMP,step='done',step_state='completed',inputs=[],outputs=[],pending_questions=[],invalidation_reasons=[],summary_only=True)];r=self.check(d);self.assertNotEqual(r.returncode,0)
 def test_optional_journals_initialized_and_existing_kept(self):
  r=subprocess.run(['bash',str(ROOT/'scripts/init-project.sh'),str(self.project)],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
  for k in ['searches','tensions','experiments','failures','handoffs']:self.assertTrue((self.project/'research'/f'{k}.jsonl').exists())
 def test_search_zero_count_inconsistent_and_missing_totals_declared(self):
  for replacement in [{'status':'zero_hits','returned_count':0,'total_hits':2},{'status':'complete','returned_count':0}]:
   d=bundle();d['opportunities'][0]['status']='candidate';d['searches'][0].update(replacement);r=self.check(d);self.assertNotEqual(r.returncode,0)
  d=bundle();d['opportunities'][0]['status']='candidate';del d['searches'][0]['total_hits'];r=self.check(d);self.assertNotEqual(r.returncode,0)
 def test_failure_types_need_consistent_evidence(self):
  d=bundle();d['experiments']=[plan(),self.run_record()];d['failures']=[self.failure()];d['failures'][0]['failure_type']='technical'
  r=self.check(d);self.assertNotEqual(r.returncode,0)
 def test_ready_cannot_skip_generated_search_unknown_contract(self):
  d=bundle();d['opportunities'][0]['next_search']['priority']='confirm_favorite';r=self.check(d);self.assertNotEqual(r.returncode,0)
 def test_schema_downgrade_rejected_and_unknown_schema_non_mutating(self):
  d=bundle();old=copy.deepcopy(d['claims'][0]);old.update(rev=2,schema_version=1);d['claims'].append(old)
  r=self.check(d);self.assertNotEqual(r.returncode,0);self.assertIn('downgrade',r.stdout)
  d=bundle();d['claims'][0]['schema_version']=999;r=self.check(d,'--mark-review');self.assertNotEqual(r.returncode,0)
  self.assertEqual(len((self.project/'research/claims.jsonl').read_text().splitlines()),1)
 def test_text_change_transitive_review_and_hash_repinned_recovery(self):
  p=self.project/'evidence.txt';p.write_text('supporting fragment')
  d=bundle();d['claims'][0]['text_binding']={'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'excerpt':'supporting fragment'}
  r=self.check(d);self.assertEqual(r.returncode,0,r.stdout)
  p.write_text('supporting fragment changed');r=self.check(d,'--mark-review');self.assertNotEqual(r.returncode,0)
  claims=[json.loads(x) for x in (self.project/'research/claims.jsonl').read_text().splitlines()];ops=[json.loads(x) for x in (self.project/'research/opportunities.jsonl').read_text().splitlines()]
  self.assertEqual(claims[-1]['review_status'],'needs_review');self.assertEqual(ops[-1]['status'],'needs_review')
  c=copy.deepcopy(claims[-1]);c.update(rev=3,review_status='current',review_note='reread changed fragment');c['text_binding']['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
  o=copy.deepcopy(ops[-1]);o.update(rev=3,status='ready',updated_at=ops[-1]['updated_at']);o['supports']=[{'id':'c1','rev':3}]
  d['claims']=claims+[c];d['opportunities']=ops+[o];r=self.check(d);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_unchecked_mismatch_and_missing_file_distinct_computed_states(self):
  for state in ['unchecked','unavailable','extraction_failed']:
   d=bundle();d['claims'][0]['material_access']=state;r=self.check(d);self.assertNotEqual(r.returncode,0)
  d=bundle();d['opportunities'][0]['status']='candidate';d['claims'][0]['text_binding']={'path':'absent.txt','sha256':'0'*64,'excerpt':'abc'};r=self.check(d);self.assertIn('binding unavailable',r.stdout)
 def test_handoff_review_snapshot_changes_step_state_and_explains_invalidation(self):
  p=self.project/'in.txt';p.write_text('changed');d=bundle();d['handoffs']=[dict(schema_version=2,id='h1',rev=1,updated_at=STAMP,step='inspect',step_state='completed',inputs=[{'path':p.name,'sha256':'0'*64}],outputs=[{'path':p.name,'sha256':'0'*64}],pending_questions=[],invalidation_reasons=[],review_status='current')]
  r=self.check(d,'--mark-review');self.assertNotEqual(r.returncode,0)
  rows=[json.loads(x) for x in (self.project/'research/handoffs.jsonl').read_text().splitlines()];self.assertEqual(rows[-1]['step_state'],'needs_review');self.assertTrue(rows[-1]['invalidation_reasons'])
 def test_search_revision_invalidates_ready_and_retirement_skips_head(self):
  d=bundle();q=copy.deepcopy(d['searches'][0]);q.update(rev=2,status='access_failed',coverage_claim='unknown',total_hits=None,returned_count=0);q['capability']['access']='access_failed';q['pagination']['state']='incomplete';d['searches'].append(q)
  r=self.check(d,'--mark-review');self.assertNotEqual(r.returncode,0);self.assertIn('needs_review',r.stdout)
  rows=[json.loads(x) for x in (self.project/'research/opportunities.jsonl').read_text().splitlines()];o=copy.deepcopy(rows[-1]);o.update(rev=3,status='rejected',active=False,review_note='retired due to unresolved coverage');d['opportunities']=rows+[o]
  r=self.check(d);self.assertEqual(r.returncode,0,r.stdout)
 def test_claim_cannot_impersonate_executed_failure_evidence(self):
  for ftype,result,disc in [('hypothesis_refuted','refuting',True),('non_discriminating','inconclusive',False),('technical','inconclusive',False)]:
   d=bundle();d['claims'][0].update(phase='executed',actual={'result':result,'discriminating':disc,'execution_state':'technical_failure'})
   f=self.failure();f.update(failure_type=ftype,evidence=[{'kind':'claims','id':'c1','rev':1}]);d['failures']=[f];r=self.check(d);self.assertNotEqual(r.returncode,0)
 def test_nested_exhausted_budget_cannot_remain_ready(self):
  d=bundle();n=d['opportunities'][0]['next_search'];n['state']='complete';n['budget'].update(spent=3,state='exhausted');r=self.check(d);self.assertNotEqual(r.returncode,0);self.assertIn('budget',r.stdout)
 def test_handoff_recovery_without_explanation_rejected(self):
  p=self.project/'same.txt';p.write_text('same');b={'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
  h=dict(schema_version=2,id='h1',rev=1,updated_at=STAMP,step='recheck',step_state='needs_review',review_status='needs_review',inputs=[b],outputs=[b],pending_questions=[],invalidation_reasons=['changed input'])
  d=bundle();fixed=copy.deepcopy(h);fixed.update(rev=2,step_state='completed',review_status='current',invalidation_reasons=[]);d['handoffs']=[h,fixed];r=self.check(d);self.assertNotEqual(r.returncode,0);self.assertIn('recovery',r.stdout)
 def test_minimal_plan_requires_discrimination_limit(self):
  d=bundle();d['opportunities'][0]['experiment_plan'].pop('discrimination_limit',None);r=self.check(d);self.assertNotEqual(r.returncode,0)
 def test_handoff_intermediate_revision_cannot_erase_review_obligation(self):
  p=self.project/'artifact.txt';p.write_text('ok');b={'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
  h=dict(schema_version=2,id='h1',rev=1,updated_at=STAMP,step='verify',step_state='needs_review',review_status='needs_review',inputs=[b],outputs=[b],pending_questions=[],invalidation_reasons=['changed'])
  middle=copy.deepcopy(h);middle.update(rev=2,step_state='in_progress',review_status='current')
  final=copy.deepcopy(middle);final.update(rev=3,step_state='completed',invalidation_reasons=[])
  d=bundle();d['handoffs']=[h,middle,final];r=self.check(d);self.assertNotEqual(r.returncode,0);self.assertIn('recovery',r.stdout)
  final.update(recovery_note='repeated verification of changed input',invalidation_reasons=['changed']);r=self.check(d);self.assertEqual(r.returncode,0,r.stdout)
 def test_arbitrary_review_status_cannot_bypass_handoff(self):
  d=bundle();d['handoffs']=[dict(schema_version=2,id='h1',rev=1,updated_at=STAMP,step='verify',step_state='completed',review_status='recovered',inputs=[],outputs=[],pending_questions=[],invalidation_reasons=[])];r=self.check(d);self.assertNotEqual(r.returncode,0);self.assertIn('review_status',r.stdout)
