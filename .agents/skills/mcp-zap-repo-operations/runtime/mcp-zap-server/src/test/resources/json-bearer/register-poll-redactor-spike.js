// Fixture-only probe for the Java HttpSenderListener extension point. Unlike an
// HTTP Sender script, this registers the same interface a ZAP add-on would use.
// It deliberately redacts only authentication polling; the test demonstrates
// that native JSON login history remains outside this safe interception point.
const HttpSender = Java.type("org.parosproxy.paros.network.HttpSender");
const HttpSenderListener = Java.type("org.zaproxy.zap.network.HttpSenderListener");
const ScriptVars = Java.type("org.zaproxy.zap.extension.script.ScriptVars");
const STATE_PREFIX = "__STATE_PREFIX__";

function enabled() {
    return ScriptVars.getGlobalVar(STATE_PREFIX + "enabled") === "true";
}

const listener = new HttpSenderListener({
    getListenerOrder: function () {
        // Run after normal authentication/session listeners but still before
        // AuthenticationHelper persists the returned HttpMessage.
        return 2147483000;
    },
    onHttpRequestSend: function (msg, initiator, sender) {
        if (!enabled()) {
            return;
        }
        if (initiator === HttpSender.AUTHENTICATION_POLL_INITIATOR) {
            ScriptVars.setGlobalVar(STATE_PREFIX + "pollRequestSeen", "true");
        }
        if (initiator === HttpSender.AUTHENTICATION_INITIATOR) {
            ScriptVars.setGlobalVar(STATE_PREFIX + "loginRequestSeen", "true");
        }
    },
    onHttpResponseReceive: function (msg, initiator, sender) {
        if (!enabled() || initiator !== HttpSender.AUTHENTICATION_POLL_INITIATOR) {
            return;
        }
        const authorization = msg.getRequestHeader().getHeader("Authorization");
        if (authorization !== null && authorization.startsWith("Bearer ")) {
            msg.getRequestHeader().setHeader("Authorization", "<redacted>");
            ScriptVars.setGlobalVar(STATE_PREFIX + "pollRedacted", "true");
        }
    }
});

ScriptVars.setGlobalVar(STATE_PREFIX + "enabled", "true");
HttpSender.addListener(listener);
ScriptVars.setGlobalVar(STATE_PREFIX + "registered", "true");
