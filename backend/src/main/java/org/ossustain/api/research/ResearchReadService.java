package org.ossustain.api.research;

import org.ossustain.api.ApiException;
import org.ossustain.api.JsonSupport;
import org.ossustain.api.dto.DatasetSummaryResponse;
import org.ossustain.api.dto.EvaluationResponse;
import org.ossustain.api.dto.FeatureDefinitionResponse;
import org.ossustain.api.dto.FeatureImportanceResponse;
import org.ossustain.api.dto.LabelDefinitionResponse;
import org.ossustain.api.dto.ModelVersionResponse;
import org.ossustain.api.dto.PageResponse;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

@Service
public class ResearchReadService {
    private static final int MAX_PAGE_SIZE = 200;
    private static final String LATEST_DATASET = "(SELECT id FROM dataset_versions ORDER BY id DESC LIMIT 1)";

    private final JdbcTemplate jdbcTemplate;
    private final JsonSupport jsonSupport;

    public ResearchReadService(JdbcTemplate jdbcTemplate, JsonSupport jsonSupport) {
        this.jdbcTemplate = jdbcTemplate;
        this.jsonSupport = jsonSupport;
    }

    public PageResponse<ModelVersionResponse> models(int page, int pageSize) {
        validatePage(page, pageSize);
        Long total = jdbcTemplate.queryForObject(
                "SELECT count(*) FROM model_versions WHERE dataset_version_id = " + LATEST_DATASET,
                Long.class);
        List<ModelVersionResponse> rows = jdbcTemplate.query(
                """
SELECT model.id, model.dataset_version_id, dataset.version_hash,
                          model.feature_set_id, model.feature_set_name, model.algorithm,
                          model.params::text AS params, model.seed, model.validation_threshold,
                          model.risk_low_cutoff, model.risk_high_cutoff, model.is_selected,
                          model.code_revision, model.trained_at
                   FROM model_versions model
                   JOIN dataset_versions dataset ON dataset.id = model.dataset_version_id
                   WHERE model.dataset_version_id = """ + LATEST_DATASET + " "
                        + "ORDER BY model.id LIMIT ? OFFSET ?",
                (result, rowNumber) -> new ModelVersionResponse(
                        result.getLong("id"), result.getLong("dataset_version_id"),
                        result.getString("version_hash"), result.getLong("feature_set_id"),
                        result.getString("feature_set_name"), result.getString("algorithm"),
                        jsonSupport.read(result.getString("params")), result.getInt("seed"),
                        result.getDouble("validation_threshold"), result.getObject("risk_low_cutoff", Double.class),
                        result.getObject("risk_high_cutoff", Double.class), result.getBoolean("is_selected"),
                        result.getString("code_revision"),
                        result.getObject("trained_at", java.time.OffsetDateTime.class)),
                pageSize, (long) page * pageSize);
        return page(rows, page, pageSize, total);
    }

    public PageResponse<EvaluationResponse> evaluations(
            String split, String featureSet, String stratum, int page, int pageSize) {
        validatePage(page, pageSize);
        validateValue("split", split, List.of("train", "validation", "test"));
        validateValue("featureSet", featureSet, List.of("activity_only", "extended"));
        validateValue("stratum", stratum, List.of("overall", "small", "medium", "large"));
        StringBuilder where = new StringBuilder(
                " WHERE model.dataset_version_id = " + LATEST_DATASET + " ");
        List<Object> args = new ArrayList<>();
        if (split != null) {
            where.append(" AND evaluation.split = ? ");
            args.add(split);
        }
        if (featureSet != null) {
            where.append(" AND model.feature_set_name = ? ");
            args.add(featureSet);
        }
        if (stratum != null) {
            where.append(" AND evaluation.stratum = ? ");
            args.add(stratum);
        }
        String joins = " FROM evaluation_results evaluation JOIN model_versions model"
                + " ON model.id = evaluation.model_version_id ";
        Long total = jdbcTemplate.queryForObject("SELECT count(*)" + joins + where, Long.class, args.toArray());
        args.add(pageSize);
        args.add((long) page * pageSize);
        List<EvaluationResponse> rows = jdbcTemplate.query(
                """
SELECT evaluation.model_version_id, model.feature_set_name, model.algorithm,
                          evaluation.split, evaluation.stratum, evaluation.metric, evaluation.value,
                          evaluation.ci_low, evaluation.ci_high, evaluation.details::text AS details
                   """ + joins + where + " ORDER BY evaluation.model_version_id, evaluation.split, "
                        + "evaluation.stratum, evaluation.metric LIMIT ? OFFSET ?",
                (result, rowNumber) -> new EvaluationResponse(
                        result.getLong("model_version_id"), result.getString("feature_set_name"),
                        result.getString("algorithm"), result.getString("split"),
                        result.getString("stratum"), result.getString("metric"),
                        result.getObject("value", Double.class), result.getObject("ci_low", Double.class),
                        result.getObject("ci_high", Double.class),
                        jsonSupport.read(result.getString("details"))), args.toArray());
        return page(rows, page, pageSize, total);
    }

