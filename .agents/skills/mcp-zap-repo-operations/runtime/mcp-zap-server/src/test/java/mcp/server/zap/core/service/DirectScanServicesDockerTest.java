package mcp.server.zap.core.service;

import mcp.server.zap.core.configuration.AuthBootstrapProperties;
import mcp.server.zap.core.configuration.ScanLimitProperties;
import mcp.server.zap.core.gateway.GatewayRecordFactory;
import mcp.server.zap.core.gateway.TimeoutZapClientApi;
import mcp.server.zap.core.gateway.ZapEngineAdapter;
import mcp.server.zap.core.gateway.ZapEngineAjaxSpiderExecution;
import mcp.server.zap.core.gateway.ZapEngineContextAccess;
import mcp.server.zap.core.gateway.ZapEngineScanExecution;
import mcp.server.zap.core.model.ScanJobStatus;
import mcp.server.zap.core.model.ScanJobType;
import mcp.server.zap.core.service.auth.bootstrap.AuthProfileResolver;
import mcp.server.zap.core.service.auth.bootstrap.CredentialReferenceResolver;
import mcp.server.zap.core.service.auth.bootstrap.FormLoginAuthBootstrapProvider;
import mcp.server.zap.core.service.auth.bootstrap.GuidedAuthSessionService;
import mcp.server.zap.core.service.auth.bootstrap.InMemoryPreparedAuthSessionRegistry;
import mcp.server.zap.core.service.auth.bootstrap.JsonBearerAuthBootstrapProvider;
import mcp.server.zap.core.service.jobstore.InMemoryScanJobStore;
import mcp.server.zap.core.service.queue.leadership.SingleNodeQueueLeadershipCoordinator;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.api.extension.ExtensionContext;
import org.junit.jupiter.api.extension.RegisterExtension;
import org.junit.jupiter.api.extension.TestWatcher;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.containers.Network;
import org.testcontainers.containers.wait.strategy.Wait;
import org.testcontainers.images.builder.Transferable;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;
import org.testcontainers.utility.MountableFile;
import org.zaproxy.clientapi.core.ApiResponseElement;
import org.zaproxy.clientapi.core.ApiResponseList;
import org.zaproxy.clientapi.core.ApiResponseSet;
import org.zaproxy.clientapi.core.ClientApi;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Stream;

import static org.awaitility.Awaitility.await;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

@Tag("docker")
@Testcontainers
class DirectScanServicesDockerTest {
    @RegisterExtension
    final TestWatcher engineFailureDiagnostics = new TestWatcher() {
        @Override
        public void testFailed(ExtensionContext context, Throwable cause) {
            System.out.println("Failure detail: " + cause.getMessage());
            String logs = ZAP.getLogs();
            System.out.println("ZAP failure diagnostics for " + context.getDisplayName() + "\n"
                    + logs.substring(Math.max(0, logs.length() - 24000)));
            try {
                System.out.println(clientApi.script.listScripts().toString(0));
            } catch (Exception diagnosticsFailure) {
                System.out.println("Script diagnostics unavailable: " + diagnosticsFailure.getMessage());
            }
        }
    };
    private static final Pattern SCAN_ID_PATTERN = Pattern.compile("Scan ID: ([^\\n]+)");
    private static final Network NETWORK = Network.newNetwork();

    @Container
    static final GenericContainer<?> TARGET =
            new GenericContainer<>(DockerImageName.parse("nginx:1.27-alpine"))
                    .withNetwork(NETWORK)
                    .withNetworkAliases("direct-scan-target")
                    .withCopyToContainer(Transferable.of("""
                            server {
                                listen 80;
                                root /usr/share/nginx/html;
                                index index.html;
                                location = /http-slow { limit_rate 1024; }
                                location / { try_files $uri $uri/ =404; }
                            }
                            """), "/etc/nginx/conf.d/default.conf")
                    .withCopyToContainer(Transferable.of("""
                            <!doctype html>
                            <html><body><h1>Client Spider fixture</h1>
                            <script>
                            fetch('/' + ['client', 'discovered'].join('-') + location.search);
                            </script></body></html>
                            """), "/usr/share/nginx/html/client-crawl.html")
                    .withCopyToContainer(Transferable.of("""
                            <!doctype html>
                            <html><body><a href="/http-slow">Finite slow response</a>
                            <script>
                            fetch('/' + ['client', 'discovered'].join('-') + location.search);
                            </script></body></html>
                            """), "/usr/share/nginx/html/http-stop.html")
                    .withCopyToContainer(Transferable.of("x".repeat(64 * 1024)),
                            "/usr/share/nginx/html/http-slow")
                    .withCopyToContainer(Transferable.of("Discovered through JavaScript"),
                            "/usr/share/nginx/html/client-discovered")
                    .withCopyToContainer(Transferable.of("<!doctype html><html><body></body></html>"),
                            "/usr/share/nginx/html/client-idle.html")
                    .withCopyToContainer(Transferable.of("""
                            <!doctype html>
                            <html><body><script>
                            const next = new URL(location.href);
                            const step = Number(next.searchParams.get('step') || 0) + 1;
                            next.searchParams.set('step', step);
                            const link = document.createElement('a');
                            link.href = next.href;
                            link.textContent = 'Continue to page ' + step;
                            document.body.appendChild(link);
                            </script></body></html>
                            """), "/usr/share/nginx/html/client-duration.html")
                    .withExposedPorts(80)
                    .waitingFor(Wait.forHttp("/"));

    @Container
    static final GenericContainer<?> AUTH_TARGET =
            new GenericContainer<>(DockerImageName.parse("python:3.13-alpine"))
                    .withNetwork(NETWORK)
                    .withNetworkAliases("client-auth-target")
                    .withCopyToContainer(MountableFile.forClasspathResource("client-spider/form-login.py"),
                            "/form-login.py")
                    .withCommand("python", "/form-login.py")
                    .withExposedPorts(8080)
                    .waitingFor(Wait.forHttp("/"));

    @Container
    static final GenericContainer<?> ZAP =
            new GenericContainer<>(ZapDockerTestSupport.zapImage())
                    .withNetwork(NETWORK)
                    .dependsOn(TARGET, AUTH_TARGET)
                    .withExposedPorts(8090)
                    .withSharedMemorySize(512 * 1024 * 1024L)
                    .withCommand(
                            "zap.sh",
                            "-daemon",
                            "-host",
                            "0.0.0.0",
                            "-port",
                            "8090",
                            "-config",
                            "api.disablekey=true",
                            "-config",
                            "api.addrs.addr.name=.*",
                            "-config",
                            "api.addrs.addr.regex=true",
                            "-addoninstall",
                            "client",
                            "-addoninstall",
                            "spiderAjax"
                    )
                    .waitingFor(ZapDockerTestSupport.waitForZapPort());

    private static ClientApi clientApi;
    private static ActiveScanService activeScanService;
    private static SpiderScanService spiderScanService;
    private static ClientSpiderService clientSpiderService;

    @BeforeEach
    void isolateEngineState() throws Exception {
        // These independent cases install Java listeners and replace network internals.
        // Removing a Graal script does not unregister its Java listener; it can also
        // leave a closed script context reachable by later HTTP sender threads.
        // A new session clears history but cannot clear these process-global hooks,
        // browser/session detection or Client Spider background work. Give every
        // invocation (including parameterized cases) a fresh class-owned process.
        // The target fixtures stay running; production recovery is not under test.
        ZAP.stop();
        ZAP.start();
        setupServices();
    }

    static void setupServices() throws Exception {
        clientApi = ZapDockerTestSupport.clientApi(ZAP.getHost(), ZAP.getMappedPort(8090));
        ZapDockerTestSupport.awaitZapApiReady(clientApi);
        System.out.println("Crawler test ZAP core: " + clientApi.core.version().toString(0));
        System.out.println("Crawler test installed add-ons: " + clientApi.autoupdate.installedAddons().toString(0));
        String firefoxPath = ((ApiResponseElement) clientApi.selenium.optionFirefoxBinaryPath()).getValue();
        String driverPath = ((ApiResponseElement) clientApi.selenium.optionFirefoxDriverPath()).getValue();
        printBrowserVersion("Firefox", firefoxPath.isBlank() ? "firefox" : firefoxPath);
        printBrowserVersion("WebDriver", driverPath.isBlank() ? "geckodriver" : driverPath);

        ScanLimitProperties scanLimitProperties = new ScanLimitProperties();
        scanLimitProperties.setMaxActiveScanDurationInMins(1);
        scanLimitProperties.setHostPerScan(2);
        scanLimitProperties.setThreadPerHost(2);
        scanLimitProperties.setSpiderThreadCount(2);
        scanLimitProperties.setMaxSpiderScanDurationInMins(1);
        scanLimitProperties.setSpiderMaxDepth(5);

        UrlValidationService urlValidationService = mock(UrlValidationService.class);
        ZapEngineScanExecution engineScanExecution = new ZapEngineScanExecution(clientApi);
        activeScanService = new ActiveScanService(engineScanExecution, urlValidationService, scanLimitProperties);
        spiderScanService = new SpiderScanService(engineScanExecution, urlValidationService, scanLimitProperties);
        clientSpiderService = new ClientSpiderService(engineScanExecution, urlValidationService, scanLimitProperties);
    }

