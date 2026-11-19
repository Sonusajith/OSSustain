package org.ossustain.api.dto;

public record FeatureImportanceResponse(
        long modelVersionId,
        String featureSet,
        String algorithm,
        String method,
        String featureName,
        double value,
        int rank) {
}
