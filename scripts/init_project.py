#!/usr/bin/env python3
"""Local modification 2026-10-01: exclusive, non-destructive project initialization."""
import argparse
import os
from pathlib import Path

IGNORE='''DataSet/
related_work/
experiment/**/checkpoints/
experiment/**/*.pt
.shot-tmp/
__pycache__/
'''

def initialize(destination,claude_guide=False):
 root=Path(destination).absolute()
 # macOS /var and /tmp aliases are normal; reject destination itself.
 if root.is_symlink(): raise ValueError(f'symlink path refused: {root}')
 root=root.parent.resolve()/root.name
 skill=Path(__file__).resolve().parents[1]
 if root==skill or skill in root.parents: raise ValueError('research project must be outside skill directory')
 root.mkdir(parents=True,exist_ok=True)
 directories=['related_work','复现','experiment','DataSet','research']
 for rel in directories:
  p=root/rel
  if p.is_symlink() or (p.exists() and not p.is_dir()): raise ValueError(f'unsafe directory: {p}')
 for rel in directories: (root/rel).mkdir(exist_ok=True)
 templates=Path(__file__).resolve().parents[1]/'assets/templates'
 mapping={'AGENTS.md':'AGENTS.md','handoff.md':'handoff.md','brainstorm.md':'brainstorm.md','dataset.md':'dataset.md','results.md':'experiment/results.md','evaluation.md':'experiment/evaluation.md','research-brief.md':'research-brief.md','landscape.md':'landscape.md','opportunities.md':'opportunities.md','tensions.md':'tensions.md','research-evaluation.md':'research-evaluation.md'}
 if claude_guide: mapping['CLAUDE.md']='CLAUDE.md'
 mapping['field-judgment.md']='field-judgment.md'
 mapping['paper-reading.md']='paper-reading.md'
 files={dest:(templates/src).read_bytes() for src,dest in mapping.items()}
 files.update({f'research/{name}.jsonl':b'' for name in ['sources','papers','claims','opportunities','searches','tensions','experiments','failures','handoffs','assertions']})
 files['.gitignore']=IGNORE.encode()
 for rel,data in files.items():
  p=root/rel
  try:
   fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o644)
  except FileExistsError:
   print(f'exists, preserved: {rel}')
   if rel=='.gitignore':
    print('gitignore preserved: review required; add related_work/, DataSet/ and experiment checkpoints exclusions manually before git add. No automatic merge.')
   continue
  with os.fdopen(fd,'wb') as f: f.write(data)
  print(f'created: {rel}')
 print('Fill research-brief.md; enter landscape before selecting opportunities. Unknown resources permit reading, not ready status.')

def main():
 p=argparse.ArgumentParser(description=__doc__); p.add_argument('destination'); p.add_argument('--claude-guide',action='store_true',help='create a small CLAUDE.md guide only if absent'); args=p.parse_args()
 try: initialize(args.destination,args.claude_guide)
 except (OSError,ValueError) as e: p.exit(1,str(e)+'\n')
if __name__=='__main__': main()
