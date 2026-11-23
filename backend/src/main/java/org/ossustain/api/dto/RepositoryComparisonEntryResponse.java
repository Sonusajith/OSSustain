package org.ossustain.api.dto;

public record RepositoryComparisonEntryResponse(
        RepositorySummaryResponse repository,
        MetricPointResponse latestMetrics) {
}
