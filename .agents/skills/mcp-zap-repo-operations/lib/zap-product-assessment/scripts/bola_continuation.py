#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from zap_assessment import bola_research as br
from zap_assessment.bola_research_expanded import run,verify
p=argparse.ArgumentParser();p.add_argument('command',choices=['run','verify']);p.add_argument('--output',required=True);p.add_argument('--discovery');p.add_argument('--inventory');p.add_argument('--receipt');p.add_argument('--failure',action='store_true');a=p.parse_args()
try:
 r=verify(a.output) if a.command=='verify' else run(json.loads(Path(a.discovery).read_text()),json.loads(Path(a.inventory).read_text()),a.output,json.loads(Path(a.receipt).read_text()),a.failure)
 print(json.dumps(r,indent=2))
except BaseException as e:
 print(json.dumps({'executionStatus':'failed','type':type(e).__name__,'diagnostic':'owned FAILURE.json; no replay'}));sys.exit(2)
