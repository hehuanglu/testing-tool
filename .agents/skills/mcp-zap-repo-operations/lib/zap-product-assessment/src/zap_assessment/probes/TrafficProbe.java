import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import org.parosproxy.paros.control.Control;
import org.parosproxy.paros.network.*;
import org.zaproxy.zap.extension.script.*;
import org.zaproxy.zap.network.HttpSenderListener;
import org.zaproxy.zap.network.HttpSenderImpl;
import org.zaproxy.zap.network.HttpRequestConfig;
import org.parosproxy.paros.core.scanner.PluginFactory;

/** Run-owned anonymous instrumentation. No escaped Graal callbacks or secrets. */
public final class TrafficProbe {
    private static final String HEADER="X-Zpa-Correlation";
    private static final Path LOG=Path.of("/zap/wrk/sender-events.jsonl");
    private static long seq=0;
    private static boolean halted=false;
    private static Object expectedSender;
    private static HttpSenderListener probeListener;
    private static final ThreadLocal<String> capturePoint=ThreadLocal.withInitial(()->"engine-listener");
    private static final java.util.concurrent.locks.ReentrantLock silentTls=new java.util.concurrent.locks.ReentrantLock();
    private static Map<Class<?>,Set<String>> ruleClasses=Map.of();
    private static final ThreadLocal<Deque<Set<String>>> calls=ThreadLocal.withInitial(ArrayDeque::new);
    // The listener API has no failure callback. Observe the existing sender's
    // thrown exception without changing its transport, redirects or retries.
    // A frame belongs to one synchronous send; redirect callbacks update it.
    private static Object observeSender(HttpSenderImpl<?> delegate) {
        return java.lang.reflect.Proxy.newProxyInstance(HttpSenderImpl.class.getClassLoader(),new Class<?>[]{HttpSenderImpl.class},(proxy,method,args)->{
            if(!method.getName().equals("sendAndReceive")) {
                try{return method.invoke(delegate,args);}catch(java.lang.reflect.InvocationTargetException e){throw e.getCause();}
            }
            if(halted)throw new IOException("traffic capture halted");
            boolean suppressedTls=args[1] instanceof HttpRequestConfig config && !config.isNotifyListeners()
                    && args[2] instanceof HttpMessage msg && msg.getRequestHeader().isSecure();
            // This HTTP-only fixture has no concurrent TLS capability. Serialize
            // listener-suppressed denial attempts before recording, so CONNECT
            // authority matching cannot guess among concurrent background sends.
            if(suppressedTls)silentTls.lock();
            var stack=calls.get();var pending=new LinkedHashSet<String>();stack.push(pending);
            try{
                // Some engine requests explicitly suppress listeners. Observe
                // only their initial HTTPS attempt at the real sender entry.
                // The mandatory boundary never opens a tunnel. A successful
                // return without callbacks stays incomplete, never a response.
                if(suppressedTls && args[2] instanceof HttpMessage msg) {
                    int initiator;
                    if(args[0] instanceof HttpSender sender) {
                        var field=HttpSender.class.getDeclaredField("initiator");field.setAccessible(true);initiator=field.getInt(sender);
                    }else initiator=(Integer)args[0].getClass().getMethod("getInitiator").invoke(args[0]);
                    capturePoint.set("sender-entry-listeners-disabled");
                    try{probeListener.onHttpRequestSend(msg,initiator,args[0] instanceof HttpSender sender?sender:null);}
                    finally{capturePoint.remove();}
                }
                return method.invoke(delegate,args);
            }
            catch(java.lang.reflect.InvocationTargetException e){
                var cause=e.getCause();
                if(pending.size()==1)record("{\"kind\":\"transport-failure\",\"requestId\":"+q(pending.iterator().next())+",\"failureKind\":"+q(cause instanceof IOException?"io":"exception")+",\"exceptionType\":"+q(cause.getClass().getName())+"}");
                if(pending.isEmpty() && args[2] instanceof HttpMessage msg) {
                    var uri=java.net.URI.create(msg.getRequestHeader().getURI().toString());
                    String authority=uri.getHost()+":"+(uri.getPort()<0?(uri.getScheme().equals("https")?443:80):uri.getPort());
                    record("{\"kind\":\"unobserved-transport-failure\",\"scheme\":"+q(uri.getScheme())+",\"authoritySha256\":"+q(sha(authority.getBytes(StandardCharsets.UTF_8)))+",\"exceptionType\":"+q(cause.getClass().getName())+"}");
                }
                // Multiple unresolved callbacks cannot be assigned a terminal
                // result safely. Leave them incomplete rather than backfill.
                throw cause;
            }finally{stack.pop();if(stack.isEmpty())calls.remove();if(suppressedTls)silentTls.unlock();}
        });
    }
    private static String sha(byte[] bytes) throws Exception {return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));}
    private static String wireUrl(String value) {
        var uri=java.net.URI.create(value);
        if(uri.getRawFragment()!=null)throw new IllegalArgumentException("fragment is not a wire target");
        if(uri.getRawPath()==null || uri.getRawPath().isEmpty())
            return uri.getScheme()+"://"+uri.getRawAuthority()+"/"+(uri.getRawQuery()==null?"":"?"+uri.getRawQuery());
        return value;
    }
    private static String q(String v) {return "\""+v.replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n").replace("\r","\\r")+"\"";}
    public static void bindRules(String ids) {
        Map<Class<?>,Set<String>> map=new HashMap<>();
        for(String id:ids.split(",")) {
            var plugin=PluginFactory.getLoadedPlugin(Integer.parseInt(id));
            if(plugin==null || plugin.getId()!=Integer.parseInt(id))throw new IllegalStateException("loaded rule binding unavailable");
            map.computeIfAbsent(plugin.getClass(),k->new HashSet<>()).add(id);
        }
        ruleClasses=map;
    }
    private static boolean activeControl() throws Exception {
        Class<?> analyser=Class.forName("org.parosproxy.paros.core.scanner.Analyser",false,HttpSender.class.getClassLoader());
        return StackWalker.getInstance(StackWalker.Option.RETAIN_CLASS_REFERENCE).walk(s->s.anyMatch(f->f.getDeclaringClass()==analyser && f.getMethodName().equals("sendAndReceive")));
    }
    private static String activeRule() {
        Set<String> ids=StackWalker.getInstance(StackWalker.Option.RETAIN_CLASS_REFERENCE).walk(frames->{
            Set<String> found=new HashSet<>();frames.forEach(frame->found.addAll(ruleClasses.getOrDefault(frame.getDeclaringClass(),Set.of())));return found;
        });
        return ids.size()==1?ids.iterator().next():null;
    }
    private static synchronized void record(String data) {
        try (var out=new FileOutputStream(LOG.toFile(),true)) {
            out.write((data+"\n").getBytes(StandardCharsets.UTF_8));out.getFD().sync();
        } catch(Exception e) {halted=true;throw new IllegalStateException("traffic capture writer failure");}
    }
    public static void install(String run) {
        if(ScriptVars.getGlobalCustomVar("w4.listener")!=null)throw new IllegalStateException("collector already installed");
        try {
            var field=HttpSender.class.getDeclaredField("impl");field.setAccessible(true);
            var delegate=(HttpSenderImpl<?>)field.get(null);
            // Synthetic pinned-engine integration only. Preserve the exact
            // existing delegate/state/listeners; no second client or transport.
            expectedSender=observeSender(delegate);field.set(null,expectedSender);
        }catch(ReflectiveOperationException e){throw new IllegalStateException("sender failure hook unavailable");}
        HttpSenderListener listener=new HttpSenderListener(){
            public int getListenerOrder(){return Integer.MAX_VALUE-10;}
            public void onHttpRequestSend(HttpMessage msg,int initiator,HttpSender sender){
                if(halted)throw new IllegalStateException("capture halted");
                try {
                    String id; synchronized(TrafficProbe.class){id=run+"-"+(++seq);}
                    msg.getRequestHeader().setHeader(HEADER,id);
                    String url=msg.getRequestHeader().getURI().toString();
                    String method=msg.getRequestHeader().getMethod();
                    // Caller-controlled rule headers are diagnostic only and
                    // cannot authorize an active producer.
                    String phase=Files.exists(Path.of("/zap/wrk/observer-phase.txt"))?Files.readString(Path.of("/zap/wrk/observer-phase.txt")):"unmarked";
                    String activeStack=StackWalker.getInstance().walk(s->s.limit(24).map(f->f.getClassName()+"#"+f.getMethodName()).collect(java.util.stream.Collectors.joining(";")));
                    String rule=initiator==HttpSender.ACTIVE_SCANNER_INITIATOR?activeRule():null;
                    var uri=java.net.URI.create(url);
                    String authority=uri.getHost()+":"+(uri.getPort()<0?(uri.getScheme().equals("https")?443:80):uri.getPort());
                    record("{\"kind\":\"request\",\"requestId\":"+q(id)+",\"phase\":"+q(phase)+",\"activeControl\":"+(initiator==2 && rule==null && activeControl())+",\"activeStack\":"+q(initiator==2?activeStack:"")+",\"capturePoint\":"+q(capturePoint.get())+",\"initiator\":"+initiator+",\"method\":"+q(method)+",\"urlSha256\":"+q(sha(wireUrl(url).getBytes(StandardCharsets.UTF_8)))+",\"rawUrlSha256\":"+q(sha(url.getBytes(StandardCharsets.UTF_8)))+",\"scheme\":"+q(uri.getScheme())+",\"authoritySha256\":"+q(sha(authority.getBytes(StandardCharsets.UTF_8)))+",\"urlNormalization\":\"empty-path-as-slash-only\",\"bodySha256\":"+q(sha(msg.getRequestBody().getBytes()))+",\"ruleId\":"+(rule==null?"null":q(rule))+"}");
                    if(!calls.get().isEmpty())calls.get().peek().add(id);
                }catch(Exception e){halted=true;throw new IllegalStateException("capture request failed");}
            }
            public void onHttpResponseReceive(HttpMessage msg,int initiator,HttpSender sender){
                try {
                    String id=msg.getRequestHeader().getHeader(HEADER);
                    if(id==null)throw new IllegalStateException("request correlation lost");
                    record("{\"kind\":\"response\",\"requestId\":"+q(id)+",\"status\":"+msg.getResponseHeader().getStatusCode()+",\"bodySha256\":"+q(sha(msg.getResponseBody().getBytes()))+"}");
                    if(!calls.get().isEmpty())calls.get().peek().remove(id);
                }catch(Exception e){halted=true;throw new IllegalStateException("capture response failed");}
            }
        };
        probeListener=listener;HttpSender.addListener(listener);ScriptVars.setGlobalCustomVar("w4.listener",listener);
        ScriptVars.setGlobalVar("w4.installed",run);
    }
    public static void inventory(String ignored) throws Exception {
        var senderField=HttpSender.class.getDeclaredField("impl");senderField.setAccessible(true);
        if(senderField.get(null)!=expectedSender)throw new IllegalStateException("sender observer replaced");
        ExtensionScript ext=Control.getSingleton().getExtensionLoader().getExtension(ExtensionScript.class);
        List<String> rows=new ArrayList<>();
        for(ScriptType type:ext.getScriptTypes()) {
            for(ScriptWrapper script:ext.getScripts(type)) {
                rows.add("{\"name\":"+q(script.getName())+",\"type\":"+q(type.getName())+",\"enabled\":"+script.isEnabled()+",\"sha256\":"+q(sha(script.getContents().getBytes(StandardCharsets.UTF_8)))+"}");
            }
        }
        String data="["+String.join(",",rows)+"]";
        Path path=Path.of("/zap/wrk/script-inventory.json");
        Files.writeString(path,data,StandardCharsets.UTF_8);
        ScriptVars.setGlobalVar("w4.inventory",sha(data.getBytes(StandardCharsets.UTF_8)));
    }
}
