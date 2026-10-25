// Fixture-only proof for a wire-only authorization boundary. This deliberately
// uses reflection into the installed network add-on because it exposes no
// public outbound-client interceptor API. Production code must not depend on
// these internal fields; success here is evidence for an upstream/core hook.
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
const HttpRequestInterceptor = Java.type("org.apache.hc.core5.http.HttpRequestInterceptor");
const HttpResponseInterceptor = Java.type("org.apache.hc.core5.http.HttpResponseInterceptor");
const HttpClientContext = Java.type("org.apache.hc.client5.http.protocol.HttpClientContext");
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
login.getRequestBody().setBody("");
login.getResponseBody().setBody("");

// Reach the concrete network sender and its Apache processor. HttpSender
// listeners run before this conversion and therefore cannot provide the same
// history isolation.
const implField = HttpSender.class.getDeclaredField("impl");
implField.setAccessible(true);
const senderImpl = implField.get(null);
const processorField = senderImpl.getClass().getDeclaredField("mainHttpProcessor");
processorField.setAccessible(true);
const processor = processorField.get(senderImpl);
const interceptorsField = processor.getClass().getDeclaredField("requestInterceptors");
interceptorsField.setAccessible(true);
const interceptors = interceptorsField.get(processor);
const originalInterceptor = interceptors[0];
const responseInterceptorsField = processor.getClass().getDeclaredField("responseInterceptors");
responseInterceptorsField.setAccessible(true);
const responseInterceptors = responseInterceptorsField.get(processor);
const responseIndex = responseInterceptors.length - 1;
const originalResponseInterceptor = responseInterceptors[responseIndex];

const wireInterceptor = new HttpRequestInterceptor({
    process: function (request, entityDetails, context) {
        try {
            originalInterceptor.process(request, entityDetails, context);
            if (!enabled() || token === null) {
                return;
            }
            // Spider requests commonly use a relative request target and therefore
            // have no authority on the request object. The resolved route is the
            // transport-level source of truth for the actual destination.
            const route = HttpClientContext.adapt(context).getHttpRoute();
            const target = route === null ? null : route.getTargetHost();
            const scheme = target === null ? null : target.getSchemeName();
            const port = target === null ? -1
                    : (target.getPort() === -1 ? (scheme === "https" ? 443 : 80) : target.getPort());
            if (target !== null && scheme === ALLOWED_SCHEME
                    && target.getHostName() === ALLOWED_HOST && port === ALLOWED_PORT) {
                request.setHeader("Authorization", "Bearer " + token);
                setState("wireInjected", true);
            } else if (!request.containsHeader("Authorization")) {
                setState("crossOriginClean", true);
            }
        } catch (error) {
            setState("requestError", error.getClass === undefined
                    ? String(error) : error.getClass().getName() + ":" + error.getMessage());
            throw error;
        }
    }
});

// ZAP 2.17 copies the Apache request headers back into HttpMessage after the
// exchange. Strip the wire-only secret from the Apache request during response
// processing so that copy-back and all later history writers see a clean model.
const wireCleanupInterceptor = new HttpResponseInterceptor({
    process: function (response, entityDetails, context) {
        try {
            originalResponseInterceptor.process(response, entityDetails, context);
            const wireRequest = HttpClientContext.adapt(context).getRequest();
            if (wireRequest !== null && wireRequest.containsHeader("Authorization")) {
                wireRequest.removeHeaders("Authorization");
                setState("wireRemoved", true);
            }
        } catch (error) {
            setState("responseError", error.getClass === undefined
                    ? String(error) : error.getClass().getName() + ":" + error.getMessage());
            throw error;
        }
    }
});

setState("enabled", true);
interceptors[0] = wireInterceptor;
responseInterceptors[responseIndex] = wireCleanupInterceptor;

// Restore the network internals and erase the token once the test disables the
// lease and sends any request. This keeps the fixture isolated within a shared
// Docker test class.
let cleanupListener = null;
cleanupListener = new HttpSenderListener({
    getListenerOrder: function () { return -2147483000; },
    onHttpRequestSend: function (msg, initiator, sender) {
        if (!enabled()) {
            interceptors[0] = originalInterceptor;
            responseInterceptors[responseIndex] = originalResponseInterceptor;
            token = null;
            HttpSender.removeListener(cleanupListener);
            setState("cleaned", true);
        }
    },
    onHttpResponseReceive: function (msg, initiator, sender) {}
});
HttpSender.addListener(cleanupListener);

const protectedMessage = new HttpMessage(new URI(PROTECTED_URL, false));
new HttpSender(HttpSender.SPIDER_INITIATOR).sendAndReceive(protectedMessage, false);
setState("protectedStatus", protectedMessage.getResponseHeader().getStatusCode());
setState("modelHeaderClean", protectedMessage.getRequestHeader().getHeader("Authorization") === null);
new HistoryReference(Model.getSingleton().getSession(), HistoryReference.TYPE_MANUAL, protectedMessage);

const crossOriginMessage = new HttpMessage(new URI(CROSS_ORIGIN_URL, false));
new HttpSender(HttpSender.SPIDER_INITIATOR).sendAndReceive(crossOriginMessage, false);
setState("crossOriginStatus", crossOriginMessage.getResponseHeader().getStatusCode());
new HistoryReference(Model.getSingleton().getSession(), HistoryReference.TYPE_MANUAL, crossOriginMessage);
setState("ready", true);
