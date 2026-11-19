package org.ossustain.api.dto;

import tools.jackson.databind.JsonNode;

public record EvaluationResponse(
        long modelVersionId,
        String featureSet,
        String algorithm,
        String split,
        String stratum,
        String metric,
        Double value,
        Double ciLow,
        Double ciHigh,
        JsonNode details) {
}
