package org.ossustain;

import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.HashSet;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@Testcontainers
class CoreSchemaIntegrationTest {
    @Container
    static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>("postgres:16.15")
            .withDatabaseName("ossustain")
            .withUsername("ossustain")
            .withPassword("test-password");

    private Connection connection;

    @BeforeAll
    static void migrateEmptyDatabase() {
        Flyway.configure()
                .dataSource(POSTGRES.getJdbcUrl(), POSTGRES.getUsername(), POSTGRES.getPassword())
                .locations("classpath:db/migration")
                .load()
                .migrate();
    }

    @BeforeEach
    void connectAndClear() throws SQLException {
        connection = DriverManager.getConnection(
                POSTGRES.getJdbcUrl(), POSTGRES.getUsername(), POSTGRES.getPassword());
        try (Statement statement = connection.createStatement()) {
            statement.execute("TRUNCATE TABLE risk_indicators, predictions, model_runs, labels, "
                    + "repo_windows, collection_progress, reviews, pull_requests, issues, commits, "
                    + "contributors, repositories RESTART IDENTITY CASCADE");
        }
    }

    @AfterEach
    void closeConnection() throws SQLException {
        connection.close();
    }

    @Test
    void migrationsApplyToAnEmptyPostgres16Database() throws SQLException {
        assertThat(queryStrings("SELECT version FROM flyway_schema_history "
                + "WHERE success ORDER BY installed_rank"))
                .containsExactlyInAnyOrder("1", "2", "3");
    }

    @Test
    void everyCoreTableViewAndRequiredIndexExists() throws SQLException {
        Set<String> tables = new HashSet<>(queryStrings(
                "SELECT table_name FROM information_schema.tables "
                        + "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"));
        assertThat(tables).contains("repositories", "contributors", "commits", "issues",
                "pull_requests", "reviews", "collection_progress", "repo_windows", "labels",
                "model_runs", "predictions", "risk_indicators");

        assertThat(queryStrings("SELECT table_name FROM information_schema.views "
                + "WHERE table_schema = 'public'"))
                .contains("v_repo_latest_risk");

        assertThat(queryStrings("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"))
                .contains("uq_repo_windows_repo_end", "idx_issues_repo_created_at",
                        "idx_pull_requests_repo_created_at", "idx_commits_repo_committed_at",
                        "idx_predictions_window_id", "uq_risk_indicators_prediction_rank");
    }

    @Test
    void uniqueConstraintsRejectDuplicateRows() throws SQLException {
        long repositoryId = insertRepository(101, "sample/unique-check");
        long contributorId = insertContributor("a".repeat(64));
        assertSqlState("INSERT INTO contributors (contributor_key, first_seen_at) "
                + "VALUES ('" + "a".repeat(64) + "', now())", "23505");

        execute("INSERT INTO commits (repo_id, contributor_id, sha, committed_at) "
                + "VALUES (" + repositoryId + ", " + contributorId + ", 'commit-1', now())");
        assertSqlState("INSERT INTO commits (repo_id, contributor_id, sha, committed_at) "
                + "VALUES (" + repositoryId + ", " + contributorId + ", 'commit-1', now())", "23505");

        execute("INSERT INTO issues (repo_id, github_number, created_at) VALUES ("
                + repositoryId + ", 1, TIMESTAMPTZ '2024-01-01 00:00:00+00')");
        assertSqlState("INSERT INTO issues (repo_id, github_number, created_at) VALUES ("
                + repositoryId + ", 1, TIMESTAMPTZ '2024-01-01 00:00:00+00')", "23505");

        execute("INSERT INTO pull_requests (repo_id, github_number, state, created_at) VALUES ("
                + repositoryId + ", 1, 'open', TIMESTAMPTZ '2024-01-01 00:00:00+00')");
        assertSqlState("INSERT INTO pull_requests (repo_id, github_number, state, created_at) VALUES ("
                + repositoryId + ", 1, 'open', TIMESTAMPTZ '2024-01-01 00:00:00+00')", "23505");

        execute("INSERT INTO collection_progress (repo_id, resource_type, status) VALUES ("
                + repositoryId + ", 'commits', 'pending')");
        assertSqlState("INSERT INTO collection_progress (repo_id, resource_type, status) VALUES ("
                + repositoryId + ", 'commits', 'running')", "23505");

        long windowId = insertWindow(repositoryId, "2024-01-01T00:00:00Z", "2024-02-01T00:00:00Z");
        assertSqlState("INSERT INTO repo_windows (repo_id, window_start, window_end) VALUES ("
                + repositoryId + ", TIMESTAMPTZ '2024-01-10 00:00:00+00', "
                + "TIMESTAMPTZ '2024-02-01 00:00:00+00')", "23505");

        execute("INSERT INTO labels (window_id, horizon_days, future_activity_score, decline_ratio, "
                + "is_decline, label_version) VALUES (" + windowId + ", 90, 1, 0.5, TRUE, 'v1')");
        assertSqlState("INSERT INTO labels (window_id, horizon_days, future_activity_score, decline_ratio, "
                + "is_decline, label_version) VALUES (" + windowId + ", 90, 1, 0.5, TRUE, 'v2')", "23505");

        long modelRunId = insertModelRun("baseline", "unique-v1", true);
        assertSqlState("INSERT INTO model_runs (model_name, model_version, train_start, train_end, "
                + "test_start, test_end) VALUES ('baseline', 'unique-v1', "
                + "TIMESTAMPTZ '2020-01-01 00:00:00+00', TIMESTAMPTZ '2020-12-31 00:00:00+00', "
                + "TIMESTAMPTZ '2021-01-01 00:00:00+00', TIMESTAMPTZ '2021-12-31 00:00:00+00')",
                "23505");
        assertSqlState("INSERT INTO model_runs (model_name, model_version, train_start, train_end, "
                + "test_start, test_end, is_primary) VALUES ('random_forest', 'second-primary', "
                + "TIMESTAMPTZ '2020-01-01 00:00:00+00', TIMESTAMPTZ '2020-12-31 00:00:00+00', "
                + "TIMESTAMPTZ '2021-01-01 00:00:00+00', TIMESTAMPTZ '2021-12-31 00:00:00+00', TRUE)",
                "23505");

        long predictionId = insertPrediction(modelRunId, windowId, "0.5000", "medium");
        assertSqlState("INSERT INTO predictions (model_run_id, window_id, risk_score, risk_level) "
                + "VALUES (" + modelRunId + ", " + windowId + ", 0.5, 'medium')", "23505");

        execute("INSERT INTO risk_indicators (prediction_id, feature_name, direction, weight, rank, "
                + "description) VALUES (" + predictionId + ", 'activity_score', 'increases_risk', "
                + "0.5, 1, 'Higher activity score')");
        assertSqlState("INSERT INTO risk_indicators (prediction_id, feature_name, direction, weight, rank, "
                + "description) VALUES (" + predictionId + ", 'activity_score', 'increases_risk', "
                + "0.4, 1, 'Duplicate rank')", "23505");
    }

