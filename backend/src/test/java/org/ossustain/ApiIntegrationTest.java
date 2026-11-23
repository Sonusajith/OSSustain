package org.ossustain;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpHeaders;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.net.URI;
import java.net.CookieManager;
import java.net.CookiePolicy;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import static org.assertj.core.api.Assertions.assertThat;

@Testcontainers
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class ApiIntegrationTest {
    @Container
    static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>("postgres:16.15")
            .withDatabaseName("ossustain")
            .withUsername("ossustain")
            .withPassword("test-password");

    @DynamicPropertySource
    static void configureDatabase(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", POSTGRES::getUsername);
        registry.add("spring.datasource.password", POSTGRES::getPassword);
        registry.add("ossustain.security.bootstrap-admin-username", () -> "phase17admin");
        registry.add("ossustain.security.bootstrap-admin-password", () -> "test-bootstrap-password-2026");
    }

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @LocalServerPort
    private int port;

    private long alphaId;
    private long betaId;
    private final CookieManager cookies = new CookieManager(null, CookiePolicy.ACCEPT_ORIGINAL_SERVER);
    private final HttpClient client = HttpClient.newBuilder().cookieHandler(cookies).build();

    @BeforeEach
    void seedResearchData() {
        jdbcTemplate.update("TRUNCATE TABLE analysis_jobs, on_demand_api_requests CASCADE");
        jdbcTemplate.update("TRUNCATE TABLE repositories, cohorts, dataset_versions, model_runs "
                + "RESTART IDENTITY CASCADE");
        alphaId = insertRepository(9001, "test/alpha", "small", 75);
        betaId = insertRepository(9002, "test/beta", "large", 250);

        long cohortId = jdbcTemplate.queryForObject(
                """
                INSERT INTO cohorts (name, selection_date, config_hash, criteria)
                VALUES ('api-test', DATE '2024-01-01', ?, '{}'::jsonb) RETURNING id
                """,
                Long.class, "a".repeat(64));
        jdbcTemplate.update("INSERT INTO cohort_memberships (cohort_id, repository_id, stratum, inclusion_notes) "
                + "VALUES (?, ?, 'small', 'test fixture'), (?, ?, 'large', 'test fixture')",
                cohortId, alphaId, cohortId, betaId);

        long datasetId = jdbcTemplate.queryForObject(
                """
                INSERT INTO dataset_versions
                    (version_hash, cohort_name, config, source_hash, code_revision, summary)
                VALUES (?, 'api-test', ?::jsonb, ?, 'api-test-revision', ?::jsonb) RETURNING id
                """,
                Long.class, "b".repeat(64),
                """
                {"experiment":{"protocol_version":"1.0.0","label":{"theta":0.5,"min_reference_commits":20},"splits":{"train":{"start":"2022-01-01","end":"2022-12-31"},"validation":{"start":"2023-01-01","end":"2023-12-31"},"test":{"start":"2024-01-01","end":"2024-12-31"}}}}
                """,
                "c".repeat(64),
                """
                {"overall":{"repositories":2,"snapshots":1},"quality_flags":[{"github_id":9001,"full_name":"test/alpha","flags":["fixture_flag"]}]}
                """
        );

        long snapshotId = jdbcTemplate.queryForObject(
                """
                INSERT INTO snapshots
                    (dataset_version_id, repo_id, prediction_date, reference_start, future_end,
                     observed_until, reference_activity, future_activity, label, label_status, split)
                VALUES (?, ?, DATE '2024-01-01', DATE '2023-10-03', DATE '2024-03-31',
                        DATE '2024-06-01', 30, 15, FALSE, 'labeled', 'test') RETURNING id
                """,
                Long.class, datasetId, alphaId);

        long featureSetId = jdbcTemplate.queryForObject(
                """
                INSERT INTO feature_sets
                    (dataset_version_id, feature_set_hash, code_revision, config, summary)
                VALUES (?, ?, 'feature-test', '{}'::jsonb, '{}'::jsonb) RETURNING id
                """,
                Long.class, datasetId, "d".repeat(64));
        jdbcTemplate.update(
                """
                INSERT INTO feature_definitions
                    (feature_set_id, feature_name, feature_group, description, time_window, missing_policy)
                VALUES (?, 'commits_90d', 'activity', 'Commits in the prior 90 days.',
                        '[t-90d,t)', 'zero when complete')
                """,
                featureSetId);
        jdbcTemplate.update(
                """
                INSERT INTO snapshot_features
                    (snapshot_id, dataset_version_id, feature_set_id, features, missing_flags)
                VALUES (?, ?, ?, '{"commits_90d":30}'::jsonb, '{"commits_90d":false}'::jsonb)
                """,
                snapshotId, datasetId, featureSetId);
        jdbcTemplate.update(
                """
                INSERT INTO repository_metrics_monthly
                    (snapshot_id, feature_set_id, prediction_date, metrics, completeness)
                VALUES (?, ?, DATE '2024-01-01', '{"commits_90d":30}'::jsonb,
                        '{"commits_90d":{"rate":0}}'::jsonb)
                """,
                snapshotId, featureSetId);

        long modelId = jdbcTemplate.queryForObject(
                """
                INSERT INTO model_versions
                    (dataset_version_id, feature_set_id, feature_set_name, algorithm, params,
                     params_hash, seed, label_config, training_config, code_revision,
                     validation_threshold, is_selected)
                VALUES (?, ?, 'activity_only', 'logistic_regression', '{}'::jsonb, ?, 42,
                        '{"theta":0.5}'::jsonb, '{}'::jsonb, 'api-test-revision', 0.5, TRUE)
                RETURNING id
                """,
                Long.class, datasetId, featureSetId, "e".repeat(64));
        jdbcTemplate.update(
                """
                INSERT INTO evaluation_results (model_version_id, split, stratum, metric, value, details)
                VALUES (?, 'test', 'overall', 'pr_auc', 0.75, '{"n_snapshots":1}'::jsonb)
                """,
                modelId);
        jdbcTemplate.update(
                """
                INSERT INTO feature_importances (model_version_id, method, feature_name, value, rank)
                VALUES (?, 'standardized_coefficient', 'commits_90d', -0.25, 1)
                """,
                modelId);
        long predictionId = jdbcTemplate.queryForObject(
                """
                INSERT INTO predictions
                    (model_version_id, snapshot_id, dataset_version_id, risk_score, risk_level,
                     prediction_date, limitation_flags)
                VALUES (?, ?, ?, 0.75, 'high', DATE '2024-01-01', '["low_activity"]'::jsonb)
                RETURNING id
                """,
                Long.class, modelId, snapshotId, datasetId);
        jdbcTemplate.update(
                """
                INSERT INTO prediction_outcomes
                    (model_version_id, dataset_version_id, repo_id, snapshot_id, prediction_id, status)
                VALUES (?, ?, ?, ?, ?, 'predicted')
                """,
                modelId, datasetId, alphaId, snapshotId, predictionId);
        jdbcTemplate.update(
                """
                INSERT INTO prediction_explanations
                    (prediction_id, feature_name, feature_value, reference_value, probability_delta,
                     direction, rank, description)
                VALUES (?, 'commits_90d', 30, 25, 0.12, 'increases_risk', 1,
                        'Associated with a higher score, not a cause.')
                """,
                predictionId);
    }

    @Test
    void analysisSubmissionIsBoundedDurableAndReadable() throws Exception {
        loginAsAdmin();
        HttpResponse<String> invalid = post("/api/v1/analyses", "{\"repository\":\"https://github.com/acme/repo\"}");
        assertThat(invalid.statusCode()).isEqualTo(400);
        assertThat(invalid.body()).contains("invalid_repository");

        HttpResponse<String> accepted = post("/api/v1/analyses", "{\"repository\":\"Acme/PublicRepo\"}");
        assertThat(accepted.statusCode()).as(accepted.body()).isEqualTo(202);
        assertThat(accepted.body()).contains("\"repository\":\"acme/publicrepo\"", "\"status\":\"queued\"");
        String id = accepted.body().replaceAll(".*\\\"id\\\":\\\"([^\\\"]+)\\\".*", "$1");

        HttpResponse<String> duplicate = post("/api/v1/analyses", "{\"repository\":\"acme/publicrepo\"}");
        assertThat(duplicate.statusCode()).isEqualTo(202);
        assertThat(duplicate.body()).contains(id);
        assertThat(post("/api/v1/analyses", "{\"repository\":\"acme/secondpublic\"}").statusCode())
                .isEqualTo(202);
        assertThat(post("/api/v1/analyses", "{\"repository\":\"acme/thirdpublic\"}").statusCode())
                .isEqualTo(202);
        HttpResponse<String> limited = post("/api/v1/analyses", "{\"repository\":\"acme/fourthpublic\"}");
        assertThat(limited.statusCode()).isEqualTo(429);
        assertThat(limited.body()).contains("submission_limit");
        HttpResponse<String> status = get("/api/v1/analyses/" + id);
        assertThat(status.statusCode()).isEqualTo(200);
        assertThat(status.body()).contains("\"status\":\"queued\"");
    }

    @Test
    void analysisRequiresAuthenticationWhileResearchReadsRemainPublic() throws Exception {
        assertThat(get("/api/v1/repositories?page=0&pageSize=1").statusCode()).isEqualTo(200);
        assertThat(get("/api/v1/analyses/00000000-0000-0000-0000-000000000001").statusCode())
                .isEqualTo(401);
        assertThat(post("/api/v1/analyses", "{\"repository\":\"acme/publicrepo\"}").statusCode())
                .isEqualTo(401);
        assertThat(get("/api/v1/admin/users").statusCode()).isEqualTo(401);
    }

    @Test
    void administratorCanCreateResearcherAndDisableIsAudited() throws Exception {
        loginAsAdmin();
        HttpResponse<String> created = post("/api/v1/admin/users",
                "{\"username\":\"researcher-one\",\"role\":\"RESEARCHER\"}");
        assertThat(created.statusCode()).isEqualTo(201);
        assertThat(created.body()).contains("researcher-one", "RESEARCHER", "temporaryPassword");
        Matcher idMatcher = Pattern.compile("\\\"id\\\":(\\d+)").matcher(created.body());
        assertThat(idMatcher.find()).isTrue();
        long userId = Long.parseLong(idMatcher.group(1));
        CookieManager researcherCookies = new CookieManager(null, CookiePolicy.ACCEPT_ORIGINAL_SERVER);
        HttpClient researcherClient = HttpClient.newBuilder().cookieHandler(researcherCookies).build();
        loginAs(researcherClient, "researcher-one", temporaryPassword(created.body()));

        HttpResponse<String> users = get("/api/v1/admin/users?page=0&pageSize=10");
        assertThat(users.statusCode()).isEqualTo(200);
        assertThat(users.body()).contains("researcher-one", "phase17admin");

        HttpResponse<String> disabled = patch("/api/v1/admin/users/" + userId + "/enabled",
                "{\"enabled\":false}");
        assertThat(disabled.statusCode()).isEqualTo(200);
        assertThat(disabled.body()).contains("\"enabled\":false");
        assertThat(get(researcherClient, "/api/v1/auth/me").statusCode()).isEqualTo(401);
        assertThat(jdbcTemplate.queryForObject(
                "SELECT count(*) FROM admin_audit_events WHERE target_id = ? AND action = 'user_disabled'",
                Integer.class, Long.toString(userId))).isEqualTo(1);

        HttpResponse<String> lastAdmin = patch("/api/v1/admin/users/" +
                jdbcTemplate.queryForObject("SELECT id FROM app_users WHERE username = 'phase17admin'", Long.class) +
                "/enabled", "{\"enabled\":false}");
        assertThat(lastAdmin.statusCode()).isEqualTo(409);
        assertThat(lastAdmin.body()).contains("last_admin");
    }

    @Test
    void analysisJobsArePrivateToTheirOwnerAndAdministratorsCanCancelThem() throws Exception {
        loginAsAdmin();
        HttpResponse<String> firstCreated = post("/api/v1/admin/users",
                "{\"username\":\"owner-one\",\"role\":\"RESEARCHER\"}");
        assertThat(firstCreated.statusCode()).isEqualTo(201);
        String firstPassword = temporaryPassword(firstCreated.body());
        CookieManager firstCookies = new CookieManager(null, CookiePolicy.ACCEPT_ORIGINAL_SERVER);
        HttpClient firstClient = HttpClient.newBuilder().cookieHandler(firstCookies).build();
        loginAs(firstClient, "owner-one", firstPassword);

        HttpResponse<String> csrfRejected = sendPost(firstClient, "/api/v1/analyses",
                "{\"repository\":\"acme/owner-private\"}", "");
        assertThat(csrfRejected.statusCode()).isEqualTo(403);
        assertThat(get(firstClient, "/api/v1/admin/users").statusCode()).isEqualTo(403);
        HttpResponse<String> submitted = sendPost(firstClient, "/api/v1/analyses",
                "{\"repository\":\"acme/owner-private\"}", csrfToken(firstClient));
        assertThat(submitted.statusCode()).as(submitted.body()).isEqualTo(202);
        String jobId = analysisId(submitted.body());
        assertThat(get(firstClient, "/api/v1/analyses/" + jobId).statusCode()).isEqualTo(200);

        HttpResponse<String> secondCreated = post("/api/v1/admin/users",
                "{\"username\":\"owner-two\",\"role\":\"RESEARCHER\"}");
        assertThat(secondCreated.statusCode()).isEqualTo(201);
        CookieManager secondCookies = new CookieManager(null, CookiePolicy.ACCEPT_ORIGINAL_SERVER);
        HttpClient secondClient = HttpClient.newBuilder().cookieHandler(secondCookies).build();
        loginAs(secondClient, "owner-two", temporaryPassword(secondCreated.body()));
        HttpResponse<String> hidden = get(secondClient, "/api/v1/analyses/" + jobId);
        assertThat(hidden.statusCode()).isEqualTo(404);
        assertThat(hidden.body()).contains("analysis_not_found");

        HttpResponse<String> cancelled = post("/api/v1/admin/analyses/" + jobId + "/cancel", "{}");
        assertThat(cancelled.statusCode()).isEqualTo(200);
        assertThat(cancelled.body()).contains("\"status\":\"failed\"", "cancelled_by_admin");
        assertThat(jdbcTemplate.queryForObject(
                "SELECT count(*) FROM admin_audit_events WHERE target_id = ? AND action = 'analysis_cancelled'",
                Integer.class, jobId)).isEqualTo(1);
    }

    @Test
    void loginRejectsInvalidCredentialsAndLogoutInvalidatesTheSession() throws Exception {
        CookieManager unauthenticatedCookies = new CookieManager(null, CookiePolicy.ACCEPT_ORIGINAL_SERVER);
        HttpClient unauthenticatedClient = HttpClient.newBuilder().cookieHandler(unauthenticatedCookies).build();
        HttpResponse<String> denied = sendPost(unauthenticatedClient, "/api/v1/auth/login",
                "{\"username\":\"missing-user\",\"password\":\"wrong-password\"}",
                csrfToken(unauthenticatedClient));
        assertThat(denied.statusCode()).isEqualTo(401);
        assertThat(denied.body()).contains("invalid_credentials");

        loginAsAdmin();
        assertThat(post("/api/v1/auth/logout", "{}").statusCode()).isEqualTo(204);
        assertThat(get("/api/v1/auth/me").statusCode()).isEqualTo(401);
    }

    @Test
    void repositoryEndpointsReturnStoredDataAndSupportFiltersAndPagination() throws Exception {
        HttpResponse<String> response = get("/api/v1/repositories?risk=high&sizeGroup=small&q=alpha&page=0&pageSize=1");
        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.body()).contains("\"totalElements\":1", "test/alpha", "fixture_flag", "\"latestRiskCategory\":\"high\"");

        response = get("/api/v1/repositories/" + alphaId);
        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.body()).contains("\"githubId\":9001", "test/alpha");

        response = get("/api/v1/repositories?page=10&pageSize=1");
        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.body()).contains("\"content\":[]");
    }

    @Test
    void repositoryAnalyticsEndpointsReturnMetricsHistoryAndLatestIndicators() throws Exception {
        HttpResponse<String> response = get("/api/v1/repositories/" + alphaId + "/metrics");
        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.body()).contains("\"commits_90d\":30");

        response = get("/api/v1/repositories/" + alphaId + "/predictions");
        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.body()).contains("\"modelVersionId\"", "b".repeat(64));

        response = get("/api/v1/repositories/" + alphaId + "/predictions/latest");
        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.body()).contains("\"riskCategory\":\"high\"", "low_activity",
                "increases_risk", "\"method\":\"local_substitution\"");
    }

    @Test
    void comparisonEndpointReturnsSelectedCohortRepositoriesInRequestOrder() throws Exception {
        HttpResponse<String> response = get("/api/v1/compare?ids=" + betaId + "," + alphaId);
        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.body()).contains("test/beta", "test/alpha", "\"commits_90d\":30",
                "\"latestRiskCategory\":\"high\"");
        assertThat(response.body().indexOf("test/beta"))
                .isLessThan(response.body().indexOf("test/alpha"));

        response = get("/api/v1/compare?ids=" + alphaId);
        assertThat(response.statusCode()).isEqualTo(400);
        assertThat(response.body()).contains("invalid_parameter");

        response = get("/api/v1/compare?ids=" + alphaId + "," + betaId + "," + alphaId + "," + betaId + "," + alphaId);
        assertThat(response.statusCode()).isEqualTo(400);
        assertThat(response.body()).contains("between 2 and 4");

        response = get("/api/v1/compare?ids=" + alphaId + "," + alphaId);
        assertThat(response.statusCode()).isEqualTo(400);
        assertThat(response.body()).contains("unique");

        response = get("/api/v1/compare?ids=" + alphaId + ",999999");
        assertThat(response.statusCode()).isEqualTo(404);
        assertThat(response.body()).contains("repository_not_found");
    }

    @Test
    void researchEndpointsReturnModelsEvaluationsImportanceAndVersionedDefinitions() throws Exception {
        HttpResponse<String> response = get("/api/v1/research/models");
        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.body()).contains("logistic_regression");

        response = get("/api/v1/research/evaluations?split=test&featureSet=activity_only&stratum=overall");
        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.body()).contains("pr_auc", "n_snapshots");

        response = get("/api/v1/research/feature-importance");
        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.body()).contains("commits_90d", "standardized_coefficient");

        response = get("/api/v1/research/dataset-summary");
        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.body()).contains("\"repositories\":2");

        response = get("/api/v1/research/label-definition");
        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.body()).contains("\"theta\":0.5", "\"featureName\":\"commits_90d\"");
    }

    @Test
    void invalidParametersAndMissingRecordsUseTheSharedErrorShape() throws Exception {
        HttpResponse<String> response = get("/api/v1/repositories?risk=critical");
        assertThat(response.statusCode()).isEqualTo(400);
        assertThat(response.body()).contains("\"code\":\"invalid_parameter\"", "\"path\":\"/api/v1/repositories\"");

        response = get("/api/v1/repositories?pageSize=500");
        assertThat(response.statusCode()).isEqualTo(400);
        assertThat(response.body()).contains("\"status\":400");

        response = get("/api/v1/repositories?sort=riskCategory&direction=asc&pageSize=2");
        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.body().indexOf("\"fullName\":\"test/beta\""))
                .isLessThan(response.body().indexOf("\"fullName\":\"test/alpha\""));

        response = get("/api/v1/repositories/999999");
        assertThat(response.statusCode()).isEqualTo(404);
        assertThat(response.body()).contains("repository_not_found");

        response = get("/api/v1/repositories/" + betaId + "/predictions/latest");
        assertThat(response.statusCode()).isEqualTo(404);
        assertThat(response.body()).contains("prediction_not_found");
    }

    @Test
    void corsIsRestrictedAndOpenApiDocumentIsServed() throws Exception {
        HttpResponse<String> response = get("/api/v1");
        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.body()).contains("OSSustain Read API", "http://localhost:5173",
                "/api/v1/research", "/api/v1/compare", "/openapi.yaml");

        response = options("/api/v1/repositories", "http://localhost:5173");
        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.headers().firstValue(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN))
                .contains("http://localhost:5173");

        response = options("/api/v1/repositories", "https://not-allowed.example");
        assertThat(response.headers().firstValue(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN)).isEmpty();

        response = get("/openapi.yaml");
        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.body()).contains("openapi: 3.1.0", "/research/models", "/compare");
    }

    private HttpResponse<String> get(String path) throws Exception {
        return get(client, path);
    }

    private HttpResponse<String> get(HttpClient httpClient, String path) throws Exception {
        HttpRequest request = HttpRequest.newBuilder(URI.create("http://localhost:" + port + path))
                .GET().build();
        return httpClient.send(request, HttpResponse.BodyHandlers.ofString());
    }

    private HttpResponse<String> post(String path, String body) throws Exception {
        return sendPost(client, path, body, csrfToken(client));
    }

    private HttpResponse<String> patch(String path, String body) throws Exception {
        HttpRequest request = HttpRequest.newBuilder(URI.create("http://localhost:" + port + path))
                .header(HttpHeaders.CONTENT_TYPE, "application/json")
                .header("X-CSRF-TOKEN", csrfToken(client))
                .method("PATCH", HttpRequest.BodyPublishers.ofString(body)).build();
        return client.send(request, HttpResponse.BodyHandlers.ofString());
    }

    private HttpResponse<String> sendPost(HttpClient httpClient, String path, String body, String csrf)
            throws Exception {
        HttpRequest request = HttpRequest.newBuilder(URI.create("http://localhost:" + port + path))
                .header(HttpHeaders.CONTENT_TYPE, "application/json")
                .header("X-CSRF-TOKEN", csrf)
                .POST(HttpRequest.BodyPublishers.ofString(body)).build();
        return httpClient.send(request, HttpResponse.BodyHandlers.ofString());
    }

    private String csrfToken(HttpClient httpClient) throws Exception {
        HttpRequest request = HttpRequest.newBuilder(URI.create("http://localhost:" + port + "/api/v1/auth/csrf"))
                .GET().build();
        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        assertThat(response.statusCode()).isEqualTo(200);
        Matcher matcher = Pattern.compile("\\\"token\\\":\\\"([^\\\"]+)\\\"").matcher(response.body());
        assertThat(matcher.find()).isTrue();
        return matcher.group(1);
    }

    private void loginAsAdmin() throws Exception {
        HttpResponse<String> login = sendPost(client, "/api/v1/auth/login",
                "{\"username\":\"phase17admin\",\"password\":\"test-bootstrap-password-2026\"}",
                csrfToken(client));
        if (login.statusCode() == 401) {
            login = sendPost(client, "/api/v1/auth/login",
                    "{\"username\":\"phase17admin\",\"password\":\"test-research-admin-password-2026\"}",
                    csrfToken(client));
        }
        assertThat(login.statusCode()).isEqualTo(200);
        if (login.body().contains("\"mustChangePassword\":true")) {
            HttpResponse<String> changed = post("/api/v1/auth/password",
                    "{\"currentPassword\":\"test-bootstrap-password-2026\",\"newPassword\":\"test-research-admin-password-2026\"}");
            assertThat(changed.statusCode()).isEqualTo(200);
        }
    }

    private void loginAs(HttpClient httpClient, String username, String password) throws Exception {
        HttpResponse<String> login = sendPost(httpClient, "/api/v1/auth/login",
                "{\"username\":\"" + username + "\",\"password\":\"" + password + "\"}",
                csrfToken(httpClient));
        assertThat(login.statusCode()).as(login.body()).isEqualTo(200);
        assertThat(login.body()).contains("\"mustChangePassword\":true");
        HttpResponse<String> changed = sendPost(httpClient, "/api/v1/auth/password",
                "{\"currentPassword\":\"" + password + "\",\"newPassword\":\"researcher-new-password-2026\"}",
                csrfToken(httpClient));
        assertThat(changed.statusCode()).as(changed.body()).isEqualTo(200);
    }

    private static String temporaryPassword(String responseBody) {
        Matcher matcher = Pattern.compile("\\\"temporaryPassword\\\":\\\"([^\\\"]+)\\\"").matcher(responseBody);
        assertThat(matcher.find()).isTrue();
        return matcher.group(1);
    }

    private static String analysisId(String responseBody) {
        Matcher matcher = Pattern.compile("\\\"id\\\":\\\"([^\\\"]+)\\\"").matcher(responseBody);
        assertThat(matcher.find()).isTrue();
        return matcher.group(1);
    }

    private HttpResponse<String> options(String path, String origin) throws Exception {
        HttpRequest request = HttpRequest.newBuilder(URI.create("http://localhost:" + port + path))
                .header(HttpHeaders.ORIGIN, origin)
                .header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "GET")
                .method("OPTIONS", HttpRequest.BodyPublishers.noBody())
                .build();
        return client.send(request, HttpResponse.BodyHandlers.ofString());
    }

    private long insertRepository(long githubId, String fullName, String sizeGroup, int stars) {
        return jdbcTemplate.queryForObject(
                """
                INSERT INTO repositories
                    (github_id, full_name, default_branch, created_at, stars_at_selection,
                     size_group, selected_at, metadata)
                VALUES (?, ?, 'main', TIMESTAMPTZ '2020-01-01 00:00:00Z', ?, ?,
                        TIMESTAMPTZ '2024-01-01 00:00:00Z', '{}'::jsonb) RETURNING id
                """,
                Long.class, githubId, fullName, stars, sizeGroup);
    }
}
