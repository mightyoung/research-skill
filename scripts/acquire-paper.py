#!/usr/bin/env python3
"""Resolve public candidates or import host evidence; explicitly save one material."""
import argparse
import json
from pathlib import Path
from acquire import AcquisitionError, SOURCES, MAX_METADATA, resolve, import_result, save, secret_free, registration_draft

def read_json(path):
    if path.is_symlink() or any(x.is_symlink() for x in path.parents):raise AcquisitionError('symlink JSON input refused')
    with path.open('rb') as f:raw=f.read(MAX_METADATA+1)
    if len(raw)>MAX_METADATA:raise AcquisitionError('JSON input exceeds limit')
    try:value=json.loads(raw)
    except (ValueError,UnicodeError):raise AcquisitionError('invalid input JSON') from None
    secret_free(value);return value

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    r=sub.add_parser('resolve');r.add_argument('source',choices=SOURCES);r.add_argument('identity');r.add_argument('--version')
    i=sub.add_parser('import-result');i.add_argument('file',type=Path)
    s=sub.add_parser('save');s.add_argument('manifest',type=Path);s.add_argument('destination',type=Path);s.add_argument('--material',type=int,required=True);s.add_argument('--file',type=Path)
    d=sub.add_parser('registration-draft');d.add_argument('saved_directory',type=Path);d.add_argument('project',type=Path)
    d.add_argument('--work-id',required=True);d.add_argument('--source-id',required=True);d.add_argument('--paper-id',required=True)
    args=p.parse_args()
    try:
        if args.command=='resolve':result=resolve(args.source,args.identity,args.version)
        elif args.command=='import-result':result=import_result(read_json(args.file))
        elif args.command=='registration-draft':
            print(json.dumps(registration_draft(args.saved_directory,args.project,args.work_id,args.source_id,args.paper_id),ensure_ascii=False,indent=2));return 0
        else:
            path=save(read_json(args.manifest),args.destination,args.material,local_file=args.file)
            print(json.dumps({'state':'fulltext_saved','path':str(path),'reading_depth':'metadata','review_required':True},ensure_ascii=False));return 0
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result['state'] in ('metadata','abstract','passages') else 2
    except AcquisitionError as e:p.exit(1,'acquisition stopped: '+str(e)+'\n')
    except (OSError,ValueError,TypeError,KeyError):p.exit(1,'acquisition stopped: local input or source response invalid; raw errors suppressed\n')
if __name__=='__main__':raise SystemExit(main())
