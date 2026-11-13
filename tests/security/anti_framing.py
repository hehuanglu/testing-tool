"""Narrow HTTP response-header oracle for ``anti-framing-http-v1``.

This module interprets policy headers only.  It does not claim that a browser
navigation was attempted or that browser enforcement was observed.
"""

from __future__ import annotations

import re


_HOST_SOURCE = re.compile(
    r"^(?:[a-z][a-z0-9+.-]*:|(?:[a-z][a-z0-9+.-]*://)?(?:\*\.)?"
    r"[a-z0-9.-]+(?::(?:\d+|\*))?)$",
    re.IGNORECASE,
)


def _result(state, reason, mechanism=None, details=None):
    value = {
        "assumption": "modern-user-agent-csp3-html-xfo",
        "browserEnforcementTested": False,
        "reason": reason,
        "state": state,
    }
    if mechanism is not None:
        value["mechanism"] = mechanism
    if details:
        value["details"] = details
    return value


def _frame_ancestors(policy):
    directives = {}
    for raw_directive in policy.split(";"):
        raw_directive = raw_directive.strip()
        if not raw_directive:
            continue
        pieces = raw_directive.split()
        name = pieces[0].lower()
        if name in directives:
            return "indeterminate", "DUPLICATE_CSP_DIRECTIVE"
        directives[name] = pieces[1:]
    if "frame-ancestors" not in directives:
        return "absent", None
    sources = directives["frame-ancestors"]
    if not sources:
        return "indeterminate", "EMPTY_FRAME_ANCESTORS"
    lowered = [source.lower() for source in sources]
    if lowered == ["'none'"]:
        return "protected", "CSP_FRAME_ANCESTORS_NONE"
    if "'none'" in lowered:
        return "indeterminate", "MIXED_NONE_FRAME_ANCESTORS"
    if lowered == ["'self'"]:
        # CSP source matching can upgrade an HTTP protected origin to a secure
        # same-host origin.  That is broader than this profile's exact-origin
        # trust boundary, so a header-only parser without an ancestor origin
        # must not call it protected.
        return "indeterminate", "CSP_SELF_REQUIRES_ORIGIN_MATCH_EVALUATION"
    for source in lowered:
        if source in ("*", "'self'"):
            continue
        if not _HOST_SOURCE.fullmatch(source):
            return "indeterminate", "UNSUPPORTED_FRAME_ANCESTORS_SOURCE"
    # This profile's trust boundary is same-origin only.  A wildcard, scheme,
    # or host source admits at least one untrusted cross-origin ancestor.
    return "unprotected", "CSP_FRAME_ANCESTORS_ALLOWS_CROSS_ORIGIN"


def evaluate_anti_framing(headers):
    """Evaluate complete lower-case response-header lists.

    Supported protection is an enforcing CSP ``frame-ancestors 'none'`` or
    ``'self'``, or (when no enforcing frame-ancestors directive exists) one
    unambiguous X-Frame-Options value of DENY or SAMEORIGIN.
    """
    enforcing = headers.get("content-security-policy", [])
    report_only = headers.get("content-security-policy-report-only", [])
    if not all(isinstance(value, str) and value.strip() for value in enforcing + report_only):
        return _result("indeterminate", "EMPTY_OR_NON_STRING_POLICY_HEADER")

    frame_results = [_frame_ancestors(policy) for policy in enforcing]
    present = [row for row in frame_results if row[0] != "absent"]
    if present:
        if any(reason == "CSP_FRAME_ANCESTORS_NONE" for _, reason in present):
            return _result("protected", "ENFORCING_CSP_RESTRICTS_FRAME_ANCESTORS",
                           "csp-frame-ancestors", ["CSP_FRAME_ANCESTORS_NONE"])
        if any(state == "indeterminate" for state, _ in present):
            return _result("indeterminate", next(reason for state, reason in present
                                                  if state == "indeterminate"),
                           "csp-frame-ancestors")
        if len(present) > 1:
            return _result("indeterminate", "MULTIPLE_FRAME_ANCESTOR_POLICIES_REQUIRE_INTERSECTION",
                           "csp-frame-ancestors")
        return _result("unprotected", "ENFORCING_CSP_ALLOWS_UNTRUSTED_FRAME_ANCESTOR",
                       "csp-frame-ancestors", sorted({reason for _, reason in present}))

    xfo_fields = headers.get("x-frame-options", [])
    # Comma-combined or repeated values have browser-specific/confusion
    # handling.  They are deliberately outside this profile's narrow parser.
    if len(xfo_fields) > 1 or any("," in value for value in xfo_fields):
        return _result("indeterminate", "COMPLEX_OR_CONFLICTING_X_FRAME_OPTIONS",
                       "x-frame-options")
    if len(xfo_fields) == 1:
        value = xfo_fields[0].strip().upper()
        if value in ("DENY", "SAMEORIGIN"):
            return _result("protected", "X_FRAME_OPTIONS_" + value,
                           "x-frame-options")
        return _result("indeterminate", "INVALID_OR_UNSUPPORTED_X_FRAME_OPTIONS",
                       "x-frame-options")

    # Report-Only is retained in details but is not enforcement.
    details = ["report-only-present"] if report_only else None
    return _result("unprotected", "NO_ENFORCING_ANTI_FRAMING_POLICY", details=details)
