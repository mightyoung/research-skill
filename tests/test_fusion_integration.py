"""Offline distribution/init checks; the agent behavior study is separate."""
from pathlib import Path
import re,subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
class FusionIntegrationTests(unittest.TestCase):
 def test_optional_reference_is_connected_to_existing_workflow_stages(self):
  target=ROOT/'references/transfer-and-engineering.md'
  self.assertTrue(target.is_file(),'optional workflow reference missing')
  for name in ('SKILL.md','references/problem-construction.md','references/opportunity-review.md'):
   p=ROOT/name
   links=re.findall(r'\]\(([^)]+)\)',p.read_text())
   self.assertTrue(any((p.parent/x).resolve()==target.resolve() for x in links if '://' not in x),'unreachable from '+name)
 def test_existing_project_preferences_survive_missing_file_completion(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'project'
   p.mkdir()
   cmd=[sys.executable,str(ROOT/'scripts/init_project.py'),str(p)]
   (p/'research-brief.md').write_text('User: no field data; engineering preference is optional.\n')
   (p/'opportunities.md').write_text('User directions; do not merge or replace.\n')
   before={str(x.relative_to(p)):x.read_bytes() for x in p.rglob('*') if x.is_file()}
   second=subprocess.run(cmd,capture_output=True,text=True)
   self.assertEqual(second.returncode,0,second.stderr)
   for name,body in before.items():self.assertEqual(body,(p/name).read_bytes())
   self.assertTrue((p/'field-judgment.md').is_file())
   self.assertTrue((p/'research/sources.jsonl').is_file())
   complete={str(x.relative_to(p)):x.read_bytes() for x in p.rglob('*') if x.is_file()}
   third=subprocess.run(cmd,capture_output=True,text=True)
   self.assertEqual(third.returncode,0,third.stderr)
   self.assertEqual(complete,{str(x.relative_to(p)):x.read_bytes() for x in p.rglob('*') if x.is_file()})
if __name__=='__main__':unittest.main()
