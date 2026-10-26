import org.parosproxy.paros.core.scanner.PluginFactory;
import org.zaproxy.zap.extension.script.ScriptVars;
public class PolicyFaultInstallCheck {
    public static void main(String[] args) throws Exception {
        // Standalone callback fixture supplies an empty registry; this is not
        // daemon/add-on loading proof. The live campaign uses the real registry.
        var loaded=PluginFactory.class.getDeclaredField("loadedPlugins");loaded.setAccessible(true);loaded.set(null,new java.util.ArrayList<>());
        var map=PluginFactory.class.getDeclaredField("mapLoadedPlugins");map.setAccessible(true);map.set(null,new java.util.HashMap<>());
        PolicyFaultProbe.install("");
        var plugin=PluginFactory.getLoadedPlugin(990001);
        if(plugin==null || plugin.isEnabled() || !"false".equals(ScriptVars.getGlobalVar("w4.fixture.enabled")))throw new AssertionError("disabled native fixture registration");
        System.out.println("{\"disabledRuleFixtureRegistered\":true,\"syntheticRegistry\":true,\"liveEngineAttestation\":false,\"networkRequests\":0}");
    }
}
