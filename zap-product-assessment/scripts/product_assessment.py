#!/usr/bin/env python3
"""Explicit multi-product backend entry. Legacy CLIs retain their scope and readers."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from zap_assessment.product_cli import main
if __name__=='__main__':raise SystemExit(main())