    @ParameterizedTest
    @MethodSource("guidedCrawlerModes")
    void guidedCrawlerSelectionKeepsNativeLifecycleAndMeasuredJavaScriptCoverage(
            String strategy, GuidedExecutionModeResolver.ExecutionMode mode) throws Exception {
        String effectiveStrategy = "auto".equals(strategy) ? "http" : strategy;
        String query = "?crawl=matrix-" + mode.name() + "-" + strategy;
        String origin = "http://direct-scan-target";
        boolean browserCrawl = !"http".equals(effectiveStrategy);
        String targetUrl = origin + (browserCrawl ? "/client-crawl.html" : "/http-stop.html") + query;
        String discoveredUrl = origin + "/client-discovered" + query;
        GuidedExecutionModeResolver executionMode = mock(GuidedExecutionModeResolver.class);
        when(executionMode.resolveDefaultMode()).thenReturn(mode);
        InMemoryScanJobStore store = new InMemoryScanJobStore();
        AjaxSpiderService ajaxSpider = new AjaxSpiderService(
                new ZapEngineAjaxSpiderExecution(clientApi), mock(UrlValidationService.class));
        ajaxSpider.setScanJobStore(store);
        var retryPolicy = new ScanJobQueueService.RetryPolicy(1, 0, 0, 1.0);
        ScanJobQueueService queue = new ScanJobQueueService(
                activeScanService, spiderScanService, ajaxSpider, clientSpiderService,
                mock(UrlValidationService.class), new ScanLimitProperties(), retryPolicy, retryPolicy,
                false, store, new SingleNodeQueueLeadershipCoordinator());
        GuidedScanWorkflowService guided = new GuidedScanWorkflowService(
                executionMode, spiderScanService, ajaxSpider, clientSpiderService, activeScanService,
                queue, mock(GuidedAuthSessionService.class), new ZapEngineAdapter(), new GatewayRecordFactory());
        String operationId = null;
        try {
            String started = guided.startCrawl(targetUrl, strategy, null, null);
            operationId = extractResponseValue(started, "Operation ID: ");
            assertTrue(started.contains("Strategy: " + effectiveStrategy), started);
            assertTrue(started.contains("Execution Mode: " + mode.name().toLowerCase(Locale.ROOT)), started);
            String jobId = mode == GuidedExecutionModeResolver.ExecutionMode.QUEUE
                    ? extractResponseValue(started, "Job ID: ") : null;
            String scanId;
            if (jobId != null) {
                String operationToPoll = operationId;
                // Queue admission can precede backend startup. Poll through normal dispatch.
                await().atMost(Duration.ofSeconds(90)).pollInterval(Duration.ofMillis(250)).untilAsserted(() -> {
                    String queuedStatus = guided.getCrawlStatus(operationToPoll);
                    var pending = store.load(jobId).orElseThrow();
                    assertTrue(pending.getZapScanId() != null && !pending.getZapScanId().isBlank(), queuedStatus);
                });
                var job = store.load(jobId).orElseThrow();
                ScanJobType expectedType = switch (effectiveStrategy) {
                    case "client" -> ScanJobType.CLIENT_SPIDER;
                    case "browser" -> ScanJobType.AJAX_SPIDER;
                    default -> ScanJobType.SPIDER_SCAN;
                };
                assertEquals(expectedType, job.getType());
                scanId = job.getZapScanId();
            } else {
                scanId = "browser".equals(effectiveStrategy) ? null : extractScanId(started);
            }
            String status = guided.getCrawlStatus(operationId);
            assertTrue(status.contains("Strategy: " + effectiveStrategy), status);
            if (jobId != null) {
                assertTrue(status.contains("Job ID: " + jobId), status);
                assertTrue(status.contains("ZAP Scan ID: " + scanId), status);
            } else if (scanId != null) {
                assertTrue(status.contains("Scan ID: " + scanId), status);
            } else {
                assertTrue(status.contains("AJAX Spider Status:"), status);
            }
            if (browserCrawl) {
                await().atMost(Duration.ofSeconds(90)).pollInterval(Duration.ofMillis(500))
                        .until(() -> recordedUrls(origin).contains(discoveredUrl));
                if ("client".equals(effectiveStrategy)) {
                    assertTrue(clientSpiderService.getClientSpiderProgressPercent(scanId) < 100,
                            "Client crawl must still be running when cancellation is requested");
                } else {
                    assertTrue(ajaxSpider.isAjaxSpiderRunning(),
                            "AJAX crawl must still be running when cancellation is requested");
                }
            } else {
                await().atMost(Duration.ofSeconds(45)).pollInterval(Duration.ofMillis(250))
                        .until(() -> {
                            int progress = spiderScanService.getSpiderScanProgressPercent(scanId);
                            return progress > 0 && progress < 100;
                        });
                assertFalse(recordedUrls(origin).contains(discoveredUrl),
                        "An HTTP or auto crawl must not be treated as JavaScript coverage");
                assertTrue(spiderScanService.getSpiderScanProgressPercent(scanId) < 100,
                        "HTTP crawl must still be running when cancellation is requested");
            }
            String operationToStop = operationId;
            assertTrue(guided.stopCrawl(operationToStop).contains("Guided crawl stop requested."));
            await().atMost(Duration.ofSeconds(30)).pollInterval(Duration.ofMillis(500)).untilAsserted(() -> {
                String stopped = guided.getCrawlStatus(operationToStop);
                switch (effectiveStrategy) {
                    case "client" -> assertEquals(100, clientSpiderService.getClientSpiderProgressPercent(scanId));
                    case "browser" -> assertFalse(ajaxSpider.isAjaxSpiderRunning());
                    default -> assertEquals(100, spiderScanService.getSpiderScanProgressPercent(scanId));
                }
                if (jobId != null) {
                    assertEquals(ScanJobStatus.CANCELLED, store.load(jobId).orElseThrow().getStatus());
                }
                if (browserCrawl) {
                    assertFalse(stopped.contains("Continue security testing: call zap_attack_start"), stopped);
                }
            });
        } finally {
            try {
                if (operationId != null) {
                    guided.stopCrawl(operationId);
                }
            } finally {
                queue.shutdownExecutor();
            }
        }
    }

    private static Stream<Arguments> guidedCrawlerModes() {
        return Stream.of("http", "client", "browser", "auto")
                .flatMap(strategy -> Stream.of(GuidedExecutionModeResolver.ExecutionMode.values())
                        .map(mode -> Arguments.of(strategy, mode)));
    }

    private static void printBrowserVersion(String name, String executable) throws Exception {
        var result = ZAP.execInContainer(executable, "--version");
        System.out.printf("Crawler test %s (exit %d): %s %s%n", name, result.getExitCode(),
                result.getStdout().trim(), result.getStderr().trim());
    }

