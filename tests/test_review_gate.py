"""P1: reviewer reference reachability and pre-execution approval/budget gate."""
import copy,re,unittest
from pathlib import Path
from test_research import STAMP
from test_v2 import bundle,plan
from test_trace import TraceBase
ROOT=Path(__file__).resolve().parents[1]
LATER='2026-10-02T12:00:00Z'
EARLIER='2026-09-30T12:00:00Z'

class ReviewerReferenceTests(unittest.TestCase):
 def test_reviewer_reference_reachable_and_names_checks(self):
  target=ROOT/'references/reviewer.md';self.assertTrue(target.is_file())
  for name in ('SKILL.md','references/opportunity-review.md'):
   source=ROOT/name;links=re.findall(r'\]\(([^)]+)\)',source.read_text())
   self.assertTrue(any((source.parent/l).resolve()==target.resolve() for l in links if '://' not in l),name)
  text=target.read_text()
  for term in ('[kind/id@rev]','provenance','strongest_rival','pending_questions'):self.assertIn(term,text)

class ApprovalGateTests(TraceBase):
 def approved_plan(self,at=STAMP,limit=1):
  p=plan();p['budget']={'limit':limit,'unit':'CPU-hour'};p['approval']={'by':'PI','at':at,'scope':'1 CPU-hour on local split'};return p
 def run_row(self,spent=0.5,executed_at=LATER,**extra):
  actual={'executed_at':executed_at,'measured_values':[0.51],'result':'inconclusive','discriminating':False,'reason':'overlap','budget_spent':spent,'execution_state':'technical_failure'}
  actual.update(extra)
  return dict(schema_version=2,id='run1',rev=1,updated_at=LATER,review_status='current',phase='executed',plan_ref={'id':'e1','rev':1},actual=actual)
 def data(self,p,run):
  d=bundle();d['experiments']=[p,run];return d
 def test_approved_within_budget_passes_strict(self):
  r=self.check(self.data(self.approved_plan(),self.run_row()),'--strict-v2');self.assertEqual(r.returncode,0,r.stdout)
 def test_missing_approval_noted_then_strict_fails(self):
  r=self.check(self.data(plan(),self.run_row()));self.assertEqual(r.returncode,0,r.stdout);self.assertIn('no recorded approval',r.stdout)
  r=self.check(self.data(plan(),self.run_row()),'--strict-v2');self.assertNotEqual(r.returncode,0);self.assertIn('approval',r.stdout)
 def test_malformed_or_late_approval_fails(self):
  for approval in [{'by':'','at':STAMP,'scope':'x'},{'by':'PI','at':'yesterday','scope':'x'},{'by':'PI','at':STAMP},{'by':'PI','at':STAMP,'scope':'x','verified':True}]:
   p=plan();p['approval']=approval;r=self.check(self.data(p,self.run_row()));self.assertNotEqual(r.returncode,0,approval);self.assertIn('approval',r.stdout)
  r=self.check(self.data(self.approved_plan(at=LATER),self.run_row(executed_at=EARLIER)));self.assertNotEqual(r.returncode,0);self.assertIn('before execution',r.stdout)
 def test_overrun_requires_separate_prior_approval(self):
  r=self.check(self.data(self.approved_plan(),self.run_row(spent=3)),'--strict-v2');self.assertNotEqual(r.returncode,0);self.assertIn('overrun',r.stdout)
  r=self.check(self.data(self.approved_plan(),self.run_row(spent=3)));self.assertEqual(r.returncode,0,r.stdout);self.assertIn('overrun',r.stdout)
  ok=self.run_row(spent=3,overrun_approval={'by':'PI','at':STAMP,'scope':'extend to 3 CPU-hour'})
  r=self.check(self.data(self.approved_plan(),ok),'--strict-v2');self.assertEqual(r.returncode,0,r.stdout)
 def test_late_overrun_approval_rejected_in_both_modes(self):
  late=self.run_row(spent=3,overrun_approval={'by':'PI','at':'2099-01-01T00:00:00Z','scope':'extend to 3 CPU-hour'})
  for args in [(),('--strict-v2',)]:
   result=self.check(self.data(self.approved_plan(),late),*args)
   self.assertNotEqual(result.returncode,0,result.stdout)
   self.assertIn('overrun_approval',result.stdout)
   self.assertIn('before execution',result.stdout)
 def test_planned_approval_is_not_a_result(self):
  p=self.approved_plan();p['approval']['result']='supporting'
  r=self.check(self.data(p,self.run_row()));self.assertNotEqual(r.returncode,0)

if __name__=='__main__':unittest.main()
