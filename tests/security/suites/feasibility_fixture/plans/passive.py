"""Retain the Requestor, passive-drain and report steps from the qualified plan."""

from plan import generate


def render(origin, directory, scenario, profiles):
    definition = generate(origin, directory, scenario)
    env = definition["env"]
    env["contexts"] = env["contexts"][:1]
    jobs = definition["jobs"]
    definition["jobs"] = [job for job in jobs if job["type"] != "spider"]
    if not profiles:
        env["contexts"][0] = {"name": "fixture", "urls": [origin]}
        definition["jobs"] = [job for job in definition["jobs"]
                              if job["type"] != "requestor" or not job["parameters"].get("user")]
    else:
        profile, = profiles.values()
        context = env["contexts"][0]
        if set(profile["actors"]) != {user["name"] for user in context["users"]}:
            raise ValueError("fixture actor configuration does not match provisioned users")
        auth = context["authentication"]
        auth["parameters"].update(
            loginPageUrl=origin + profile["loginPath"], loginRequestUrl=origin + profile["loginPath"],
            loginRequestBody=profile["loginRequestBody"],
        )
        auth["verification"].update(loggedInRegex=profile["loggedInRegex"],
                                    loggedOutRegex=profile["loggedOutRegex"])
    if scenario == "incomplete":
        definition["jobs"][0]["requests"].pop(0)
    return definition
