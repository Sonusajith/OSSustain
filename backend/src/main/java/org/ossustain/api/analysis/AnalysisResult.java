package org.ossustain.api.analysis;

import tools.jackson.databind.JsonNode;

import java.time.LocalDate;
import java.time.OffsetDateTime;

public record AnalysisResult(
        long modelVersionId,
        double probability,
        String riskCategory,
        LocalDate predictionDate,
        String featureSet,
        String algorithm,
        JsonNode limitations,
        JsonNode features,
        JsonNode indicators,
        int requestsUsed,
        OffsetDateTime completedAt) { }
