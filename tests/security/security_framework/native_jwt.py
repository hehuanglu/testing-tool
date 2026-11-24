"""Build the reviewed native JSON-login and header-session passive plan."""

from dataclasses import dataclass
import re

from .manifest import require

MARKER = "X-Fixture-Check"
CONTROL = "/__pilot_passive_control"
CONTROL_RULE = "10038-1"
MODE = "zap-owned-jwt-requestor"
ACTOR = "fixture-user"
PATH = re.compile(r"/[A-Za-z0-9/_-]+\Z")
FIELD = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")
PLACEHOLDERS = {"username": "${FIXTURE_USER_EMAIL}", "password": "${FIXTURE_USER_PASSWORD}"}


@dataclass(frozen=True)
class NativeJwt:
    login_path: str
    profile_path: str
    username_field: str
    password_field: str
    token_field: str
    subject: int

    def plan(self, origin, directory):
        require(all(PATH.fullmatch(path) for path in (self.login_path, self.profile_path))
                and len({self.login_path, self.profile_path, CONTROL}) == 3, "native JWT paths")
        fields = (self.username_field, self.password_field, self.token_field)
        require(all(FIELD.fullmatch(field) for field in fields) and len(set(fields)) == 3
                and type(self.subject) is int and self.subject > 0, "native JWT fields")
        profile_url = origin + self.profile_path
        return {
            "env": {
                "contexts": [{
                    "name": MODE, "urls": [origin],
                    "includePaths": ["^" + re.escape(profile_url) + "$"],
                    "authentication": {
                        "method": "json",
                        "parameters": {
                            "loginPageUrl": origin + self.login_path,
                            "loginRequestUrl": origin + self.login_path,
                            "loginRequestBody": ('{"%s":"{%%username%%}","%s":"{%%password%%}"}'
                                                 % (self.username_field, self.password_field)),
                        },
                        "verification": {
                            "method": "poll", "pollUrl": profile_url, "pollFrequency": 1, "pollUnits": "requests",
                            "loggedInRegex": r'"id"\s*:\s*' + str(self.subject) + r"\b",
                            "loggedOutRegex": r"(?im)^WWW-Authenticate:\s*Bearer\b",
                        },
                    },
                    "sessionManagement": {
                        "method": "headers", "parameters": {"Authorization": "Bearer {%json:" + self.token_field + "%}"},
                    },
                    "users": [{"name": ACTOR, "credentials": PLACEHOLDERS.copy()}],
                }],
                "parameters": {"failOnError": True, "failOnWarning": False},
            },
            "jobs": [
                {"type": "requestor", "requests": [
                    {"url": profile_url, "method": "GET", "headers": [MARKER + ": anonymous"], "responseCode": 401},
                    {"url": origin + CONTROL, "method": "GET", "responseCode": 200},
                ]},
                {"type": "requestor", "parameters": {"user": ACTOR}, "requests": [
                    {"url": profile_url, "method": "GET", "headers": [MARKER + ": authenticated"], "responseCode": 200},
                ]},
                {"type": "passiveScan-wait", "parameters": {"maxDuration": 0}},
                {"type": "report", "parameters": {
                    "template": "traditional-json", "reportDir": str(directory), "reportFile": "zap-report",
                }},
            ],
        }


def identity_status(events, expected_role):
    """Correlate a fixed anonymous control, a native login, its poll and its named request."""
    allowed = {"anonymous", "passive-control", "login-page", "login", "poll", "authenticated"}
    if any(row["phase"] not in allowed for row in events):
        return "SCANNER_WITNESS_MISMATCH"
    anonymous = [row for row in events if row["phase"] == "anonymous"]
    if not anonymous:
        return "INCOMPLETE_EXECUTION"
    if anonymous != [{"phase": "anonymous", "status": 401, "bearer": False, "challenge": True}]:
        return "AUTHENTICATION_FAILURE"
    logins = [index for index, row in enumerate(events) if row["phase"] == "login" and row["status"] == 200]
    requests = [index for index, row in enumerate(events) if row["phase"] == "authenticated"]
    if any(row["phase"] == "login" and row["status"] in (400, 401, 403) for row in events):
        return "AUTHENTICATION_FAILURE"
    pages = [index for index, row in enumerate(events) if row == {"phase": "login-page", "status": 204}]
    if not logins or not requests or not pages:
        return "INCOMPLETE_EXECUTION"
    if len(pages) != 1 or len(logins) != 1 or len(requests) != 1 or not pages[0] < logins[0] < requests[0]:
        return "SCANNER_WITNESS_MISMATCH"
    profiles = [row for index, row in enumerate(events)
                if row["phase"] in ("authenticated", "poll") and index > logins[0]]
    if len(profiles) != sum(row["phase"] in ("authenticated", "poll") for row in events):
        return "SCANNER_WITNESS_MISMATCH"
    if any(
            row["status"] != 200 or row.get("bearer") is not True or row.get("issuedTokenMatches") is not True
            or row.get("principalMatches") is not True or row.get("verified") is not True
            or row.get("role") != expected_role for row in profiles):
        return "AUTHENTICATION_FAILURE"
    if not any(row["phase"] == "poll" for row in profiles):
        return "INCOMPLETE_EXECUTION"
    return None