    @Test
    void researchJsonBearerCompletesActiveDetectionControlsAndRejectsLostIdentity(@TempDir Path dir) throws Exception {
        String origin = "http://client-auth-target:8080";
        String local = "http://" + AUTH_TARGET.getHost() + ":" + AUTH_TARGET.getMappedPort(8080);
        var profile = jsonBearerProfile("research-control", origin,
                Files.writeString(dir.resolve("password"), "fixture-password"));
        profile.setVerificationUrl(origin + "/bearer/identity");
        profile.setLoggedInIndicatorRegex("user_id");
        profile.setSubjectJsonPointer("/data/user_id");
        profile.setExpectedSubject("1");
        var properties = new AuthBootstrapProperties();
        properties.setProfiles(List.of(profile));
        var contexts = new ContextUserService(new ZapEngineContextAccess(clientApi));
        var registry = new InMemoryPreparedAuthSessionRegistry();
        var auth = new GuidedAuthSessionService(List.of(new JsonBearerAuthBootstrapProvider(
                contexts, new CredentialReferenceResolver(), mock(UrlValidationService.class))), registry,
                new AuthProfileResolver(properties));
        String sid = extractResponseValue(auth.prepareSession(profile.getId(), origin + "/bearer/identity"), "Session ID: ");
        assertTrue(auth.validateSession(sid).contains("Valid: true"));
        var session = auth.getPreparedSession(sid);
        var mode = mock(GuidedExecutionModeResolver.class);
        when(mode.resolveDefaultMode()).thenReturn(GuidedExecutionModeResolver.ExecutionMode.DIRECT);
        var guided = new GuidedScanWorkflowService(mode, spiderScanService, mock(AjaxSpiderService.class),
                mock(ClientSpiderService.class), activeScanService, mock(ScanJobQueueService.class), auth,
                new ZapEngineAdapter(), new GatewayRecordFactory());
        String policy = "research-xss-control";
        clientApi.ascan.addScanPolicy(policy, "LOW", "MEDIUM");
        clientApi.ascan.disableAllScanners(policy);
        clientApi.ascan.enableScanners("40012", policy);
        long firstMessage = latestMessageId();
        for (String variant : List.of("vulnerable", "fixed")) {
            String url = origin + "/bearer/" + variant + "?q=researchseed";
            runResearchRequestAsUser(session.contextId(), session.userId(), url);
            String started = guided.startAttack(url, "false", policy, null, sid);
            String scanId = extractScanId(started);
            await().atMost(Duration.ofSeconds(90)).pollInterval(Duration.ofMillis(250))
                    .until(() -> activeScanService.getActiveScanProgressPercent(scanId) == 100);
            assertFalse(clientApi.ascan.scanProgress(scanId).toString(0).contains("100043"),
                    "A disabled script rule must stay disabled under a selected policy");
            System.out.println("RESEARCH active control " + variant + " scanId=" + scanId
                    + " status=" + guided.getAttackStatus(extractResponseValue(started, "Operation ID: ")));
        }
        await().atMost(Duration.ofSeconds(45)).until(() ->
                "0".equals(((ApiResponseElement) clientApi.pscan.recordsToScan()).getValue()));
        String vulnerableAlerts = clientApi.core.alerts(origin + "/bearer/vulnerable", "0", "100").toString(0);
        String fixedAlerts = clientApi.core.alerts(origin + "/bearer/fixed", "0", "100").toString(0);
        assertTrue(vulnerableAlerts.contains("40012"), vulnerableAlerts);
        assertFalse(fixedAlerts.contains("40012"), fixedAlerts);
        assertTrue(messagesAfter(firstMessage).stream().anyMatch(message ->
                message.getStringValue("requestHeader").contains("Authorization: Bearer ")
                        && message.getStringValue("responseHeader").contains(" 200 ")
                        && message.getStringValue("requestHeader").contains("q=")));
        String lossUrl = origin + "/bearer/vulnerable?q=researchseed";
        String lossStarted = guided.startAttack(lossUrl, "false", policy, null, sid);
        String lossOperation = extractResponseValue(lossStarted, "Operation ID: ");
        String lossScan = extractScanId(lossStarted);
        assertTrue(activeScanService.getActiveScanProgressPercent(lossScan) < 100,
                "Loss control must interrupt an in-flight active scan");
        try (var http = HttpClient.newHttpClient()) {
            http.send(HttpRequest.newBuilder(URI.create(local + "/bearer/reject-on")).GET().build(),
                    HttpResponse.BodyHandlers.discarding());
            assertTrue(auth.validateSession(sid).contains("Valid: false"));
            long firstFailure = System.nanoTime();
            long countAtFailure = latestMessageId();
            guided.stopAttack(lossOperation);
            long stopAck = System.nanoTime();
            await().atMost(Duration.ofSeconds(30)).pollInterval(Duration.ofMillis(100))
                    .until(() -> activeScanService.getActiveScanProgressPercent(lossScan) == 100);
            long terminal = System.nanoTime();
            System.out.println("RESEARCH auth loss scan=" + lossScan + " stopAckMs="
                    + (stopAck-firstFailure)/1_000_000.0 + " terminalMs=" + (terminal-firstFailure)/1_000_000.0
                    + " historyRecordsAfterFirstFailure=" + messagesAfter(countAtFailure).size());
            assertTrue((stopAck-firstFailure) < Duration.ofSeconds(10).toNanos());
            assertFalse(auth.isValidated(sid));
            org.junit.jupiter.api.Assertions.assertThrows(IllegalArgumentException.class,
                    () -> guided.startAttack(origin + "/bearer/vulnerable?q=x", "false", policy, null, sid));
            http.send(HttpRequest.newBuilder(URI.create(local + "/bearer/reject-off")).GET().build(),
                    HttpResponse.BodyHandlers.discarding());
        }
    }

    private static AuthBootstrapProperties.Profile jsonBearerProfile(
            String id, String targetOrigin, Path passwordFile) {
        AuthBootstrapProperties.Profile profile = new AuthBootstrapProperties.Profile();
        profile.setId(id);
        profile.setKind("json-bearer");
        profile.setAllowedOrigin(targetOrigin);
        profile.setCredentialReference("file:" + passwordFile);
        profile.setLoginUrl(targetOrigin + "/bearer/login");
        profile.setUsername("scan-user");
        profile.setZapUserName(id + "-user");
        profile.setUsernameJsonField("username");
        profile.setPasswordJsonField("password");
        profile.setTokenJsonPointer("/data/accessToken");
        profile.setHeaderName("Authorization");
        profile.setHeaderPrefix("Bearer ");
        profile.setVerificationUrl(targetOrigin + "/bearer/user");
        profile.setLoggedInIndicatorRegex("Signed in as scan-user");
        profile.setLoggedOutIndicatorRegex("statusCode.*401");
        return profile;
    }

    private static String loadJsonBearerController(
            String scriptName, String contextId, String userId) throws Exception {
        String template;
        try (var input = DirectScanServicesDockerTest.class.getResourceAsStream(
                "/json-bearer/retry-once-redact-spike.js")) {
            if (input == null) {
                throw new IllegalStateException("Missing JSON bearer controller test resource");
            }
            template = new String(input.readAllBytes(), StandardCharsets.UTF_8);
        }
        // ZAP ScriptVars keys are capped at 30 characters; leave room for the
        // longest state suffix (retryInProgress).
        String statePrefix = "j" + UUID.randomUUID().toString().substring(0, 6) + ".";
        String script = template
                .replace("__CONTEXT_ID__", contextId)
                .replace("__USER_ID__", userId)
                .replace("__ALLOWED_SCHEME__", "http")
                .replace("__ALLOWED_HOST__", "client-auth-target")
                .replace("__ALLOWED_PORT__", "8080")
                .replace("__STATE_PREFIX__", statePrefix);
        String containerPath = "/zap/wrk/" + scriptName + ".js";
        ZAP.copyFileToContainer(Transferable.of(script), containerPath);
        clientApi.script.load(scriptName, "httpsender", "Graal.js", containerPath,
                "Fixture-only JSON bearer retry/redaction feasibility controller", StandardCharsets.UTF_8);
        clientApi.script.enable(scriptName);
        return statePrefix;
    }

    private static String globalScriptValue(String key) throws Exception {
        return ((ApiResponseElement) clientApi.script.globalVar(key)).getValue();
    }

    private static String optionalGlobalScriptValue(String key) throws Exception {
        try {
            return globalScriptValue(key);
        } catch (org.zaproxy.clientapi.core.ClientApiException exception) {
            if (exception.getMessage().contains("Does Not Exist")) {
                return "missing";
            }
            throw exception;
        }
    }

    private static String registerAuthenticationPollRedactor(String scriptName) throws Exception {
        String statePrefix = "jpr" + UUID.randomUUID().toString().substring(0, 6) + ".";
        String script = nativeListenerProbeScript("poll", statePrefix);
        String containerPath = "/zap/wrk/" + scriptName + ".js";
        ZAP.copyFileToContainer(Transferable.of(script), containerPath);
        clientApi.script.load(scriptName, "standalone", "Graal.js", containerPath,
                "Fixture-only Java listener interception probe", StandardCharsets.UTF_8);
        clientApi.script.runStandAloneScript(scriptName);
        await().atMost(Duration.ofSeconds(15)).pollInterval(Duration.ofMillis(100)).until(() ->
                "true".equals(optionalGlobalScriptValue(statePrefix + "registered")));
        return statePrefix;
    }

    private static String startAddonOwnedJsonBearerProbe(String scriptName) throws Exception {
        String statePrefix = "jao" + UUID.randomUUID().toString().substring(0, 6) + ".";
        String script = nativeListenerProbeScript("addon", statePrefix);
        String containerPath = "/zap/wrk/" + scriptName + ".js";
        ZAP.copyFileToContainer(Transferable.of(script), containerPath);
        clientApi.script.load(scriptName, "standalone", "Graal.js", containerPath,
                "Fixture-only add-on-owned bearer lifecycle probe", StandardCharsets.UTF_8);
        clientApi.script.runStandAloneScript(scriptName);
        await().atMost(Duration.ofSeconds(15)).pollInterval(Duration.ofMillis(100)).until(() ->
                "true".equals(optionalGlobalScriptValue(statePrefix + "ready")));
        return statePrefix;
    }

    private static String nativeListenerProbeScript(String method, String statePrefix) throws Exception {
        ZAP.copyFileToContainer(MountableFile.forClasspathResource("json-bearer/FixtureBearerProbe.java"),
                "/zap/wrk/FixtureBearerProbe.java");
        var compiled = ZAP.execInContainer("javac", "-cp", "/zap/*:/zap/lib/*", "-d", "/tmp/probe-classes",
                "/zap/wrk/FixtureBearerProbe.java");
        assertEquals(0, compiled.getExitCode(), compiled.getStdout() + compiled.getStderr());
        return """
                const URLClassLoader = Java.type('java.net.URLClassLoader');
                const File = Java.type('java.io.File');
                const HttpSender = Java.type('org.parosproxy.paros.network.HttpSender');
                const loader = new URLClassLoader(Java.to([new File('/tmp/probe-classes').toURI().toURL()],
                        'java.net.URL[]'), HttpSender.class.getClassLoader());
                const probe = loader.loadClass('FixtureBearerProbe');
                probe.getMethod('%s', Java.type('java.lang.String').class).invoke(null, '%s');
                """.formatted(method, statePrefix);
    }

