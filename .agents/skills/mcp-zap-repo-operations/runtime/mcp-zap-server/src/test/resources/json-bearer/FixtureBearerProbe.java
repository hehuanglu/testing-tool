import java.util.regex.Pattern;
import org.apache.commons.httpclient.URI;
import org.parosproxy.paros.model.HistoryReference;
import org.parosproxy.paros.model.Model;
import org.parosproxy.paros.network.HttpMessage;
import org.parosproxy.paros.network.HttpSender;
import org.zaproxy.zap.extension.script.ScriptVars;
import org.zaproxy.zap.network.HttpSenderListener;

/** Test-only native listeners. A Graal callback escaping a standalone script is
 * invalid once its Context closes, even if its Java listener remains registered.
 * This fixture measures the real add-on extension point without that lifetime bug.
 */
public final class FixtureBearerProbe {
    private static void state(String p, String k, Object v) {
        ScriptVars.setGlobalVar(p + k, String.valueOf(v));
    }
    private static boolean enabled(String p) {
        return "true".equals(ScriptVars.getGlobalVar(p + "enabled"));
    }
    public static void poll(String p) {
        HttpSenderListener listener = new HttpSenderListener() {
            public int getListenerOrder() { return 2147483000; }
            public void onHttpRequestSend(HttpMessage msg, int initiator, HttpSender sender) {
                if (!enabled(p)) return;
                if (initiator == HttpSender.AUTHENTICATION_POLL_INITIATOR) state(p,"pollRequestSeen",true);
                if (initiator == HttpSender.AUTHENTICATION_INITIATOR) state(p,"loginRequestSeen",true);
            }
            public void onHttpResponseReceive(HttpMessage msg, int initiator, HttpSender sender) {
                if (!enabled(p) || initiator != HttpSender.AUTHENTICATION_POLL_INITIATOR) return;
                String auth = msg.getRequestHeader().getHeader("Authorization");
                if (auth != null && auth.startsWith("Bearer ")) {
                    msg.getRequestHeader().setHeader("Authorization", "<redacted>");
                    state(p,"pollRedacted",true);
                }
            }
        };
        state(p,"enabled",true);
        ScriptVars.setGlobalCustomVar(p + "listener", listener);
        HttpSender.addListener(listener);
        state(p,"registered",true);
    }
    public static void addon(String p) throws Exception {
        HttpMessage login = new HttpMessage(new URI("http://client-auth-target:8080/bearer/login",false));
        login.getRequestHeader().setMethod("POST");
        login.getRequestHeader().setHeader("Content-Type","application/json");
        login.getRequestBody().setBody("{\"username\":\"scan-user\",\"password\":\"fixture-password\"}");
        login.getRequestHeader().setContentLength(login.getRequestBody().length());
        new HttpSender(HttpSender.AUTHENTICATION_HELPER_INITIATOR).sendAndReceive(login,false);
        if (login.getResponseHeader().getStatusCode()!=200) throw new IllegalStateException("fixture login failed");
        var matcher=Pattern.compile("\\\"accessToken\\\"\\s*:\\s*\\\"([^\\\"]+)\\\"").matcher(login.getResponseBody().toString());
        if (!matcher.find()) throw new IllegalStateException("fixture token absent");
        String token=matcher.group(1);
        login.getRequestBody().setBody("");login.getResponseBody().setBody("");
        HttpSenderListener listener = new HttpSenderListener() {
            public int getListenerOrder() { return 2147483000; }
            public void onHttpRequestSend(HttpMessage msg, int initiator, HttpSender sender) {
                if (!enabled(p)) return;
                java.net.URI uri=java.net.URI.create(msg.getRequestHeader().getURI().toString());
                if ("http".equals(uri.getScheme()) && "client-auth-target".equals(uri.getHost()) && uri.getPort()==8080) {
                    msg.getRequestHeader().setHeader("Authorization","Bearer "+token);
                    state(p,"sameOriginInjected",true);
                } else if (msg.getRequestHeader().getHeader("Authorization")==null) state(p,"crossOriginClean",true);
            }
            public void onHttpResponseReceive(HttpMessage msg, int initiator, HttpSender sender) {
                if (!enabled(p)) return;
                String auth=msg.getRequestHeader().getHeader("Authorization");
                if (auth!=null && auth.startsWith("Bearer ")) {
                    msg.getRequestHeader().setHeader("Authorization","<redacted>");state(p,"redacted",true);
                }
            }
        };
        state(p,"enabled",true);ScriptVars.setGlobalCustomVar(p+"listener",listener);HttpSender.addListener(listener);
        HttpMessage protectedMsg=new HttpMessage(new URI("http://client-auth-target:8080/bearer/user",false));
        new HttpSender(HttpSender.SPIDER_INITIATOR).sendAndReceive(protectedMsg,false);
        state(p,"protectedStatus",protectedMsg.getResponseHeader().getStatusCode());
        new HistoryReference(Model.getSingleton().getSession(),HistoryReference.TYPE_MANUAL,protectedMsg);
        HttpMessage crossMsg=new HttpMessage(new URI("http://direct-scan-target/",false));
        new HttpSender(HttpSender.SPIDER_INITIATOR).sendAndReceive(crossMsg,false);
        state(p,"crossOriginStatus",crossMsg.getResponseHeader().getStatusCode());
        new HistoryReference(Model.getSingleton().getSession(),HistoryReference.TYPE_MANUAL,crossMsg);
        state(p,"ready",true);
    }
    public static void remove(String p) {
        state(p,"enabled",false);
        Object listener=ScriptVars.getGlobalCustomVar(p+"listener");
        if (listener instanceof HttpSenderListener) HttpSender.removeListener((HttpSenderListener)listener);
        ScriptVars.setGlobalCustomVar(p+"listener",null);
    }
}
