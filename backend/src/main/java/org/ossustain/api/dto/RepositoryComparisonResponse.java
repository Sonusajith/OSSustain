package org.ossustain.api.dto;

import java.util.List;

public record RepositoryComparisonResponse(List<RepositoryComparisonEntryResponse> repositories) {
}
