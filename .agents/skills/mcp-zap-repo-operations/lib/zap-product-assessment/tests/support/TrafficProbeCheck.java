import java.nio.file.*;
import org.apache.commons.httpclient.URI;
import org.parosproxy.paros.network.*;
import org.zaproxy.zap.extension.script.ScriptVars;
import org.zaproxy.zap.network.HttpSenderListener;
public class TrafficProbeCheck {
    public static void main(String[] args) throws Exception {
        var normalize=TrafficProbe.class.getDeclaredMethod("wireUrl",String.class);normalize.setAccessible(true);
        for(var pair:new String[][]{{"http://127.0.0.1:18080","http://127.0.0.1:18080/"},{"http://127.0.0.1:18080?x=%2F","http://127.0.0.1:18080/?x=%2F"},{"http://127.0.0.1:18080/a%2Fb","http://127.0.0.1:18080/a%2Fb"}})
            if(!pair[1].equals(normalize.invoke(null,pair[0])))throw new AssertionError("wire URL normalization");
        try{normalize.invoke(null,"http://127.0.0.1:18080/#fragment");throw new AssertionError("fragment accepted");}
        catch(java.lang.reflect.InvocationTargetException expected){if(!(expected.getCause() instanceof IllegalArgumentException))throw expected;}
        TrafficProbe.install("native-fixture");
        var l=(HttpSenderListener)ScriptVars.getGlobalCustomVar("w4.listener");
        var msg=new HttpMessage(new URI("http://127.0.0.1:18080/health",false));
        l.onHttpRequestSend(msg,HttpSender.SPIDER_INITIATOR,null);
        if(!"native-fixture-1".equals(msg.getRequestHeader().getHeader("X-Zpa-Correlation")))throw new AssertionError("ID mismatch");
        msg.setResponseHeader("HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n");msg.setResponseBody("{}");
        l.onHttpResponseReceive(msg,HttpSender.SPIDER_INITIATOR,null);
        var lines=Files.readAllLines(Path.of("/zap/wrk/sender-events.jsonl"));
        if(lines.size()!=2 || !lines.get(0).contains("\"initiator\":3") || !lines.get(1).contains("\"status\":200"))throw new AssertionError("observer record mismatch");
        System.out.println("{\"nativeCallbackFixture\":true,\"eventCount\":2,\"networkRequests\":0,\"liveEngineAttestation\":false}");
    }
}
