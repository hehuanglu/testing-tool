"""Connect the original fixture witnesses to the standardized evidence keys."""

import json
from urllib.parse import urlencode

from app_assertions import EXPECTED_AUTHORIZATION, authorize, client, request
from fixture import CSP_AUTH, CSP_OPEN, PASSWORD
from runner import RULE, evaluate_csp, observed
from security_framework.evidence import assertion, outcome


def scanner_identities(events, profile):
    identities = {}
    for actor in profile["actors"]:
        logins = [row for row in observed(events, "POST", profile["loginPath"])
                  if row.get("loginActor") == actor]
        samples = observed(events, "GET", profile["identityPaths"][actor])
        if any(row["status"] == 401 for row in logins):
            identities[actor] = {"status": 401, "actor": None}
        elif samples and any(row["status"] == 200 and row["actor"] == actor for row in logins):
            row = next((row for row in samples if row["status"] != 200 or row["actor"] != actor),
                       samples[-1])
            identities[actor] = {"status": row["status"], "actor": row["actor"]}
    return identities


def passive(evidence, paths, actor):
    events = evidence["scannerEvents"]["data"]
    alerts = {row["path"] for row in evidence["zapReport"]["data"]["ruleInstances"]
              if row["alertRef"] == RULE and row["method"] == "GET"}
    requests = [row for row in events if row["method"] == "GET" and row["path"] in paths]
    witnesses = {"requests": requests, "alertPaths": sorted(alerts.intersection(paths))}
    return evaluate_csp(events, alerts, paths, actor), witnesses


def public_csp(_origin, evidence, _profile):
    status, witnesses = passive(evidence, CSP_OPEN, "anonymous")
    return status, {"publicCsp": witnesses}, {}


def private_csp(_origin, evidence, profile):
    status, witnesses = passive(evidence, CSP_AUTH, profile["protectedActor"])
    guest = observed(evidence["scannerEvents"]["data"], "GET", profile["guestIdentityPath"])
    witnesses["guest"] = guest
    if not guest:
        status = outcome("ERROR", "INCOMPLETE_EXECUTION")
    elif any(row["status"] != 401 or row["actor"] != "anonymous" for row in guest):
        status = outcome("FAIL", "ANONYMOUS_IDENTITY_ASSERTION")
    return status, {"protectedCsp": witnesses}, {}


def authorization(origin, _evidence, _profile):
    raw_identities, state = authorize(origin)
    identities = {actor: {"actor": row["actor"], "status": row["identityStatus"]}
                  for actor, row in raw_identities.items()}
    return (assertion(state == EXPECTED_AUTHORIZATION, "AUTHORIZATION_ASSERTION_VIOLATED"),
            {"policyTransition": {"expected": EXPECTED_AUTHORIZATION, "observed": state}},
            identities)


def initial_state(origin, _evidence, profile):
    session = client()
    actor, = profile["actors"]
    form = urlencode({"username": actor, "password": PASSWORD}).encode()
    login, _ = request(session, origin, profile["loginPath"], form, "POST")
    status, raw = request(session, origin, "/policy/state")
    state = json.loads(raw)
    identities = {actor: {"actor": state.get("actor"), "status": status if login == 200 else login}}
    observed_revision = state.get("revision")
    if type(observed_revision) is not int:
        result = outcome("ERROR", "APPLICATION_EVIDENCE_FAILURE")
    else:
        result = assertion(observed_revision == 0, "INITIAL_STATE_ASSERTION_VIOLATED")
    return result, {"initialState": {"observedRevision": observed_revision, "expectedRevision": 0}}, identities


def framework_receipt(_origin, evidence, _profile):
    events = evidence["scannerEvents"]["data"]
    status = (assertion(True, "") if observed(events, "GET", CSP_OPEN[0]) else
              outcome("ERROR", "INCOMPLETE_EXECUTION"))
    return status, {}, {}


ORACLES = {
    "public-csp": public_csp, "private-csp": private_csp, "authorization": authorization,
    "initial-state": initial_state, "framework-receipt": framework_receipt,
}
