import java.io.IOException;
import java.nio.file.*;
import org.apache.commons.httpclient.URI;
import org.parosproxy.paros.network.*;
import org.zaproxy.zap.extension.script.ScriptVars;
import org.zaproxy.zap.network.*;

/** Deterministic callback/delegate failure fixture; does not send network traffic. */
public class TrafficFailureCheck {
    public static void main(String[] args) throws Exception {
        var original=new HttpSenderImpl<HttpSenderContext>() {
            public boolean isGlobalStateEnabled(){return false;}
            public void addListener(HttpSenderListener l){}
            public void removeListener(HttpSenderListener l){}
            public HttpSenderContext createContext(HttpSender sender,int initiator){
                return (HttpSenderContext)java.lang.reflect.Proxy.newProxyInstance(HttpSenderContext.class.getClassLoader(),new Class<?>[]{HttpSenderContext.class},(p,m,a)->m.getReturnType()==boolean.class?false:m.getReturnType()==int.class?0:null);
            }
            public void sendAndReceive(HttpSenderContext context,HttpRequestConfig config,HttpMessage msg,Path path) throws IOException {
                sendAndReceive((HttpSender)null,config,msg,path);
            }
            public void sendAndReceive(HttpSender sender,HttpRequestConfig config,HttpMessage msg,Path path) throws IOException {
                if(config!=null && !config.isNotifyListeners())throw new IOException("listener-suppressed transport fixture");
                var listener=(HttpSenderListener)ScriptVars.getGlobalCustomVar("w4.listener");
                listener.onHttpRequestSend(msg,3,sender);
                msg.setResponseHeader("HTTP/1.1 302 Found\r\nContent-Length: 0\r\n\r\n");
                listener.onHttpResponseReceive(msg,3,sender);
                try{msg.getRequestHeader().setURI(new URI("https://127.0.0.1:18080/scheme-canary",false));}
                catch(Exception e){throw new IOException(e);}
                listener.onHttpRequestSend(msg,3,sender);
                throw new IOException("private diagnostic must not be serialized");
            }
        };
        HttpSender.setImpl(original);TrafficProbe.install("failure-fixture");
        var sender=new HttpSender(3);
        try{sender.sendAndReceive(new HttpMessage(new URI("http://127.0.0.1:18080/redirect-scheme",false)));throw new AssertionError("exception swallowed");}
        catch(IOException e){if(!e.getMessage().equals("private diagnostic must not be serialized"))throw e;}
        var lines=Files.readAllLines(Path.of("/zap/wrk/sender-events.jsonl"));
        if(lines.size()!=4 || !lines.get(3).contains("\"transport-failure\"") || !lines.get(3).contains("failure-fixture-2") || lines.get(3).contains("private diagnostic"))throw new AssertionError("failure correlation/privacy");
        // Exercise the public-sender overload and its listener-suppressed path.
        var ctx=HttpSender.class.getDeclaredField("ctx");ctx.setAccessible(true);ctx.set(sender,null);
        try{sender.sendAndReceive(new HttpMessage(new URI("https://127.0.0.1:18080/denied",false)),HttpRequestConfig.builder().setNotifyListeners(false).build());throw new AssertionError("suppressed exception swallowed");}
        catch(IOException expected){}
        lines=Files.readAllLines(Path.of("/zap/wrk/sender-events.jsonl"));
        if(lines.size()!=6 || !lines.get(4).contains("sender-entry-listeners-disabled") || !lines.get(5).contains("failure-fixture-3"))throw new AssertionError("suppressed HTTPS capture");
        var failures=new java.util.concurrent.atomic.AtomicInteger();
        Runnable concurrent=()->{
            try{
                var client=new HttpSender(7);ctx.set(client,null);
                client.sendAndReceive(new HttpMessage(new URI("https://127.0.0.1:18080/denied",false)),HttpRequestConfig.builder().setNotifyListeners(false).build());
            }catch(IOException expected){failures.incrementAndGet();}catch(Exception e){throw new RuntimeException(e);}
        };
        var a=new Thread(concurrent);var b=new Thread(concurrent);a.start();b.start();a.join();b.join();
        lines=Files.readAllLines(Path.of("/zap/wrk/sender-events.jsonl"));
        if(failures.get()!=2 || lines.size()!=10 || !lines.get(6).contains("failure-fixture-4") || !lines.get(7).contains("failure-fixture-4") || !lines.get(8).contains("failure-fixture-5") || !lines.get(9).contains("failure-fixture-5"))throw new AssertionError("concurrent suppressed TLS calls interleaved");
        System.out.println("{\"nativeFailureFixture\":true,\"eventCount\":10,\"exceptionRethrown\":true,\"suppressedHttpsCaptured\":true,\"concurrentDenialsSerialized\":true,\"networkRequests\":0}");
    }
}
