package org.ossustain.api.dto;

public record PredictionIndicatorResponse(
        String method,
        String featureName,
        Double featureValue,
        Double referenceValue,
        double probabilityDelta,
        String direction,
        int rank,
        String description) {
}
