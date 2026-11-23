package org.ossustain.security;

import java.util.List;

public final class AuthDtos {
    private AuthDtos() { }

    public record UserResponse(long id, String username, List<String> roles, boolean mustChangePassword) { }
    public record AdminUserResponse(long id, String username, List<String> roles, boolean enabled,
            boolean mustChangePassword, java.time.OffsetDateTime createdAt) { }
    public record AdminUserPage(List<AdminUserResponse> content, int page, int pageSize, long totalElements) { }
    public record CreatedUserResponse(AdminUserResponse user, String temporaryPassword) { }
    public record AdminAnalysisResponse(java.util.UUID id, String repository, String status, String submittedBy,
            java.time.OffsetDateTime createdAt, java.time.OffsetDateTime finishedAt, String errorCode) { }
    public record AdminAnalysisPage(List<AdminAnalysisResponse> content, int page, int pageSize, long totalElements) { }
}
