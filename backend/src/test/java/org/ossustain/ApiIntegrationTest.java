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
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

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
    }

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @LocalServerPort
    private int port;

    private long alphaId;
    private long betaId;

    @BeforeEach
    void seedResearchData() {
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
        assertThat(response.body()).contains("\"riskCategory\":\"high\"", "low_activity", "increases_risk");
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
        HttpRequest request = HttpRequest.newBuilder(URI.create("http://localhost:" + port + path))
                .GET().build();
        return HttpClient.newHttpClient().send(request, HttpResponse.BodyHandlers.ofString());
    }

    private HttpResponse<String> options(String path, String origin) throws Exception {
        HttpRequest request = HttpRequest.newBuilder(URI.create("http://localhost:" + port + path))
                .header(HttpHeaders.ORIGIN, origin)
                .header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "GET")
                .method("OPTIONS", HttpRequest.BodyPublishers.noBody())
                .build();
        return HttpClient.newHttpClient().send(request, HttpResponse.BodyHandlers.ofString());
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
