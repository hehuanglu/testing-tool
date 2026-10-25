// Fixture-only transport probe for the smallest credible ZAP add-on design.
// The synthetic fixture credential is intentionally not a production secret.
// Login is owned by this controller and is never added to ZAP history. The
// token lives only in this script closure, like it would in a private Java map.
const ALLOWED_SCHEME = "http";
const ALLOWED_HOST = "client-auth-target";
const ALLOWED_PORT = 8080;
const LOGIN_URL = "http://client-auth-target:8080/bearer/login";
const PROTECTED_URL = "http://client-auth-target:8080/bearer/user";
const CROSS_ORIGIN_URL = "http://direct-scan-target/";
const STATE_PREFIX = "__STATE_PREFIX__";

const HttpMessage = Java.type("org.parosproxy.paros.network.HttpMessage");
const HttpRequestHeader = Java.type("org.parosproxy.paros.network.HttpRequestHeader");
const HttpSender = Java.type("org.parosproxy.paros.network.HttpSender");
const HttpSenderListener = Java.type("org.zaproxy.zap.network.HttpSenderListener");
const HistoryReference = Java.type("org.parosproxy.paros.model.HistoryReference");
const Model = Java.type("org.parosproxy.paros.model.Model");
const ScriptVars = Java.type("org.zaproxy.zap.extension.script.ScriptVars");
const URI = Java.type("org.apache.commons.httpclient.URI");
const JSONObject = Java.type("net.sf.json.JSONObject");

let token = null;

function setState(name, value) {
    ScriptVars.setGlobalVar(STATE_PREFIX + name, String(value));
}

function enabled() {
    return ScriptVars.getGlobalVar(STATE_PREFIX + "enabled") === "true";
}

function isAllowedOrigin(msg) {
    const uri = msg.getRequestHeader().getURI();
    const port = uri.getPort() === -1 ? (uri.getScheme() === "https" ? 443 : 80) : uri.getPort();
    return uri.getScheme() === ALLOWED_SCHEME && uri.getHost() === ALLOWED_HOST && port === ALLOWED_PORT;
}

const listener = new HttpSenderListener({
    getListenerOrder: function () {
        return 2147483000;
    },
    onHttpRequestSend: function (msg, initiator, sender) {
        if (!enabled() || token === null) {
            return;
        }
        if (isAllowedOrigin(msg)) {
            msg.getRequestHeader().setHeader("Authorization", "Bearer " + token);
            setState("sameOriginInjected", true);
        } else if (msg.getRequestHeader().getHeader("Authorization") === null) {
            setState("crossOriginClean", true);
        }
    },
    onHttpResponseReceive: function (msg, initiator, sender) {
        if (!enabled()) {
            return;
        }
        const authorization = msg.getRequestHeader().getHeader("Authorization");
        if (authorization !== null && authorization.startsWith("Bearer ")) {
            msg.getRequestHeader().setHeader("Authorization", "<redacted>");
            setState("redacted", true);
        }
    }
});

const login = new HttpMessage(new URI(LOGIN_URL, false));
login.getRequestHeader().setMethod(HttpRequestHeader.POST);
login.getRequestHeader().setHeader("Content-Type", "application/json");
login.getRequestBody().setBody('{"username":"scan-user","password":"fixture-password"}');
login.getRequestHeader().setContentLength(login.getRequestBody().length());
new HttpSender(HttpSender.AUTHENTICATION_HELPER_INITIATOR).sendAndReceive(login, false);
if (login.getResponseHeader().getStatusCode() !== 200) {
    throw new Error("fixture login failed");
}
token = JSONObject.fromObject(login.getResponseBody().toString()).getJSONObject("data").getString("accessToken");
// Erase the only message object that temporarily held the credential/token.
login.getRequestBody().setBody("");
login.getResponseBody().setBody("");

setState("enabled", true);
HttpSender.addListener(listener);

const protectedMessage = new HttpMessage(new URI(PROTECTED_URL, false));
new HttpSender(HttpSender.SPIDER_INITIATOR).sendAndReceive(protectedMessage, false);
setState("protectedStatus", protectedMessage.getResponseHeader().getStatusCode());
new HistoryReference(Model.getSingleton().getSession(), HistoryReference.TYPE_MANUAL, protectedMessage);

const crossOriginMessage = new HttpMessage(new URI(CROSS_ORIGIN_URL, false));
new HttpSender(HttpSender.SPIDER_INITIATOR).sendAndReceive(crossOriginMessage, false);
setState("crossOriginStatus", crossOriginMessage.getResponseHeader().getStatusCode());
new HistoryReference(Model.getSingleton().getSession(), HistoryReference.TYPE_MANUAL, crossOriginMessage);

setState("ready", true);
