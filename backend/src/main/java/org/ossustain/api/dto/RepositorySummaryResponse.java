package org.ossustain.api.dto;

import tools.jackson.databind.JsonNode;
import java.time.LocalDate;

public record RepositorySummaryResponse(
        long id,
        String fullName,
        String owner,
        String name,
        String sizeGroup,
        long stars,
        JsonNode dataQualityFlags,
        Double latestProbability,
        String latestRiskCategory,
        LocalDate predictionDate) {
}
