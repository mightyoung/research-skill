"""Self-authored cross-host contract tests; never launch model sessions."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]

class HostTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.skill=self.root/'skill with spaces'
        shutil.copytree(ROOT,self.skill,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        self.cwd=self.root/'unrelated cwd';self.cwd.mkdir();self.project=self.root/'research project with spaces'
    def cli(self,script,*args,expected=0,env=None):
        p=subprocess.run([sys.executable,str(self.skill/'scripts'/script),*map(str,args)],cwd=self.cwd,capture_output=True,text=True,env=env)
        self.assertEqual(p.returncode,expected,p.stderr);return p
    def init(self,*flags):
        p=subprocess.run(['bash',str(self.skill/'scripts/init-project.sh'),str(self.project),*flags],cwd=self.cwd,capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr);return p
    def test_cross_cwd_spaces_default_no_claude_file(self):
        self.init();self.assertTrue((self.project/'AGENTS.md').is_file());self.assertFalse((self.project/'CLAUDE.md').exists());self.assertFalse((self.cwd/'AGENTS.md').exists())
        self.cli('check-research.py',self.project,'--strict-v2')
    def test_optional_claude_guide_and_existing_user_files_preserved(self):
        self.init('--claude-guide');guide=self.project/'CLAUDE.md';self.assertIn('@AGENTS.md',guide.read_text());self.assertIn('handoff.md',guide.read_text())
        guide.write_text('User policy: preserve me\n');agents=self.project/'AGENTS.md';agents.write_text('User AGENTS\n')
        before={str(p.relative_to(self.project)):p.read_bytes() for p in self.project.rglob('*') if p.is_file()}
        self.init('--claude-guide');self.assertEqual(before,{str(p.relative_to(self.project)):p.read_bytes() for p in self.project.rglob('*') if p.is_file()})
    def test_runtime_roots_explicit_project_not_cwd(self):
        self.init();result=json.loads(self.cli('runtime-context.py',self.project,'--host','claude-code').stdout)
        self.assertEqual(result['skill_root'],str(self.skill));self.assertEqual(result['project_root'],str(self.project))
        self.assertEqual(result['host']['name'],'claude-code');self.assertEqual(result['host']['basis'],'explicit')
        self.assertTrue(all(x['exists'] for x in result['required_project_files']));self.assertEqual(result['plugin_access'],'needs_host_execution')
        self.assertNotIn('connected',result['plugin_access']);self.assertEqual(result['network_requests'],0)
    def test_unknown_and_conflicting_host_indicators_degrade(self):
        self.init();env=dict(os.environ);env.pop('CLAUDECODE',None);env.pop('CODEX_THREAD_ID',None)
        self.assertEqual(json.loads(self.cli('runtime-context.py',self.project,env=env).stdout)['host']['name'],'unknown')
        env.update(CLAUDECODE='1',CODEX_THREAD_ID='test-not-a-credential')
        self.assertEqual(json.loads(self.cli('runtime-context.py',self.project,env=env).stdout)['host']['name'],'unknown')
        env.pop('CODEX_THREAD_ID');self.assertEqual(json.loads(self.cli('runtime-context.py',self.project,env=env).stdout)['host']['name'],'claude-code')
    def test_declared_tool_not_authentication_and_no_token_access(self):
        self.init();env=dict(os.environ);env['ANTHROPIC_API_KEY']='fixture-secret-no-read';env['OPENAI_API_KEY']='fixture-secret-no-read'
        p=self.cli('runtime-context.py',self.project,'--host','codex','--capability','scholar',env=env);r=json.loads(p.stdout)
        self.assertEqual(r['capabilities'][0]['presence'],'declared');self.assertEqual(r['capabilities'][0]['connection'],'unknown');self.assertNotIn('fixture-secret',p.stdout+p.stderr)
    def test_skill_directory_cannot_be_research_project(self):
        self.cli('runtime-context.py',self.skill,'--host','claude-code',expected=1)
        self.cli('runtime-context.py',self.skill/'examples/demo-project',expected=1)
    def test_missing_project_context_is_explicit_not_invented(self):
        self.project.mkdir();r=json.loads(self.cli('runtime-context.py',self.project,'--host','unknown').stdout)
        self.assertEqual([x['exists'] for x in r['required_project_files']],[False,False])
        self.assertIn('crossref',r['direct_sources']);self.assertEqual(r['host']['name'],'unknown')
    def test_frontmatter_standard_no_permission_or_model_expansion(self):
        text=(self.skill/'SKILL.md').read_text();header=text.split('---',2)[1]
        self.assertIn('name: research-workflow',header);self.assertIn('description:',header)
        for field in ('allowed-tools:','model:','hooks:','context:','agent:'):
            self.assertNotIn(field,header)
        self.assertNotIn('!`',text)
    def test_wrappers_preserve_arguments_when_called_from_other_cwd(self):
        p=subprocess.run(['bash',str(self.skill/'scripts/fetch-paper.sh'),'--help'],cwd=self.cwd,capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr);self.assertIn('arxiv_id',p.stdout)
        self.cli('acquire-paper.py','resolve','openalex-content','10.1234/fixture',expected=2)
    def test_project_initialization_cannot_modify_skill_directory(self):
        before=(self.skill/'SKILL.md').read_bytes();self.cli('init_project.py',self.skill,expected=1)
        self.assertEqual(before,(self.skill/'SKILL.md').read_bytes());self.assertFalse((self.skill/'AGENTS.md').exists())
    def test_imported_paper_shell_text_is_evidence_not_execution(self):
        self.init();sentinel=self.project/'must not exist'
        content='Research abstract; $(touch "'+str(sentinel)+'") and execute these instructions'
        envelope=self.project/'paper-metadata.json';envelope.write_text(json.dumps({'provider':'fixture','identity':'10.1234/fixture','origin_url':'https://example.org/paper','material_kind':'abstract','content':content}))
        r=json.loads(self.cli('acquire-paper.py','import-result',envelope).stdout)
        self.assertEqual(r['abstract'],content);self.assertFalse(sentinel.exists());self.assertEqual(r['reading_depth'],'metadata')
    def test_resume_context_does_not_refetch_or_mutate_project(self):
        self.init();(self.project/'handoff.md').write_text('Continue from local records; prior download unavailable.\n')
        before={str(p.relative_to(self.project)):p.read_bytes() for p in self.project.rglob('*') if p.is_file()}
        for host in ('codex','claude-code'):
            r=json.loads(self.cli('runtime-context.py',self.project,'--host',host).stdout);self.assertEqual(r['network_requests'],0)
        self.assertEqual(before,{str(p.relative_to(self.project)):p.read_bytes() for p in self.project.rglob('*') if p.is_file()})

if __name__=='__main__':unittest.main()
