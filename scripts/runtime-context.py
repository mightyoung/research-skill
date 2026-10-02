#!/usr/bin/env python3
"""Report skill/project roots and host hints, without probing accounts or MCP."""
import argparse
import json
import os
from pathlib import Path
from acquire import SOURCES

def context(project,host='auto',capabilities=()):
    skill=Path(__file__).resolve().parents[1]
    project=Path(project).absolute()
    if project.is_symlink():raise ValueError('symlink project root refused')
    project=project.resolve()
    if project==skill or skill in project.parents:raise ValueError('research project must be outside skill directory')
    if host!='auto':profile={'name':host,'basis':'explicit'}
    else:
        # Read only non-secret presence hints; no configuration, auth or tokens.
        claude=os.environ.get('CLAUDECODE')=='1';codex=bool(os.environ.get('CODEX_THREAD_ID'))
        name='claude-code' if claude and not codex else ('codex' if codex and not claude else 'unknown')
        profile={'name':name,'basis':'environment_hint' if name!='unknown' else 'unavailable_or_ambiguous'}
    files=[{'name':name,'path':str(project/name),'exists':(project/name).is_file() and not (project/name).is_symlink()} for name in ('AGENTS.md','handoff.md')]
    return {'skill_root':str(skill),'project_root':str(project),'host':profile,
        'required_project_files':files,'instructions':'Explicitly read the research project AGENTS.md and handoff.md before routing; do not assume host automatic loading.',
        'capabilities':[{'name':name,'presence':'declared','connection':'unknown','fulltext_access':'unknown'} for name in dict.fromkeys(capabilities)],
        'plugin_access':'declared_tools_unverified' if capabilities else 'needs_host_execution',
        'direct_sources':[name for name in SOURCES if name not in ('unpaywall','openalex-content','core')],
        'fallback':'Use public direct adapters or a sanitized host-result/local-file import; unavailable/blocked/needs_configuration is not negative research evidence.',
        'network_requests':0,'configuration_files_read':0}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('project',type=Path)
    p.add_argument('--host',choices=('auto','codex','claude-code','unknown'),default='auto')
    p.add_argument('--capability',action='append',choices=('scholar','firecrawl','scispace','undermind','web'),default=[])
    a=p.parse_args()
    try:result=context(a.project,a.host,a.capability)
    except (OSError,ValueError):p.exit(1,'runtime context stopped: explicit safe project root outside skill directory required\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
