import hashlib
import json
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from .contracts import Blocked,canonical,validate

class EvidenceInvalid(Blocked): pass
class SecretLeak(EvidenceInvalid): pass

def _read_envelope(root,name,limit):
    try: fd=os.open(safe_path(root,name),os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    except OSError as exc: raise EvidenceInvalid('manifest envelope unreadable') from exc
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode): raise EvidenceInvalid('manifest envelope must be regular')
        with os.fdopen(fd,'rb',closefd=False) as stream: data=stream.read(limit+1)
        if len(data)>limit: raise EvidenceInvalid('manifest envelope size limit')
        return data
    except OSError as exc: raise EvidenceInvalid('manifest envelope unreadable') from exc
    finally: os.close(fd)

def decide(execution,evidence,cleanup,coverage,confirmed=False,untriaged=False):
    verdict='fail' if confirmed else 'inconclusive'
    if execution!='completed' or evidence!='complete' or not coverage: return verdict,'block',2
    if confirmed: return 'fail','block',1
    if cleanup!='clean': return 'inconclusive','block',2
    if untriaged: return 'inconclusive','review_required',3
    return 'pass','allow',0

def safe_path(root,name):
    root=Path(root)
    if not isinstance(name,str) or not name or Path(name).name!=name or name in ('.','..') or '\\' in name: raise EvidenceInvalid('artifact path rejected')
    if root.is_symlink() or (root/name).is_symlink(): raise EvidenceInvalid('artifact symlink rejected')
    return root/name