    private static String startNetworkWireInjectionProbe(String scriptName) throws Exception {
        String template;
        try (var input = DirectScanServicesDockerTest.class.getResourceAsStream(
                "/json-bearer/network-wire-injection-spike.js")) {
            if (input == null) {
                throw new IllegalStateException("Missing network wire injection test resource");
            }
            template = new String(input.readAllBytes(), StandardCharsets.UTF_8);
        }
        String statePrefix = "jwi" + UUID.randomUUID().toString().substring(0, 6) + ".";
        String script = template.replace("__STATE_PREFIX__", statePrefix);
        String containerPath = "/zap/wrk/" + scriptName + ".js";
        ZAP.copyFileToContainer(Transferable.of(script), containerPath);
        clientApi.script.load(scriptName, "standalone", "Graal.js", containerPath,
                "Fixture-only wire injection feasibility probe", StandardCharsets.UTF_8);
        clientApi.script.runStandAloneScript(scriptName);
        await().atMost(Duration.ofSeconds(15)).pollInterval(Duration.ofMillis(100)).until(() ->
                "true".equals(optionalGlobalScriptValue(statePrefix + "ready")));
        return statePrefix;
    }

    private static void fixtureGet(String url) throws Exception {
        try (HttpClient http = HttpClient.newHttpClient()) {
            HttpResponse<Void> response = http.send(
                    HttpRequest.newBuilder(URI.create(url)).GET().build(),
                    HttpResponse.BodyHandlers.discarding());
            assertTrue(response.statusCode() >= 200 && response.statusCode() < 300,
                    () -> "Fixture control request failed with HTTP " + response.statusCode());
        }
    }

    private static void runResearchRequestAsUser(String contextId, String userId, String targetUrl) throws Exception {
        runRequestAsUser(contextId, userId, targetUrl, "/json-bearer/send-as-user-research.js");
    }

    private static void runFixtureRequestAsUser(String contextId, String userId, String targetUrl) throws Exception {
        runRequestAsUser(contextId, userId, targetUrl, "/json-bearer/send-as-user-spike.js");
    }

    private static void runRequestAsUser(String contextId, String userId, String targetUrl, String resource) throws Exception {
        String template;
        try (var input = DirectScanServicesDockerTest.class.getResourceAsStream(
                resource)) {
            if (input == null) {
                throw new IllegalStateException("Missing JSON bearer request driver test resource");
            }
            template = new String(input.readAllBytes(), StandardCharsets.UTF_8);
        }
        String scriptName = "json-bearer-driver-" + UUID.randomUUID();
        String resultKey = "jbd." + UUID.randomUUID().toString().substring(0, 12);
        String script = template
                .replace("__CONTEXT_ID__", contextId)
                .replace("__USER_ID__", userId)
                .replace("__TARGET_URL__", targetUrl)
                .replace("__RESULT_KEY__", resultKey);
        String containerPath = "/zap/wrk/" + scriptName + ".js";
        ZAP.copyFileToContainer(Transferable.of(script), containerPath);
        try {
            clientApi.script.load(scriptName, "standalone", "Graal.js", containerPath,
                    "Fixture-only authenticated request driver", StandardCharsets.UTF_8);
            clientApi.script.runStandAloneScript(scriptName);
            await().atMost(Duration.ofSeconds(15)).pollInterval(Duration.ofMillis(100)).until(() ->
                    clientApi.script.globalVars().toString(0).contains(resultKey));
            try {
                await().atMost(Duration.ofSeconds(15)).pollInterval(Duration.ofMillis(100)).until(() ->
                        "done".equals(((ApiResponseElement) clientApi.script.globalVar(resultKey)).getValue()));
            } catch (Exception exception) {
                throw new AssertionError(clientApi.script.listScripts().toString(0), exception);
            }
        } finally {
            try {
                clientApi.script.clearGlobalVar(resultKey);
                clientApi.script.remove(scriptName);
            } catch (Exception ignored) {
                // Best-effort cleanup of an isolated test-only script.
            }
        }
    }

    private static int bearerMetric(String localOrigin, String metric) throws Exception {
        try (HttpClient http = HttpClient.newHttpClient()) {
            String body = http.send(HttpRequest.newBuilder(URI.create(localOrigin + "/bearer/metrics"))
                    .GET().build(), HttpResponse.BodyHandlers.ofString()).body();
            Matcher matcher = Pattern.compile("\\\"" + Pattern.quote(metric) + "\\\"\\s*:\\s*(\\d+)")
                    .matcher(body);
            if (!matcher.find()) {
                throw new IllegalStateException("Missing fixture metric " + metric);
            }
            return Integer.parseInt(matcher.group(1));
        }
    }

    private static long latestMessageId() throws Exception {
        return allMessages().stream()
                .mapToLong(message -> Long.parseLong(message.getStringValue("id")))
                .max().orElse(0L);
    }

    private static List<ApiResponseSet> messagesAfter(long messageId) throws Exception {
        return allMessages().stream()
                .filter(message -> Long.parseLong(message.getStringValue("id")) > messageId)
                .toList();
    }

    private static List<ApiResponseSet> allMessages() throws Exception {
        ApiResponseList messages = (ApiResponseList) clientApi.core.messages("", "0", "10000");
        return messages.getItems().stream().map(ApiResponseSet.class::cast).toList();
    }

    private static void assertOnlyNativeAuthenticationVerificationLeaks(List<ApiResponseSet> messages) {
        List<ApiResponseSet> leakedMessages = messages.stream()
                .filter(message -> message.getStringValue("requestHeader").contains("Authorization: Bearer "))
                .toList();
        assertFalse(leakedMessages.isEmpty(),
                "The spike must continue documenting the native ZAP verification-history leak");
        assertTrue(leakedMessages.stream().allMatch(message ->
                        message.getStringValue("tags").contains("AuthenticationVerification")),
                "Only native AuthenticationVerification records may bypass the script redactor");
    }

    private static List<String> recordedUrls(String origin) throws Exception {
        return ((ApiResponseList) clientApi.core.urls(origin)).getItems().stream()
                .map(ApiResponseElement.class::cast).map(ApiResponseElement::getValue).toList();
    }

    private static String extractResponseValue(String response, String prefix) {
        return response.lines().filter(line -> line.startsWith(prefix))
                .map(line -> line.substring(prefix.length()).trim()).findFirst().orElseThrow();
    }

    @Test
    void clientSpiderDiscoversJavaScriptTrafficAndStopsOnlyTheRequestedScan() throws Exception {
        String stoppedScanId = extractScanId(clientSpiderService.startClientSpider(
                "http://direct-scan-target/client-crawl.html?crawl=stop", 1));
        String continuingScanId = extractScanId(clientSpiderService.startClientSpider(
                "http://direct-scan-target/client-crawl.html?crawl=continue", 1));

        try {
            assertNotEquals(stoppedScanId, continuingScanId);
            assertTrue(clientSpiderService.getClientSpiderStatus(continuingScanId)
                    .contains("Scan ID: " + continuingScanId));

            clientSpiderService.stopClientSpider(stoppedScanId);
            assertTrue(clientSpiderService.getClientSpiderProgressPercent(continuingScanId) < 100,
                    "Stopping one Client Spider scan must leave the other scan running");

            await().atMost(Duration.ofSeconds(90)).pollInterval(Duration.ofMillis(500))
                    .until(() -> clientSpiderService.getClientSpiderProgressPercent(stoppedScanId) == 100);
            await().atMost(Duration.ofSeconds(90)).pollInterval(Duration.ofMillis(500))
                    .until(() -> clientSpiderService.getClientSpiderProgressPercent(continuingScanId) == 100);

            ApiResponseList urlsResponse = (ApiResponseList) clientApi.core.urls("http://direct-scan-target/");
            List<String> discoveredUrls = urlsResponse.getItems().stream()
                    .map(ApiResponseElement.class::cast)
                    .map(ApiResponseElement::getValue)
                    .toList();
            assertTrue(discoveredUrls.contains("http://direct-scan-target/client-discovered?crawl=continue"),
                    () -> "The remaining crawl must execute JavaScript and send its discovered request through ZAP.\n"
                            + "Discovered URLs: " + discoveredUrls);
        } finally {
            clientSpiderService.stopClientSpiderJob(stoppedScanId);
            clientSpiderService.stopClientSpiderJob(continuingScanId);
        }
    }

    @ParameterizedTest
    @EnumSource(GuidedExecutionModeResolver.ExecutionMode.class)
    void guidedClientSpiderUsesPreparedBrowserSessionForProtectedJavaScriptTraffic(
            GuidedExecutionModeResolver.ExecutionMode mode, @TempDir Path temporaryDirectory)
            throws Exception {
        assertPreparedBrowserSessionCrawl(mode, temporaryDirectory, false);
    }

    @ParameterizedTest
    @EnumSource(GuidedExecutionModeResolver.ExecutionMode.class)
    void guidedClientSpiderValidatesAndCrawlsWithBearerTokenStoredInLocalStorage(
            GuidedExecutionModeResolver.ExecutionMode mode, @TempDir Path temporaryDirectory)
            throws Exception {
        assertPreparedBrowserSessionCrawl(mode, temporaryDirectory, true);
    }

