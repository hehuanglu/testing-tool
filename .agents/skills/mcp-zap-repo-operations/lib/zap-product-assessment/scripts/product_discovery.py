#!/usr/bin/env python3
"""Validate existing manifests or collect source candidates from a requested product location."""
from pathlib import Path
import argparse,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from zap_assessment.discovery import validate_discovery,canonical_hash

def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    if argv and argv[0] in ('discover','materialize'):
        from zap_assessment.product_cli import main as product_main
        return product_main(argv)
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['validate']);p.add_argument('--manifest',required=True,type=Path);p.add_argument('--executable',action='store_true');a=p.parse_args(argv)
    d=validate_discovery(json.loads(a.manifest.read_text()),executable=a.executable)
    print(json.dumps({'status':'valid','sha256':canonical_hash(d),'operations':len(d['operations']),'execution':'not-run'}));return 0
if __name__=='__main__':raise SystemExit(main())
