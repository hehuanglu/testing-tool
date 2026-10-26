"""Required secret proof denominator, shared with the stdlib-only guard."""
SINKS = frozenset(('prompt-tool-output','command-arguments','repository','journal','browser-profile',
                  'zap-history','zap-session-db','logs','reports','exports','bundle','crash-restart','credential-copy'))
LIFECYCLE = frozenset(('success','login-failure','crawl','active','expiry','refresh-failure',
                      'exception','cancel','restart','crash','cleanup'))
ENCODINGS = frozenset(('raw-utf8','base64-standard','base64-url','url-percent','json-escape'))