    private void assertPreparedBrowserSessionCrawl(GuidedExecutionModeResolver.ExecutionMode mode,
                                                   Path temporaryDirectory, boolean bearerSession) throws Exception {
        // Browser authentication's auto-detected header/cookie replay depends on passive
        // session detection. Do not carry a previous duration test's backlog into login.
        System.out.println("Browser authentication fixture passive records before setup: "
                + clientApi.pscan.recordsToScan().toString(0));
        await().atMost(Duration.ofSeconds(120)).pollInterval(Duration.ofMillis(500))
                .until(() -> "0".equals(((ApiResponseElement) clientApi.pscan.recordsToScan()).getValue()));
        String targetOrigin = "http://client-auth-target:8080";
        String authFlavor = bearerSession ? "bearer" : "cookie";
        String crawlQuery = "?crawl=" + mode.name();
        String crawlPath = bearerSession ? "/bearer/app" : "/protected";
        String verificationPath = bearerSession ? "/bearer/user" : "/protected";
        String discoveredPath = bearerSession ? "/bearer/client-discovered" : "/protected/client-discovered";
        String loginPath = bearerSession ? "/bearer/login" : "/login";
        String expectedAuthHeader = bearerSession ? "Authorization: Bearer " : "Cookie: session=";
        String targetUrl = targetOrigin + crawlPath + crawlQuery;
        String verificationUrl = bearerSession ? targetOrigin + verificationPath : targetUrl;
        String localOrigin = "http://" + AUTH_TARGET.getHost() + ":" + AUTH_TARGET.getMappedPort(8080);
        try (HttpClient http = HttpClient.newHttpClient()) {
            assertEquals(bearerSession ? 401 : 403, http.send(HttpRequest.newBuilder(URI.create(localOrigin + verificationPath)).GET().build(),
                    HttpResponse.BodyHandlers.discarding()).statusCode(),
                    "The verification endpoint must require a login");
            assertEquals(bearerSession ? 401 : 403, http.send(HttpRequest.newBuilder(URI.create(localOrigin + discoveredPath))
                            .GET().build(), HttpResponse.BodyHandlers.discarding()).statusCode(),
                    "The JavaScript resource must also require a login");
            assertEquals(403, http.send(HttpRequest.newBuilder(URI.create(localOrigin + loginPath))
                            .POST(HttpRequest.BodyPublishers.ofString(bearerSession
                                    ? "{\"username\":\"scan-user\",\"password\":\"wrong\"}"
                                    : "username=scan-user&password=wrong"))
                            .header("Content-Type", bearerSession ? "application/json" : "application/x-www-form-urlencoded").build(),
                    HttpResponse.BodyHandlers.discarding()).statusCode(),
                    "The fixture must reject incorrect credentials");
        }

        Path passwordFile = Files.writeString(temporaryDirectory.resolve("password"), "fixture-password");
        AuthBootstrapProperties.Profile profile = new AuthBootstrapProperties.Profile();
        profile.setId("client-browser-auth-" + authFlavor + "-" + mode.name());
        profile.setKind("browser");
        profile.setAllowedOrigin(targetOrigin);
        profile.setCredentialReference("file:" + passwordFile);
        profile.setLoginUrl(targetOrigin + loginPath);
        profile.setUsername("scan-user");
        profile.setZapUserName("client-browser-user-" + authFlavor + "-" + mode.name());
        profile.setLoggedInIndicatorRegex("Signed in as scan-user");
        profile.setLoggedOutIndicatorRegex("Login required");
        AuthBootstrapProperties authProperties = new AuthBootstrapProperties();
        authProperties.setProfiles(List.of(profile));
        // Browser authentication is synchronous; deployments can select this existing API read timeout.
        ClientApi browserAuthApi = new TimeoutZapClientApi(ZAP.getHost(), ZAP.getMappedPort(8090), null, 5000, 60000);
        FormLoginAuthBootstrapProvider authProvider = new FormLoginAuthBootstrapProvider(
                new ContextUserService(new ZapEngineContextAccess(browserAuthApi)),
                new CredentialReferenceResolver(), mock(UrlValidationService.class));
        GuidedAuthSessionService authSessions = new GuidedAuthSessionService(
                List.of(authProvider), new InMemoryPreparedAuthSessionRegistry(), new AuthProfileResolver(authProperties));
        String prepared = authSessions.prepareSession(profile.getId(), verificationUrl);
        String sessionId = prepared.lines().filter(line -> line.startsWith("Session ID: "))
                .map(line -> line.substring("Session ID: ".length())).findFirst().orElseThrow();
        String validated = authSessions.validateSession(sessionId);
        assertTrue(validated.contains("Valid: true"), validated);
        assertTrue(validated.contains("Outcome: authenticated"), validated);
        if (bearerSession) {
            var session = authSessions.getPreparedSession(sessionId);
            ApiResponseSet nativePoll = (ApiResponseSet) browserAuthApi.users.pollAsUser(session.contextId(), session.userId());
            assertEquals("true", nativePoll.getStringValue("pollSuccessful"),
                    "ZAP must replay the browser's bearer token when verifying authentication outside the browser");
            assertTrue(nativePoll.getStringValue("responseHeader").contains(" 200 "));
            assertTrue(nativePoll.getStringValue("responseBody").contains("Signed in as scan-user"));
        }

        GuidedExecutionModeResolver executionMode = mock(GuidedExecutionModeResolver.class);
        when(executionMode.resolveDefaultMode()).thenReturn(mode);
        InMemoryScanJobStore store = new InMemoryScanJobStore();
        var retryPolicy = new ScanJobQueueService.RetryPolicy(1, 0, 0, 1.0);
        ScanJobQueueService queue = new ScanJobQueueService(
                activeScanService, spiderScanService, mock(AjaxSpiderService.class), clientSpiderService,
                mock(UrlValidationService.class), new ScanLimitProperties(), retryPolicy, retryPolicy,
                false, store, new SingleNodeQueueLeadershipCoordinator());
        GuidedScanWorkflowService guidedScans = new GuidedScanWorkflowService(executionMode,
                mock(SpiderScanService.class), mock(AjaxSpiderService.class), clientSpiderService,
                mock(ActiveScanService.class), queue, authSessions,
                new ZapEngineAdapter(), new GatewayRecordFactory());
        try {
            String started = guidedScans.startCrawl(targetUrl, "client", null, sessionId);
            String operationId = started.lines().filter(line -> line.startsWith("Operation ID: "))
                    .map(line -> line.substring("Operation ID: ".length())).findFirst().orElseThrow();
            String jobId = mode == GuidedExecutionModeResolver.ExecutionMode.QUEUE
                    ? store.list().getFirst().getId() : null;
            try {
                assertTrue(started.contains("Authenticated Session: " + sessionId));
                String status = guidedScans.getCrawlStatus(operationId);
                assertTrue(status.contains("Strategy: client"));
                if (jobId != null) {
                    var job = store.load(jobId).orElseThrow();
                    assertEquals(ScanJobType.CLIENT_SPIDER, job.getType());
                    assertEquals(ScanJobStatus.RUNNING, job.getStatus());
                    assertEquals(profile.getId() + "-auth", job.getParameters().get("contextName"));
                    assertEquals(profile.getZapUserName(), job.getParameters().get("userName"));
                    assertTrue(status.contains("Job ID: " + jobId));
                    assertTrue(status.contains("ZAP Scan ID: " + job.getZapScanId()));
                }
                await().atMost(Duration.ofSeconds(90)).pollInterval(Duration.ofMillis(500)).untilAsserted(() -> {
                    ApiResponseList messages = (ApiResponseList) clientApi.core.messages(
                            targetOrigin + discoveredPath + crawlQuery, "0", "100");
                    assertTrue(messages.getItems().stream().map(ApiResponseSet.class::cast).anyMatch(message ->
                                    message.getStringValue("requestHeader").contains(discoveredPath + crawlQuery)
                                            && message.getStringValue("requestHeader").contains(expectedAuthHeader)
                                            && message.getStringValue("responseHeader").contains(" 200 ")
                                            && message.getStringValue("responseBody")
                                                    .contains("authenticated JavaScript resource")),
                            "Client Spider must fetch this crawl's protected JavaScript resource with its browser user's session");
                });
                String scanId = jobId == null ? extractScanId(started) : store.load(jobId).orElseThrow().getZapScanId();
                assertTrue(clientSpiderService.getClientSpiderProgressPercent(scanId) < 100,
                        "The crawl must still be running so the stop request exercises active cancellation");
            } finally {
                guidedScans.stopCrawl(operationId);
                await().atMost(Duration.ofSeconds(30)).pollInterval(Duration.ofMillis(500)).untilAsserted(() -> {
                    String status = guidedScans.getCrawlStatus(operationId);
                    String scanId = jobId == null ? extractScanId(started) : store.load(jobId).orElseThrow().getZapScanId();
                    assertEquals(100, clientSpiderService.getClientSpiderProgressPercent(scanId));
                    if (jobId != null) {
                        assertEquals(ScanJobStatus.CANCELLED, store.load(jobId).orElseThrow().getStatus());
                        assertTrue(status.contains("Status: CANCELLED"));
                    }
                });
            }
        } finally {
            queue.shutdownExecutor();
        }

        if (bearerSession) {
            return;
        }

        String unexpectedPrepared = authSessions.prepareSession(profile.getId(), targetOrigin + "/unexpected-response");
        String unexpectedSessionId = unexpectedPrepared.lines().filter(line -> line.startsWith("Session ID: "))
                .map(line -> line.substring("Session ID: ".length())).findFirst().orElseThrow();
        String unexpectedValidation = authSessions.validateSession(unexpectedSessionId);
        assertTrue(unexpectedValidation.contains("Valid: false"), unexpectedValidation);
        assertTrue(unexpectedValidation.contains("Outcome: authentication_unconfirmed"), unexpectedValidation);

        var unexpectedSession = authSessions.getPreparedSession(unexpectedSessionId);
        ApiResponseSet unexpectedPoll = (ApiResponseSet) browserAuthApi.users.pollAsUser(
                unexpectedSession.contextId(), unexpectedSession.userId());
        assertEquals("true", unexpectedPoll.getStringValue("pollSuccessful"),
                "ZAP's native verdict alone accepts a response without either configured indicator");
        assertTrue(unexpectedPoll.getStringValue("responseHeader").contains(" 500 "));
        assertTrue(unexpectedPoll.getStringValue("responseBody").contains("Temporarily unavailable"));
    }

