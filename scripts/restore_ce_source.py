#!/usr/bin/env python3
"""Restore exact CE validator bytes from the bounded trusted-source archive."""
from __future__ import annotations
import base64
import hashlib
import io
import json
import lzma
from pathlib import Path, PurePosixPath
import shutil
import tarfile

ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=ROOT/'trusted'/'ce-source-v1.5.0.tar.xz.b85'
MANIFEST=ROOT/'trusted'/'ce-source-v1.5.0.sha256.json'
DEST=ROOT/'.runtime'/'ce-source'

def restore():
    specification=json.loads(MANIFEST.read_text(encoding='utf-8'))
    compressed=base64.b85decode(''.join(ARCHIVE.read_text(encoding='ascii').split()))
    if hashlib.sha256(compressed).hexdigest()!=specification['archive_sha256']:
        raise ValueError('TRUSTED_ARCHIVE_DIGEST_MISMATCH')
    members={}
    with tarfile.open(fileobj=io.BytesIO(lzma.decompress(compressed)),mode='r:') as archive:
        for member in archive.getmembers():
            path=PurePosixPath(member.name)
            if not member.isfile() or str(path)!=member.name or path.is_absolute() or '..' in path.parts or member.name in members or member.name not in specification['files']:
                raise ValueError('TRUSTED_ARCHIVE_MEMBER_INVALID:'+member.name)
            handle=archive.extractfile(member)
            if handle is None:
                raise ValueError('TRUSTED_ARCHIVE_FILE_MISSING:'+member.name)
            data=handle.read()
            if hashlib.sha256(data).hexdigest()!=specification['files'][member.name]:
                raise ValueError('TRUSTED_SOURCE_DIGEST_MISMATCH:'+member.name)
            members[member.name]=data
    if set(members)!=set(specification['files']):
        raise ValueError('TRUSTED_ARCHIVE_FILES_INCOMPLETE')
    if DEST.exists():
        shutil.rmtree(DEST)
    for name,data in members.items():
        dest=DEST/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(data)
    return DEST

if __name__=='__main__':
    d=restore();print('TRUSTED_CE_SOURCE_RESTORED files='+str(len(list(d.rglob('*')))))