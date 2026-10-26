"""Bounded canary auditor. Seeded parser controls are not sink-access proof.

Only metadata leaves the auditor. Unknown/unreadable/binary/oversized sinks block
G3. Decoding support is explicit: UTF-8, base64, percent and JSON escapes, with
at most two decoding steps. Compression and database formats require a reader.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import stat
import os
from itertools import islice
from pathlib import Path
from urllib.parse import unquote_to_bytes

from .secret_inventory import SINKS, LIFECYCLE


class CanaryAuditor:
    def __init__(self, canaries):
        if not canaries or any(not isinstance(s, str) or len(s) < 12 for s in canaries):
            raise ValueError('invalid canary inventory')
        self._secrets = tuple(s.encode() for s in canaries)
        forms=set(self._secrets)
        for s in self._secrets:
            forms.update((base64.b64encode(s),base64.b64encode(s).rstrip(b'='),
                          base64.urlsafe_b64encode(s),base64.urlsafe_b64encode(s).rstrip(b'=')))
        # Factor shared prefixes instead of repeatedly scanning each byte view
        # for hundreds of independent canary forms.
        groups={}
        for form in forms:groups.setdefault(form[:8],[]).append(form[8:])
        self._pattern=re.compile(b'|'.join(re.escape(prefix)+b'(?:'+b'|'.join(re.escape(s) for s in tails)+b')'
                                          for prefix,tails in groups.items()))

    def matches(self, blob):
        if not isinstance(blob, bytes) or len(blob) > 8 * 1024 * 1024:
            raise ValueError('bounded bytes required')
        # Search both precomputed forms (embedded/unpadded base64) and bounded
        # decoded views (mixed-case percent, unicode JSON, nested encodings).
        views = [blob]
        for _ in range(2):
            if any(self._pattern.search(v) for v in views):return True
            next_views = []
            for view in views:
                if len(next_views)>=128:break
                next_views.append(unquote_to_bytes(view))
                # Decode escaped characters without allowing executable objects.
                def escape(m):
                    try:
                        return json.loads(b'"' + m[0] + b'"').encode()
                    except (ValueError, UnicodeError):
                        return m[0]
                if len(next_views)<128:next_views.append(re.sub(rb'\\(?:u[0-9a-fA-F]{4}|["\\/bfnrt])', escape, view))
                for m in islice(re.finditer(rb'[A-Za-z0-9_+/-]{12,}={0,2}', view),128-len(next_views)):
                    try:
                        raw = m[0].replace(b'-', b'+').replace(b'_', b'/')
                        next_views.append(base64.b64decode(raw + b'=' * (-len(raw) % 4), validate=True))
                    except (ValueError, binascii.Error):
                        pass
            views = next_views
        return any(self._pattern.search(v) for v in views)

    def response_safe(self, response):
        try:
            # Session-setting response headers may introduce a second secret.
            if any(k.lower() in ('authorization', 'set-cookie', 'www-authenticate')
                   for k in response.get('headers', {})):
                return False
            return not self.matches(json.dumps(response, ensure_ascii=False).encode())
        except (TypeError, ValueError):
            return False

    @staticmethod
    def read_file(root, relative):
        """No-follow every path component; refuse aliases, links and changing files."""
        parts = Path(relative).parts
        if (not parts or Path(relative).is_absolute() or '..' in parts
                or str(Path(relative)) != relative):
            raise ValueError('unsafe sink reference')
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for part in parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
            child = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            with os.fdopen(child, 'rb') as stream:
                before = os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > 8*1024*1024:
                    raise ValueError('unsupported sink file')
                blob = stream.read(8*1024*1024 + 1)
                after = os.fstat(stream.fileno())
                if (len(blob) != before.st_size or len(blob) > 8*1024*1024
                        or (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) !=
                           (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
                    raise ValueError('sink changed during read')
                return blob
        finally:
            os.close(fd)

    def audit(self, root, inventory, *, required_lifecycle=LIFECYCLE):
        """Inventory covers exact (sink,lifecycle) pairs; no fabricated N/A/pass.

        `reader` is utf8 only today. A .db that happens to contain no plain canary
        cannot be accepted as a fully decoded ZAP session/history database.
        """
        expected = {(s, c) for s in SINKS for c in required_lifecycle}
        keys = [(r.get('sinkId'), r.get('lifecycle')) for r in inventory]
        if len(keys) != len(set(keys)) or set(keys) != expected:
            raise ValueError('incomplete or duplicate sink lifecycle inventory')
        rows = []
        for row in inventory:
            result = {'sinkId': row['sinkId'], 'lifecycle': row['lifecycle']}
            try:
                if row.get('reader') != 'utf8':
                    raise ValueError('unproven decoder')
                data = self.read_file(root, row['path'])
                data.decode('utf-8')
                result.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                              status='leak' if self.matches(data) else 'clear')
            except (OSError, ValueError, KeyError, UnicodeError):
                result.update(status='blocked', reason='sink_access_or_decoder_unproven')
            rows.append(result)
        status = 'fail' if any(r['status'] == 'leak' for r in rows) else (
            'blocked' if any(r['status'] == 'blocked' for r in rows) else 'clear')
        return {'schemaVersion': 'canary-audit/1.0', 'auditStatus': status,
                'g3Status': 'blocked', 'secretValuesIncluded': False, 'results': rows,
                'limitation': 'Clear bytes do not prove inventory completeness, sink access across processes, or G3 admission.'}
