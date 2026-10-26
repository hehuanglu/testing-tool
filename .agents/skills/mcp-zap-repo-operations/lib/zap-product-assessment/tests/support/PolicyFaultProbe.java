import org.parosproxy.paros.core.scanner.*;
import org.parosproxy.paros.network.*;
import org.apache.commons.httpclient.URI;
import org.zaproxy.zap.extension.script.ScriptVars;

/** Deliberately faulty native rule in the owned W4 fixture only. Never an add-on. */
public final class PolicyFaultProbe extends AbstractPlugin {
    private static PolicyFaultProbe fixture;
    public int getId(){return 990001;}
    public String getName(){return "W4 disabled emission fault fixture";}
    public String getDescription(){return getName();}
    public int getCategory(){return 0;}
    public String getSolution(){return "Fault injection only";}
    public String getReference(){return "W4 C17";}
    public void notifyPluginCompleted(HostProcess process){}
    public static void install(String ignored){
        fixture=new PolicyFaultProbe();fixture.setConfig(new org.apache.commons.configuration.HierarchicalConfiguration());fixture.setEnabled(false);PluginFactory.loadedPlugin(fixture);
        ScriptVars.setGlobalVar("w4.fixture.enabled",Boolean.toString(fixture.isEnabled()));
    }
    public static void emit(String mode) throws Exception {
        if(mode.equals("disabled"))fixture.scan();
        else {
            // A distinct thread/class has no registered rule on its stack.
            // Calling from this plugin's own emit() stack would correctly bind
            // the fixture ID and would not be an unknown-producer negative.
            var emitter=new UnknownEmitter();emitter.start();emitter.join();
            if(emitter.failure!=null)throw emitter.failure;
        }
    }
    private static final class UnknownEmitter extends Thread {
        Exception failure;
        public void run(){try {
            var msg=new HttpMessage(new URI("http://127.0.0.1:18080/health",false));
            // Spoof a known enabled ID: it must not supply native rule identity.
            msg.getRequestHeader().setHeader("x-zap-scan-id","40012");
            new HttpSender(HttpSender.ACTIVE_SCANNER_INITIATOR).sendAndReceive(msg,false);
        }catch(Exception e){failure=e;}}
    }
    public void scan(){
        // Intentionally ignores isEnabled() to test detection of C17.
        try{new HttpSender(HttpSender.ACTIVE_SCANNER_INITIATOR).sendAndReceive(new HttpMessage(new URI("http://127.0.0.1:18080/health",false)),false);}
        catch(Exception e){throw new IllegalStateException("owned rule fault emission failed");}
    }
}
