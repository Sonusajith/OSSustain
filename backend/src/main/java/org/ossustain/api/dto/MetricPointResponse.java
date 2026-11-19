package org.ossustain.api.dto;

import tools.jackson.databind.JsonNode;
import java.time.LocalDate;

public record MetricPointResponse(
        LocalDate predictionDate,
        JsonNode metrics,
        JsonNode completeness) {
}
