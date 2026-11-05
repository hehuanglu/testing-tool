"""Prepare one typed repair update from the current revision and explicit evidence."""
import json
import sys
from pathlib import Path
from zap_assessment.assessment_store import load_current

base = Path(__file__).resolve().parents[1]
label, status, *evidence = sys.argv[1:]
snapshot = load_current(base / 'fixture/state')
repair = next(row for row in snapshot.operator['repairs'] if row['id'] == 'repair-fixture-reader')
payload = dict(id=repair['id'], revision=repair['revision'], status=status)
if status == 'verified':
    positive, wrong_object, wrong_action, nonterminal, changed_digest, reproduction = [
        base / 'evidence' / name for name in evidence]
    for path in (positive, wrong_object, wrong_action, nonterminal, reproduction):
        meta = path.with_suffix('.command.json')
        expected = 0 if path == positive else 2
        assert json.loads(meta.read_text())['exitCode'] == expected
    payload.update(reproductionOutcome='Captured envelope failed the flat reader, as shown by the retained stderr',
                   verificationResult='passed', verificationLevel='offline-checked',
                   changedFileRefs=[str(changed_digest)],
                   positiveCheckRefs=[str(positive)], negativeCheckRefs=list(map(str, (wrong_object, wrong_action, nonterminal))),
                   verificationRefs=[str(positive.with_suffix('.command.json')), str(reproduction)])
(base / 'setup' / (label + '.json')).write_text(json.dumps(payload, indent=2) + '\n')
