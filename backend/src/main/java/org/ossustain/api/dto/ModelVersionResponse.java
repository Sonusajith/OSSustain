package org.ossustain.api.dto;

import tools.jackson.databind.JsonNode;
import java.time.OffsetDateTime;

public record ModelVersionResponse(
        long id,
        long datasetVersionId,
        String datasetVersionHash,
        long featureSetId,
        String featureSet,
        String algorithm,
        JsonNode parameters,
        int seed,
        double validationThreshold,
        Double riskLowCutoff,
        Double riskHighCutoff,
        boolean selected,
        String codeRevision,
        OffsetDateTime trainedAt) {
}
