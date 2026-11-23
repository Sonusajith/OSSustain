package org.ossustain.api.repository;

import org.ossustain.api.ApiException;
import org.ossustain.api.JsonSupport;
import org.ossustain.api.dto.MetricPointResponse;
import org.ossustain.api.dto.RepositoryComparisonEntryResponse;
import org.ossustain.api.dto.RepositoryComparisonResponse;
import org.ossustain.api.dto.RepositorySummaryResponse;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.LocalDate;
import java.util.HashSet;
import java.util.List;

@Service
public class RepositoryComparisonReadService {
    private static final int MIN_REPOSITORIES = 2;
    private static final int MAX_REPOSITORIES = 4;

    private final JdbcTemplate jdbcTemplate;
    private final JsonSupport jsonSupport;

    public RepositoryComparisonReadService(JdbcTemplate jdbcTemplate, JsonSupport jsonSupport) {
        this.jdbcTemplate = jdbcTemplate;
        this.jsonSupport = jsonSupport;
    }

    public RepositoryComparisonResponse compare(List<Long> repositoryIds) {
        validate(repositoryIds);

        String idParameters = String.join(",", java.util.Collections.nCopies(repositoryIds.size(), "?"));
        List<RepositoryComparisonEntryResponse> entries = jdbcTemplate.query(
                """
                WITH latest_dataset AS (
                    SELECT id, cohort_name, summary FROM dataset_versions ORDER BY id DESC LIMIT 1
                ), latest_feature_set AS (
                    SELECT feature_set.id FROM feature_sets feature_set
                    JOIN latest_dataset dataset ON dataset.id = feature_set.dataset_version_id
                    ORDER BY feature_set.id DESC LIMIT 1
                )
                SELECT repository.id, repository.full_name, repository.owner, repository.name,
                       repository.size_group, repository.stars_at_selection,
                       COALESCE(quality.flags, '[]'::jsonb)::text AS quality_flags,
                       latest.risk_score AS latest_probability,
                       latest.risk_level AS latest_risk_category,
                       latest.prediction_date,
                       monthly.prediction_date AS metrics_date,
                       monthly.metrics::text AS metrics,
                       monthly.completeness::text AS completeness
                FROM latest_dataset dataset
                JOIN cohorts cohort ON cohort.name = dataset.cohort_name
                JOIN cohort_memberships membership ON membership.cohort_id = cohort.id
                JOIN repositories repository ON repository.id = membership.repository_id
                LEFT JOIN LATERAL (
                    SELECT item.value->'flags' AS flags
                    FROM jsonb_array_elements(COALESCE(dataset.summary->'quality_flags', '[]'::jsonb)) item(value)
                    WHERE item.value->>'github_id' = repository.github_id::text
                    LIMIT 1
                ) quality ON TRUE
                LEFT JOIN LATERAL (
                    SELECT prediction.risk_score, prediction.risk_level,
                           COALESCE(prediction.prediction_date, snapshot.prediction_date) AS prediction_date
                    FROM predictions prediction
                    JOIN snapshots snapshot ON snapshot.id = prediction.snapshot_id
                    WHERE prediction.model_version_id IS NOT NULL
                      AND prediction.dataset_version_id = dataset.id
                      AND snapshot.repo_id = repository.id
                    ORDER BY COALESCE(prediction.prediction_date, snapshot.prediction_date) DESC,
                             prediction.id DESC
                    LIMIT 1
                ) latest ON TRUE
                LEFT JOIN LATERAL (
                    SELECT record.prediction_date, record.metrics::text AS metrics,
                           record.completeness::text AS completeness
                    FROM repository_metrics_monthly record
                    JOIN snapshots snapshot ON snapshot.id = record.snapshot_id
                    JOIN latest_feature_set feature_set ON feature_set.id = record.feature_set_id
                    WHERE snapshot.repo_id = repository.id AND snapshot.dataset_version_id = dataset.id
                    ORDER BY record.prediction_date DESC LIMIT 1
                ) monthly ON TRUE
                WHERE repository.id IN (%s)
                """.formatted(idParameters),
                (result, rowNumber) -> entry(result), repositoryIds.toArray());

        if (entries.size() != repositoryIds.size()) {
            throw new ApiException(HttpStatus.NOT_FOUND, "repository_not_found",
                    "One or more selected repositories are not in the current cohort.");
        }

        entries.sort((left, right) -> Integer.compare(
                repositoryIds.indexOf(left.repository().id()), repositoryIds.indexOf(right.repository().id())));
        return new RepositoryComparisonResponse(List.copyOf(entries));
    }

    private RepositoryComparisonEntryResponse entry(ResultSet result) throws SQLException {
        double probability = result.getDouble("latest_probability");
        Double latestProbability = result.wasNull() ? null : probability;
        RepositorySummaryResponse repository = new RepositorySummaryResponse(
                result.getLong("id"), result.getString("full_name"), result.getString("owner"),
                result.getString("name"), result.getString("size_group"),
                result.getLong("stars_at_selection"), jsonSupport.read(result.getString("quality_flags")),
                latestProbability, result.getString("latest_risk_category"),
                result.getObject("prediction_date", LocalDate.class));
        LocalDate metricsDate = result.getObject("metrics_date", LocalDate.class);
        MetricPointResponse metrics = metricsDate == null ? null : new MetricPointResponse(
                metricsDate, jsonSupport.read(result.getString("metrics")),
                jsonSupport.read(result.getString("completeness")));
        return new RepositoryComparisonEntryResponse(repository, metrics);
    }

    private void validate(List<Long> repositoryIds) {
        if (repositoryIds == null || repositoryIds.size() < MIN_REPOSITORIES
                || repositoryIds.size() > MAX_REPOSITORIES) {
            throw badRequest("Select between 2 and 4 repository IDs.");
        }
        if (repositoryIds.stream().anyMatch(id -> id == null || id <= 0)) {
            throw badRequest("Repository IDs must be positive integers.");
        }
        if (new HashSet<>(repositoryIds).size() != repositoryIds.size()) {
            throw badRequest("Repository IDs must be unique.");
        }
    }

    private ApiException badRequest(String message) {
        return new ApiException(HttpStatus.BAD_REQUEST, "invalid_parameter", message);
    }
}
