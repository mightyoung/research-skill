"""Offline reference reachability and non-destructive init; semantics tested separately."""
from pathlib import Path
import re, subprocess, sys, tempfile, unittest

ROOT = Path(__file__).resolve().parents[1]

class CriticalReadingIntegrationTests(unittest.TestCase):
    def test_decision_reference_is_reachable_before_final_opportunity_review(self):
        target = ROOT / 'references/critical-reading.md'
        self.assertTrue(target.is_file(), 'critical decision reading reference missing')
        for name in ('SKILL.md', 'references/opportunity-review.md'):
            source = ROOT / name
            links = re.findall(r'\]\(([^)]+)\)', source.read_text())
            self.assertTrue(any((source.parent / link).resolve() == target.resolve()
                                for link in links if '://' not in link), name)

    def test_init_adds_reading_template_without_overwriting_existing_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / 'project'
            project.mkdir()
            (project / 'opportunities.md').write_text('Existing candidate; evidence unknown.\n')
            command = [sys.executable, str(ROOT / 'scripts/init_project.py'), str(project)]
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertTrue((project / 'paper-reading.md').is_file(), 'missing optional note template')
            self.assertEqual((ROOT / 'assets/templates/paper-reading.md').read_bytes(),
                             (project / 'paper-reading.md').read_bytes())
            self.assertEqual((project / 'opportunities.md').read_text(),
                             'Existing candidate; evidence unknown.\n')
            (project / 'paper-reading.md').write_text('User reading decision and limitations.\n')
            before = {str(p.relative_to(project)): p.read_bytes()
                      for p in project.rglob('*') if p.is_file()}
            again = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertEqual(before, {str(p.relative_to(project)): p.read_bytes()
                                     for p in project.rglob('*') if p.is_file()})

if __name__ == '__main__':
    unittest.main()
