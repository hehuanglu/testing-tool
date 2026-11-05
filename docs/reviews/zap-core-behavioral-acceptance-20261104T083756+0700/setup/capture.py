"""Execute exactly the supplied command and retain stdout, stderr and exit status."""
import json
import subprocess
import sys
from pathlib import Path

base = Path(__file__).resolve().parents[1]
label, *command = sys.argv[1:]
prefix = base / 'evidence' / label
if prefix.with_suffix('.command.json').exists():
    raise SystemExit('Evidence label already exists')
result = subprocess.run(command, capture_output=True, timeout=30)
prefix.with_suffix('.stdout').write_bytes(result.stdout)
prefix.with_suffix('.stderr').write_bytes(result.stderr)
prefix.with_suffix('.command.json').write_text(json.dumps(dict(argv=command, exitCode=result.returncode), indent=2) + '\n')
sys.stdout.buffer.write(result.stdout)
sys.stderr.buffer.write(result.stderr)
raise SystemExit(result.returncode)
