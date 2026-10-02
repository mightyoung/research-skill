"""Deliverable citation tracing: [kind/id@rev] must resolve to a current journal record.

Checks reference resolution and freshness only; never whether the cited record supports the sentence.
"""
import re
from pathlib import Path

REF=re.compile(r'\[([a-z]+)/([A-Za-z0-9][A-Za-z0-9_.:-]{0,127})@([1-9]\d*)\]')
# Decimals and percentages only: years, dates, page numbers and v6.3-style versions are not flagged.
# ASCII boundaries on purpose: \w matches CJK, which would hide numbers written directly after Chinese text.
NUMBER=re.compile(r'(?<![A-Za-z0-9_.\-])\d+\.\d+(?![A-Za-z0-9_.])|(?<![A-Za-z0-9_.])\d+(?:\.\d+)?%')
COMMENT=re.compile(r'<!--.*?-->',re.S)
TEXT_LIMIT=16*1024*1024

def deliverables(project):
 experiment=project/'experiment'
 # Refuse a linked directory before traversing it, not just linked leaf files.
 return sorted(project.glob('*.md'))+(sorted(experiment.glob('*.md')) if not experiment.is_symlink() else [])

def trace(project,latest,stale):
 errors=[];notes=[]
 if (project/'experiment').is_symlink():errors.append('experiment: symlink deliverable directory refused')
 for path in deliverables(project):
  name=path.relative_to(project).as_posix()
  if path.is_symlink():errors.append(f'{name}: symlink deliverable refused');continue
  if not path.is_file() or path.stat().st_size>TEXT_LIMIT:errors.append(f'{name}: deliverable unreadable or over 16 MiB');continue
  try:text=COMMENT.sub(lambda m:'\n'*m.group().count('\n'),path.read_text(encoding='utf-8-sig'))
  except (OSError,UnicodeDecodeError):errors.append(f'{name}: deliverable must be UTF-8');continue
  fenced=False
  for n,line in enumerate(text.splitlines(),1):
   if line.lstrip().startswith('```'):fenced=not fenced;continue
   if fenced:continue
   refs=REF.findall(line)
   for kind,rid,rev in refs:
    row=latest.get((kind,rid))
    if not row or int(rev)>row['rev']:errors.append(f'{name}:{n}: citation {kind}/{rid}@{rev} not found in research journals')
    elif int(rev)!=row['rev'] or (kind,rid) in stale or row.get('active') is False:errors.append(f'{name}:{n}: citation {kind}/{rid}@{rev} is stale; latest @{row["rev"]} or needs_review/retired')
   if not refs and NUMBER.search(line):notes.append(f'{name}:{n}: untraced number; cite [kind/id@rev] if it comes from evidence or experiments')
 return errors,notes
