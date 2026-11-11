"""Strict adapter for ZAP traditional-json reports used by the regression suite."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


class ReportError(ValueError):
    pass


@dataclass(frozen=True)
class AlertInstance:
    origin: str
    method: str
    path: str
    alert_ref: str
    pointer: str
    native_id: str | None


@dataclass(frozen=True)
class ParsedReport:
    instances: tuple[AlertInstance, ...]
    capped: bool
    version: str | None


def _list(value, label):
    if not isinstance(value, list):
        raise ReportError(label + " must be an array")
    return value


def parse_report(value) -> ParsedReport:
    if not isinstance(value, dict):
        raise ReportError("report must be an object")
    sites = _list(value.get("site"), "site")
    instances = []
    capped = False
    for site_index, site in enumerate(sites):
        if not isinstance(site, dict) or not isinstance(site.get("@name"), str):
            raise ReportError(f"site/{site_index} is malformed")
        alerts = _list(site.get("alerts"), f"site/{site_index}/alerts")
        for alert_index, alert in enumerate(alerts):
            if not isinstance(alert, dict) or not isinstance(alert.get("alertRef"), str):
                raise ReportError(f"site/{site_index}/alerts/{alert_index} is malformed")
            rows = _list(alert.get("instances"),
                         f"site/{site_index}/alerts/{alert_index}/instances")
            count = alert.get("count")
            if count is not None:
                try:
                    capped = capped or int(count) > len(rows)
                except (TypeError, ValueError):
                    raise ReportError("alert count must be an integer string") from None
            for instance_index, instance in enumerate(rows):
                if not isinstance(instance, dict):
                    raise ReportError("alert instance must be an object")
                uri = instance.get("uri")
                method = instance.get("method")
                if not isinstance(uri, str) or not isinstance(method, str):
                    raise ReportError("alert instance uri and method are required")
                parsed = urlsplit(uri)
                if parsed.scheme not in ("http", "https") or not parsed.netloc:
                    raise ReportError("alert instance uri must be absolute HTTP(S)")
                origin = f"{parsed.scheme}://{parsed.netloc}"
                path = parsed.path or "/"
                if parsed.query:
                    path += "?" + parsed.query
                native_id = instance.get("id")
                if native_id is not None and not isinstance(native_id, str):
                    raise ReportError("native instance id must be a string when present")
                instances.append(AlertInstance(
                    origin=origin,
                    method=method.upper(),
                    path=path,
                    alert_ref=alert["alertRef"],
                    pointer=f"/site/{site_index}/alerts/{alert_index}/instances/{instance_index}",
                    native_id=native_id,
                ))
    return ParsedReport(tuple(instances), capped, value.get("@version"))


def load_fresh_report(path: Path, not_before_ns: int) -> tuple[dict, ParsedReport]:
    if not path.is_file():
        raise ReportError("ZAP report is missing")
    if path.stat().st_mtime_ns < not_before_ns:
        raise ReportError("ZAP report predates this invocation")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReportError("ZAP report is unreadable: " + type(error).__name__) from None
    return value, parse_report(value)


def matching_instances(report: ParsedReport, *, origin: str, method: str,
                       path: str, alert_ref: str):
    return [row for row in report.instances
            if (row.origin, row.method, row.path, row.alert_ref)
            == (origin, method.upper(), path, alert_ref)]