    @Test
    void nativeJsonBearerSessionValidatesAndRoutesDirectHttpAndActiveScans(@TempDir Path temporaryDirectory)
            throws Exception {
        String targetOrigin = "http://client-auth-target:8080";
        String targetUrl = targetOrigin + "/bearer/crawl";
        String verificationUrl = targetOrigin + "/bearer/user";
        String localOrigin = "http://" + AUTH_TARGET.getHost() + ":" + AUTH_TARGET.getMappedPort(8080);
        try (HttpClient http = HttpClient.newHttpClient()) {
            assertEquals(401, http.send(HttpRequest.newBuilder(URI.create(localOrigin + "/bearer/user"))
                    .GET().build(), HttpResponse.BodyHandlers.discarding()).statusCode());
        }

        Path passwordFile = Files.writeString(temporaryDirectory.resolve("json-password"), "fixture-password");
        AuthBootstrapProperties.Profile profile = new AuthBootstrapProperties.Profile();
        profile.setId("native-json-bearer");
        profile.setKind("json-bearer");
        profile.setAllowedOrigin(targetOrigin);
        profile.setCredentialReference("file:" + passwordFile);
        profile.setLoginUrl(targetOrigin + "/bearer/login");
        profile.setUsername("scan-user");
        profile.setZapUserName("native-json-user");
        profile.setUsernameJsonField("username");
        profile.setPasswordJsonField("password");
        profile.setTokenJsonPointer("/data/accessToken");
        profile.setHeaderName("Authorization");
        profile.setHeaderPrefix("Bearer ");
        profile.setVerificationUrl(verificationUrl);
        profile.setLoggedInIndicatorRegex("Signed in as scan-user");
        profile.setLoggedOutIndicatorRegex("statusCode.*401");
        AuthBootstrapProperties properties = new AuthBootstrapProperties();
        properties.setProfiles(List.of(profile));

        ContextUserService contextUsers = new ContextUserService(new ZapEngineContextAccess(clientApi));
        InMemoryPreparedAuthSessionRegistry registry = new InMemoryPreparedAuthSessionRegistry();
        GuidedAuthSessionService authSessions = new GuidedAuthSessionService(
                List.of(new JsonBearerAuthBootstrapProvider(
                        contextUsers, new CredentialReferenceResolver(), mock(UrlValidationService.class))),
                registry,
                new AuthProfileResolver(properties)
        );
        String prepared = authSessions.prepareSession(profile.getId(), targetUrl);
        String sessionId = extractResponseValue(prepared, "Session ID: ");
        String validated = authSessions.validateSession(sessionId);
        assertTrue(validated.contains("Valid: true"), validated);
        assertTrue(validated.contains("Outcome: authenticated"), validated);
        assertTrue(validated.contains("likelyAuthenticated=true"), validated);
        assertTrue(validated.contains("Header replay verified: true"), validated);
        assertFalse(Pattern.compile("eyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+")
                .matcher(prepared + validated).find(), "MCP prepare/validate results must not contain a JWT");

        var session = authSessions.getPreparedSession(sessionId);
        ApiResponseSet poll = (ApiResponseSet) clientApi.users.pollAsUser(session.contextId(), session.userId());
        assertEquals("true", poll.getStringValue("pollSuccessful"));
        assertTrue(poll.getStringValue("responseHeader").contains(" 200 "));
        ApiResponseList verificationMessages = (ApiResponseList) clientApi.core.messages(verificationUrl, "0", "100");
        assertTrue(verificationMessages.getItems().stream().map(ApiResponseSet.class::cast).anyMatch(message ->
                message.getStringValue("requestHeader").contains("Authorization: Bearer ")
                        && message.getStringValue("responseHeader").contains(" 200 ")),
                "Verification must replay Authorization through the prepared ZAP user/context");

        GuidedExecutionModeResolver executionMode = mock(GuidedExecutionModeResolver.class);
        when(executionMode.resolveDefaultMode()).thenReturn(GuidedExecutionModeResolver.ExecutionMode.DIRECT);
        GuidedScanWorkflowService guided = new GuidedScanWorkflowService(
                executionMode,
                spiderScanService,
                mock(AjaxSpiderService.class),
                mock(ClientSpiderService.class),
                activeScanService,
                mock(ScanJobQueueService.class),
                authSessions,
                new ZapEngineAdapter(),
                new GatewayRecordFactory()
        );
        String crawlStarted = guided.startCrawl(targetUrl, "http", null, sessionId);
        String crawlScanId = extractScanId(crawlStarted);
        await().atMost(Duration.ofSeconds(60)).pollInterval(Duration.ofMillis(250))
                .until(() -> spiderScanService.getSpiderScanProgressPercent(crawlScanId) == 100);
        ApiResponseList childMessages = (ApiResponseList) clientApi.core.messages(
                targetOrigin + "/bearer/crawl-child", "0", "100");
        assertTrue(childMessages.getItems().stream().map(ApiResponseSet.class::cast).anyMatch(message ->
                message.getStringValue("requestHeader").contains("Authorization: Bearer ")
                        && message.getStringValue("responseHeader").contains(" 200 ")),
                "Authenticated HTTP Spider must reach the protected child");

        String activeStarted = guided.startAttack(targetUrl, "false", null, null, sessionId);
        String activeScanId = extractScanId(activeStarted);
        assertTrue(activeStarted.contains("Authenticated Session: " + sessionId), activeStarted);
        activeScanService.stopActiveScan(activeScanId);
        assertFalse(Pattern.compile("eyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+")
                .matcher(crawlStarted + activeStarted).find(), "Guided scan results must not contain a JWT");

        GuidedAuthSessionService restarted = new GuidedAuthSessionService(
                List.of(new JsonBearerAuthBootstrapProvider(
                        contextUsers, new CredentialReferenceResolver(), mock(UrlValidationService.class))),
                new InMemoryPreparedAuthSessionRegistry(),
                new AuthProfileResolver(properties)
        );
        boolean rejectedAfterRestart = false;
        try {
            restarted.getPreparedSession(sessionId);
        } catch (IllegalArgumentException expected) {
            rejectedAfterRestart = true;
        }
        assertTrue(rejectedAfterRestart, "An MCP restart must invalidate the opaque auth session ID");
    }

    @Test
    void javaListenerCanRedactNativePollBeforePersistenceButCannotMakeNativeLoginHistorySecretSafe(
            @TempDir Path temporaryDirectory) throws Exception {
        String targetOrigin = "http://client-auth-target:8080";
        Path passwordFile = Files.writeString(
                temporaryDirectory.resolve("json-listener-password"), "fixture-password");
        AuthBootstrapProperties.Profile profile = jsonBearerProfile(
                "json-bearer-listener-gate", targetOrigin, passwordFile);
        AuthBootstrapProperties properties = new AuthBootstrapProperties();
        properties.setProfiles(List.of(profile));
        ContextUserService contextUsers = new ContextUserService(new ZapEngineContextAccess(clientApi));
        GuidedAuthSessionService authSessions = new GuidedAuthSessionService(
                List.of(new JsonBearerAuthBootstrapProvider(
                        contextUsers, new CredentialReferenceResolver(), mock(UrlValidationService.class))),
                new InMemoryPreparedAuthSessionRegistry(),
                new AuthProfileResolver(properties));

        String scriptName = "json-bearer-poll-redactor-" + UUID.randomUUID();
        String statePrefix = registerAuthenticationPollRedactor(scriptName);
        long baselineMessageId = latestMessageId();
        try {
            String prepared = authSessions.prepareSession(profile.getId(), targetOrigin + "/bearer/crawl");
            String sessionId = extractResponseValue(prepared, "Session ID: ");
            String validated = authSessions.validateSession(sessionId);
            assertTrue(validated.contains("Valid: true"), validated);
            assertEquals("true", globalScriptValue(statePrefix + "pollRequestSeen"));
            assertEquals("true", globalScriptValue(statePrefix + "pollRedacted"));
            assertEquals("true", globalScriptValue(statePrefix + "loginRequestSeen"));

            List<ApiResponseSet> messages = messagesAfter(baselineMessageId);
            List<ApiResponseSet> verificationRecords = messages.stream()
                    .filter(message -> message.getStringValue("tags").contains("AuthenticationVerification"))
                    .toList();
            assertFalse(verificationRecords.isEmpty(), "Native verification evidence must exist");
            assertTrue(verificationRecords.stream().noneMatch(message ->
                            message.getStringValue("requestHeader").contains("Authorization: Bearer ")),
                    "A Java listener can redact native verification before AuthenticationHelper persists it");

            boolean passwordPersisted = messages.stream().anyMatch(message ->
                    message.getStringValue("requestBody").contains("fixture-password"));
            boolean tokenPersisted = messages.stream().anyMatch(message ->
                    Pattern.compile("eyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+")
                            .matcher(message.getStringValue("responseBody")).find());
            assertTrue(passwordPersisted,
                    "Native JSON authentication must remain documented as persisting the login password");
            assertTrue(tokenPersisted,
                    "Native JSON authentication must remain documented as persisting the login token response");
        } finally {
            try {
                clientApi.script.setGlobalVar(statePrefix + "enabled", "false");
                clientApi.script.remove(scriptName);
            } catch (Exception ignored) {
                // Listener remains registered until ZAP restart but is permanently disabled.
            }
        }
    }

