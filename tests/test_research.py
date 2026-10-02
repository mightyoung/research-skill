import copy,json,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STAMP='2026-10-01T12:00:00Z'
def sample():
 return {
 'sources':[dict(id='s1',rev=1,updated_at=STAMP,url='https://example.org/paper',retrieved_at=STAMP,status='active')],
 'papers':[dict(id='p1-v1',rev=1,updated_at=STAMP,source_id='s1',source_rev=1,work_id='w1',arxiv_id='2301.11305',version='v1',doi=None,title='Fixture',publication_status='preprint',reading_depth='full_text',review_status='current')],
 'claims':[dict(id='c1',rev=1,updated_at=STAMP,paper_id='p1-v1',paper_rev=1,statement='Fixture result',basis='full_text',locator={'version':'v1','page':4,'table':'2'},review_status='current')],
 'opportunities':[dict(id='o1',rev=1,updated_at=STAMP,title='Candidate',status='ready',supports=[{'id':'c1','rev':1}],refutes=[],gates={k:'pass' for k in ['data','compute','time','baseline','ethics']},closest_work={'queries':['nearest equivalent problem method'],'searched_at':STAMP,'decision':'distinct','rationale':'different tested condition'},minimal_experiment={'hypothesis':'measurable improvement','baseline':'strong baseline','metric':'accuracy','budget':'1 CPU hour','falsifier':'no gain'},stop_conditions=['no gain'],review_note='Human reviewed evidence')]
 }
