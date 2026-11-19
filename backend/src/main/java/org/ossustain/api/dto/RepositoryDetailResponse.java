package org.ossustain.api.dto;

import tools.jackson.databind.JsonNode;
import java.time.OffsetDateTime;

public record RepositoryDetailResponse(
        long id,
        long githubId,
        String fullName,
        String owner,
        String name,
        String defaultBranch,
        OffsetDateTime createdAt,
        long stars,
        String sizeGroup,
        String primaryLanguage,
        boolean archived,
        boolean fork,
        JsonNode metadata,
        JsonNode dataQualityFlags) {
}