    public PageResponse<FeatureImportanceResponse> featureImportance(
            Long modelVersionId, int page, int pageSize) {
        validatePage(page, pageSize);
        if (modelVersionId != null && modelVersionId < 1) {
            throw badRequest("modelVersionId must be greater than zero.");
        }
        StringBuilder where = new StringBuilder(
                " WHERE model.dataset_version_id = " + LATEST_DATASET + " ");
        List<Object> args = new ArrayList<>();
        if (modelVersionId != null) {
            where.append(" AND model.id = ? ");
            args.add(modelVersionId);
        }
        String joins = " FROM feature_importances importance JOIN model_versions model"
                + " ON model.id = importance.model_version_id ";
        Long total = jdbcTemplate.queryForObject("SELECT count(*)" + joins + where, Long.class, args.toArray());
        args.add(pageSize);
        args.add((long) page * pageSize);
        List<FeatureImportanceResponse> rows = jdbcTemplate.query(
                """
SELECT model.id AS model_version_id, model.feature_set_name, model.algorithm,
                          importance.method, importance.feature_name, importance.value, importance.rank
                   """ + joins + where + " ORDER BY model.id, importance.method, importance.rank LIMIT ? OFFSET ?",
                (result, rowNumber) -> new FeatureImportanceResponse(
                        result.getLong("model_version_id"), result.getString("feature_set_name"),
                        result.getString("algorithm"), result.getString("method"),
                        result.getString("feature_name"), result.getDouble("value"),
                        result.getInt("rank")), args.toArray());
        return page(rows, page, pageSize, total);
    }

    public DatasetSummaryResponse datasetSummary() {
        List<DatasetSummaryResponse> rows = jdbcTemplate.query(
                """
SELECT id, version_hash, cohort_name, created_at, summary::text AS summary
                   FROM dataset_versions ORDER BY id DESC LIMIT 1""",
                (result, rowNumber) -> new DatasetSummaryResponse(
                        result.getLong("id"), result.getString("version_hash"),
                        result.getString("cohort_name"),
                        result.getObject("created_at", java.time.OffsetDateTime.class),
                        jsonSupport.read(result.getString("summary"))));
        if (rows.isEmpty()) {
            throw new ApiException(HttpStatus.NOT_FOUND, "dataset_not_found", "No dataset version is available.");
        }
        return rows.getFirst();
    }

    public LabelDefinitionResponse labelDefinition() {
        List<LabelDefinitionResponse> rows = jdbcTemplate.query(
                """
SELECT dataset.id, dataset.version_hash,
                          dataset.config::text AS config, feature_set.id AS feature_set_id
                   FROM dataset_versions dataset
                   LEFT JOIN LATERAL (
                       SELECT id FROM feature_sets WHERE dataset_version_id = dataset.id
                       ORDER BY id DESC LIMIT 1
                   ) feature_set ON TRUE
                   ORDER BY dataset.id DESC LIMIT 1""",
                (result, rowNumber) -> {
                    var config = jsonSupport.read(result.getString("config"));
                    long featureSetId = result.getLong("feature_set_id");
                    List<FeatureDefinitionResponse> definitions = featureSetId == 0
                            ? List.of()
                            : jdbcTemplate.query(
                                    """
SELECT feature_name, feature_group, description,
                                              time_window, missing_policy
                                       FROM feature_definitions WHERE feature_set_id = ?
                                       ORDER BY feature_group, feature_name""",
                                    (feature, index) -> new FeatureDefinitionResponse(
                                            feature.getString("feature_name"),
                                            feature.getString("feature_group"),
                                            feature.getString("description"),
                                            feature.getString("time_window"),
                                            feature.getString("missing_policy")), featureSetId);
                    var experiment = config.path("experiment");
                    return new LabelDefinitionResponse(
                            result.getLong("id"), result.getString("version_hash"),
                            experiment.path("label"), experiment.path("splits"),
                            experiment, definitions);
                });
        if (rows.isEmpty()) {
            throw new ApiException(HttpStatus.NOT_FOUND, "dataset_not_found", "No dataset version is available.");
        }
        return rows.getFirst();
    }

    private <T> PageResponse<T> page(List<T> rows, int page, int pageSize, Long total) {
        long totalElements = total == null ? 0 : total;
        int totalPages = totalElements == 0 ? 0 : (int) ((totalElements + pageSize - 1) / pageSize);
        return new PageResponse<>(rows, page, pageSize, totalElements, totalPages);
    }

    private void validatePage(int page, int pageSize) {
        if (page < 0 || page > 100_000) {
            throw badRequest("page must be between 0 and 100000.");
        }
        if (pageSize < 1 || pageSize > MAX_PAGE_SIZE) {
            throw badRequest("pageSize must be between 1 and " + MAX_PAGE_SIZE + ".");
        }
    }

    private void validateValue(String name, String value, List<String> allowed) {
        if (value != null && !allowed.contains(value)) {
            throw badRequest(name + " must be one of: " + String.join(", ", allowed) + ".");
        }
    }

    private ApiException badRequest(String message) {
        return new ApiException(HttpStatus.BAD_REQUEST, "invalid_parameter", message);
    }
}
