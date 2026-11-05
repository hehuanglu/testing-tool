"""Capture exact argv, stdout, stderr and exit code under a fresh label."""
import json
import subprocess
import sys
from pathlib import Path

review = Path(__file__).resolve().parent
label, *argv = sys.argv[1:]
if len(argv) == 2 and argv[0] == '--retained-argv':
    argv = json.loads(Path(argv[1]).read_text())['argv']
paths = {kind: review / (label + '.' + kind) for kind in ('stdout', 'stderr', 'command.json')}
assert not any(path.exists() for path in paths.values())
result = subprocess.run(argv, cwd=Path.cwd(), capture_output=True, check=False)
paths['stdout'].write_bytes(result.stdout)
paths['stderr'].write_bytes(result.stderr)
paths['command.json'].write_text(json.dumps(dict(argv=argv, exitCode=result.returncode), indent=2) + '\n')
sys.exit(result.returncode)
