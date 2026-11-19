package org.ossustain.api.dto;

import tools.jackson.databind.JsonNode;
import java.time.LocalDate;

public record PredictionResponse(
        long id,
        long repositoryId,
        long snapshotId,
        long datasetVersionId,
        String datasetVersionHash,
        long modelVersionId,
        String algorithm,
        String featureSet,
        double probability,
        String riskCategory,
        LocalDate predictionDate,
        JsonNode limitationFlags) {
}
