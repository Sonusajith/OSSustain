package org.ossustain.api.dto;

import java.util.List;

public record PredictionDetailResponse(
        PredictionResponse prediction,
        List<PredictionIndicatorResponse> indicators) {
}
