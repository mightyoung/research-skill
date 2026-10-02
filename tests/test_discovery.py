"""Template behavior tests; static guidance checks do not certify research quality."""
import hashlib,json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]

class DiscoveryTests(unittest.TestCase):
    def scoped_check(self,scope):
        from test_research import sample
        data=sample();data['opportunities']=[]
        data['papers'][0]['reading_depth']='targeted_body'
        if scope is not None:data['papers'][0]['reading_scope']=scope
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();(root/'research').mkdir()
            for kind,rows in data.items():(root/'research'/f'{kind}.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            return subprocess.run([sys.executable,str(ROOT/'scripts/check-research.py'),str(root)],capture_output=True,text=True)
    def test_targeted_body_can_support_located_statement_without_claiming_full_read(self):
        p=self.scoped_check('Read method section 3 and table 2; introduction and supplement not read.')
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertIn('not a truth or originality certification',p.stdout)
    def test_targeted_body_requires_declared_reading_scope(self):
        p=self.scoped_check(None);self.assertNotEqual(p.returncode,0);self.assertIn('reading_scope',p.stdout)
    def test_one_page_judgment_is_created_and_user_changes_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()/'project'
            cmd=[sys.executable,str(ROOT/'scripts/init_project.py'),str(root)]
            p=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr)
            report=root/'field-judgment.md';self.assertTrue(report.exists(),'one-page synthesis absent')
            self.assertIn('瓶颈',report.read_text());report.write_text('User judgment, do not replace\n')
            before={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            p=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual(before,{str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()})
    def test_brief_carries_query_analysis_plan_and_landscape_uses_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()/'project'
            p=subprocess.run([sys.executable,str(ROOT/'scripts/init_project.py'),str(root)],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr)
            brief=(root/'research-brief.md').read_text()
        for required in ('## 查询分析','问题形状','直接型','横向型','纵深型','术语变体','子问题','检索预算档','停止条件'):
            self.assertIn(required,brief)
        guide=(ROOT/'references/landscape.md').read_text()
        for required in ('问题形状','先宽后窄','subq'):
            self.assertIn(required,guide)
        self.assertIn('subq',(ROOT/'references/evidence-schema.md').read_text())
    def test_discovery_and_review_guidance_are_distinct_without_quality_certification(self):
        guide=ROOT/'references/field-discovery.md';self.assertTrue(guide.exists())
        text=guide.read_text()
        for required in ('discover','review','决定性近邻','原数据已支持','需要新增标注','待核实','最强替代解释'):
            self.assertIn(required,text)
        self.assertIn('不是科研质量认证',text)

if __name__=='__main__':unittest.main()
