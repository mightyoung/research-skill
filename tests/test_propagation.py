"""Staleness propagation across pinned dependencies, arXiv versions and reverse assertion links."""
import copy,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from test_research import sample
from test_v2 import bundle,plan
from test_assertions import assertion,run,SUP
ROOT=Path(__file__).resolve().parents[1]
LATER='2026-10-02T00:00:00Z'

def bump(rows,rid,**changes):
 row=copy.deepcopy([r for r in rows if r['id']==rid][-1]);row.update(rev=row['rev']+1,updated_at=LATER);row.update(changes);rows.append(row)

class PropagationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.project=Path(self.tmp.name);(self.project/'research').mkdir()
 def check(self,data,*args):
  for kind,rows in data.items():(self.project/'research'/f'{kind}.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
  r=subprocess.run([sys.executable,str(ROOT/'scripts/check-research.py'),str(self.project),*args],capture_output=True,text=True)
  return r,{line.split(':')[0] for line in r.stdout.splitlines() if 'needs_review:' in line}
 def stale(self,data,expected,*args):
  r,found=self.check(data,*args);self.assertEqual(found,set(expected),r.stdout)
  self.assertEqual(r.returncode,1 if expected else 0,r.stdout)
  return r

 # Pinned chain s1 -> p1-v1 -> c1 -> o1: a newer revision or a bad status moves everything downstream.
 def test_new_source_revision_reaches_whole_chain(self):
  d=sample();bump(d['sources'],'s1',url='https://example.org/paper-v2')
  self.stale(d,{'papers/p1-v1','claims/c1','opportunities/o1'})
 def test_retracted_source_and_paper_reach_whole_chain(self):
  d=sample();bump(d['sources'],'s1',status='retracted');self.stale(d,{'papers/p1-v1','claims/c1','opportunities/o1'})
  d=sample();bump(d['papers'],'p1-v1',publication_status='retracted');self.stale(d,{'papers/p1-v1','claims/c1','opportunities/o1'})
 def test_claim_revision_stales_only_its_dependents_until_repinned(self):
  d=sample();bump(d['claims'],'c1',statement='revised');self.stale(d,{'opportunities/o1'})
  bump(d['opportunities'],'o1',supports=[{'id':'c1','rev':2}]);self.stale(d,set())
 def test_retired_record_is_not_reported(self):
  d=sample();bump(d['opportunities'],'o1',active=False,status='rejected',review_note='retired');self.stale(d,set())
 def test_mark_review_appends_and_stays_failing_until_repinned(self):
  d=sample();bump(d['sources'],'s1',url='https://example.org/paper-v2');self.check(d)
  r=subprocess.run([sys.executable,str(ROOT/'scripts/check-research.py'),str(self.project),'--mark-review'],capture_output=True,text=True);self.assertEqual(r.returncode,1,r.stdout)
  rows=[json.loads(l) for l in (self.project/'research/claims.jsonl').read_text().splitlines()]
  self.assertEqual([x['rev'] for x in rows],[1,2]);self.assertEqual(rows[1]['review_status'],'needs_review');self.assertEqual(rows[0]['review_status'],'current')
  r,found=self.check({});self.assertEqual(r.returncode,1)

 # A newer arXiv version makes the older paper stale until a full-text comparison is recorded.
 def versions(self,depth):
  d=sample();v2=copy.deepcopy(d['papers'][0]);v2.update(id='p1-v2',version='v2',reading_depth=depth,updated_at=LATER);d['papers'].append(v2);return d
 def test_newer_arxiv_version_stales_older_paper_and_dependents(self):
  self.stale(self.versions('abstract'),{'papers/p1-v1','claims/c1','opportunities/o1'})
  self.stale(self.versions('full_text'),{'papers/p1-v1','claims/c1','opportunities/o1'})
 def test_comparison_needs_fulltext_newer_version_and_note(self):
  d=self.versions('full_text');bump(d['papers'],'p1-v1',reviewed_against={'id':'p1-v2','rev':1},review_note='compared full text')
  self.stale(d,{'claims/c1','opportunities/o1'})
  bump(d['claims'],'c1',paper_rev=2);self.stale(d,{'opportunities/o1'})
  bump(d['opportunities'],'o1',supports=[{'id':'c1','rev':2}]);self.stale(d,set())
  d=self.versions('abstract');bump(d['papers'],'p1-v1',reviewed_against={'id':'p1-v2','rev':1},review_note='compared');self.stale(d,{'papers/p1-v1','claims/c1','opportunities/o1'})
 def test_comparison_is_pinned_so_newer_revision_reopens_it(self):
  d=self.versions('full_text');bump(d['papers'],'p1-v1',reviewed_against={'id':'p1-v2','rev':1},review_note='compared full text')
  bump(d['claims'],'c1',paper_rev=2);bump(d['opportunities'],'o1',supports=[{'id':'c1','rev':2}]);self.stale(d,set())
  bump(d['papers'],'p1-v2',title='v2 corrected');self.stale(d,{'papers/p1-v1','claims/c1','opportunities/o1'})

 # V2 pins: structured critical_unknown and decisive_neighbors propagate; prose does not.
 def unknown(self,pinned=True):
  d=bundle();other=copy.deepcopy(d['papers'][0]);other.update(id='p2-v1',work_id='w2',arxiv_id='2301.11306',title='Possible covering work',reading_depth='targeted_body',reading_scope='evaluation read; appendix not read');d['papers'].append(other)
  o=d['opportunities'][0];o.update(status='candidate',decision='continue')
  o['critical_unknown']=[{'paper':{'id':'p2-v1','rev':1},'gap':'may already score human revisions'}] if pinned else ['whether p2 covers revisions']
  return d
 def test_critical_unknown_pin_propagates_and_repins(self):
  d=self.unknown();self.stale(d,set(),'--strict-v2')
  bump(d['papers'],'p2-v1',reading_scope='evaluation and appendix read');self.stale(d,{'opportunities/o1'})
  bump(d['opportunities'],'o1',critical_unknown=[{'paper':{'id':'p2-v1','rev':2},'gap':'may already score human revisions'}]);self.stale(d,set())
 def test_retracted_unknown_paper_stales_direction(self):
  d=self.unknown();bump(d['papers'],'p2-v1',publication_status='retracted');self.stale(d,{'papers/p2-v1','opportunities/o1'})
 def test_prose_unknown_does_not_propagate(self):
  d=self.unknown(False);bump(d['papers'],'p2-v1',reading_scope='appendix read');self.stale(d,set())
 def test_decisive_neighbor_pin_propagates(self):
  d=self.unknown();bump(d['papers'],'p1-v1',reading_scope='appendix read');self.stale(d,{'claims/c1','opportunities/o1'})

 # Assertions reach their direction through an unpinned reverse link, which avoids a stale cycle.
 def assertions(self):
  d=bundle();d['experiments']=[plan(),run()];d['assertions']=[assertion(state='supported',evidence=[SUP])];d['opportunities'][0]['assertion_review']=[{'id':'a1','rev':1}];return d
 def test_unacknowledged_assertion_revision_reopens_direction_until_acknowledged(self):
  d=self.assertions();self.stale(d,set())
  bump(d['assertions'],'a1');self.stale(d,{'opportunities/o1'})
  bump(d['opportunities'],'o1',assertion_review=[{'id':'a1','rev':2}]);self.stale(d,set())
 def test_stale_evidence_flows_assertion_then_direction(self):
  d=self.assertions();bump(d['experiments'],'r1',review_status='needs_review')
  self.stale(d,{'experiments/r1','assertions/a1','opportunities/o1'})
 def test_pinned_cycles_through_assertion_are_rejected(self):
  d=self.assertions();d['assertions'][0]['depends_on']=[{'kind':'opportunities','id':'o1','rev':1}]
  r,_=self.check(d);self.assertNotEqual(r.returncode,0);self.assertIn('assertion is on a stale cycle',r.stdout)
  d=self.assertions();d['opportunities'][0]['depends_on']=[{'kind':'assertions','id':'a1','rev':1}]
  r,_=self.check(d);self.assertNotEqual(r.returncode,0);self.assertIn('cycle in pinned provenance graph',r.stdout)

if __name__=='__main__':unittest.main()
