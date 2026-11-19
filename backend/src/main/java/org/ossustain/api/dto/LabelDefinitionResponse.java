package org.ossustain.api.dto;

import tools.jackson.databind.JsonNode;
import java.util.List;

public record LabelDefinitionResponse(
        long datasetVersionId,
        String datasetVersionHash,
        JsonNode label,
        JsonNode splits,
        JsonNode protocol,
        List<FeatureDefinitionResponse> featureDictionary) {
}
