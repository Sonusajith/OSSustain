package org.ossustain.api.analysis;

import java.time.OffsetDateTime;
import java.util.UUID;

public record AnalysisResponse(
        UUID id,
        String repository,
        String status,
        int requestsUsed,
        String errorCode,
        OffsetDateTime createdAt,
        OffsetDateTime startedAt,
        OffsetDateTime finishedAt,
        AnalysisResult result) { }
