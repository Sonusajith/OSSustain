package org.ossustain.api.repository;

import org.ossustain.api.ApiException;
import org.ossustain.api.JsonSupport;
import org.ossustain.api.dto.MetricPointResponse;
import org.ossustain.api.dto.PredictionDetailResponse;
import org.ossustain.api.dto.PredictionIndicatorResponse;
import org.ossustain.api.dto.PredictionResponse;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class RepositoryAnalyticsReadService {
    private static final String PREDICTION_SELECT = """
            SELECT prediction.id, snapshot.repo_id, snapshot.id AS snapshot_id,
                   prediction.dataset_version_id, dataset.version_hash,
                   model.id AS model_version_id, model.algorithm, model.feature_set_name,
                   prediction.risk_score, prediction.risk_level,
                   COALESCE(prediction.prediction_date, snapshot.prediction_date) AS prediction_date,
                   prediction.limitation_flags::text AS limitation_flags
            FROM predictions prediction
            JOIN snapshots snapshot ON snapshot.id = prediction.snapshot_id
            JOIN model_versions model ON model.id = prediction.model_version_id
            JOIN dataset_versions dataset ON dataset.id = prediction.dataset_version_id
            WHERE prediction.model_version_id IS NOT NULL AND snapshot.repo_id = ?
            """;

    private final JdbcTemplate jdbcTemplate;
    private final JsonSupport jsonSupport;

    public RepositoryAnalyticsReadService(JdbcTemplate jdbcTemplate, JsonSupport jsonSupport) {
        this.jdbcTemplate = jdbcTemplate;
        this.jsonSupport = jsonSupport;
    }

    public List<MetricPointResponse> metrics(long repositoryId) {
        ensureRepository(repositoryId);
        return jdbcTemplate.query(
                """
WITH latest_dataset AS (
                       SELECT id FROM dataset_versions ORDER BY id DESC LIMIT 1
                   ), latest_feature_set AS (
                       SELECT feature_set.id FROM feature_sets feature_set
                       JOIN latest_dataset dataset ON dataset.id = feature_set.dataset_version_id
                       ORDER BY feature_set.id DESC LIMIT 1
                   )
                   SELECT monthly.prediction_date, monthly.metrics::text AS metrics,
                          monthly.completeness::text AS completeness
                   FROM latest_dataset dataset
                   JOIN latest_feature_set feature_set ON TRUE
                   JOIN repository_metrics_monthly monthly
                     ON monthly.feature_set_id = feature_set.id
                   JOIN snapshots snapshot ON snapshot.id = monthly.snapshot_id
                   WHERE snapshot.repo_id = ? AND snapshot.dataset_version_id = dataset.id
                   ORDER BY monthly.prediction_date ASC""",
                (result, rowNumber) -> new MetricPointResponse(
                        result.getObject("prediction_date", java.time.LocalDate.class),
                        jsonSupport.read(result.getString("metrics")),
                        jsonSupport.read(result.getString("completeness"))),
                repositoryId);
    }

    public List<PredictionResponse> history(long repositoryId) {
        ensureRepository(repositoryId);
        return jdbcTemplate.query(
                PREDICTION_SELECT + " ORDER BY prediction_date DESC, prediction.id DESC",
                (result, rowNumber) -> prediction(result), repositoryId);
    }

    public PredictionDetailResponse latest(long repositoryId) {
        ensureRepository(repositoryId);
        List<PredictionResponse> rows = jdbcTemplate.query(
                PREDICTION_SELECT + " ORDER BY prediction_date DESC, prediction.id DESC LIMIT 1",
                (result, rowNumber) -> prediction(result), repositoryId);
        if (rows.isEmpty()) {
            throw new ApiException(HttpStatus.NOT_FOUND, "prediction_not_found",
                    "No prediction is available for this repository.");
        }
        PredictionResponse latest = rows.getFirst();
        List<PredictionIndicatorResponse> indicators = jdbcTemplate.query(
                """
SELECT feature_name, feature_value, reference_value, probability_delta,
                          direction, rank, description
                   FROM prediction_explanations WHERE prediction_id = ? ORDER BY rank""",
                (result, rowNumber) -> new PredictionIndicatorResponse(
                        result.getString("feature_name"), result.getObject("feature_value", Double.class),
                        result.getObject("reference_value", Double.class),
                        result.getDouble("probability_delta"), result.getString("direction"),
                        result.getInt("rank"), result.getString("description")),
                latest.id());
        return new PredictionDetailResponse(latest, indicators);
    }

    private PredictionResponse prediction(java.sql.ResultSet result) throws java.sql.SQLException {
        return new PredictionResponse(
                result.getLong("id"), result.getLong("repo_id"), result.getLong("snapshot_id"),
                result.getLong("dataset_version_id"), result.getString("version_hash"),
                result.getLong("model_version_id"), result.getString("algorithm"),
                result.getString("feature_set_name"), result.getDouble("risk_score"),
                result.getString("risk_level"),
                result.getObject("prediction_date", java.time.LocalDate.class),
                jsonSupport.read(result.getString("limitation_flags")));
    }

    private void ensureRepository(long repositoryId) {
        Integer count = jdbcTemplate.queryForObject(
                "SELECT count(*) FROM repositories WHERE id = ?", Integer.class, repositoryId);
        if (count == null || count == 0) {
            throw new ApiException(HttpStatus.NOT_FOUND, "repository_not_found", "Repository was not found.");
        }
    }
}
