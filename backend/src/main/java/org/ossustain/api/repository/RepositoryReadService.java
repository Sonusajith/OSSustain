package org.ossustain.api.repository;

import org.ossustain.api.ApiException;
import org.ossustain.api.JsonSupport;
import org.ossustain.api.dto.PageResponse;
import org.ossustain.api.dto.RepositoryDetailResponse;
import org.ossustain.api.dto.RepositorySummaryResponse;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Service
public class RepositoryReadService {
    private static final int MAX_PAGE_SIZE = 100;
    private static final int MAX_PAGE = 100_000;
    private static final Map<String, String> SORT_COLUMNS = Map.of(
            "fullName", "repository.full_name",
            "stars", "repository.stars_at_selection",
            "riskCategory", "CASE latest.risk_level WHEN 'high' THEN 3 WHEN 'medium' THEN 2 WHEN 'low' THEN 1 ELSE 0 END",
            "predictionDate", "latest.prediction_date");
    private static final String REPOSITORY_SOURCE = """
            WITH latest_dataset AS (
                SELECT id, cohort_name, summary FROM dataset_versions ORDER BY id DESC LIMIT 1
            )
            SELECT repository.id, repository.github_id, repository.full_name,
                   repository.owner, repository.name, repository.default_branch,
                   repository.created_at, repository.stars_at_selection, repository.size_group,
                   repository.primary_language, repository.archived, repository.fork,
                   repository.metadata::text AS metadata,
                   COALESCE(quality.flags, '[]'::jsonb)::text AS quality_flags,
                   latest.risk_score AS latest_probability,
                   latest.risk_level AS latest_risk_category,
                   latest.prediction_date
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
            """;

    private final JdbcTemplate jdbcTemplate;
    private final JsonSupport jsonSupport;

    public RepositoryReadService(JdbcTemplate jdbcTemplate, JsonSupport jsonSupport) {
        this.jdbcTemplate = jdbcTemplate;
        this.jsonSupport = jsonSupport;
    }

    public PageResponse<RepositorySummaryResponse> list(
            String risk, String sizeGroup, String query, int page, int pageSize,
            String sort, String direction) {
        validatePage(page, pageSize);
        validateEnum("risk", risk, List.of("low", "medium", "high"));
        validateEnum("sizeGroup", sizeGroup, List.of("small", "medium", "large"));
        if (query != null && query.trim().length() > 100) {
            throw badRequest("q must be at most 100 characters.");
        }
        if (!SORT_COLUMNS.containsKey(sort)) {
            throw badRequest("sort must be one of: fullName, stars, riskCategory, predictionDate.");
        }
        if (!List.of("asc", "desc").contains(direction)) {
            throw badRequest("direction must be asc or desc.");
        }

        StringBuilder predicate = new StringBuilder(" WHERE 1=1 ");
        List<Object> parameters = new ArrayList<>();
        if (risk != null) {
            predicate.append(" AND latest.risk_level = ? ");
            parameters.add(risk);
        }
        if (sizeGroup != null) {
            predicate.append(" AND repository.size_group = ? ");
            parameters.add(sizeGroup);
        }
        if (query != null && !query.isBlank()) {
            predicate.append(" AND repository.full_name ILIKE ? ");
            parameters.add("%" + query.trim() + "%");
        }

        Long total = jdbcTemplate.queryForObject(
                "SELECT count(*) FROM (" + REPOSITORY_SOURCE + predicate + ") repositories", Long.class,
                parameters.toArray());
        String sortOrder = " " + direction.toUpperCase();
        String order = " ORDER BY " + SORT_COLUMNS.get(sort) + sortOrder
                + ", repository.full_name ASC ";
        List<Object> pageParameters = new ArrayList<>(parameters);
        pageParameters.add(pageSize);
        pageParameters.add((long) page * pageSize);
        List<RepositorySummaryResponse> content = jdbcTemplate.query(
                REPOSITORY_SOURCE + predicate + order + " LIMIT ? OFFSET ?",
                (result, rowNumber) -> summary(result), pageParameters.toArray());
        long totalElements = total == null ? 0 : total;
        int totalPages = totalElements == 0 ? 0 : (int) ((totalElements + pageSize - 1) / pageSize);
        return new PageResponse<>(content, page, pageSize, totalElements, totalPages);
    }

    public RepositoryDetailResponse get(long repositoryId) {
        List<RepositoryDetailResponse> rows = jdbcTemplate.query(
                REPOSITORY_SOURCE + " WHERE repository.id = ?",
                (result, rowNumber) -> new RepositoryDetailResponse(
                        result.getLong("id"), result.getLong("github_id"), result.getString("full_name"),
                        result.getString("owner"), result.getString("name"), result.getString("default_branch"),
                        result.getObject("created_at", java.time.OffsetDateTime.class),
                        result.getLong("stars_at_selection"), result.getString("size_group"),
                        result.getString("primary_language"), result.getBoolean("archived"),
                        result.getBoolean("fork"), jsonSupport.read(result.getString("metadata")),
                        jsonSupport.read(result.getString("quality_flags"))),
                repositoryId);
        if (rows.isEmpty()) {
            throw new ApiException(HttpStatus.NOT_FOUND, "repository_not_found", "Repository was not found.");
        }
        return rows.getFirst();
    }

    private RepositorySummaryResponse summary(ResultSet result) throws SQLException {
        double probability = result.getDouble("latest_probability");
        Double latestProbability = result.wasNull() ? null : probability;
        return new RepositorySummaryResponse(
                result.getLong("id"), result.getString("full_name"), result.getString("owner"),
                result.getString("name"), result.getString("size_group"),
                result.getLong("stars_at_selection"), jsonSupport.read(result.getString("quality_flags")),
                latestProbability, result.getString("latest_risk_category"),
                result.getObject("prediction_date", java.time.LocalDate.class));
    }

    private void validatePage(int page, int pageSize) {
        if (page < 0 || page > MAX_PAGE) {
            throw badRequest("page must be between 0 and " + MAX_PAGE + ".");
        }
        if (pageSize < 1 || pageSize > MAX_PAGE_SIZE) {
            throw badRequest("pageSize must be between 1 and " + MAX_PAGE_SIZE + ".");
        }
    }

    private void validateEnum(String name, String value, List<String> allowed) {
        if (value != null && !allowed.contains(value)) {
            throw badRequest(name + " must be one of: " + String.join(", ", allowed) + ".");
        }
    }

    private ApiException badRequest(String message) {
        return new ApiException(HttpStatus.BAD_REQUEST, "invalid_parameter", message);
    }
}
