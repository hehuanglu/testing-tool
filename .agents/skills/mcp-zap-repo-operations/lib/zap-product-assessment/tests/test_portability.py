"""Skill-local imports and CLI routing without Docker, traffic or a dev checkout."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from zap_assessment.contracts import ROOT
from zap_assessment import research


class PortableSkillTests(unittest.TestCase):
    def test_transport_is_bundled_and_matches_provenance(self):
        bundled = ROOT.parent
        self.assertTrue(Path(research.gate.__file__).is_relative_to(bundled))
        provenance = json.loads((bundled / 'vendor-provenance.json').read_text())
        for row in provenance['files']:
            path = bundled / 'mcp-zap-server' / row['path']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row['sha256'])

    def test_common_cli_and_skill_helpers_work_from_another_directory(self):
        skill = ROOT.parent.parent
        entries = [ROOT / 'scripts/product_assessment.py',
                   ROOT / 'scripts/fe_anonymous_research.py',
                   ROOT / 'scripts/fe_authenticated_research.py',
                   *(skill / 'scripts').glob('*.py')]
        env = os.environ.copy()
        env['PYTHONPATH'] = str(ROOT / 'src')
        with tempfile.TemporaryDirectory() as unrelated:
            for entry in entries:
                with self.subTest(entry=entry.name):
                    result = subprocess.run([sys.executable, '-B', str(entry), '--help'],
                                            cwd=unrelated, env=env, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
