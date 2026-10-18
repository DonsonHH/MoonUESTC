#!/usr/bin/env python3
"""Read-only public-source audit; optional private markers stay outside the repo."""
import argparse,hashlib,json,re,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--root',default=str(Path(__file__).resolve().parents[1]));p.add_argument('--private-markers');a=p.parse_args()
root=Path(a.root).resolve();problems=[];count=0
markers=json.loads(Path(a.private_markers).read_text()) if a.private_markers else []
patterns=[re.compile(r'gh[pousr]_[A-Za-z0-9]{25,}'),re.compile(r'github_pat_[A-Za-z0-9_]{25,}'),re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),re.compile(r'[A-Za-z]:[\\/](?:Users|MoonUESTC)[\\/]')]
for file in root.rglob('*'):
    rel=file.relative_to(root)
    if '.git' in rel.parts:continue
    if not file.is_file():continue
    count+=1
    if file.name.startswith('SHANGHAI-') or file.name=='.env' or (file.name.startswith('.env.') and file.name!='.env.example') or file.suffix in ['.pem','.key','.sqlite3','.lwp'] or rel.parts[0] in ['data','config','backups','release-artifacts']:
        problems.append({'file':str(rel),'reason':'private_runtime_file'})
    try:text=file.read_text(encoding='utf-8')
    except UnicodeError:continue
    if any(pattern.search(text) for pattern in patterns):problems.append({'file':str(rel),'reason':'credential_or_machine_path_pattern'})
    if any(marker in text for marker in markers):problems.append({'file':str(rel),'reason':'private_marker'})
raw=(root/'third_party/UESTC-MoonCheck.LICENSE.original').read_text(encoding='utf-8-sig')
clean=(root/'third_party/UESTC-MoonCheck.LICENSE').read_text(encoding='utf-8')
expected='\n'.join(line for line in raw.splitlines() if not line.startswith(('<<<<<<<','=======','>>>>>>>')))+'\n'
if clean!=expected:problems.append({'file':'third_party/UESTC-MoonCheck.LICENSE','reason':'unexpected_license_change'})
for name in ['README.md','Dockerfile','compose.yaml','install.sh','moonuestc/__init__.py']:
    if '0.4.1' not in (root/name).read_text(encoding='utf-8'):problems.append({'file':name,'reason':'release_version_missing'})
print(json.dumps({'passed':not problems,'files_checked':count,'problems':problems},ensure_ascii=False))
sys.exit(bool(problems))
