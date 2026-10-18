#!/usr/bin/env python3
"""Read GitHub's authenticated PR metadata, not untrusted comment text, for a pinned head."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import sys

NAME = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
SHA = re.compile(r'^[0-9a-f]{40}$')

def resolve(metadata: dict, repository: str) -> dict[str,str]:
    head = metadata.get('head') or {}
    base = metadata.get('base') or {}
    head_repo = (head.get('repo') or {}).get('full_name')
    base_repo = (base.get('repo') or {}).get('full_name')
    head_sha = head.get('sha')
    if base_repo != repository or base.get('ref') != 'main':
        raise ValueError('PR_MUST_TARGET_THIS_REPOSITORY_MAIN')
    if not isinstance(head_repo,str) or not NAME.fullmatch(head_repo):
        raise ValueError('PR_HEAD_REPOSITORY_INVALID')
    if not isinstance(head_sha,str) or not SHA.fullmatch(head_sha):
        raise ValueError('PR_HEAD_SHA_INVALID')
    return {'head_repo':head_repo,'head_sha':head_sha}

def main():
    source=Path(sys.argv[1])
    output=resolve(json.loads(source.read_text(encoding='utf-8')),os.environ['GITHUB_REPOSITORY'])
    with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as f:
        for k,v in output.items(): f.write(k+'='+v+'\n')
    return 0

if __name__=='__main__': raise SystemExit(main())