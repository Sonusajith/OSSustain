package org.ossustain.api.analysis;

import org.ossustain.api.ApiException;
import org.ossustain.api.JsonSupport;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.util.Locale;
import java.util.UUID;

@Service
public class AnalysisService {
    private static final String REPOSITORY_PATTERN = "^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$";
    private final JdbcTemplate jdbc;
    private final JsonSupport jsonSupport;
    private final String ipHashSecret;

    public AnalysisService(JdbcTemplate jdbc, JsonSupport jsonSupport,
            @Value("${ossustain.analysis.ip-hash-secret:}") String ipHashSecret) {
        this.jdbc = jdbc;
        this.jsonSupport = jsonSupport;
        this.ipHashSecret = ipHashSecret.isBlank() ? UUID.randomUUID().toString() : ipHashSecret;
    }

    @Transactional
    public AnalysisResponse submit(String rawRepository, String remoteAddress, long userId) {
        if (rawRepository == null || !rawRepository.matches(REPOSITORY_PATTERN)
                || rawRepository.contains("..")) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "invalid_repository",
                    "Enter a public repository as owner/repository.");
        }
        String repository = rawRepository.toLowerCase(Locale.ROOT);
        String ipHash = sha256(ipHashSecret + ":" + remoteAddress);
        jdbc.execute("SELECT pg_advisory_xact_lock(771603016)");

        Integer submissions = jdbc.queryForObject("""
                SELECT count(*) FROM analysis_jobs
                WHERE client_ip_hash = ? AND created_at > now() - interval '1 hour'
                """, Integer.class, ipHash);
        if (submissions != null && submissions >= 3) {
            throw new ApiException(HttpStatus.TOO_MANY_REQUESTS, "submission_limit",
                    "The hourly submission limit has been reached. Try again later.");
        }
        UUID cachedJobId = jdbc.query("""
                INSERT INTO analysis_jobs (repository_full_name, client_ip_hash, submitted_by_user_id,
                                           status, started_at, finished_at)
                SELECT ?, ?, ?, 'succeeded', now(), now()
                WHERE EXISTS (
                    SELECT 1 FROM analysis_results r
                    WHERE lower(r.repository_full_name) = ?
                      AND r.completed_at > now() - interval '24 hours'
                      AND r.model_version_id = (
                        SELECT version.id FROM model_versions version
                        JOIN evaluation_results evaluation ON evaluation.model_version_id = version.id
                        WHERE version.is_selected AND evaluation.split = 'validation'
                          AND evaluation.stratum = 'overall' AND evaluation.metric = 'pr_auc'
                        ORDER BY version.dataset_version_id DESC, evaluation.value DESC, version.id LIMIT 1)
                    ORDER BY r.completed_at DESC LIMIT 1)
                RETURNING id
                """, (rs, row) -> rs.getObject("id", UUID.class), repository, ipHash, userId, repository)
                .stream().findFirst().orElse(null);
        if (cachedJobId != null) {
            int copied = jdbc.update("""
                    INSERT INTO analysis_results
                        (job_id, repository_full_name, model_version_id, probability, risk_category,
                         prediction_date, feature_set_name, algorithm, limitation_flags, features,
                         indicators, request_count, completed_at)
                    SELECT ?, repository_full_name, model_version_id, probability, risk_category,
                           prediction_date, feature_set_name, algorithm, limitation_flags, features,
                           indicators, request_count, now()
                    FROM analysis_results
                    WHERE lower(repository_full_name) = ? AND completed_at > now() - interval '24 hours'
                      AND model_version_id = (
                        SELECT version.id FROM model_versions version
                        JOIN evaluation_results evaluation ON evaluation.model_version_id = version.id
                        WHERE version.is_selected AND evaluation.split = 'validation'
                          AND evaluation.stratum = 'overall' AND evaluation.metric = 'pr_auc'
                        ORDER BY version.dataset_version_id DESC, evaluation.value DESC, version.id LIMIT 1)
                    ORDER BY completed_at DESC LIMIT 1
                    """, cachedJobId, repository);
            if (copied == 1) return getForUser(cachedJobId, userId);
            jdbc.update("DELETE FROM analysis_jobs WHERE id = ?", cachedJobId);
        }
        Integer waiting = jdbc.queryForObject(
                "SELECT count(*) FROM analysis_jobs WHERE status = 'queued'", Integer.class);
        if (waiting != null && waiting >= 20) {
            throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE, "queue_full",
                    "The analysis queue is full. Try again later.");
        }
        var active = jdbc.query("""
                SELECT id, submitted_by_user_id
                FROM analysis_jobs WHERE lower(repository_full_name) = ?
                  AND status IN ('queued', 'running') ORDER BY created_at LIMIT 1
                """, (rs, row) -> new ActiveJob(rs.getObject("id", UUID.class),
                rs.getObject("submitted_by_user_id", Long.class)), repository);
        if (!active.isEmpty()) {
            if (active.getFirst().submittedByUserId() == userId) return getForUser(active.getFirst().id(), userId);
            throw activeJobConflict();
        }

        var inserted = jdbc.query("""
                INSERT INTO analysis_jobs (repository_full_name, client_ip_hash, submitted_by_user_id)
                VALUES (?, ?, ?) ON CONFLICT (lower(repository_full_name))
                  WHERE status IN ('queued', 'running') DO NOTHING RETURNING id
                """, (rs, row) -> rs.getObject("id", UUID.class), repository, ipHash, userId);
        if (inserted.isEmpty()) {
            var activeAfterConflict = jdbc.query("""
                    SELECT id, submitted_by_user_id FROM analysis_jobs WHERE lower(repository_full_name) = ?
                      AND status IN ('queued', 'running') LIMIT 1
                    """, (rs, row) -> new ActiveJob(rs.getObject("id", UUID.class),
                    rs.getObject("submitted_by_user_id", Long.class)), repository);
            if (!activeAfterConflict.isEmpty() && activeAfterConflict.getFirst().submittedByUserId() != null
                    && activeAfterConflict.getFirst().submittedByUserId() == userId) {
                return getForUser(activeAfterConflict.getFirst().id(), userId);
            }
            throw activeJobConflict();
        }
        return getForUser(inserted.getFirst(), userId);
    }

    public AnalysisResponse getForUser(UUID id, long userId) {
        return getWhere("j.id = ? AND j.submitted_by_user_id = ?", id, userId);
    }

    public AnalysisResponse getForAdmin(UUID id) {
        return getWhere("j.id = ?", id);
    }

    private AnalysisResponse getWhere(String restriction, Object... args) {
        try {
            return jdbc.queryForObject("""
                    SELECT j.id, j.repository_full_name, j.status, j.requests_used, j.error_code,
                           j.created_at, j.started_at, j.finished_at,
                           r.model_version_id, r.probability, r.risk_category, r.prediction_date,
                           r.feature_set_name, r.algorithm, r.limitation_flags, r.features,
                           r.indicators, r.request_count, r.completed_at
                    FROM analysis_jobs j LEFT JOIN analysis_results r ON r.job_id = j.id
                    WHERE """ + " " + restriction + " AND j.created_at > now() - interval '30 days'",
                    this::map, args);
        } catch (EmptyResultDataAccessException error) {
            throw new ApiException(HttpStatus.NOT_FOUND, "analysis_not_found", "Analysis job was not found.");
        }
    }

    private ApiException activeJobConflict() {
        return new ApiException(HttpStatus.CONFLICT, "analysis_already_running",
                "This repository already has an analysis in progress. Try again after it finishes.");
    }

    private AnalysisResponse map(ResultSet rs, int row) throws SQLException {
        AnalysisResult result = null;
        if (rs.getObject("model_version_id") != null) {
            result = new AnalysisResult(rs.getLong("model_version_id"), rs.getDouble("probability"),
                    rs.getString("risk_category"), rs.getDate("prediction_date").toLocalDate(),
                    rs.getString("feature_set_name"), rs.getString("algorithm"),
                    jsonSupport.read(rs.getString("limitation_flags")), jsonSupport.read(rs.getString("features")),
                    jsonSupport.read(rs.getString("indicators")), rs.getInt("request_count"),
                    rs.getObject("completed_at", OffsetDateTime.class));
        }
        return new AnalysisResponse(rs.getObject("id", UUID.class), rs.getString("repository_full_name"),
                rs.getString("status"), rs.getInt("requests_used"), rs.getString("error_code"),
                rs.getObject("created_at", OffsetDateTime.class), rs.getObject("started_at", OffsetDateTime.class),
                rs.getObject("finished_at", OffsetDateTime.class), result);
    }

    private record ActiveJob(UUID id, Long submittedByUserId) { }

    private static String sha256(String value) {
        try {
            return java.util.HexFormat.of().formatHex(
                    MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException error) {
            throw new IllegalStateException(error);
        }
    }
}