    @Test
    void addonOwnedLifecycleProtectsLoginAndOriginButHttpSenderInjectionLeaksIntoSpiderHistory()
            throws Exception {
        String targetOrigin = "http://client-auth-target:8080";
        String scriptName = "json-bearer-addon-owned-" + UUID.randomUUID();
        long baselineMessageId = latestMessageId();
        String statePrefix = startAddonOwnedJsonBearerProbe(scriptName);
        String scanId = null;
        try {
            assertEquals("200", globalScriptValue(statePrefix + "protectedStatus"));
            assertEquals("200", globalScriptValue(statePrefix + "crossOriginStatus"));
            assertEquals("true", globalScriptValue(statePrefix + "sameOriginInjected"));
            assertEquals("true", globalScriptValue(statePrefix + "crossOriginClean"));
            assertEquals("true", globalScriptValue(statePrefix + "redacted"));

            List<ApiResponseSet> probeMessages = messagesAfter(baselineMessageId);
            assertTrue(probeMessages.stream().noneMatch(message ->
                            message.getStringValue("requestBody").contains("fixture-password")),
                    "An add-on-owned login must not persist the password in ZAP history");
            assertTrue(probeMessages.stream().noneMatch(message ->
                            message.getStringValue("requestHeader").contains("Authorization: Bearer ")
                                    || Pattern.compile("eyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+")
                                            .matcher(message.getStringValue("responseBody")).find()),
                    "An add-on-owned login and response redactor must keep the token out of history");

            int protectedCountBefore = bearerMetric(
                    "http://" + AUTH_TARGET.getHost() + ":" + AUTH_TARGET.getMappedPort(8080),
                    "protectedCount");
            scanId = spiderScanService.startSpiderScanJob(targetOrigin + "/bearer/crawl");
            String scanToWait = scanId;
            await().atMost(Duration.ofSeconds(60)).pollInterval(Duration.ofMillis(250))
                    .until(() -> spiderScanService.getSpiderScanProgressPercent(scanToWait) == 100);
            assertTrue(bearerMetric(
                            "http://" + AUTH_TARGET.getHost() + ":" + AUTH_TARGET.getMappedPort(8080),
                            "protectedCount") > protectedCountBefore,
                    "The ordinary HTTP Spider must use the in-memory exact-origin header controller");
            assertTrue(recordedUrls(targetOrigin).contains(targetOrigin + "/bearer/crawl-child"),
                    "The authenticated spider must discover the protected child");

            List<ApiResponseSet> crawlMessages = messagesAfter(baselineMessageId);
            List<ApiResponseSet> leakedSpiderMessages = crawlMessages.stream()
                    .filter(message -> message.getStringValue("requestHeader").contains("Authorization: Bearer "))
                    .filter(message -> message.getStringValue("requestHeader").contains("/bearer/crawl"))
                    .toList();
            assertFalse(leakedSpiderMessages.isEmpty(),
                    "The feasibility gate must document that HttpSender injection reaches Spider history");
            assertTrue(leakedSpiderMessages.stream().allMatch(message ->
                            message.getStringValue("responseHeader").contains(" 200 ")),
                    "The leaked records must be the authenticated Spider traffic, not failed fixture noise");
        } finally {
            if (scanId != null) {
                spiderScanService.stopSpiderScanJob(scanId);
            }
            try {
                clientApi.script.setGlobalVar(statePrefix + "enabled", "false");
                clientApi.script.remove(scriptName);
            } catch (Exception ignored) {
                // Listener remains registered until ZAP restart but is permanently disabled.
            }
        }
    }

    @Test
    void networkWireInjectionKeepsAuthorizationOutOfModelForManualExchange() throws Exception {
        String scriptName = "json-bearer-wire-injection-" + UUID.randomUUID();
        long baselineMessageId = latestMessageId();
        String statePrefix = startNetworkWireInjectionProbe(scriptName);
        try {
            assertEquals("200", globalScriptValue(statePrefix + "protectedStatus"));
            assertEquals("200", globalScriptValue(statePrefix + "crossOriginStatus"));
            assertEquals("true", globalScriptValue(statePrefix + "wireInjected"));
            assertEquals("true", globalScriptValue(statePrefix + "wireRemoved"));
            assertEquals("true", globalScriptValue(statePrefix + "crossOriginClean"));
            assertEquals("true", globalScriptValue(statePrefix + "modelHeaderClean"));

            List<ApiResponseSet> probeMessages = messagesAfter(baselineMessageId);
            assertTrue(probeMessages.stream().noneMatch(message ->
                            message.getStringValue("requestBody").contains("fixture-password")
                                    || message.getStringValue("requestHeader").contains("Authorization: Bearer ")
                                    || Pattern.compile("eyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+")
                                            .matcher(message.getStringValue("responseBody")).find()),
                    "Wire-only injection must keep credentials and token out of model/history");
        } finally {
            try {
                clientApi.script.setGlobalVar(statePrefix + "enabled", "false");
                clientApi.core.accessUrl("http://direct-scan-target/", "false");
                await().atMost(Duration.ofSeconds(10)).pollInterval(Duration.ofMillis(100)).until(() ->
                        "true".equals(optionalGlobalScriptValue(statePrefix + "cleaned")));
                clientApi.script.remove(scriptName);
            } catch (Exception ignored) {
                // Testcontainers destroys this isolated ZAP instance if cleanup itself fails.
            }
        }
    }

    @Test
    void experimentalJsonBearerControllerRefreshesOnceFailsClosedButNativeVerificationLeaksToken(
            @TempDir Path temporaryDirectory) throws Exception {
        String targetOrigin = "http://client-auth-target:8080";
        String targetUrl = targetOrigin + "/bearer/crawl";
        String localOrigin = "http://" + AUTH_TARGET.getHost() + ":" + AUTH_TARGET.getMappedPort(8080);
        Path passwordFile = Files.writeString(temporaryDirectory.resolve("json-controller-password"),
                "fixture-password");
        AuthBootstrapProperties.Profile profile = jsonBearerProfile(
                "experimental-json-bearer", targetOrigin, passwordFile);
        AuthBootstrapProperties properties = new AuthBootstrapProperties();
        properties.setProfiles(List.of(profile));
        ContextUserService contextUsers = new ContextUserService(new ZapEngineContextAccess(clientApi));
        GuidedAuthSessionService authSessions = new GuidedAuthSessionService(
                List.of(new JsonBearerAuthBootstrapProvider(
                        contextUsers, new CredentialReferenceResolver(), mock(UrlValidationService.class))),
                new InMemoryPreparedAuthSessionRegistry(),
                new AuthProfileResolver(properties));

        String prepared = authSessions.prepareSession(profile.getId(), targetUrl);
        String sessionId = extractResponseValue(prepared, "Session ID: ");
        String validated = authSessions.validateSession(sessionId);
        assertTrue(validated.contains("Valid: true"), validated);
        var session = authSessions.getPreparedSession(sessionId);

        GuidedExecutionModeResolver executionMode = mock(GuidedExecutionModeResolver.class);
        when(executionMode.resolveDefaultMode()).thenReturn(GuidedExecutionModeResolver.ExecutionMode.DIRECT);
        GuidedScanWorkflowService guided = new GuidedScanWorkflowService(
                executionMode, spiderScanService, mock(AjaxSpiderService.class), mock(ClientSpiderService.class),
                activeScanService, mock(ScanJobQueueService.class), authSessions,
                new ZapEngineAdapter(), new GatewayRecordFactory());

        String scriptName = "json-bearer-controller-" + UUID.randomUUID();
        try {
            String seedCrawl = guided.startCrawl(targetUrl, "http", null, sessionId);
            String seedScanId = extractScanId(seedCrawl);
            await().atMost(Duration.ofSeconds(60)).pollInterval(Duration.ofMillis(250))
                    .until(() -> spiderScanService.getSpiderScanProgressPercent(seedScanId) == 100);
            String controllerStatePrefix = loadJsonBearerController(
                    scriptName, session.contextId(), session.userId());
            long baselineMessageId = latestMessageId();
            int loginCountBefore = bearerMetric(localOrigin, "loginCount");
            fixtureGet(localOrigin + "/bearer/expire");
            assertEquals(0, bearerMetric(localOrigin, "sessionCount"));

            runFixtureRequestAsUser(session.contextId(), session.userId(), targetOrigin + "/bearer/user");
            assertEquals("true", globalScriptValue(controllerStatePrefix + "sendSeen"));
            assertEquals("true", globalScriptValue(controllerStatePrefix + "responseSeen"));
            assertEquals("true", globalScriptValue(controllerStatePrefix + "allowedSeen"));
            assertEquals("true", optionalGlobalScriptValue(controllerStatePrefix + "unauthorizedSeen"),
                    "successSeen=" + optionalGlobalScriptValue(controllerStatePrefix + "successSeen"));
            assertEquals("true", globalScriptValue(controllerStatePrefix + "retryAttempted"));

            assertEquals(loginCountBefore + 1, bearerMetric(localOrigin, "loginCount"),
                    "An expired token must cause exactly one re-login; scripts="
                            + clientApi.script.listScripts().toString(0));
            List<ApiResponseSet> refreshedMessages = messagesAfter(baselineMessageId);
            assertTrue(refreshedMessages.stream().anyMatch(message ->
                            message.getStringValue("requestHeader").contains("Authorization: <redacted>")
                                    && message.getStringValue("responseHeader").contains(" 200 ")
                                    && message.getStringValue("requestHeader").contains("/bearer/")),
                    "The retried protected request must succeed and be redacted before history persistence");
            assertOnlyNativeAuthenticationVerificationLeaks(refreshedMessages);

            clientApi.script.remove(scriptName);
            scriptName = "json-bearer-controller-" + UUID.randomUUID();
            controllerStatePrefix = loadJsonBearerController(scriptName, session.contextId(), session.userId());
            fixtureGet(localOrigin + "/bearer/reject-on");
            fixtureGet(localOrigin + "/bearer/expire");
            baselineMessageId = latestMessageId();
            loginCountBefore = bearerMetric(localOrigin, "loginCount");
            int protectedCountBefore = bearerMetric(localOrigin, "protectedCount");

            runFixtureRequestAsUser(session.contextId(), session.userId(), targetOrigin + "/bearer/user");
            assertEquals(loginCountBefore + 1, bearerMetric(localOrigin, "loginCount"),
                    "A rejected refresh must still attempt re-login only once");
            assertTrue(bearerMetric(localOrigin, "protectedCount") > protectedCountBefore,
                    "The first protected request must reach the fixture and prove rejection");

            int protectedCountAfterFailure = bearerMetric(localOrigin, "protectedCount");
            runFixtureRequestAsUser(session.contextId(), session.userId(), targetOrigin + "/bearer/user");
            assertEquals(protectedCountAfterFailure, bearerMetric(localOrigin, "protectedCount"),
                    "Once blocked, later scan traffic must not reach the target origin");
            assertEquals(loginCountBefore + 1, bearerMetric(localOrigin, "loginCount"),
                    "The controller must never attempt a second re-login");

            List<ApiResponseSet> failedMessages = messagesAfter(baselineMessageId);
            assertTrue(failedMessages.stream().anyMatch(message ->
                            message.getStringValue("requestHeader").contains("X-ZAP-Auth-Blocked: true")),
                    "Fail-closed rerouting must leave a non-secret marker for an MCP scan controller");
            assertOnlyNativeAuthenticationVerificationLeaks(failedMessages);
            String scripts = clientApi.script.listScripts().toString(0);
            assertTrue(scripts.contains(scriptName), scripts);
            assertFalse(scripts.contains("lastError=org.graalvm"), scripts);
            assertFalse(Pattern.compile("eyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+")
                    .matcher(prepared + validated + seedCrawl + scripts).find(),
                    "Results and script metadata must not contain a JWT");
        } finally {
            try {
                clientApi.script.remove(scriptName);
            } catch (Exception ignored) {
                // Best-effort cleanup of an isolated test-only script.
            }
            fixtureGet(localOrigin + "/bearer/reject-off");
        }
    }

