"""Bounded standard-library HTTP exchange; also the isolated Docker stdin worker."""
import http.client
import ipaddress
import json
import socket
import threading
import time
from urllib.parse import urlsplit


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON field')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def exchange(origin, method, path, headers, payload, timeout, not_after=None, *, ssl_context=None, allow_empty=False):
    url = urlsplit(origin)
    try:
        ipaddress.IPv4Address(url.hostname)
    except ValueError:
        # An explicit verified local CA is the only hostname extension. Keep
        # legacy/Docker workers literal-IP only and reject DNS escape.
        if ssl_context is None or url.hostname != 'localhost' or any(
                not ipaddress.ip_address(row[4][0]).is_loopback
                for row in socket.getaddrinfo(url.hostname, url.port)):
            raise ValueError('unsupported hostname transport') from None
    kind = http.client.HTTPSConnection if url.scheme == 'https' else http.client.HTTPConnection
    # Optional verified local CA for the research direct client. Legacy callers
    # retain the default trust store and the literal IPv4 restriction.
    options = {'context': ssl_context} if ssl_context is not None and url.scheme == 'https' else {}
    connection = kind(url.hostname, url.port, timeout=timeout, **options)
    deadline = time.monotonic()+timeout
    timer = None
    expired = threading.Event()
    try:
        if not_after is not None and time.time() >= not_after:
            raise ValueError('authority expired before connect')
        connection.connect()
        sock = connection.sock
        def abort():
            expired.set()
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        remaining = deadline-time.monotonic()
        if remaining <= 0:
            raise TimeoutError()
        timer = threading.Timer(remaining, abort)
        timer.daemon = True
        timer.start()
        if not_after is not None and time.time() >= not_after:
            raise ValueError('authority expired before send')
        connection.request(method, path, body=payload, headers=headers)
        response = connection.getresponse()
        if (300 <= response.status < 400 or response.getheader('Content-Encoding', 'identity') != 'identity'
                or (not (allow_empty and response.status == 204) and response.getheader('Content-Type', '').split(';')[0].strip() != 'application/json')):
            raise ValueError('response contract rejected')
        chunks, size = [], 0
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError()
            part = response.read1(min(8192, 65537-size))
            if not part:
                break
            chunks.append(part)
            size += len(part)
            if size > 65536:
                raise ValueError('response exceeds byte budget')
        if expired.is_set():
            raise TimeoutError()
        return response.status, (None if allow_empty and response.status == 204 and size == 0 else decode(b''.join(chunks))), size
    except (OSError, ValueError, http.client.HTTPException):
        if expired.is_set():
            raise TimeoutError() from None
        raise
    finally:
        if timer:
            timer.cancel()
            timer.join()
        connection.close()


def worker():
    import sys
    try:
        job = decode(sys.stdin.buffer.read(65537))
        u = urlsplit(job['origin'])
        address = ipaddress.IPv4Address(u.hostname)
        if (u.scheme not in ('http', 'https') or u.path or u.query or u.fragment or u.username or u.password
                or address.is_link_local or address.is_multicast or address.is_unspecified):
            raise ValueError()
        allowed = {('POST', '/api/auth/login'), ('GET', '/api/v1/accounts'),
                   ('GET', '/api/v1/accounts/'+str(job['accountId']))}
        if (job['method'], job['path']) not in allowed or 'Cookie' in job['headers'] or 'Host' in job['headers']:
            raise ValueError()
        status, body, size = exchange(job['origin'], job['method'], job['path'], job['headers'],
                                      job['payload'].encode() if job['payload'] is not None else None,
                                      min(5, job['timeout']), job['notAfter'])
        # Captured only by parent process memory. Never docker logs or a tool result.
        print(json.dumps({'ok': True, 'status': status, 'body': body, 'size': size}))
    except (Exception,):
        print(json.dumps({'ok': False, 'error': 'bounded-exchange-failed'}))


if __name__ == '__main__':
    worker()