    @Test
    void foreignKeysAndRiskChecksRejectInvalidValues() throws SQLException {
        assertSqlState("INSERT INTO commits (repo_id, sha, committed_at) "
                + "VALUES (999999, 'orphan', now())", "23503");
        assertSqlState("INSERT INTO reviews (pull_request_id, state) VALUES (999999, 'approved')", "23503");

        long repositoryId = insertRepository(102, "sample/checks");
        long windowId = insertWindow(repositoryId, "2024-01-01T00:00:00Z", "2024-02-01T00:00:00Z");
        long modelRunId = insertModelRun("baseline", "check-v1", true);
        assertSqlState("INSERT INTO predictions (model_run_id, window_id, risk_score, risk_level) "
                + "VALUES (" + modelRunId + ", " + windowId + ", 1.0001, 'high')", "23514");
        assertSqlState("INSERT INTO predictions (model_run_id, window_id, risk_score, risk_level) "
                + "VALUES (" + modelRunId + ", " + windowId + ", 0.5, 'critical')", "23514");
        assertSqlState("INSERT INTO repo_windows (repo_id, window_start, window_end) VALUES ("
                + repositoryId + ", TIMESTAMPTZ '2024-02-01 00:00:00+00', "
                + "TIMESTAMPTZ '2024-01-01 00:00:00+00')", "23514");
        assertSqlState("INSERT INTO model_runs (model_name, model_version, train_start, train_end, "
                + "test_start, test_end) VALUES ('random_forest', 'bad-split', "
                + "TIMESTAMPTZ '2020-01-01 00:00:00+00', TIMESTAMPTZ '2021-02-01 00:00:00+00', "
                + "TIMESTAMPTZ '2021-01-01 00:00:00+00', TIMESTAMPTZ '2021-12-31 00:00:00+00')",
                "23514");
    }

