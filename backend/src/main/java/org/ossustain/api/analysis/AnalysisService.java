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
    public AnalysisResponse submit(String rawRepository, String remoteAddress) {
        if (rawRepository == null || !rawRepository.matches(REPOSITORY_PATTERN)
                || rawRepository.contains("..")) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "invalid_repository",
                    "Enter a public repository as owner/repository.");
        }
        String repository = rawRepository.toLowerCase(Locale.ROOT);
        String ipHash = sha256(ipHashSecret + ":" + remoteAddress);
        jdbc.execute("SELECT pg_advisory_xact_lock(771603016)");

        var cached = jdbc.query("""
                SELECT j.id, j.repository_full_name, j.status, j.requests_used, j.error_code,
                       j.created_at, j.started_at, j.finished_at,
                       r.model_version_id, r.probability, r.risk_category, r.prediction_date,
                       r.feature_set_name, r.algorithm, r.limitation_flags, r.features,
                       r.indicators, r.request_count, r.completed_at
                FROM analysis_results r JOIN analysis_jobs j ON j.id = r.job_id
                WHERE lower(r.repository_full_name) = ? AND r.completed_at > now() - interval '24 hours'
                  AND r.model_version_id = (
                    SELECT version.id FROM model_versions version
                    JOIN evaluation_results evaluation ON evaluation.model_version_id = version.id
                    WHERE version.is_selected AND evaluation.split = 'validation'
                      AND evaluation.stratum = 'overall' AND evaluation.metric = 'pr_auc'
                    ORDER BY version.dataset_version_id DESC, evaluation.value DESC, version.id LIMIT 1)
                ORDER BY r.completed_at DESC LIMIT 1
                """, this::map, repository);
        if (!cached.isEmpty()) return cached.getFirst();

        Integer submissions = jdbc.queryForObject("""
                SELECT count(*) FROM analysis_jobs
                WHERE client_ip_hash = ? AND created_at > now() - interval '1 hour'
                """, Integer.class, ipHash);
        if (submissions != null && submissions >= 3) {
            throw new ApiException(HttpStatus.TOO_MANY_REQUESTS, "submission_limit",
                    "The hourly submission limit has been reached. Try again later.");
        }
        Integer waiting = jdbc.queryForObject(
                "SELECT count(*) FROM analysis_jobs WHERE status = 'queued'", Integer.class);
        if (waiting != null && waiting >= 20) {
            throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE, "queue_full",
                    "The analysis queue is full. Try again later.");
        }
        var active = jdbc.query("""
                SELECT id, repository_full_name, status, requests_used, error_code,
                       created_at, started_at, finished_at, NULL::jsonb AS result
                FROM analysis_jobs WHERE lower(repository_full_name) = ?
                  AND status IN ('queued', 'running') ORDER BY created_at LIMIT 1
                """, (rs, row) -> mapJob(rs), repository);
        if (!active.isEmpty()) return active.getFirst();

        var inserted = jdbc.query("""
                INSERT INTO analysis_jobs (repository_full_name, client_ip_hash)
                VALUES (?, ?) ON CONFLICT (lower(repository_full_name))
                  WHERE status IN ('queued', 'running') DO NOTHING RETURNING id
                """, (rs, row) -> rs.getObject("id", UUID.class), repository, ipHash);
        if (inserted.isEmpty()) {
            return jdbc.queryForObject("""
                    SELECT id, repository_full_name, status, requests_used, error_code,
                           created_at, started_at, finished_at, NULL::jsonb AS result
                    FROM analysis_jobs WHERE lower(repository_full_name) = ?
                      AND status IN ('queued', 'running') LIMIT 1
                    """, (rs, row) -> mapJob(rs), repository);
        }
        return get(inserted.getFirst());
    }

    public AnalysisResponse get(UUID id) {
        try {
            return jdbc.queryForObject("""
                    SELECT j.id, j.repository_full_name, j.status, j.requests_used, j.error_code,
                           j.created_at, j.started_at, j.finished_at,
                           r.model_version_id, r.probability, r.risk_category, r.prediction_date,
                           r.feature_set_name, r.algorithm, r.limitation_flags, r.features,
                           r.indicators, r.request_count, r.completed_at
                    FROM analysis_jobs j LEFT JOIN analysis_results r ON r.job_id = j.id
                    WHERE j.id = ? AND j.created_at > now() - interval '30 days'
                    """, this::map, id);
        } catch (EmptyResultDataAccessException error) {
            throw new ApiException(HttpStatus.NOT_FOUND, "analysis_not_found", "Analysis job was not found.");
        }
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

    private AnalysisResponse mapJob(ResultSet rs) throws SQLException {
        return new AnalysisResponse(rs.getObject("id", UUID.class), rs.getString("repository_full_name"),
                rs.getString("status"), rs.getInt("requests_used"), rs.getString("error_code"),
                rs.getObject("created_at", OffsetDateTime.class), rs.getObject("started_at", OffsetDateTime.class),
                rs.getObject("finished_at", OffsetDateTime.class), null);
    }

    private static String sha256(String value) {
        try {
            return java.util.HexFormat.of().formatHex(
                    MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException error) {
            throw new IllegalStateException(error);
        }
    }
}