    @Test
    void clientSpiderDurationExpiresWithoutReceivingNewNodes() throws Exception {
        String previousInitialLoadTime = ((ApiResponseElement) clientApi.callApi(
                "clientSpider", "view", "optionInitialLoadTimeInSecs", Map.of())).getValue();
        String previousPageLoadTime = ((ApiResponseElement) clientApi.callApi(
                "clientSpider", "view", "optionPageLoadTimeInSecs", Map.of())).getValue();
        String durationStatistic = "stats.client.spider.event.max.time";
        String scanId = null;
        try {
            // Client 0.33 schedules the deadline independently of new-node events. A finite,
            // blank page with a longer initial wait must expire before that wait finishes.
            clientApi.callApi("clientSpider", "action", "setOptionInitialLoadTimeInSecs", Map.of("Integer", "120"));
            clientApi.callApi("clientSpider", "action", "setOptionPageLoadTimeInSecs", Map.of("Integer", "120"));
            clientApi.stats.clearStats(durationStatistic);
            scanId = clientSpiderService.startClientSpiderJob("http://direct-scan-target/client-idle.html", 1);
            String scanToExpire = scanId;
            await().atMost(Duration.ofSeconds(100)).pollInterval(Duration.ofSeconds(1))
                    .until(() -> clientSpiderService.getClientSpiderProgressPercent(scanToExpire) == 100);
            ApiResponseSet statistics = (ApiResponseSet) clientApi.stats.stats(durationStatistic);
            String expirations = statistics.getStringValue(durationStatistic);
            assertTrue(expirations != null && Long.parseLong(expirations) > 0,
                    "The idle crawl must finish because ZAP enforced its duration, without new-node activity");
        } finally {
            try {
                if (scanId != null) {
                    clientSpiderService.stopClientSpiderJob(scanId);
                }
            } finally {
                clientApi.callApi("clientSpider", "action", "setOptionInitialLoadTimeInSecs",
                        Map.of("Integer", previousInitialLoadTime));
                clientApi.callApi("clientSpider", "action", "setOptionPageLoadTimeInSecs",
                        Map.of("Integer", previousPageLoadTime));
            }
        }
    }

    @Test
    void clientSpiderDurationExpiresWithoutChangingAnotherScansLimit() throws Exception {
        String previousPageLoadTime = ((ApiResponseElement) clientApi.callApi(
                "clientSpider", "view", "optionPageLoadTimeInSecs", Map.of())).getValue();
        String durationStatistic = "stats.client.spider.event.max.time";
        String limitedScanId = null;
        String unlimitedScanId = null;
        try {
            clientApi.callApi("clientSpider", "action", "setOptionPageLoadTimeInSecs", Map.of("Integer", "2"));
            clientApi.stats.clearStats(durationStatistic);

            limitedScanId = extractScanId(clientSpiderService.startClientSpider(
                    "http://direct-scan-target/client-duration.html?crawl=limited", 0));

            ScanLimitProperties unlimitedProperties = new ScanLimitProperties();
            unlimitedProperties.setMaxSpiderScanDurationInMins(0);
            ClientSpiderService unlimitedService = new ClientSpiderService(
                    new ZapEngineScanExecution(clientApi), mock(UrlValidationService.class), unlimitedProperties);
            unlimitedScanId = unlimitedService.startClientSpiderJob(
                    "http://direct-scan-target/client-duration.html?crawl=unlimited", 0);

            String scanToExpire = limitedScanId;
            await().atMost(Duration.ofSeconds(100)).pollInterval(Duration.ofSeconds(1))
                    .until(() -> clientSpiderService.getClientSpiderProgressPercent(scanToExpire) == 100);

            ApiResponseSet statistics = (ApiResponseSet) clientApi.stats.stats(durationStatistic);
            String expirations = statistics.getStringValue(durationStatistic);
            assertTrue(expirations != null && Long.parseLong(expirations) > 0,
                    "The limited crawl must finish because ZAP enforced its duration, not because the fixture ended");
            assertTrue(unlimitedService.getClientSpiderProgressPercent(unlimitedScanId) < 100,
                    "A subsequent unlimited crawl must stay running without removing the first scan's saved limit");
        } finally {
            if (limitedScanId != null) {
                clientSpiderService.stopClientSpiderJob(limitedScanId);
            }
            if (unlimitedScanId != null) {
                clientSpiderService.stopClientSpiderJob(unlimitedScanId);
            }
            clientApi.callApi("clientSpider", "action", "setOptionPageLoadTimeInSecs",
                    Map.of("Integer", previousPageLoadTime));
        }
    }

    @Test
    void directSpiderAndActiveScanToolsWorkAgainstRealZap() throws Exception {
        String spiderStart = spiderScanService.startSpiderScan("http://direct-scan-target/");
        String spiderScanId = extractScanId(spiderStart);
        String spiderStatus = spiderScanService.getSpiderScanStatus(spiderScanId);

        assertTrue(spiderStart.contains("Direct spider scan started."));
        assertTrue(spiderStatus.contains("Scan ID: " + spiderScanId));

        clientApi.core.accessUrl("http://direct-scan-target/", "true");
        String activeStart = activeScanService.startActiveScan("http://direct-scan-target/", "true", null);
        String activeScanId = extractScanId(activeStart);
        String activeStatus = activeScanService.getActiveScanStatus(activeScanId);

        assertTrue(activeStart.contains("Direct active scan started."));
        assertTrue(activeStatus.contains("Scan ID: " + activeScanId));

        String activeStop = activeScanService.stopActiveScan(activeScanId);
        String spiderStop = spiderScanService.stopSpiderScan(spiderScanId);

        assertTrue(activeStop.contains("Direct active scan stopped."));
        assertTrue(spiderStop.contains("Direct spider scan stopped."));
    }

    private static String extractScanId(String response) {
        Matcher matcher = SCAN_ID_PATTERN.matcher(response);
        if (!matcher.find()) {
            throw new IllegalStateException("Scan ID not found in response: " + response);
        }
        return matcher.group(1).trim();
    }
}
