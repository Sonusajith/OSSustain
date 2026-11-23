package org.ossustain.security;

import org.ossustain.api.ApiException;
import org.ossustain.api.analysis.AnalysisResponse;
import org.ossustain.api.analysis.AnalysisService;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.security.SecureRandom;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.util.Arrays;
import java.util.Base64;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

@Service
public class AdminService {
    private static final SecureRandom RANDOM = new SecureRandom();
    private final JdbcTemplate jdbc;
    private final PasswordEncoder passwords;
    private final AnalysisService analyses;

    public AdminService(JdbcTemplate jdbc, PasswordEncoder passwords, AnalysisService analyses) {
        this.jdbc = jdbc;
        this.passwords = passwords;
        this.analyses = analyses;
    }

    public AuthDtos.AdminUserPage listUsers(int requestedPage, int requestedSize) {
        int page = Math.max(0, requestedPage);
        int pageSize = Math.max(1, Math.min(requestedSize, 100));
        Long total = jdbc.queryForObject("SELECT count(*) FROM app_users", Long.class);
        List<AuthDtos.AdminUserResponse> users = jdbc.query("""
                SELECT u.id, u.username, u.enabled, u.must_change_password, u.created_at,
                       COALESCE(string_agg(r.role, ',' ORDER BY r.role), '') AS roles
                FROM app_users u LEFT JOIN app_user_roles r ON r.user_id = u.id
                GROUP BY u.id ORDER BY u.created_at DESC, u.id DESC
                LIMIT ? OFFSET ?
                """, this::mapUser, pageSize, (long) page * pageSize);
        return new AuthDtos.AdminUserPage(users, page, pageSize, total == null ? 0 : total);
    }

