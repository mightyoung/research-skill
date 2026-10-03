"""Own research assertions: separate from paper claims, state backed by typed evidence."""
import copy,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from test_research import STAMP
from test_v2 import bundle,plan
ROOT=Path(__file__).resolve().parents[1]

def run(result='supporting',discriminating=True,state='completed',rid='r1'):
 return dict(schema_version=2,id=rid,rev=1,updated_at=STAMP,review_status='current',phase='executed',plan_ref={'id':'e1','rev':1},actual={'executed_at':STAMP,'measured_values':[0.61,0.52],'result':result,'discriminating':discriminating,'reason':'intervals separate','budget_spent':0.5,'execution_state':state})
def assertion(state='untested',evidence=(),**extra):
 row=dict(schema_version=2,id='a1',rev=1,updated_at=STAMP,review_status='current',statement='Rework resets step completion; history-only trackers miss it',assertion_state=state,opportunity={'id':'o1','rev':1},evidence=list(evidence),does_not_support=['all assembly lines','online deployment'])
 row.update(extra);return row
SUP={'kind':'experiments','id':'r1','rev':1,'role':'supports'}

class AssertionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.project=Path(self.tmp.name);(self.project/'research').mkdir()
 def check(self,data,*args):
  for kind,rows in data.items():(self.project/'research'/f'{kind}.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows),encoding='utf-8')
  return subprocess.run([sys.executable,str(ROOT/'scripts/check-research.py'),str(self.project),*args],capture_output=True,text=True)
 def data(self,*runs,**assertion_args):
  d=bundle();d['experiments']=[plan(),*runs];d['assertions']=[assertion(**assertion_args)];return d

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

 def test_init_creates_assertions_journal(self):
  target=self.project/'new'
  subprocess.run([sys.executable,str(ROOT/'scripts/init_project.py'),str(target)],check=True,capture_output=True)
  self.assertTrue((target/'research/assertions.jsonl').is_file())

if __name__=='__main__':unittest.main()
