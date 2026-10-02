"""Checks distributable navigation/init behavior, not scientific correctness."""
from pathlib import Path
import subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
class ConstructionTests(unittest.TestCase):
 def test_method_reference_is_reachable_from_entry(self):
  entry=(ROOT/'SKILL.md').read_text()
  self.assertIn('(references/problem-construction.md)',entry)
  self.assertTrue((ROOT/'references/problem-construction.md').is_file())
 def test_initialized_candidate_separates_knowledge_and_access_probes(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=subprocess.run([sys.executable,str(ROOT/'scripts/init_project.py'),tmp],capture_output=True,text=True)
   self.assertEqual(p.returncode,0,p.stderr)
   text=(Path(tmp)/'opportunities.md').read_text()
   for required in ('知识增量','资源探查','科学判别','验证系统','不可区分'):
    self.assertIn(required,text)
if __name__=='__main__':unittest.main()
