package org.ossustain.api.dto;

import tools.jackson.databind.JsonNode;
import java.time.OffsetDateTime;

public record DatasetSummaryResponse(
        long id,
        String versionHash,
        String cohortName,
        OffsetDateTime createdAt,
        JsonNode summary) {
}
