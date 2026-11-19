package org.ossustain.api.dto;

public record FeatureDefinitionResponse(
        String featureName,
        String featureGroup,
        String description,
        String timeWindow,
        String missingPolicy) {
}
