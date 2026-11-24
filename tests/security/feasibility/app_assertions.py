"""Application-owned assertions against documented fixture operations."""

from http.cookiejar import CookieJar
import json
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, HTTPCookieProcessor, ProxyHandler, Request, build_opener

from fixture import ACTORS, PASSWORD


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def client():
    return build_opener(ProxyHandler({}), NoRedirect(), HTTPCookieProcessor(CookieJar()))


def request(session, origin, path, data=None, method="GET"):
    req = Request(origin + path, data=data, method=method)
    try:
        response = session.open(req, timeout=5)
    except HTTPError as error:
        response = error
    with response:
        return response.status, response.read()


def authorize(origin):
    actors = {actor: client() for actor in ACTORS}
    witnesses = {}
    for actor, session in actors.items():
        form = urlencode({"username": actor, "password": PASSWORD}).encode()
        login, _ = request(session, origin, "/login", form, "POST")
        status, body = request(session, origin, f"/identity/{actor}")
        identity = json.loads(body)
        witnesses[actor] = {"login": login, "identityStatus": status, "actor": identity.get("actor")}
    if any(result != {"login": 200, "identityStatus": 200, "actor": actor}
           for actor, result in witnesses.items()):
        return witnesses, None

    editor = actors["editor"]

    def state():
        status, body = request(editor, origin, "/policy/state")
        body = json.loads(body)
        if status != 200 or body.get("actor") != "editor" or type(body.get("revision")) is not int:
            raise ValueError("invalid application state witness")
        return body["revision"]

    def update(actor, session):
        status, body = request(session, origin, "/policy/update", b"", "POST")
        body = json.loads(body)
        return {"actor": actor, "resolvedActor": body.get("actor"), "status": status,
                "decision": body.get("decision"), "revisionAfter": state()}

    return witnesses, {
        "revisionBefore": state(),
        "updates": [update("anonymous", client()), update("reader", actors["reader"]),
                    update("editor", editor)],
    }


EXPECTED_AUTHORIZATION = {
    "revisionBefore": 0,
    "updates": [
        {"actor": "anonymous", "resolvedActor": None, "status": 401,
         "decision": None, "revisionAfter": 0},
        {"actor": "reader", "resolvedActor": "reader", "status": 403,
         "decision": "denied", "revisionAfter": 0},
        {"actor": "editor", "resolvedActor": "editor", "status": 200,
         "decision": "allowed", "revisionAfter": 1},
    ],
}
