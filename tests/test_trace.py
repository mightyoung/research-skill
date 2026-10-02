import copy,hashlib,json,subprocess,tempfile,unittest
from pathlib import Path
from test_research import sample,STAMP
from test_v2 import bundle,plan
ROOT=Path(__file__).resolve().parents[1]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

class TraceBase(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.project=Path(self.tmp.name);(self.project/'research').mkdir()
 def check(self,data,*args):
  for kind,rows in data.items():(self.project/'research'/f'{kind}.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows),encoding='utf-8')
  return subprocess.run(['python3',str(ROOT/'scripts/check-research.py'),str(self.project),*args],capture_output=True,text=True)
 def report(self,text,name='REPORT.md'):
  path=self.project/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')

class DeliverableTraceTests(TraceBase):
 def test_resolving_citation_passes_without_number_note(self):
  self.report('基线 0.51 高于朴素 0.49 [claims/c1@1]\n')
  r=self.check(sample());self.assertEqual(r.returncode,0,r.stdout);self.assertNotIn('untraced number',r.stdout)
 def test_missing_id_or_revision_fails(self):
  for ref in ['claims/c9@1','claims/c1@2','widgets/c1@1']:
   self.report(f'结论 [{ref}]\n');r=self.check(sample());self.assertNotEqual(r.returncode,0,ref);self.assertIn('REPORT.md:1',r.stdout)
 def test_superseded_revision_is_stale(self):
  d=sample();newer=copy.deepcopy(d['claims'][0]);newer.update(rev=2);d['claims'].append(newer)
  self.report('旧结论 [claims/c1@1]\n');r=self.check(d);self.assertNotEqual(r.returncode,0);self.assertIn('REPORT.md:1',r.stdout);self.assertIn('stale',r.stdout)
 def test_untraced_number_is_noted_not_failed(self):
  self.report('增益 0.49→0.51，提升 4%\n基线均0.51\n')
  r=self.check(sample());self.assertEqual(r.returncode,0,r.stdout)
  for n in (1,2):self.assertIn(f'REPORT.md:{n}: untraced number',r.stdout)
 def test_code_fences_comments_and_versions_ignored(self):
  self.report('<!-- Apache-2.0 -->\n```\n[claims/c9@1] 0.5\n```\n版本 v6.3 日期 2026-10-01\n')
  r=self.check(sample());self.assertEqual(r.returncode,0,r.stdout);self.assertNotIn('untraced',r.stdout)
 def test_experiment_results_scanned(self):
  self.report('| v1 | baseline | 0.51 | [experiments/run9@1] |\n','experiment/results.md')
  r=self.check(sample());self.assertNotEqual(r.returncode,0);self.assertIn('experiment/results.md:1',r.stdout)
 def test_symlinked_deliverable_refused(self):
  outside=Path(self.tmp.name+'-outside.md');outside.write_text('[claims/c9@1]\n');self.addCleanup(outside.unlink)
  (self.project/'LINK.md').symlink_to(outside);r=self.check(sample());self.assertNotEqual(r.returncode,0);self.assertIn('symlink',r.stdout)
 def test_symlinked_experiment_directory_refused_without_external_citation_read(self):
  outside=Path(self.tmp.name+'-external');outside.mkdir();self.addCleanup(lambda:outside.rmdir())
  report=outside/'results.md';report.write_text('[claims/privateoutside@1]\n');self.addCleanup(report.unlink)
  (self.project/'experiment').symlink_to(outside,target_is_directory=True)
  result=self.check(sample());self.assertNotEqual(result.returncode,0,result.stdout)
  self.assertIn('symlink',result.stdout)
  self.assertNotIn('privateoutside',result.stdout)
 def test_mark_review_not_blocked_by_deliverable_errors(self):
  d=sample();newer=copy.deepcopy(d['claims'][0]);newer.update(rev=2);d['claims'].append(newer)
  self.report('[claims/c9@1]\n');r=self.check(d,'--mark-review');self.assertNotEqual(r.returncode,0)
  self.assertIn('needs_review',(self.project/'research/opportunities.jsonl').read_text())

class ExperimentProvenanceTests(TraceBase):
 def run_row(self,**actual):
  base={'executed_at':STAMP,'measured_values':[0.51,0.50],'result':'inconclusive','discriminating':False,'reason':'too little separation','budget_spent':0.5,'execution_state':'completed'}
  base.update(actual)
  return dict(schema_version=2,id='run1',rev=1,updated_at=STAMP,review_status='current',phase='executed',plan_ref={'id':'e1','rev':1},actual=base)
 def provenance(self):
  env=self.project/'env/requirements.lock';env.parent.mkdir();env.write_text('numpy==2.1.0\n')
  out=self.project/'experiment/runs/run1/metrics.json';out.parent.mkdir(parents=True);out.write_text('{"acc": 0.51}\n')
  return {'code':{'repo':'experiment','commit':'a'*40},'command':'python3 train.py --seed 1','environment':{'path':'env/requirements.lock','sha256':sha(env)},'outputs':[{'path':'experiment/runs/run1/metrics.json','sha256':sha(out)}]}
 def data(self,run):
  p=plan();p['approval']={'by':'PI','at':STAMP,'scope':'1 CPU-hour'};d=bundle();d['experiments']=[p,run];return d
 def test_traceable_run_passes_strict(self):
  r=self.check(self.data(self.run_row(provenance=self.provenance())),'--strict-v2');self.assertEqual(r.returncode,0,r.stdout);self.assertIn('local binding matched: experiment/runs/run1/metrics.json',r.stdout)
 def test_changed_output_makes_run_stale(self):
  d=self.data(self.run_row(provenance=self.provenance()));(self.project/'experiment/runs/run1/metrics.json').write_text('{"acc": 0.99}\n')
  r=self.check(d);self.assertNotEqual(r.returncode,0);self.assertIn('experiments/run1',r.stdout);self.assertIn('needs_review',r.stdout)
 def test_invalid_provenance_fields_fail(self):
  good=self.provenance()
  for key,value in [('code',{'repo':'experiment','commit':'HEAD'}),('command',''),('outputs',[]),('environment',{'path':'../x','sha256':'0'*64}),('verified',True)]:
   p=copy.deepcopy(good);p[key]=value
   r=self.check(self.data(self.run_row(provenance=p)));self.assertNotEqual(r.returncode,0,key);self.assertIn('provenance',r.stdout,key)
 def test_missing_provenance_noted_and_strict_fails_only_completed(self):
  r=self.check(self.data(self.run_row()));self.assertEqual(r.returncode,0,r.stdout);self.assertIn('not traceable',r.stdout)
  r=self.check(self.data(self.run_row()),'--strict-v2');self.assertNotEqual(r.returncode,0);self.assertIn('provenance',r.stdout)
  r=self.check(self.data(self.run_row(execution_state='technical_failure')),'--strict-v2');self.assertEqual(r.returncode,0,r.stdout)

if __name__=='__main__':unittest.main()
