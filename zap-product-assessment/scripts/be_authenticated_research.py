#!/usr/bin/env python3
"""Run the explicit native be-authenticated research contract on finalsource-zap-test.

No legacy P0 override. No strict secret-safe claim. Uses a dedicated ZAP + MCP pair,
upstream MCP client/parsers, native context/user seeds and guided crawl/attack.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from zap_assessment.research_product import main
if __name__=='__main__':raise SystemExit(main())
