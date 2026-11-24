"""Generate a narrow Automation Framework plan, represented as JSON-compatible YAML."""

from fixture import ACTORS, CSP_AUTH, CSP_OPEN, PASSWORD


def generate(origin, directory, scenario):
    # Separate exploration contexts keep earlier Requestor traffic out of Spider scope.
    base = origin.replace(".", r"\.")
    users = [
        {"name": actor, "credentials": {
            "username": actor,
            "password": "wrong-fixture-password" if scenario == "bad-password" and actor == "reader"
            else PASSWORD,
        }}
        for actor in ACTORS
    ]
    context = {
        "name": "fixture", "urls": [origin],
        "includePaths": [base + r"/(?:login|public/.*|private/.*|identity/.*|ready)"],
        "authentication": {
            "method": "form",
            "parameters": {"loginPageUrl": origin + "/login", "loginRequestUrl": origin + "/login",
                           "loginRequestBody": "username={%username%}&password={%password%}"},
            "verification": {"method": "response", "loggedInRegex": "signed-in",
                             "loggedOutRegex": "logged-out"},
        },
        "sessionManagement": {"method": "cookie", "parameters": {}},
        "users": users,
    }

    def requestor(name, paths, user=None):
        return {
            "type": "requestor", "name": name, "parameters": {"user": user} if user else {},
            "requests": [{"url": origin + path, "method": "GET", "responseCode": status}
                         for path, status in paths],
        }

    public_paths = [(path, 200) for path in CSP_OPEN] + [("/identity/guest", 401)]
    if scenario == "warning":
        public_paths.append(("/ready", 204))
    jobs = [requestor("public-control", public_paths)]
    jobs.append(requestor("reader-requests", [("/identity/reader", 200)]
                          + [(path, 200) for path in CSP_AUTH], "reader"))
    jobs.append(requestor("editor-requests", [("/identity/editor", 200)], "editor"))
    contexts = [context]
    for actor, user in zip(ACTORS, users):
        contexts.append({
            **context, "name": actor + "-scope", "urls": [f"{origin}/explore/{actor}/"],
            "includePaths": [base + rf"/(?:login|explore/{actor}/.*)"],
            "excludePaths": [base + rf"/(?!login$|explore/{actor}/).*"],
            "users": [dict(user, name=actor + "-explorer")],
        })
        jobs.append({"type": "spider", "name": f"{actor}-exploration", "parameters": {
            "context": actor + "-scope", "user": actor + "-explorer",
            "url": f"{origin}/explore/{actor}/", "maxDuration": 0,
            "postForm": False, "processForm": False, "parseRobotsTxt": False,
            "parseSitemapXml": False,
        }})
    jobs += [
        {"type": "passiveScan-wait", "name": "drain-passive", "parameters": {"maxDuration": 0}},
        {"type": "report", "name": "write-report", "parameters": {
            "template": "traditional-json", "reportDir": str(directory), "reportFile": "zap-report",
        }},
    ]
    if scenario == "bad-plan":
        jobs.insert(0, {"type": "invalidFeasibilityJob"})
    return {"env": {"contexts": contexts, "parameters": {"failOnError": True,
                                                         "failOnWarning": False}}, "jobs": jobs}
