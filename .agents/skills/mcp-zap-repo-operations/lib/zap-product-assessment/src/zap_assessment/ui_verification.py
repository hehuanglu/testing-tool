"""Offline W7 readback with existing safe BundleReader, no browser or network."""
import hashlib
from .business import digest
from .contracts import canonical
from .evidence import EvidenceInvalid
from .verification import BundleReader,strict_json
from .ui_contract import audit_ui,VERSION


def verify_ui_bundle(root,expected_plan_hash):
    if not isinstance(expected_plan_hash,str) or len(expected_plan_hash)!=64:raise EvidenceInvalid('external_ui_plan_pin_required')
    with BundleReader(root) as reader:
        raw=reader.read('manifest.json');manifest=strict_json(raw)
        if manifest.get('contractVersion')!=VERSION or reader.read('manifest.sha256')!=(hashlib.sha256(raw).hexdigest()+'\n').encode():raise EvidenceInvalid('ui_manifest_checksum')
        inventory={r['path']:r for r in manifest['artifacts']}
        if len(inventory)!=len(manifest['artifacts']) or set(reader.initial)!=set(inventory)|{'manifest.json','manifest.sha256'}:raise EvidenceInvalid('ui_artifact_inventory')
        required={'plan.json','fixture.json','observations.json','arrivals.json','secret-audit.json','cleanup.json','result.json'}
        if not required<=inventory.keys() or any(name not in required and not name.startswith('screenshots/') for name in inventory):raise EvidenceInvalid('ui_document_inventory')
        for name,row in inventory.items():
            blob=reader.read(name)
            if len(blob)!=row['bytes'] or hashlib.sha256(blob).hexdigest()!=row['sha256']:raise EvidenceInvalid('ui_artifact_digest')
        plan_raw=reader.read('plan.json');plan=strict_json(plan_raw)
        if hashlib.sha256(plan_raw).hexdigest()!=expected_plan_hash or canonical(plan)!=plan_raw:raise EvidenceInvalid('external_ui_plan_pin_mismatch')
        observations=strict_json(reader.read('observations.json'))
        result=audit_ui(plan,strict_json(reader.read('fixture.json')),observations,
                        strict_json(reader.read('arrivals.json')),strict_json(reader.read('secret-audit.json')),strict_json(reader.read('cleanup.json')))
        if result!=strict_json(reader.read('result.json')):raise EvidenceInvalid('ui_claim_disagrees_with_recomputation')
        declared={'screenshots/'+s['path']:s for s in observations['screenshots']}
        if len(declared)!=len(observations['screenshots']) or set(inventory)-required!=set(declared):raise EvidenceInvalid('ui_screenshot_inventory')
        for name,s in declared.items():
            blob=reader.read(name)
            if (s['scope']!='summary-element-only-no-login-form' or len(blob)>256*1024 or len(blob)!=s['bytes']
                    or hashlib.sha256(blob).hexdigest()!=s['sha256'] or not blob.startswith(b'\x89PNG\r\n\x1a\n')):raise EvidenceInvalid('ui_screenshot_bounds')
        from .opaque_canary import OpaqueCanaryAuditor
        auditor=OpaqueCanaryAuditor(strict_json(reader.read('secret-audit.json'))['fingerprints'])
        for name in inventory:
            if auditor.matches(reader.read(name)):raise EvidenceInvalid('private_canary_in_ui_bundle')
        reader.unchanged()
        return {'verified':True,'semanticRecomputed':True,'planHash':expected_plan_hash,'sourcePins':plan['sourcePins'],'image':plan['image'],**result}
