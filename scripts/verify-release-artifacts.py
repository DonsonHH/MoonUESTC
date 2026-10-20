#!/usr/bin/env python3
"""Verify all release checksums and privacy before an image can be uploaded."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
sys.dont_write_bytecode=True
from privacy_scan import Scanner

def verify(directory,tag,scanner):
    if not re.fullmatch(r"v\d+\.\d+\.\d+",tag):
        raise ValueError("invalid_tag")
    directory=Path(directory)
    items=list(directory.iterdir())
    if any(not p.is_file() or p.is_symlink() or not re.fullmatch(r"[A-Za-z0-9_.-]+",p.name) for p in items):
        raise ValueError("unsafe_artifact")
    names={p.name:p for p in items}
    required={f"MoonUESTC-{tag}-{part}" for part in ["source.zip","deploy.zip","deploy.tar.gz",
              "linux-amd64.image.tar.gz","validation.json"]}|{"SHA256SUMS.release.txt"}
    if not required.issubset(names):
        raise ValueError("missing_artifact")
    covered=set()
    for filename in ["SHA256SUMS.release.txt"]+[x for x in names if x.endswith(".sha256")]:
        rows=names[filename].read_text(encoding="utf-8").splitlines()
        if not rows:
            raise ValueError("empty_checksum")
        seen=set()
        for line in rows:
            match=re.fullmatch(r"([a-f0-9]{64})  ([A-Za-z0-9_.-]+)",line)
            if not match:
                raise ValueError("invalid_checksum")
            digest,name=match.groups()
            if name not in names or name in seen or name==filename:
                raise ValueError("invalid_checksum")
            if hashlib.sha256(names[name].read_bytes()).hexdigest()!=digest:
                raise ValueError("checksum_mismatch")
            seen.add(name);covered.add(name)
    exempt={"SHA256SUMS.release.txt"}|{x for x in names if x.endswith(".sha256")}
    if set(names)-exempt-covered:
        raise ValueError("unchecked_artifact")
    image=f"MoonUESTC-{tag}-linux-amd64.image.tar.gz"
    layers=0
    for name,path in sorted(names.items()):
        before=scanner.layers
        scanner.file(path)
        if name==image:
            layers=scanner.layers-before
    if layers<1:
        raise ValueError("invalid_image")
    return {"image_archive":image,"image_sha256":hashlib.sha256(names[image].read_bytes()).hexdigest(),
            "artifact_count":len(names)}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--directory",required=True,type=Path)
    p.add_argument("--tag",required=True);p.add_argument("--output",type=Path);a=p.parse_args()
    try:
        scanner=Scanner(Path(__file__).with_name("privacy-allowlist.json"))
        result=verify(a.directory,a.tag,scanner)
        result.update(scanner.report())
    except Exception:
        result={"passed":False,"findings":[{"rule":"artifact_gate_unavailable"}],"matched_values_logged":False}
    if a.output:
        a.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    if result["passed"] and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"],"a",encoding="utf-8") as f:
            for key in ("image_archive","image_sha256"):
                f.write(key+"="+result[key]+"\n")
    print(json.dumps(result))
    return 0 if result["passed"] else 1

if __name__=="__main__":
    raise SystemExit(main())
