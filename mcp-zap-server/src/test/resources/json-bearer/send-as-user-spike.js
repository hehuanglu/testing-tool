// Fixture-only driver for the retry/redaction feasibility test. The generated
// values are non-secret ZAP identifiers and an exact fixture URL.
const CONTEXT_ID = __CONTEXT_ID__;
const USER_ID = __USER_ID__;
const TARGET_URL = "__TARGET_URL__";
const RESULT_KEY = "__RESULT_KEY__";

const Control = Java.type("org.parosproxy.paros.control.Control");
const ExtensionUserManagement = Java.type("org.zaproxy.zap.extension.users.ExtensionUserManagement");
const HttpMessage = Java.type("org.parosproxy.paros.network.HttpMessage");
const HttpSender = Java.type("org.parosproxy.paros.network.HttpSender");
const HistoryReference = Java.type("org.parosproxy.paros.model.HistoryReference");
const Model = Java.type("org.parosproxy.paros.model.Model");
const URI = Java.type("org.apache.commons.httpclient.URI");
const ScriptVars = Java.type("org.zaproxy.zap.extension.script.ScriptVars");

ScriptVars.setGlobalVar(RESULT_KEY, "started");
const loader = Control.getSingleton().getExtensionLoader();
const users = loader.getExtension(ExtensionUserManagement.class);
const user = users.getContextUserAuthManager(CONTEXT_ID).getUserById(USER_ID);
const msg = new HttpMessage(new URI(TARGET_URL, false));
user.processMessageToMatchUser(msg);

const sender = new HttpSender(HttpSender.SPIDER_INITIATOR);
sender.setUser(user);
sender.sendAndReceive(msg, false);

// Persist only after HTTP Sender response hooks have had the opportunity to
// redact the request header.
new HistoryReference(Model.getSingleton().getSession(), HistoryReference.TYPE_MANUAL, msg);
ScriptVars.setGlobalVar(RESULT_KEY, "done");
