#!/usr/bin/env python3
"""FE anonymous research (finite browser journeys through isolated native ZAP)."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from zap_assessment.fe_anonymous_cli import main
if __name__=='__main__':raise SystemExit(main())