def write_file(root,name,data):
    p=safe_path(root,name)
    from .safety_io import atomic_bytes
    atomic_bytes(p,data)
    return {'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}

@dataclass
class ReportReadResult:
    """Private read progress. Never serialize data/pages into a public handoff."""
    status: str
    reason: str
    data: bytes = field(default=b'', repr=False)
    pages: list = field(default_factory=list, repr=False)
    document: object = field(default=None, repr=False)
    next_offset: int = 0
    total_characters: int | None = None
    artifact_sha256: str | None = None

    def summary(self):
        return {'status': self.status, 'reason': self.reason, 'bytes': len(self.data),
                'pages': len(self.pages), 'nextOffset': self.next_offset,
                'totalCharacters': self.total_characters, 'artifactSha256': self.artifact_sha256}


class ReportReadFailure(EvidenceInvalid):
    def __init__(self, result):
        super().__init__(result.reason)
        self.result = result


def report_preview_document(text, report_path):
    """Return a JSON document only for an explicitly complete native preview.

    Truncated, malformed or unmarked previews are never a document source; callers
    must use chunks. Split at the artifact envelope, not at arbitrary report text.
    """
    import re
    marker = 'Report artifact\n'
    if not isinstance(text, str) or marker not in text:
        return None
    header, separator, content = text.rsplit(marker, 1)[1].partition('\n\n')
    if not separator:
        return None
    m = re.fullmatch(r'Path: (.+)\nCharacters Returned: (\d+)\nTruncated: (yes|no)', header)
    if not m or m[1] != report_path or m[3] != 'no' or len(content) != int(m[2]):
        return None
    try:
        return json.loads(content)
    except (ValueError, RecursionError):
        return None


def collect_report(reader, report_path, max_bytes, *, saved_pages=(), on_page=None,
                   max_pages=10000, parse_json=False):
    """Validate/reuse ordered saved pages, then read only the missing suffix.

    reader(path, code_point_offset, expected_sha256) keeps the existing transport
    signature. on_page persists each new validated page in the caller's private
    store before the next read. Limits return partial with progress retained;
    invalid data returns error. No producer or report-generation calls occur here.
    """
    result = ReportReadResult('error', 'report input invalid')
    if (not isinstance(report_path, str) or not report_path.startswith('/zap/wrk/')
            or '..' in Path(report_path).parts or type(max_bytes) is not int or max_bytes < 0
            or type(max_pages) is not int or max_pages < 1):
        return result
    offset = 0; sha = None; total = None; parts = []; size = 0
    cached = iter(saved_pages)
    replaying = True

    def finish(status, reason):
        result.status = status; result.reason = reason
        result.data = ''.join(parts).encode('utf-8')
        result.next_offset = offset; result.total_characters = total; result.artifact_sha256 = sha
        return result

    for _ in range(max_pages):
        if replaying:
            try:
                page = next(cached)
            except StopIteration:
                replaying = False
        if not replaying:
            try:
                page = reader(report_path, offset, sha)
            except Exception:
                # Transport exceptions may embed response bodies or credentials.
                return finish('partial' if result.pages else 'error', 'report transport failed; resume saved pages')
        keys = {'reportPath','offset','nextOffset','charactersReturned','endOfFile','totalCharacters','offsetUnit','artifactSha256','content'}
        if not isinstance(page, dict) or set(page) != keys:
            return finish('error', 'chunk contract mismatch')
        content = page['content']
        if (not isinstance(content, str) or page['reportPath'] != report_path
                or type(page['offset']) is not int or page['offset'] != offset
                or page['offsetUnit'] != 'unicodeCodePoints' or type(page['endOfFile']) is not bool
                or type(page['charactersReturned']) is not int or page['charactersReturned'] != len(content)):
            return finish('error', 'chunk encoding/offset mismatch')
        if type(page['totalCharacters']) is not int or page['totalCharacters'] < 0:
            return finish('error', 'invalid total')
        digest = page['artifactSha256']
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            return finish('error', 'report hash contract mismatch')
        if sha is None:
            sha = digest; total = page['totalCharacters']
        if digest != sha or page['totalCharacters'] != total:
            return finish('error', 'report changed during export')
        try:
            encoded_size = len(content.encode('utf-8'))
        except UnicodeError:
            return finish('error', 'chunk UTF-8 encoding invalid')
        end = offset + len(content)
        if end > total:
            return finish('error', 'report size mismatch')
        # EOF takes precedence: nextOffset=null is valid only at true EOF.
        if page['endOfFile']:
            if page['nextOffset'] is not None or end != total:
                return finish('error', 'truncated report')
        elif not content or type(page['nextOffset']) is not int or page['nextOffset'] != end:
            return finish('error', 'non-progressing chunk')
        if size + encoded_size > max_bytes:
            # Keep the validated received page even when assembly exceeds budget.
            result.pages.append(dict(page))
            if on_page is not None and not replaying:
                try: on_page(dict(page))
                except Exception: return finish('partial', 'report checkpoint failed; received page retained')
            return finish('partial', 'report byte limit reached; resume with a sufficient budget')
        result.pages.append(dict(page)); parts.append(content); offset = end; size += encoded_size
        if on_page is not None and not replaying:
            try: on_page(dict(page))
            except Exception: return finish('partial', 'report checkpoint failed; received page retained')
        if page['endOfFile']:
            if replaying:
                try: next(cached)
                except StopIteration: pass
                else: return finish('error', 'saved pages continue after EOF')
            finish('complete', 'report read to EOF')
            if hashlib.sha256(result.data).hexdigest() != sha:
                return finish('error', 'report hash mismatch')
            if parse_json:
                try: result.document = json.loads(result.data)
                except (ValueError, RecursionError): return finish('error', 'report JSON parse failed')
            return result
    return finish('partial', 'report page limit reached; resume saved pages')


def read_report(reader, report_path, max_bytes, *, saved_pages=(), on_page=None):
    """Compatibility entry: existing gate callers still require complete bytes."""
    result = collect_report(reader, report_path, max_bytes, saved_pages=saved_pages, on_page=on_page)
    if result.status != 'complete':
        raise ReportReadFailure(result)
    return result.data

def secret_check(data,canaries=()):
    import base64,urllib.parse
    for secret in canaries:
        for candidate in (secret,urllib.parse.quote(secret,safe=''),base64.b64encode(secret.encode()).decode()):
            if candidate.encode() in data: raise SecretLeak('secret canary detected; export blocked')
    # Anonymous-only pipeline rejects auth-like material rather than promising generic redaction.
    if any(x in data.lower() for x in [b'authorization: bearer ',b'set-cookie:',b'"password":']): raise SecretLeak('credential-like material; export blocked')

def verify_bundle(root,expected_plan_hash=None):
    root=Path(root)
    raw=_read_envelope(root,'manifest.json',16*1024*1024)
    try: expected=_read_envelope(root,'manifest.sha256',4096).decode('ascii').strip()
    except UnicodeError as exc: raise EvidenceInvalid('manifest digest encoding') from exc
    if hashlib.sha256(raw).hexdigest()!=expected: raise EvidenceInvalid('manifest digest mismatch')
    try: manifest=json.loads(raw)
    except (ValueError,UnicodeError,RecursionError) as exc: raise EvidenceInvalid('invalid manifest JSON') from exc
    if not isinstance(manifest,dict): raise EvidenceInvalid('manifest object required')
    if expected_plan_hash is not None and manifest.get('planHash')!=expected_plan_hash:
        raise EvidenceInvalid('external_plan_pin_mismatch')
    if manifest.get('schemaVersion')=='2.0':
        from .verification import verify_v2_bundle
        return verify_v2_bundle(root,expected_plan_hash)
    validate('manifest',manifest)
    if manifest.get('schemaVersion') in ('1.2','1.3','1.4'):
        from .bola import verify_bola_bundle
        return verify_bola_bundle(root,manifest)
    seen=set()
    for a in manifest['artifacts']:
        if a['path'] in seen: raise EvidenceInvalid('duplicate artifact')
        seen.add(a['path']); data=safe_path(root,a['path']).read_bytes()
        if len(data)!=a['bytes'] or hashlib.sha256(data).hexdigest()!=a['sha256']: raise EvidenceInvalid('artifact readback mismatch')
    if not {'plan.json','journal.jsonl','report.json','coverage.json','findings.json','network.json','report-readback.json','health.json'}<=seen: raise EvidenceInvalid('required evidence missing')
    plan=safe_path(root,'plan.json').read_bytes()
    if hashlib.sha256(plan).hexdigest()!=manifest['planHash']: raise EvidenceInvalid('plan digest mismatch')
    if manifest['evidenceStatus']!='complete': raise EvidenceInvalid('incomplete bundle')
    locked=json.loads(plan); validate('normalized-plan',locked)
    product=locked['product']
    from .contracts import digest
    if canonical(locked)!=plan or digest(product)!=locked['profileHash'] or digest(locked['workflow'])!=locked['workflowHash'] or digest(locked['authority'])!=locked['authorizationHash']: raise EvidenceInvalid('plan normalization/reference mismatch')
    borrowed=[product['binding']] if product['schemaVersion']=='1.1' else []
    if manifest['schemaVersion']!=product['schemaVersion']: raise EvidenceInvalid('manifest contract version mismatch')
    if manifest['ownership'].get('createdByRun')!=manifest['runId'] or manifest['ownership'].get('borrowed')!=borrowed or manifest['ownership'].get('cleanupVerified') is not True: raise EvidenceInvalid('ownership/cleanup proof missing')
    if manifest['scope']!=product['attackOrigins'] or manifest['targetBuildRef']!=product['targetBuildRef']: raise EvidenceInvalid('manifest plan context mismatch')
    from .journal import Journal
    journal=Journal(safe_path(root,'journal.jsonl'),manifest['runId'],manifest['planHash'])
    if journal.state not in ('EVIDENCE_READY','FINALIZED'): raise EvidenceInvalid('evidence journal not ready')
    health=json.loads(safe_path(root,'health.json').read_bytes())
    if product['schemaVersion']=='1.1':
        from .binding import validate_binding,guard_values
        from .contracts import check_authority
        from datetime import datetime
        validate_binding(product,locked['workflow'],locked['authority'])
        check_authority(locked['authority'],product,locked['workflow'],datetime.fromisoformat(manifest['startedAt']))
        if locked['guard']!=guard_values(product,locked['workflow'],locked['authority']) or digest(locked['schema'])!=locked['schemaHash']: raise EvidenceInvalid('binding plan guard/schema mismatch')
        if 'binding.json' not in seen: raise EvidenceInvalid('binding proof missing')
        binding=json.loads(safe_path(root,'binding.json').read_bytes());b=product['binding']
        if binding.get('borrowed')!=b or binding.get('targetCleanupActions')!=[]: raise EvidenceInvalid('borrowed ownership proof mismatch')
        for key in ('before','after'):
            obs=binding.get(key,{})
            if obs.get('running') is not True or any(obs.get(k)!=b[k] for k in ('containerId','imageId','startedAt')) or {'networkId':b['networkId'],'address':b['address']} not in obs.get('networks',{}).values(): raise EvidenceInvalid('target binding evidence mismatch')
        expected_assertions=[{**x,'matched':True} for x in product['healthAssertions']]
        if health.get('status')!=200 or health.get('assertions')!=expected_assertions or len(health.get('bodySha256',''))!=64: raise EvidenceInvalid('health assertion evidence missing')
    elif health.get('build')!=product['targetBuildRef'] or health.get('productId')!=product['productId']: raise EvidenceInvalid('target identity evidence mismatch')
    coverage=json.loads(safe_path(root,'coverage.json').read_bytes())
    expected=product['expectedOperations']; observed=coverage.get('observed')
    if coverage.get('expected')!=expected or not isinstance(observed,list) or len(observed)!=len(expected): raise EvidenceInvalid('coverage denominator mismatch')
    for exp,obs in zip(expected,observed,strict=True):
        if any(obs.get(k)!=exp[k] for k in ('method','path','status')) or obs.get('assertion') is not True or obs.get('actor')!='anonymous' or obs.get('phase')!='seed': raise EvidenceInvalid('required coverage assertion missing')
    report=json.loads(safe_path(root,'report.json').read_bytes())
    if not isinstance(report.get('site'),list) or not report['site']: raise EvidenceInvalid('report site missing')
    untriaged=False
    from .contracts import origin
    from urllib.parse import urlsplit
    for site in report['site']:
        site_url=site.get('@name',site.get('name'))
        if origin(site_url) not in manifest['scope'] or urlsplit(site_url).path not in ('','/'): raise EvidenceInvalid('report scope mismatch')
        if not isinstance(site.get('alerts'),list): raise EvidenceInvalid('report alerts missing')
        for alert in site['alerts']:
            if str(alert.get('riskcode')) not in {'0','1','2','3'}: raise EvidenceInvalid('invalid risk code')
            untriaged=untriaged or int(alert['riskcode'])>=2
    statuses={k:manifest[k] for k in ('executionStatus','evidenceStatus','securityVerdict','cleanupStatus','gateDecision')}
    verdict,gate,_=decide(manifest['executionStatus'],manifest['evidenceStatus'],manifest['cleanupStatus'],True,untriaged=untriaged)
    if (verdict,gate)!=(manifest['securityVerdict'],manifest['gateDecision']): raise EvidenceInvalid('decision inconsistent with measured evidence')
    if sorted(t['track'] for t in manifest['tracks'])!=sorted(locked['workflow']['requiredTracks']): raise EvidenceInvalid('required track missing/duplicated')
    for track in manifest['tracks']:
        if any(track[k]!=v for k,v in statuses.items()) or track['expected']!=expected or track['observed']!=observed: raise EvidenceInvalid('track evidence/status mismatch')
    network=json.loads(safe_path(root,'network.json').read_bytes())
    if network.get('forbiddenRequests')!=0: raise EvidenceInvalid('forbidden egress evidence')
    if manifest['provenance'].get('network') in ('none+UID-output-firewall+origin-guard','borrowed-bridge+UID-firewall+plan-guard'):
        for observed_key,plan_key in [('zapImage','zap'),('mcpImage','mcp'),('pythonImage','python'),('boundaryImageId','boundary')]:
            if manifest['provenance'].get(observed_key)!=locked['runtime'][plan_key]: raise EvidenceInvalid('scanner baseline mismatch')
        if manifest['provenance'].get('engine',{}).get('version')!=locked['runtime']['zapVersion'] or manifest['provenance'].get('serverInfo',{}).get('version')!=locked['runtime']['mcpVersion']: raise EvidenceInvalid('observed scanner version mismatch')
        guard=network.get('originGuardProof',{})
        guard_keys={'allowedTarget','outsidePort','hostAlias','schemeChange','connectTunnel','metadata','hostOverride'}
        if product['schemaVersion']=='1.1': guard_keys|={'forbiddenPath','credentialForward','cookieForward'}
        if set(guard)!=guard_keys or guard.get('allowedTarget')!=200 or any(v!=403 for k,v in guard.items() if k!='allowedTarget'): raise EvidenceInvalid('origin guard proof missing/failed')
        probe=network.get('boundaryProbe',{})
        if probe.get('approvedProxy') is not True or set(probe)!={'approvedProxy','directTarget','outside-port','control-api','metadata','external','ipv6'} or any(v for k,v in probe.items() if k!='approvedProxy'): raise EvidenceInvalid('boundary proof missing/failed')
        initial=manifest['provenance'].get('initialSession',{})
        if initial.get('sites')!={'sites':[]} or str(initial.get('messages',{}).get('numberOfMessages'))!='0' or initial.get('spider')!={'scans':[]} or initial.get('active')!={'scans':[]}: raise EvidenceInvalid('fresh session proof missing/failed')
    if product['schemaVersion']=='1.1':
        if manifest['provenance'].get('network')!='borrowed-bridge+UID-firewall+plan-guard': raise EvidenceInvalid('binding network proof missing')
        approved={hashlib.sha256((product['attackOrigins'][0]+p).encode()).hexdigest() for p in product['allowedPaths']}
        entries=network.get('egress',[])
        if not entries or not any(e.get('action')=='forwarded' for e in entries) or any(e.get('action')=='forwarded' and e.get('urlSha256') not in approved for e in entries): raise EvidenceInvalid('forwarded egress scope mismatch')
    readback=json.loads(safe_path(root,'report-readback.json').read_bytes())
    raw_report=safe_path(root,'report.json').read_bytes()
    if readback.get('bytes')!=len(raw_report) or readback.get('sha256')!=hashlib.sha256(raw_report).hexdigest(): raise EvidenceInvalid('report readback metadata mismatch')
    return manifest

def publish(staging,destination,manifest,canaries=()):
    if manifest.get('schemaVersion')=='2.0': raise EvidenceInvalid('v2 publication gated; verification-only contract')
    validate('manifest',manifest)
    for a in manifest['artifacts']: secret_check(safe_path(staging,a['path']).read_bytes(),canaries)
    raw=canonical(manifest); secret_check(raw,canaries)
    write_file(staging,'manifest.json',raw)
    write_file(staging,'manifest.sha256',(hashlib.sha256(raw).hexdigest()+'\n').encode())
    verify_bundle(staging)
    if Path(destination).exists(): raise EvidenceInvalid('bundle already exists')
    os.rename(staging,destination)
    fd=os.open(Path(destination).parent,os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)
