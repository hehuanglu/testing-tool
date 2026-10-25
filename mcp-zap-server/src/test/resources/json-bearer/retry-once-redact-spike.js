// Feasibility spike only. The Docker integration test replaces these placeholders
// with non-secret values for its isolated context and user.
const CONTEXT_ID = __CONTEXT_ID__;
const USER_ID = __USER_ID__;
const ALLOWED_SCHEME = "__ALLOWED_SCHEME__";
const ALLOWED_HOST = "__ALLOWED_HOST__";
const ALLOWED_PORT = __ALLOWED_PORT__;

const Control = Java.type("org.parosproxy.paros.control.Control");
const ExtensionUserManagement = Java.type("org.zaproxy.zap.extension.users.ExtensionUserManagement");
const ScriptVars = Java.type("org.zaproxy.zap.extension.script.ScriptVars");
const URI = Java.type("org.apache.commons.httpclient.URI");
const HttpSender = Java.type("org.parosproxy.paros.network.HttpSender");
const STATE_PREFIX = "__STATE_PREFIX__";

function state(name) {
    return ScriptVars.getGlobalVar(STATE_PREFIX + name) === "true";
}

function setState(name, value) {
    ScriptVars.setGlobalVar(STATE_PREFIX + name, value ? "true" : "false");
}

function isAllowedOrigin(msg) {
    const uri = msg.getRequestHeader().getURI();
    const port = uri.getPort() === -1 ? (uri.getScheme() === "https" ? 443 : 80) : uri.getPort();
    return uri.getScheme() === ALLOWED_SCHEME && uri.getHost() === ALLOWED_HOST && port === ALLOWED_PORT;
}

function redact(msg) {
    const value = msg.getRequestHeader().getHeader("Authorization");
    if (value !== null && value.startsWith("Bearer ")) {
        msg.getRequestHeader().setHeader("Authorization", "<redacted>");
    }
}

function configuredUser() {
    const loader = Control.getSingleton().getExtensionLoader();
    const users = loader.getExtension(ExtensionUserManagement.class);
    return users.getContextUserAuthManager(CONTEXT_ID).getUserById(USER_ID);
}

function sendingRequest(msg, initiator, helper) {
    setState("sendSeen", true);
    if (isAllowedOrigin(msg) && state("blocked") && !state("retryInProgress")) {
        msg.getRequestHeader().setHeader("Authorization", null);
        msg.getRequestHeader().setHeader("X-ZAP-Auth-Blocked", "true");
        // Keep fail-closed traffic inside the ZAP process boundary. The MCP-side
        // controller must observe the marker/state and stop the owning scan.
        msg.getRequestHeader().setURI(new URI("http://127.0.0.1:8090/JSON/core/view/version/", false));
    }
}

function responseReceived(msg, initiator, helper) {
    setState("responseSeen", true);
    if (msg.getRequestHeader().getHeader("X-ZAP-Auth-Blocked") === "true") {
        redact(msg);
        return;
    }
    if (!isAllowedOrigin(msg)) {
        return;
    }
    setState("allowedSeen", true);
    if (msg.getResponseHeader().getStatusCode() === 401) {
        setState("unauthorizedSeen", true);
    }
    if (msg.getResponseHeader().getStatusCode() === 200) {
        setState("successSeen", true);
    }

    if (!state("retryInProgress") && msg.getResponseHeader().getStatusCode() === 401
            && !state("retryAttempted")) {
        setState("retryAttempted", true);
        const user = configuredUser();
        // A server-side token revocation is not visible to ZAP's local auth clock.
        // Reset that clock so authenticate() performs one real login rather than
        // treating the stale session as still authenticated.
        user.getAuthenticationState().setLastSuccessfulAuthTime(0);
        user.authenticate();

        const retry = msg.cloneAll();
        retry.setHistoryRef(null);
        retry.getRequestHeader().setHeader("Authorization", null);
        user.processMessageToMatchUser(retry);
        setState("retryInProgress", true);
        try {
            // Do not reuse the original user-bound sender: its own auth listener
            // may start a second login cycle after a failed retry.
            const retrySender = new HttpSender(initiator);
            retrySender.sendAndReceive(retry, false);
        } finally {
            setState("retryInProgress", false);
        }
        msg.setResponseHeader(retry.getResponseHeader());
        msg.setResponseBody(retry.getResponseBody());
        if (retry.getResponseHeader().getStatusCode() === 401
                || retry.getResponseHeader().getStatusCode() === 403) {
            setState("blocked", true);
        }
    } else if (!state("retryInProgress") && (msg.getResponseHeader().getStatusCode() === 401
            || msg.getResponseHeader().getStatusCode() === 403)) {
        setState("blocked", true);
    }
    redact(msg);
}