    @Transactional
    public AuthDtos.CreatedUserResponse createUser(long actorId, CreateUserRequest request) {
        if (request == null || request.username() == null || request.role() == null) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "invalid_user", "Enter a username and role.");
        }
        String username = request.username().trim().toLowerCase(Locale.ROOT);
        String role = request.role().trim().toUpperCase(Locale.ROOT);
        if (!username.matches("^[a-z0-9][a-z0-9._-]{2,99}$")
                || !List.of("ADMIN", "RESEARCHER").contains(role)) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "invalid_user", "The username or role is invalid.");
        }
        if (jdbc.queryForObject("SELECT count(*) FROM app_users WHERE username = ?", Integer.class, username) > 0) {
            throw new ApiException(HttpStatus.CONFLICT, "username_exists", "That username is already in use.");
        }
        String temporaryPassword = temporaryPassword();
        long userId = jdbc.queryForObject("""
                INSERT INTO app_users (username, password_hash, must_change_password)
                VALUES (?, ?, TRUE) RETURNING id
                """, Long.class, username, passwords.encode(temporaryPassword));
        jdbc.update("INSERT INTO app_user_roles (user_id, role) VALUES (?, ?)", userId, role);
        audit(actorId, "user_created", "user", Long.toString(userId), "role", role);
        return new AuthDtos.CreatedUserResponse(getUser(userId), temporaryPassword);
    }

    @Transactional
    public AuthDtos.AdminUserResponse setEnabled(long actorId, long userId, boolean enabled) {
        // Serialize admin disable operations so two concurrent requests cannot disable the final admins.
        jdbc.execute("SELECT pg_advisory_xact_lock(771603017)");
        AuthDtos.AdminUserResponse user = getUserOrThrow(userId);
        if (!enabled && user.enabled() && user.roles().contains("ADMIN")) {
            Integer admins = jdbc.queryForObject("""
                    SELECT count(DISTINCT u.id) FROM app_users u JOIN app_user_roles r ON r.user_id = u.id
                    WHERE u.enabled AND r.role = 'ADMIN'
                    """, Integer.class);
            if (admins != null && admins <= 1) {
                throw new ApiException(HttpStatus.CONFLICT, "last_admin", "The last active administrator cannot be disabled.");
            }
        }
        jdbc.update("UPDATE app_users SET enabled = ?, updated_at = now() WHERE id = ?", enabled, userId);
        jdbc.update("DELETE FROM SPRING_SESSION WHERE PRINCIPAL_NAME = ?", user.username());
        audit(actorId, enabled ? "user_enabled" : "user_disabled", "user", Long.toString(userId), "username", user.username());
        return getUser(userId);
    }

    public AuthDtos.AdminAnalysisPage listAnalyses(int requestedPage, int requestedSize) {
        int page = Math.max(0, requestedPage);
        int pageSize = Math.max(1, Math.min(requestedSize, 100));
        Long total = jdbc.queryForObject("SELECT count(*) FROM analysis_jobs WHERE created_at > now() - interval '30 days'",
                Long.class);
        List<AuthDtos.AdminAnalysisResponse> rows = jdbc.query("""
                SELECT j.id, j.repository_full_name, j.status, u.username, j.created_at, j.finished_at, j.error_code
                FROM analysis_jobs j LEFT JOIN app_users u ON u.id = j.submitted_by_user_id
                WHERE j.created_at > now() - interval '30 days'
                ORDER BY j.created_at DESC LIMIT ? OFFSET ?
                """, this::mapAnalysis, pageSize, (long) page * pageSize);
        return new AuthDtos.AdminAnalysisPage(rows, page, pageSize, total == null ? 0 : total);
    }

    @Transactional
    public AnalysisResponse cancelAnalysis(long actorId, UUID id) {
        int changed = jdbc.update("""
                UPDATE analysis_jobs SET status = 'failed', error_code = 'cancelled_by_admin',
                    finished_at = now(), lease_until = NULL
                WHERE id = ? AND created_at > now() - interval '30 days'
                  AND status IN ('queued', 'running')
                """, id);
        if (changed == 0) {
            Integer exists = jdbc.queryForObject("SELECT count(*) FROM analysis_jobs WHERE id = ?", Integer.class, id);
            if (exists == null || exists == 0) {
                throw new ApiException(HttpStatus.NOT_FOUND, "analysis_not_found", "Analysis job was not found.");
            }
            throw new ApiException(HttpStatus.CONFLICT, "analysis_not_cancellable",
                    "Only queued or running analysis jobs can be canceled.");
        }
        audit(actorId, "analysis_cancelled", "analysis", id.toString(), "status", "failed");
        return analyses.getForAdmin(id);
    }

    private AuthDtos.AdminUserResponse getUserOrThrow(long id) {
        try {
            return jdbc.queryForObject("""
                    SELECT u.id, u.username, u.enabled, u.must_change_password, u.created_at,
                           COALESCE(string_agg(r.role, ',' ORDER BY r.role), '') AS roles
                    FROM app_users u LEFT JOIN app_user_roles r ON r.user_id = u.id
                    WHERE u.id = ? GROUP BY u.id
                    """, this::mapUser, id);
        } catch (org.springframework.dao.EmptyResultDataAccessException error) {
            throw new ApiException(HttpStatus.NOT_FOUND, "user_not_found", "Account was not found.");
        }
    }

    private AuthDtos.AdminUserResponse getUser(long id) { return getUserOrThrow(id); }

    private AuthDtos.AdminUserResponse mapUser(ResultSet rs, int row) throws SQLException {
        String roleNames = rs.getString("roles");
        return new AuthDtos.AdminUserResponse(rs.getLong("id"), rs.getString("username"),
                roleNames == null || roleNames.isBlank() ? List.of() : Arrays.asList(roleNames.split(",")),
                rs.getBoolean("enabled"), rs.getBoolean("must_change_password"),
                rs.getObject("created_at", OffsetDateTime.class));
    }

    private AuthDtos.AdminAnalysisResponse mapAnalysis(ResultSet rs, int row) throws SQLException {
        return new AuthDtos.AdminAnalysisResponse(rs.getObject("id", UUID.class),
                rs.getString("repository_full_name"), rs.getString("status"), rs.getString("username"),
                rs.getObject("created_at", OffsetDateTime.class), rs.getObject("finished_at", OffsetDateTime.class),
                rs.getString("error_code"));
    }

    private void audit(long actorId, String action, String targetType, String targetId, String key, String value) {
        jdbc.update("""
                INSERT INTO admin_audit_events (actor_user_id, action, target_type, target_id, details)
                VALUES (?, ?, ?, ?, jsonb_build_object(?, ?))
                """, actorId, action, targetType, targetId, key, value);
    }

    private static String temporaryPassword() {
        byte[] bytes = new byte[24];
        RANDOM.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }
}