    @Test
    void latestRiskViewUsesOnlyThePrimaryModelsNewestWindow() throws SQLException {
        long repositoryId = insertRepository(103, "sample/view-check");
        long primaryRunId = insertModelRun("baseline", "primary-v1", true);
        long otherRunId = insertModelRun("random_forest", "other-v1", false);

        long januaryWindow = insertWindow(repositoryId, "2024-01-01T00:00:00Z", "2024-02-01T00:00:00Z");
        long februaryWindow = insertWindow(repositoryId, "2024-02-01T00:00:00Z", "2024-03-01T00:00:00Z");
        long marchWindow = insertWindow(repositoryId, "2024-03-01T00:00:00Z", "2024-04-01T00:00:00Z");
        insertPrediction(primaryRunId, januaryWindow, "0.2000", "low");
        insertPrediction(primaryRunId, februaryWindow, "0.6000", "medium");
        insertPrediction(otherRunId, marchWindow, "0.9000", "high");

        try (Statement statement = connection.createStatement();
             ResultSet result = statement.executeQuery("SELECT repo_id, full_name, window_end, risk_score, "
                     + "risk_level FROM v_repo_latest_risk WHERE repo_id = " + repositoryId)) {
            assertThat(result.next()).isTrue();
            assertThat(result.getLong("repo_id")).isEqualTo(repositoryId);
            assertThat(result.getString("full_name")).isEqualTo("sample/view-check");
            assertThat(result.getTimestamp("window_end").toInstant())
                    .isEqualTo(Instant.parse("2024-03-01T00:00:00Z"));
            assertThat(result.getBigDecimal("risk_score").toPlainString()).isEqualTo("0.6000");
            assertThat(result.getString("risk_level")).isEqualTo("medium");
            assertThat(result.next()).isFalse();
        }
    }

    private long insertRepository(long githubId, String fullName) throws SQLException {
        String sql = "INSERT INTO repositories (github_id, full_name, created_at, stars_at_selection, "
                + "size_group, selected_at) VALUES (?, ?, ?, 10, 'small', ?) RETURNING id";
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            Timestamp timestamp = Timestamp.from(Instant.parse("2020-01-01T00:00:00Z"));
            statement.setLong(1, githubId);
            statement.setString(2, fullName);
            statement.setTimestamp(3, timestamp);
            statement.setTimestamp(4, timestamp);
            try (ResultSet result = statement.executeQuery()) {
                result.next();
                return result.getLong(1);
            }
        }
    }

    private long insertContributor(String key) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(
                "INSERT INTO contributors (contributor_key, first_seen_at) VALUES (?, now()) RETURNING id")) {
            statement.setString(1, key);
            try (ResultSet result = statement.executeQuery()) {
                result.next();
                return result.getLong(1);
            }
        }
    }

    private long insertWindow(long repositoryId, String start, String end) throws SQLException {
        String sql = "INSERT INTO repo_windows (repo_id, window_start, window_end) "
                + "VALUES (?, ?, ?) RETURNING id";
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setLong(1, repositoryId);
            statement.setTimestamp(2, Timestamp.from(Instant.parse(start)));
            statement.setTimestamp(3, Timestamp.from(Instant.parse(end)));
            try (ResultSet result = statement.executeQuery()) {
                result.next();
                return result.getLong(1);
            }
        }
    }

    private long insertModelRun(String modelName, String version, boolean primary) throws SQLException {
        String sql = "INSERT INTO model_runs (model_name, model_version, train_start, train_end, "
                + "test_start, test_end, is_primary) VALUES (?, ?, "
                + "TIMESTAMPTZ '2020-01-01 00:00:00+00', TIMESTAMPTZ '2020-12-31 00:00:00+00', "
                + "TIMESTAMPTZ '2021-01-01 00:00:00+00', TIMESTAMPTZ '2021-12-31 00:00:00+00', ?) "
                + "RETURNING id";
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setString(1, modelName);
            statement.setString(2, version);
            statement.setBoolean(3, primary);
            try (ResultSet result = statement.executeQuery()) {
                result.next();
                return result.getLong(1);
            }
        }
    }

    private long insertPrediction(long modelRunId, long windowId, String score, String level)
            throws SQLException {
        String sql = "INSERT INTO predictions (model_run_id, window_id, risk_score, risk_level) "
                + "VALUES (?, ?, ?, ?) RETURNING id";
        try (PreparedStatement statement = connection.prepareStatement(sql)) {
            statement.setLong(1, modelRunId);
            statement.setLong(2, windowId);
            statement.setBigDecimal(3, new java.math.BigDecimal(score));
            statement.setString(4, level);
            try (ResultSet result = statement.executeQuery()) {
                result.next();
                return result.getLong(1);
            }
        }
    }

    private void assertSqlState(String sql, String expectedState) {
        assertThatThrownBy(() -> execute(sql))
                .isInstanceOf(SQLException.class)
                .satisfies(exception -> assertThat(((SQLException) exception).getSQLState())
                        .isEqualTo(expectedState));
    }

    private void execute(String sql) throws SQLException {
        try (Statement statement = connection.createStatement()) {
            statement.execute(sql);
        }
    }

    private Set<String> queryStrings(String sql) throws SQLException {
        Set<String> values = new HashSet<>();
        try (Statement statement = connection.createStatement(); ResultSet result = statement.executeQuery(sql)) {
            while (result.next()) {
                values.add(result.getString(1));
            }
        }
        return values;
    }
}