class ResearchTests(unittest.TestCase):
 def run_check(self,data,*args):
  self.assertTrue((ROOT/'scripts/check-research.py').exists(),'validator missing')
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup); root=Path(t.name); (root/'research').mkdir()
  for kind,rows in data.items(): (root/'research'/f'{kind}.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
  run=subprocess.run(['python3',str(ROOT/'scripts/check-research.py'),str(root),*args],capture_output=True,text=True)
  return run,root
 def test_valid_ready(self):
  run,_=self.run_check(sample());self.assertEqual(run.returncode,0,run.stdout+run.stderr)
 def test_data_unknown_blocks_ready_but_candidate_permitted(self):
  d=sample();d['opportunities'][0]['gates']['data']='unknown'
  run,_=self.run_check(d);self.assertNotEqual(run.returncode,0);self.assertIn('data',run.stdout)
  d['opportunities'][0]['status']='candidate';run,_=self.run_check(d);self.assertEqual(run.returncode,0,run.stdout)
 def test_unavailable_data_blocks_ready(self):
  d=sample();d['opportunities'][0]['gates']['data']='fail';run,_=self.run_check(d);self.assertNotEqual(run.returncode,0)
 def test_abstract_cannot_be_fulltext_evidence(self):
  d=sample();d['papers'][0]['reading_depth']='abstract';run,_=self.run_check(d);self.assertNotEqual(run.returncode,0);self.assertIn('reading',run.stdout)
 def test_locator_version_and_foreign_key(self):
  for field,value in [('paper_rev',2),('locator',{'version':'v2','page':4})]:
   d=sample();d['claims'][0][field]=value;run,_=self.run_check(d);self.assertNotEqual(run.returncode,0)
 def test_duplicate_version_identity_rejected(self):
  d=sample();p=copy.deepcopy(d['papers'][0]);p['id']='alias';d['papers'].append(p)
  run,_=self.run_check(d);self.assertNotEqual(run.returncode,0);self.assertIn('duplicate',run.stdout)
 def test_versions_one_independent_work(self):
  d=sample();p=copy.deepcopy(d['papers'][0]);p.update(id='p1-v2',version='v2');d['papers'].append(p);d['claims']=[];d['opportunities']=[]
  run,_=self.run_check(d);self.assertIn('independent_works=1',run.stdout)
 def test_doi_normalization_dedup_and_link(self):
  d=sample();d['papers'][0]['doi']='https://doi.org/10.1000/Test';p=copy.deepcopy(d['papers'][0]);p.update(id='p1-v2',version='v2',work_id='wrong',doi='10.1000/test');d['papers'].append(p)
  run,_=self.run_check(d);self.assertNotEqual(run.returncode,0);self.assertIn('work_id',run.stdout)
 def test_covered_idea_cannot_be_ready(self):
  d=sample();d['opportunities'][0]['closest_work']['decision']='covered';run,_=self.run_check(d);self.assertNotEqual(run.returncode,0)
  d['opportunities'][0]['status']='rejected';run,_=self.run_check(d);self.assertEqual(run.returncode,0,run.stdout)
 def test_evidence_revision_marks_transitive_review_preserves_history(self):
  d=sample();s=copy.deepcopy(d['sources'][0]);s.update(rev=2,status='retracted');d['sources'].append(s)
  run,root=self.run_check(d,'--mark-review');self.assertNotEqual(run.returncode,0,run.stdout)
  for kind in ['papers','claims','opportunities']:
   rows=[json.loads(x) for x in (root/'research'/f'{kind}.jsonl').read_text().splitlines()]
   self.assertEqual(len(rows),2);self.assertEqual(rows[0],d[kind][0]);self.assertEqual(rows[-1]['rev'],2)
  before={p.name:p.read_bytes() for p in (root/'research').glob('*.jsonl')}
  subprocess.run(['python3',str(ROOT/'scripts/check-research.py'),str(root),'--mark-review'],capture_output=True)
  self.assertEqual(before,{p.name:p.read_bytes() for p in (root/'research').glob('*.jsonl')})
 def test_malformed_rows_and_missing_journal_report_without_traceback(self):
  for data in [{'sources':[None],'papers':[],'claims':[],'opportunities':[]},{'sources':[]}]:
   run,_=self.run_check(data);self.assertNotEqual(run.returncode,0);self.assertNotIn('Traceback',run.stderr)
 def test_revision_must_be_monotone_and_located(self):
  d=sample();d['claims'][0]['locator']={'version':'v1'};run,_=self.run_check(d);self.assertNotEqual(run.returncode,0)
  d=sample();d['sources'].append(copy.deepcopy(d['sources'][0]));run,_=self.run_check(d);self.assertNotEqual(run.returncode,0)

 def test_new_paper_version_marks_existing_claim_and_opportunity(self):
  d=sample();p=copy.deepcopy(d['papers'][0]);p.update(id='p1-v2',version='v2');d['papers'].append(p)
  run,root=self.run_check(d,'--mark-review');self.assertNotEqual(run.returncode,0);self.assertIn('needs_review',run.stdout)
  rows=[json.loads(x) for x in (root/'research/opportunities.jsonl').read_text().splitlines()]
  self.assertEqual(rows[-1]['status'],'needs_review')
 def test_circular_dependencies_rejected(self):
  d=sample();d['sources'][0]['depends_on']=[{'kind':'claims','id':'c1','rev':1}]
  run,_=self.run_check(d);self.assertNotEqual(run.returncode,0);self.assertIn('cycle',run.stdout)
 def test_reviewed_older_version_can_remain_valid_after_comparison(self):
  d=sample();p=copy.deepcopy(d['papers'][0]);p.update(id='p1-v2',version='v2');d['papers'].append(p)
  old=copy.deepcopy(d['papers'][0]);old.update(rev=2,reviewed_against={'id':'p1-v2','rev':1},review_note='Compared v2 full text, table 2 unchanged');d['papers'].append(old)
  d['claims'][0]['paper_rev']=2
  run,_=self.run_check(d);self.assertEqual(run.returncode,0,run.stdout)
 def test_retirement_preserves_history_without_permanent_fail(self):
  d=sample();s=copy.deepcopy(d['sources'][0]);s.update(rev=2,status='retracted');d['sources'].append(s)
  for kind in ['papers','claims','opportunities']:
   r=copy.deepcopy(d[kind][0]);r.update(rev=2,active=False,review_note='Retired after retraction review')
   if kind=='opportunities':r['status']='rejected'
   d[kind].append(r)
  run,root=self.run_check(d,'--mark-review');self.assertEqual(run.returncode,0,run.stdout)
  for kind in ['papers','claims','opportunities']:
   self.assertEqual(len((root/'research'/f'{kind}.jsonl').read_text().splitlines()),2)
 def test_active_opportunity_cannot_depend_on_retired_claim(self):
  d=sample();d['claims'][0].update(active=False,review_note='Retired evidence');run,_=self.run_check(d);self.assertNotEqual(run.returncode,0)
 def test_retired_ready_cannot_hide_invalid_decision(self):
  d=sample();d['opportunities'][0].update(active=False,review_note='hide');run,_=self.run_check(d);self.assertNotEqual(run.returncode,0)
 def test_compared_new_version_change_triggers_review_again(self):
  for change in ('v3','revision'):
   d=sample();p=copy.deepcopy(d['papers'][0]);p.update(id='p1-v2',version='v2');d['papers'].append(p)
   old=copy.deepcopy(d['papers'][0]);old.update(rev=2,reviewed_against={'id':'p1-v2','rev':1},review_note='Comparison performed');d['papers'].append(old);d['claims'][0]['paper_rev']=2
   if change=='v3':p=copy.deepcopy(p);p.update(id='p1-v3',version='v3')
   else:p=copy.deepcopy(p);p.update(rev=2,reading_depth='skim')
   d['papers'].append(p);run,_=self.run_check(d);self.assertNotEqual(run.returncode,0);self.assertIn('needs_review',run.stdout)
 def test_mark_review_handles_missing_final_newline(self):
  d=sample();s=copy.deepcopy(d['sources'][0]);s.update(rev=2,status='updated');d['sources'].append(s)
  _,root=self.run_check(d)
  for p in (root/'research').glob('*.jsonl'):p.write_bytes(p.read_bytes().rstrip(b'\n'))
  run=subprocess.run(['python3',str(ROOT/'scripts/check-research.py'),str(root),'--mark-review'],capture_output=True,text=True)
  self.assertNotIn('Traceback',run.stderr)
  for kind in ['papers','claims','opportunities']:
   rows=[json.loads(line) for line in (root/'research'/f'{kind}.jsonl').read_text().splitlines()]
   self.assertEqual(len(rows),2)
