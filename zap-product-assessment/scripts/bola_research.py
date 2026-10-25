#!/usr/bin/env python3
"""Bounded BOLA direct research; no ZAP active scan authority implied."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from zap_assessment import bola_research as br


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('discover',help='Read selected local test deployment/source/live OpenAPI; no fixture writes');p.add_argument('--output',required=True)
    p=sub.add_parser('product-run',help='Fresh API-only actors/fixtures, bounded BOLA reads/mutations, cleanup/retention')
    for f in ('discovery','inventory','receipt','output'):p.add_argument('--'+f,required=True)
    p.add_argument('--interrupt-after',type=int,help='Stop before the next case after N completed cases; cleanup still runs')
    p=sub.add_parser('verify',help='Offline integrity/reference/oracle replay; no traffic');p.add_argument('--run',required=True)
    p=sub.add_parser('compare',help='Offline same-build logical BOLA repeatability')
    p.add_argument('--before',required=True);p.add_argument('--after',required=True)
    args=parser.parse_args()
    try:
        if args.command=='discover':
            from zap_assessment.bola_research_product import discover
            d,inv=discover(args.output);result={'operations':len(inv['operations']),'output':args.output,'executionStatus':'discovered-only'}
        elif args.command=='product-run':
            from zap_assessment.bola_research_product import run
            result=run(br.decode(Path(args.discovery).read_bytes()),br.decode(Path(args.inventory).read_bytes()),args.output,br.decode(Path(args.receipt).read_bytes()),args.interrupt_after)
        elif args.command=='verify':result=br.verify(args.run)
        else:result=br.compare_runs(args.before,args.after)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except Exception as error:
        print(json.dumps({'executionStatus':'failed','errorType':type(error).__name__,'detail':'See owned output for retained evidence; no mutation replay. Sensitive values withheld.'}));return 2

if __name__=='__main__':raise SystemExit(main())
