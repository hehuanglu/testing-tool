"""Version 2 read-only bundle verification: integrity, binding, oracle, agreement.

The external plan pin is mandatory. Files are data; reports/scripts are never
executed. Semantic decisions live in an independent audit, not coverage.evaluate.
"""
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import unicodedata

from .contracts import Blocked, canonical, validate
from .evidence import EvidenceInvalid, read_report

MAX_FILE = 16 * 1024 * 1024
MAX_BUNDLE = 64 * 1024 * 1024


def strict_json(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise EvidenceInvalid('duplicate_json_key')
            value[key] = item
        return value

    def floating(value):
        number = float(value)
        if not math.isfinite(number):
            raise EvidenceInvalid('nonfinite_json_number')
        return number

    def invalid(_):
        raise EvidenceInvalid('nonfinite_json_number')

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_float=floating, parse_constant=invalid)
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise EvidenceInvalid('invalid_or_ambiguous_json') from exc


def _path(name):
    if (not isinstance(name, str) or not name or len(name) > 1024
            or unicodedata.normalize('NFC', name) != name
            or any(ord(c) < 32 or ord(c) == 127 for c in name)
            or '\\' in name or ':' in name):
        raise EvidenceInvalid('unsafe_artifact_path')
    parts = name.split('/')
    if (any(p in ('', '.', '..') for p in parts) or len(parts) > 32
            or PurePosixPath(name).is_absolute() or str(PurePosixPath(name)) != name):
        raise EvidenceInvalid('unsafe_artifact_path')
    return parts


def _signature(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


class BundleReader:
    """Stable directory FD, no-follow file/ancestor opens, bounded bytes, no writes."""
    def __init__(self, root):
        path = Path(root)
        if path.is_symlink():
            raise EvidenceInvalid('bundle_root_symlink')
        self.fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self.path = path.resolve()
        self.root_identity = os.fstat(self.fd).st_dev, os.fstat(self.fd).st_ino
        self.cache = {}
        self.bytes_read = 0
        try:
            self.initial = self.inventory()
        except BaseException:
            os.close(self.fd)
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        os.close(self.fd)

    def inventory(self):
        found = {}

        def visit(fd, prefix='', depth=0):
            if depth > 32:
                raise EvidenceInvalid('bundle_directory_depth')
            for name in sorted(os.listdir(fd)):
                relative = prefix + name
                _path(relative)
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    try:
                        visit(child, relative + '/', depth + 1)
                    finally:
                        os.close(child)
                elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                    found[relative] = _signature(info)
                    if len(found) > 4098:
                        raise EvidenceInvalid('bundle_file_count_limit')
                else:
                    raise EvidenceInvalid('symlink_hardlink_or_special_artifact')
        visit(self.fd)
        return found

    def read(self, name):
        parts = _path(name)
        if name in self.cache:
            return self.cache[name]
        if name not in self.initial:
            raise EvidenceInvalid('missing_artifact')
        directory = os.dup(self.fd)
        handle = None
        try:
            for part in parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                os.close(directory)
                directory = child
            handle = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            before = os.fstat(handle)
            if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                    or before.st_size > MAX_FILE or _signature(before) != self.initial[name]):
                raise EvidenceInvalid('artifact_type_size_or_read_race')
            parts_read, length = [], 0
            while True:
                blob = os.read(handle, min(1024 * 1024, MAX_FILE + 1 - length))
                if not blob:
                    break
                length += len(blob)
                if length > MAX_FILE:
                    raise EvidenceInvalid('artifact_size_limit')
                parts_read.append(blob)
            if _signature(os.fstat(handle)) != _signature(before) or length != before.st_size:
                raise EvidenceInvalid('artifact_changed_during_read')
            data = b''.join(parts_read)
            self.bytes_read += len(data)
            if self.bytes_read > MAX_BUNDLE:
                raise EvidenceInvalid('bundle_size_limit')
            self.cache[name] = data
            return data
        finally:
            if handle is not None:
                os.close(handle)
            os.close(directory)

    def document(self, name, kind):
        value = strict_json(self.read(name))
        if not isinstance(value, dict) or value.get('schemaVersion') != '2.0':
            raise EvidenceInvalid('mixed_document_version')
        validate(kind, value)
        return value

    def unchanged(self):
        current_root = os.stat(self.path, follow_symlinks=False)
        if (current_root.st_dev, current_root.st_ino) != self.root_identity:
            raise EvidenceInvalid('bundle_root_changed_during_verification')
        if self.inventory() != self.initial:
            raise EvidenceInvalid('bundle_changed_during_verification')


def _unique(items, key, reason):
    indexed = {}
    for value in items:
        if value[key] in indexed:
            raise EvidenceInvalid(reason)
        indexed[value[key]] = value
    return indexed


