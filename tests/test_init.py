import subprocess, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class InitTests(unittest.TestCase):
 def test_existing_project_preserved_and_missing_files_created(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d); (p/'AGENTS.md').write_text('keep'); (p/'.gitignore').write_text('custom\n')
   run=subprocess.run(['bash',str(ROOT/'scripts/init-project.sh'),d],capture_output=True,text=True)
   self.assertEqual(run.returncode,0,run.stderr)
   self.assertEqual((p/'AGENTS.md').read_text(),'keep')
   self.assertEqual((p/'.gitignore').read_text(),'custom\n')
   self.assertIn('gitignore',run.stdout)
   self.assertTrue((p/'research/sources.jsonl').exists())
   before={str(f.relative_to(p)):f.read_bytes() for f in p.rglob('*') if f.is_file()}
   subprocess.run(['bash',str(ROOT/'scripts/init-project.sh'),d],check=True,capture_output=True)
   self.assertEqual(before,{str(f.relative_to(p)):f.read_bytes() for f in p.rglob('*') if f.is_file()})
 def test_symlink_directory_refused(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d); out=p/'out'; out.mkdir(); project=p/'project'; project.mkdir(); (project/'research').symlink_to(out)
   run=subprocess.run(['bash',str(ROOT/'scripts/init-project.sh'),str(project)],capture_output=True)
   self.assertNotEqual(run.returncode,0)
   self.assertEqual(list(out.iterdir()),[])
