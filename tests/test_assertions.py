"""Own research assertions: separate from paper claims, state backed by typed evidence."""
import copy,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from test_research import STAMP
from test_v2 import bundle,plan
ROOT=Path(__file__).resolve().parents[1]

def run(result='supporting',discriminating=True,state='completed',rid='r1'):
 return dict(schema_version=2,id=rid,rev=1,updated_at=STAMP,review_status='current',phase='executed',plan_ref={'id':'e1','rev':1},actual={'executed_at':STAMP,'measured_values':[0.61,0.52],'result':result,'discriminating':discriminating,'reason':'intervals separate','budget_spent':0.5,'execution_state':state})
def assertion(state='untested',evidence=(),**extra):
 row=dict(schema_version=2,id='a1',rev=1,updated_at=STAMP,review_status='current',statement='Rework resets step completion; history-only trackers miss it',assertion_state=state,opportunity_id='o1',evidence=list(evidence),does_not_support=['all assembly lines','online deployment'])
 row.update(extra);return row
SUP={'kind':'experiments','id':'r1','rev':1,'role':'supports'}

class AssertionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.project=Path(self.tmp.name);(self.project/'research').mkdir()
 def check(self,data,*args):
  for kind,rows in data.items():(self.project/'research'/f'{kind}.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows),encoding='utf-8')
  return subprocess.run([sys.executable,str(ROOT/'scripts/check-research.py'),str(self.project),*args],capture_output=True,text=True)
 def data(self,*runs,**assertion_args):
  d=bundle();d['experiments']=[plan(),*runs];d['assertions']=[assertion(**assertion_args)];d['opportunities'][0]['assertion_review']=[{'id':'a1','rev':1}];return d
 def acknowledge(self,d,rev):
  d['opportunities'].append(dict(copy.deepcopy(d['opportunities'][-1]),rev=d['opportunities'][-1]['rev']+1,assertion_review=[{'id':'a1','rev':rev}]))

 def test_untested_assertion_needs_no_paper(self):
  r=self.check(self.data(),'--strict-v2');self.assertEqual(r.returncode,0,r.stdout)
  d=self.data();del d['assertions'][0]['does_not_support'];r=self.check(d);self.assertNotEqual(r.returncode,0);self.assertIn('does_not_support',r.stdout)
  d=self.data(state='proven');r=self.check(d);self.assertIn('assertion_state',r.stdout)

 def test_supported_needs_discriminating_supporting_run_or_fulltext_claim(self):
  r=self.check(self.data(run(),state='supported',evidence=[SUP]));self.assertEqual(r.returncode,0,r.stdout)
  claim={'kind':'claims','id':'c1','rev':1,'role':'supports'}
  r=self.check(self.data(state='supported',evidence=[claim]));self.assertEqual(r.returncode,0,r.stdout)
  plan_only={'kind':'experiments','id':'e1','rev':1,'role':'supports'}
  for runs,ev in [((),[]),((),[plan_only]),((run('inconclusive',False),),[SUP]),((run(state='technical_failure',result='inconclusive'),),[SUP])]:
   r=self.check(self.data(*runs,state='supported',evidence=ev));self.assertNotEqual(r.returncode,0,(runs,ev));self.assertIn('supported',r.stdout)
  d=self.data(state='supported',evidence=[claim]);d['claims'][0]['evidence_kind']='hypothesis';d['opportunities'][0]['status']='candidate'
  r=self.check(d);self.assertNotEqual(r.returncode,0);self.assertIn('supported',r.stdout)

 def test_role_must_match_run_result(self):
  r=self.check(self.data(run('refuting'),evidence=[SUP]));self.assertNotEqual(r.returncode,0);self.assertIn('role',r.stdout)
  ref=dict(SUP,role='refutes');r=self.check(self.data(run('supporting'),evidence=[ref]));self.assertNotEqual(r.returncode,0)
  r=self.check(self.data(run('inconclusive',False),evidence=[dict(SUP,role='context')]));self.assertEqual(r.returncode,0,r.stdout)
  r=self.check(self.data(evidence=[dict(SUP,role='proves')]));self.assertNotEqual(r.returncode,0)

 def test_refuted_and_inconclusive_need_executed_runs(self):
  ref=dict(SUP,role='refutes')
  r=self.check(self.data(run('refuting'),state='refuted',evidence=[ref]));self.assertEqual(r.returncode,0,r.stdout)
  r=self.check(self.data(state='refuted'));self.assertNotEqual(r.returncode,0);self.assertIn('refuted',r.stdout)
  r=self.check(self.data(run('inconclusive',False),state='inconclusive',evidence=[dict(SUP,role='context')]));self.assertEqual(r.returncode,0,r.stdout)
  r=self.check(self.data(state='inconclusive'));self.assertNotEqual(r.returncode,0);self.assertIn('inconclusive',r.stdout)
  for decisive in (run('supporting'),run('refuting')):
   role='supports' if decisive['actual']['result']=='supporting' else 'refutes'
   r=self.check(self.data(decisive,state='inconclusive',evidence=[dict(SUP,role=role)]));self.assertNotEqual(r.returncode,0,decisive);self.assertIn('inconclusive',r.stdout)

 def test_untested_cannot_hold_decisive_evidence(self):
  claim={'kind':'claims','id':'c1','rev':1,'role':'supports'}
  for runs,ev in [((run('supporting'),),[SUP]),((run('refuting'),),[dict(SUP,role='refutes')]),((),[claim])]:
   r=self.check(self.data(*runs,evidence=ev));self.assertNotEqual(r.returncode,0,ev);self.assertIn('untested',r.stdout)
  r=self.check(self.data(run('inconclusive',False),evidence=[dict(SUP,role='context')]));self.assertEqual(r.returncode,0,r.stdout)
  r=self.check(self.data(evidence=[dict(claim,role='context')]));self.assertEqual(r.returncode,0,r.stdout)

 def test_malformed_evidence_reported_not_crashing(self):
  for field,value in [('id',['r1']),('kind',{'x':1}),('rev',[1])]:
   r=self.check(self.data(run(),evidence=[dict(SUP,**{field:value})]))
   self.assertNotEqual(r.returncode,0);self.assertIn('evidence',r.stdout,field);self.assertNotIn('could not complete',r.stdout+r.stderr,field)

 def test_literature_support_needs_available_material(self):
  claim={'kind':'claims','id':'c1','rev':1,'role':'supports'}
  for access in ('unchecked','unavailable','extraction_failed'):
   d=self.data(state='supported',evidence=[claim]);d['claims'][0]['material_access']=access;d['opportunities'][0]['status']='candidate'
   r=self.check(d);self.assertNotEqual(r.returncode,0,access);self.assertIn('supported',r.stdout)
   d['assertions'][0]['assertion_state']='untested';r=self.check(d);self.assertEqual(r.returncode,0,r.stdout)

 def test_unacknowledged_assertion_revision_reopens_direction(self):
  for value in (['o1'],{'id':'o1','rev':1},'',2,'missing'):
   r=self.check(self.data(opportunity_id=value));self.assertNotEqual(r.returncode,0,value);self.assertIn('opportunity_id',r.stdout)
  d=self.data();del d['assertions'][0]['opportunity_id'];r=self.check(d);self.assertEqual(r.returncode,0,r.stdout)
  for value in ('a1',[{'id':'a1'}],[{'id':'a1','rev':'1'}],[{'id':'a1','rev':9}]):
   d=self.data();d['opportunities'][0]['assertion_review']=value;r=self.check(d);self.assertNotEqual(r.returncode,0,value);self.assertIn('assertion_review',r.stdout)
  d=self.data();del d['opportunities'][0]['assertion_review'];r=self.check(d);self.assertIn('opportunities/o1',r.stdout)
  # Same updated_at on every record: acknowledgement, not timestamp order, decides.
  d=self.data(run('refuting'),evidence=[dict(SUP,role='refutes')],state='refuted',rev=2)
  d['assertions'].insert(0,assertion());self.assertEqual(d['experiments'][0]['opportunity'],{'id':'o1','rev':1})  # default plan shape stays pinned
  r=self.check(d);self.assertNotEqual(r.returncode,0);self.assertIn('opportunities/o1',r.stdout)
  for chain in ('experiments/e1','experiments/r1','assertions/a1'):self.assertNotIn(chain+': needs_review',r.stdout)
  self.acknowledge(d,2);d['opportunities'][-1].update(status='candidate',decision='revise')
  r=self.check(d);self.assertEqual(r.returncode,0,r.stdout)
  d['assertions'][-1]['review_status']='needs_review'
  r=self.check(d);self.assertIn('opportunities/o1',r.stdout)

 def test_conflicting_decisive_runs_force_inconclusive(self):
  ev=[SUP,{'kind':'experiments','id':'r2','rev':1,'role':'refutes'}];runs=(run('supporting'),run('refuting',rid='r2'))
  for state in ('supported','refuted'):
   r=self.check(self.data(*runs,state=state,evidence=ev));self.assertNotEqual(r.returncode,0,state);self.assertIn('conflicting',r.stdout)
  r=self.check(self.data(*runs,state='inconclusive',evidence=ev));self.assertEqual(r.returncode,0,r.stdout)

 def test_withdrawn_keeps_history_with_reason(self):
  r=self.check(self.data(state='withdrawn'));self.assertNotEqual(r.returncode,0);self.assertIn('withdrawn',r.stdout)
  r=self.check(self.data(state='withdrawn',review_note='nearest neighbour already handles rework'));self.assertEqual(r.returncode,0,r.stdout)

 def test_changed_evidence_makes_assertion_and_citation_stale(self):
  d=self.data(run(),state='supported',evidence=[SUP]);(self.project/'outline.md').write_text('主张 [assertions/a1@1]\n',encoding='utf-8')
  r=self.check(d);self.assertEqual(r.returncode,0,r.stdout)
  moved=copy.deepcopy(d['experiments'][1]);moved.update(rev=2,review_status='needs_review');d['experiments'].append(moved)
  r=self.check(d);self.assertNotEqual(r.returncode,0);self.assertIn('assertions/a1',r.stdout)
  r=self.check(d,'--mark-review');rows=(self.project/'research/assertions.jsonl').read_text().splitlines()
  self.assertEqual(json.loads(rows[-1])['review_status'],'needs_review')
  opp=(self.project/'research/opportunities.jsonl').read_text().splitlines()
  self.assertEqual(json.loads(opp[-1])['status'],'needs_review','one --mark-review pass must also reopen the direction')

 def test_explicit_opportunity_dependency_keeps_freshness(self):
  d=self.data();d['experiments'][0]['depends_on']=[{'kind':'opportunities','id':'o1','rev':1}]
  d['opportunities'].append(dict(copy.deepcopy(d['opportunities'][0]),rev=2,updated_at='2026-10-02T18:00:00Z'))
  r=self.check(d);self.assertNotEqual(r.returncode,0);self.assertIn('experiments/e1: needs_review',r.stdout)
  del d['experiments'][0]['depends_on'];r=self.check(d);self.assertEqual(r.returncode,0,r.stdout)

 def test_assertion_cannot_depend_on_its_own_opportunity(self):
  pin={'kind':'opportunities','id':'o1','rev':1}
  d=self.data();d['assertions'][0]['depends_on']=[pin];r=self.check(d);self.assertNotEqual(r.returncode,0);self.assertIn('stale cycle',r.stdout)
  d=self.data(evidence=[dict(pin,role='context')]);r=self.check(d);self.assertNotEqual(r.returncode,0);self.assertIn('stale cycle',r.stdout)
  f=dict(schema_version=2,id='f1',rev=1,updated_at=STAMP,review_status='current',failure_type='resource_infeasible',cause='no labels',conditions={'data':'d','scale':'s','evaluation':'e','method_version':'m'},evidence=[pin],generalization_scope='this site',reopen_conditions=['labels arrive'])
  d=self.data(evidence=[{'kind':'failures','id':'f1','rev':1,'role':'context'}]);d['failures']=[f];r=self.check(d);self.assertNotEqual(r.returncode,0);self.assertIn('stale cycle',r.stdout)
  self.assertNotIn('could not complete',r.stdout+r.stderr)
  d=self.data(evidence=[dict(pin,role='context')]);del d['assertions'][0]['opportunity_id'];r=self.check(d);self.assertIn('stale cycle',r.stdout,'acknowledgement is also a reverse link')
  del d['opportunities'][0]['assertion_review'];r=self.check(d);self.assertEqual(r.returncode,0,r.stdout)

 def test_retiring_assertion_reopens_direction_once(self):
  d=self.data();d['assertions'].append(dict(assertion(),rev=2,active=False,review_note='superseded by a narrower assertion'))
  r=self.check(d);self.assertNotEqual(r.returncode,0);self.assertIn('opportunities/o1',r.stdout)
  self.acknowledge(d,2)
  r=self.check(d);self.assertEqual(r.returncode,0,r.stdout)

 def test_own_opportunity_check_follows_pinned_revisions(self):
  later='2026-10-02T12:00:00Z'
  d=self.data(evidence=[{'kind':'assertions','id':'a2','rev':1,'role':'context'}])
  a2=assertion();a2.update(id='a2');del a2['opportunity_id']
  d['assertions']=[a2,dict(a2,rev=2,updated_at=later,depends_on=[{'kind':'opportunities','id':'o1','rev':1}])]+d['assertions']
  r=self.check(d);self.assertNotIn('stale cycle',r.stdout);self.assertIn('assertions/a1: needs_review',r.stdout)
  r=self.check(d,'--mark-review');rows=(self.project/'research/assertions.jsonl').read_text().splitlines()
  self.assertEqual(json.loads(rows[-1])['review_status'],'needs_review','recovery marking must not be blocked')

 def test_retired_needs_review_assertion_reopens_only_once(self):
  d=self.data();d['assertions'].append(dict(assertion(),rev=2,review_status='needs_review',active=False,review_note='retired after review'))
  r=self.check(d);self.assertIn('opportunities/o1',r.stdout)
  self.acknowledge(d,2)
  r=self.check(d);self.assertEqual(r.returncode,0,r.stdout)

 def test_detached_or_moved_assertion_reopens_previous_direction(self):
  for change in ({'opportunity_id':None},{'opportunity_id':'o2'}):
   d=self.data();o2=dict(copy.deepcopy(d['opportunities'][0]),id='o2',assertion_review=[{'id':'a1','rev':2}]);d['opportunities'].append(o2)
   moved=dict(assertion(),rev=2,assertion_state='withdrawn',review_note='scope moved');moved.update(change)
   if moved['opportunity_id'] is None:del moved['opportunity_id']
   d['assertions'].append(moved)
   r=self.check(d);self.assertIn('opportunities/o1',r.stdout,change);self.assertNotIn('opportunities/o2',r.stdout)
   d['opportunities'].insert(1,dict(copy.deepcopy(d['opportunities'][0]),rev=2,assertion_review=[]))
   r=self.check(d);self.assertIn('opportunities/o1',r.stdout,'a formerly linked direction must acknowledge the move')
   d['opportunities'][1]['assertion_review']=[{'id':'a1','rev':2}]
   r=self.check(d);self.assertEqual(r.returncode,0,r.stdout)

 def test_never_acknowledged_former_link_still_reopens(self):
  d=self.data();del d['opportunities'][0]['assertion_review']
  o2=dict(copy.deepcopy(d['opportunities'][0]),id='o2',assertion_review=[{'id':'a1','rev':2}]);d['opportunities'].append(o2)
  d['assertions'].append(dict(assertion(),rev=2,opportunity_id='o2'))
  r=self.check(d);self.assertIn('opportunities/o1',r.stdout);self.assertNotIn('opportunities/o2',r.stdout)

 def test_malformed_acknowledgement_reported_not_crashing(self):
  for value in ([{'id':['a1'],'rev':1}],[{'id':'a1','rev':{'n':1}}]):
   d=self.data();d['opportunities'][0]['assertion_review']=value;r=self.check(d)
   self.assertNotEqual(r.returncode,0);self.assertIn('assertion_review',r.stdout);self.assertNotIn('could not complete',r.stdout+r.stderr)

 def test_executed_run_opportunity_pin_keeps_freshness(self):
  d=self.data(dict(run(),opportunity={'id':'o1','rev':1}))
  d['opportunities'].append(dict(copy.deepcopy(d['opportunities'][0]),rev=2))
  r=self.check(d);self.assertIn('experiments/r1: needs_review',r.stdout);self.assertNotIn('experiments/e1: needs_review',r.stdout)

 def test_inherited_staleness_reaches_former_directions(self):
  d=self.data(run(),state='supported',evidence=[SUP])
  o2=dict(copy.deepcopy(d['opportunities'][0]),id='o2',assertion_review=[{'id':'a1','rev':2}]);d['opportunities'].append(o2)
  d['assertions'].append(dict(d['assertions'][0],rev=2,opportunity_id='o2'))
  d['opportunities'].insert(1,dict(copy.deepcopy(d['opportunities'][0]),rev=2,assertion_review=[{'id':'a1','rev':2}]))
  r=self.check(d);self.assertEqual(r.returncode,0,r.stdout)
  d['experiments'].append(dict(copy.deepcopy(d['experiments'][1]),rev=2,review_status='needs_review'))
  r=self.check(d);self.assertIn('opportunities/o1',r.stdout);self.assertIn('opportunities/o2',r.stdout)

 def test_assertion_cannot_depend_on_a_former_direction(self):
  d=self.data();o2=dict(copy.deepcopy(d['opportunities'][0]),id='o2',assertion_review=[{'id':'a1','rev':2}]);d['opportunities'].append(o2)
  d['assertions'].append(dict(assertion(),rev=2,opportunity_id='o2',depends_on=[{'kind':'opportunities','id':'o1','rev':1}]))
  r=self.check(d);self.assertIn('stale cycle',r.stdout)

 def test_acknowledging_direction_receives_inherited_staleness(self):
  d=self.data(run(),state='supported',evidence=[SUP])
  d['opportunities'].append(dict(copy.deepcopy(d['opportunities'][0]),id='o2',assertion_review=[{'id':'a1','rev':1}]))
  r=self.check(d);self.assertEqual(r.returncode,0,r.stdout)
  d['experiments'].append(dict(copy.deepcopy(d['experiments'][1]),rev=2,review_status='needs_review'))
  r=self.check(d);self.assertIn('opportunities/o1',r.stdout);self.assertIn('opportunities/o2',r.stdout)

 def test_cross_direction_cycle_rejected(self):
  d=self.data();d['assertions'][0]['depends_on']=[{'kind':'opportunities','id':'o2','rev':1}]
  a2=dict(assertion(),id='a2',opportunity_id='o2',depends_on=[{'kind':'opportunities','id':'o1','rev':1}])
  d['assertions'].append(a2)
  d['opportunities'].append(dict(copy.deepcopy(d['opportunities'][0]),id='o2',assertion_review=[{'id':'a2','rev':1}]))
  r=self.check(d);self.assertIn('stale cycle',r.stdout);self.assertNotIn('could not complete',r.stdout+r.stderr)
  del d['assertions'][1]['depends_on'];r=self.check(d);self.assertNotIn('stale cycle',r.stdout);self.assertEqual(r.returncode,0,r.stdout)

 def test_history_in_acknowledgement_list_is_fine_when_latest_present(self):
  d=self.data();d['assertions'].append(dict(assertion(),rev=2))
  d['opportunities'][0]['assertion_review']=[{'id':'a1','rev':1},{'id':'a1','rev':2}]
  r=self.check(d);self.assertEqual(r.returncode,0,r.stdout)

 def test_init_creates_assertions_journal(self):
  target=self.project/'new'
  subprocess.run([sys.executable,str(ROOT/'scripts/init_project.py'),str(target)],check=True,capture_output=True)
  self.assertTrue((target/'research/assertions.jsonl').is_file())

if __name__=='__main__':unittest.main()