def _reports(reader, manifest, plan):
    planned = _unique(plan['reports'], 'reportId', 'duplicate_report_id')
    reported = _unique(manifest['reports'], 'reportId', 'duplicate_report_id')
    if planned.keys() != reported.keys():
        raise EvidenceInvalid('report_inventory_mismatch')
    paths, outcomes = [], []
    for report_id, desc in planned.items():
        report = reported[report_id]
        raw = reader.read(report['artifactPath'])
        pages, used = {}, set()
        for path in report['chunkPaths']:
            value = strict_json(reader.read(path))
            # Native chunk pages have no schemaVersion; select the v2 shape explicitly.
            validate('report-chunk', value, schema_version='2.0')
            offset = value['offset']
            if offset in pages:
                raise EvidenceInvalid('duplicate_report_offset')
            pages[offset] = value

        def page(source_path, offset, expected_sha):
            if offset not in pages or offset in used:
                raise EvidenceInvalid('missing_or_reused_report_chunk')
            used.add(offset)
            return pages[offset]
        rebuilt = read_report(page, desc['sourcePath'], MAX_FILE)
        if used != pages.keys() or rebuilt != raw:
            raise EvidenceInvalid('report_reconstruction_mismatch')
        if desc['format'] == 'json':
            strict_json(raw)
        else:
            try:
                raw.decode('utf-8')
            except UnicodeError as exc:
                raise EvidenceInvalid('report_utf8_encoding') from exc
        paths.extend([report['artifactPath'], *report['chunkPaths']])
        outcomes.append({'reportId': report_id, 'bytes': len(raw), 'pages': len(pages),
                         'sha256': hashlib.sha256(raw).hexdigest()})
    return paths, outcomes


def verify_v2_bundle(root, expected_plan_hash):
    if not isinstance(expected_plan_hash, str) or not re.fullmatch('[a-f0-9]{64}', expected_plan_hash):
        raise EvidenceInvalid('external_expected_plan_hash_required')
    try:
        with BundleReader(root) as reader:
            raw = reader.read('manifest.json')
            if reader.read('manifest.sha256') != (hashlib.sha256(raw).hexdigest() + '\n').encode():
                raise EvidenceInvalid('manifest_digest_mismatch')
            manifest = reader.document('manifest.json', 'manifest')
            if manifest['planHash'] != expected_plan_hash:
                raise EvidenceInvalid('external_plan_pin_mismatch')
            inventory = _unique(manifest['artifacts'], 'path', 'duplicate_artifact')
            if set(reader.initial) != set(inventory) | {'manifest.json', 'manifest.sha256'}:
                raise EvidenceInvalid('artifact_inventory_mismatch')
            if sum(a['bytes'] for a in inventory.values()) > MAX_BUNDLE:
                raise EvidenceInvalid('bundle_size_limit')
            for name, artifact in inventory.items():
                if name in ('manifest.json', 'manifest.sha256'):
                    raise EvidenceInvalid('reserved_artifact_path')
                content = reader.read(name)
                if len(content) != artifact['bytes'] or hashlib.sha256(content).hexdigest() != artifact['sha256']:
                    raise EvidenceInvalid('artifact_digest_or_size_mismatch')
            documents = manifest['documents']
            paths = list(documents.values())
            if len(set(paths)) != len(paths) or not set(paths) <= inventory.keys():
                raise EvidenceInvalid('document_reference_collision_or_missing')
            plan_raw = reader.read(documents['plan'])
            if hashlib.sha256(plan_raw).hexdigest() != expected_plan_hash:
                raise EvidenceInvalid('plan_digest_mismatch')
            plan = reader.document(documents['plan'], 'normalized-plan')
            if canonical(plan) != plan_raw or plan['assessmentId'] != manifest['assessmentId']:
                raise EvidenceInvalid('plan_normalization_or_assessment_mismatch')
            fixture = reader.document(documents['fixture'], 'fixture-manifest')
            if hashlib.sha256(reader.read(documents['fixture'])).hexdigest() != plan['fixtureHash']:
                raise EvidenceInvalid('fixture_pin_mismatch')
            observations = reader.document(documents['observations'], 'observations')
            claims = reader.document(documents['coverage'], 'coverage')
            summary = reader.document(documents['summary'], 'summary')
            from .oracle_verification import IndependentAudit
            audit = IndependentAudit(plan, fixture, observations, expected_plan_hash)
            results, computed = audit.run()
            declared = _unique(claims['assertions'], 'assertionId', 'duplicate_assertion_claim')
            expected = {r['assertionId']: r['oracleResult'] for r in results}
            if declared.keys() != expected.keys() or any(declared[k]['oracleResult'] != v for k, v in expected.items()):
                raise EvidenceInvalid('recomputed_oracle_disagrees_with_claim')
            tracks = _unique(summary['tracks'], 'trackId', 'duplicate_track_summary')
            if tracks.keys() != computed['tracks'].keys() or any(tracks[k]['status'] != v for k, v in computed['tracks'].items()):
                raise EvidenceInvalid('track_summary_disagreement')
            if any(summary.get(k) != v for k, v in computed.items() if k != 'tracks'):
                raise EvidenceInvalid('summary_disagreement')
            report_paths, reports = _reports(reader, manifest, plan)
            paths.extend(report_paths)
            if len(set(paths)) != len(paths) or set(paths) != inventory.keys():
                raise EvidenceInvalid('unreferenced_or_aliased_artifact')
            reader.unchanged()
            return {'schemaVersion': '2.0', 'verified': True, 'integrityVerified': True,
                    'semanticRecomputed': True, 'verificationScope': 'coverage-verification-only',
                    'securityApproval': False, 'liveAssessmentPermitted': False,
                    'planHash': expected_plan_hash, 'artifactCount': len(inventory),
                    **{k: v for k, v in computed.items() if k != 'tracks'},
                    'tracks': computed['tracks'], 'assertions': results, 'reports': reports,
                    'assessmentExitCode': 1 if computed['securityVerdict'] == 'fail' else 2,
                    'limitations': ['External plan pin is a local trust anchor, not independent signed wire attestation',
                                    'Runtime/secret/policy gates remain unproven; verification does not grant allow']}
    except EvidenceInvalid:
        raise
    except (Blocked, OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        # Never echo raw document values, target responses or file contents.
        raise EvidenceInvalid('invalid_v2_bundle_' + type(exc).__name__) from exc
